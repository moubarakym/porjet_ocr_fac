"""
Module d'extraction de donnees depuis les documents d'identite.
Utilise Tesseract OCR puis des expressions regulieres pour parser les champs.
"""

import re
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

from ocr.preprocess import preprocess_image, preprocess_image_from_array


# --- Labels attendus par champ (francais + anglais + variantes) ---
# Chaque cle est le nom du champ, la valeur est une liste de labels possibles.

LABELS_PASSEPORT = {
    "nom": ["Nom", "Surname", "Nom / Surname", "Nom/Surname"],
    "prenom": ["Prenom", "Prénom", "Prenoms", "Prénoms", "Given name", "Given names",
               "Prenom / Given name", "Prenoms / Given names", "Prénom / Given name", "Prénoms / Given names"],
    "date_naissance": ["Date de naissance", "Date of birth", "Date de naissance / Date of birth", "Né le", "Née le", "Naissance"],
    "numero": ["Passeport No", "Passport No", "N° du passeport", "No du passeport",
               "Passeport / Passport No", "N° du passeport / Passport No"],
    "nationalite": ["Nationalité", "Nationality", "Nationalite", "Nationalité / Nationality", "Nationalite / Nationality"],
    "sexe": ["Sexe", "Sex", "Sexe / Sex"],
}

LABELS_CNI = {
    "nom": ["Nom", "Surname", "Nom / Surname", "Nom/Surname", "Nom de famille"],
    "prenom": ["Prenom", "Prénom", "Prenoms", "Prénoms", "Given name", "Given names",
               "Prenom / Given name", "Prenoms / Given names"],
    "date_naissance": ["Date de naissance", "Date of birth", "Date de naissance / Date of birth", "Né le", "Née le", "Naissance"],
    "numero": ["N° de la carte", "Card No", "No de la carte / Card No", "Numero de carte", "N° carte"],
    "sexe": ["Sexe", "Sex", "Sexe / Sex"],
}

LABELS_CERTIFICAT = {
    "nom": ["Nom", "Nom de famille", "Surname", "Nom de l'étudiant", "Nom de l etudiant"],
    "prenom": ["Prenom", "Prénom", "Prenoms", "Prénoms", "Given name"],
    "date_naissance": ["Date de naissance", "Date of birth", "Né le", "Née le", "Né(e) le", "Ne(e) le", "Naissance", "Ne le", "Nee le"],
    "annee_universitaire": ["Année universitaire", "Annee universitaire", "Année", "Annee"],
    "etablissement": ["Université", "Universite", "Ecole", "École", "Institut", "Faculté", "Faculte"],
    "numero_etudiant": ["N° étudiant", "Numero etudiant", "N° etudiant", "INE", "N° inscription", "Numero inscription"],
    "formation": ["Formation", "Diplôme", "Diplome", "Parcours", "Filière", "Filiere"],
}

FUZZY_THRESHOLD = 65  # Score minimum pour considerer un match


def fuzzy_find_field(text, labels_dict, existing_data):
    """
    Parcourt les lignes du texte OCR et utilise le fuzzy matching pour
    identifier les labels de champs malgre les erreurs OCR.

    Pour chaque champ encore None dans existing_data, on compare chaque ligne
    (ou segment de ligne) avec les labels attendus. Si le score depasse
    FUZZY_THRESHOLD, on extrait la valeur associee.

    Args:
        text: texte brut OCR
        labels_dict: dict {nom_champ: [labels possibles]}
        existing_data: dict des champs deja extraits (on ne touche pas aux non-None)

    Returns:
        dict mis a jour avec les champs trouves par fuzzy matching
    """
    lines = text.split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    for field, labels in labels_dict.items():
        if existing_data.get(field):
            continue

        best_score = 0
        best_line_idx = -1

        for i, line in enumerate(lines):
            # Comparer la ligne entiere ou des segments avec chaque label
            for label in labels:
                # Score sur la ligne entiere (utile si la ligne = juste le label)
                score_full = fuzz.ratio(line.lower(), label.lower())
                # Score partiel (le label est contenu dans la ligne avec des erreurs)
                score_partial = fuzz.partial_ratio(line.lower(), label.lower())
                # Token sort pour gerer les mots dans un ordre different
                score_token = fuzz.token_sort_ratio(line.lower(), label.lower())

                score = max(score_full, score_partial, score_token)

                if score > best_score and score >= FUZZY_THRESHOLD:
                    best_score = score
                    best_line_idx = i

        if best_line_idx >= 0:
            value = _extract_value_from_lines(lines, best_line_idx, field)
            if value:
                existing_data[field] = value

    return existing_data


def _extract_value_from_lines(lines, label_line_idx, field):
    """
    Extrait la valeur d'un champ a partir de la ligne du label.
    La valeur peut etre sur la meme ligne (apres ':' ou le label) ou sur les lignes suivantes.
    """
    line = lines[label_line_idx]

    # Essayer d'extraire la valeur apres un separateur sur la meme ligne
    # Ex: "Nom : DUPONT" ou "Nom: DUPONT"
    match = re.search(r"[:\s]\s*([A-ZÀ-Üa-zà-ü0-9][\w\s\-./]+)$", line)
    if match:
        candidate = match.group(1).strip()
        # Verifier que ce n'est pas juste un bout du label
        if _is_valid_value(candidate, field):
            extracted = _extract_typed_value(candidate, field)
            if extracted:
                return extracted

    # Chercher dans les lignes suivantes (jusqu'a 3 lignes apres le label)
    max_lookahead = min(label_line_idx + 4, len(lines))
    for j in range(label_line_idx + 1, max_lookahead):
        next_line = lines[j].strip()
        if not next_line or not _is_valid_value(next_line, field):
            continue
        if _looks_like_label(next_line):
            break  # On a atteint un autre label, on arrete
        extracted = _extract_typed_value(next_line, field)
        if extracted:
            return extracted

    return None


def _is_valid_value(text, field):
    """Verifie qu'un texte est une valeur exploitable (pas un point, un tiret, etc.)."""
    cleaned = re.sub(r"[^\w]", "", text)
    if len(cleaned) < 1:
        return False
    if field == "sexe" and len(cleaned) < 1:
        return False
    return True


def _extract_typed_value(text, field):
    """Extrait la valeur selon le type de champ."""
    if field == "sexe":
        sexe_match = re.search(r"\b([MFmf])\b", text)
        if sexe_match:
            return sexe_match.group(1).upper()
    elif field == "date_naissance":
        date_match = re.search(r"(\d{2}[./\-]\d{2}[./\-]\d{4})", text)
        if date_match:
            return date_match.group(1)
    else:
        # Pour les champs texte, ignorer les valeurs parasites (ponctuation seule)
        cleaned = text.strip().strip(".,;:!?")
        if len(cleaned) >= 2:
            return cleaned
    return None


def _looks_like_label(text):
    """Heuristique : retourne True si le texte ressemble a un label plutot qu'a une valeur."""
    label_keywords = ["nom", "prenom", "surname", "given", "date", "birth", "naissance",
                      "sexe", "sex", "national", "passport", "carte", "numero", "formation",
                      "diplome", "etudiant", "inscription", "universite", "ecole", "institut"]
    text_lower = text.lower()
    for kw in label_keywords:
        if kw in text_lower:
            return True
    return False


# --- Extraction du texte brut ---

def extract_text(image_path):
    """Extrait le texte brut d'une image via Tesseract."""
    processed = preprocess_image(image_path)
    pil_image = Image.fromarray(processed)
    text = pytesseract.image_to_string(pil_image, lang="fra")
    return text


def extract_text_from_array(img_array):
    """Extrait le texte brut d'un numpy array (image BGR)."""
    processed = preprocess_image_from_array(img_array)
    pil_image = Image.fromarray(processed)
    text = pytesseract.image_to_string(pil_image, lang="fra")
    return text


# --- Parsing des champs par type de document ---

def parse_cni(text):
    """
    Parse le texte extrait d'une Carte Nationale d'Identite.
    Gere les formats francais (ancien et nouveau), bilingues,
    et les labels sur la meme ligne ou la ligne suivante.
    """
    data = {
        "type_document": "CNI",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "numero": None,
        "sexe": None,
    }

    # --- Etape 1 : Labels bilingues (nouvelle CNI francaise) ---
    # Format : "Nom / Surname" suivi du nom sur la meme ligne ou la suivante

    # Nom / Surname (nouvelle CNI)
    match = re.search(
        r"[Nn]om\s*/?\s*[Ss]urname[s]?\s*[:\s]?\s*\n?\s*([A-ZÀ-Üa-zà-ü][\w\s\-]+)",
        text
    )
    if match:
        data["nom"] = match.group(1).strip().split("\n")[0].strip()

    # Prenom(s) / Given name(s)
    match = re.search(
        r"[Pp]r[ée]nom[s]?\s*/?\s*[Gg]iven\s*[Nn]ame[s]?\s*[:\s]?\s*\n?\s*([A-ZÀ-Üa-zà-ü][\w\s\-]+)",
        text
    )
    if match:
        data["prenom"] = match.group(1).strip().split("\n")[0].strip()

    # Date de naissance / Date of birth
    match = re.search(
        r"[Dd]ate\s*de\s*naissance\s*/?\s*[Dd]ate\s*of\s*[Bb]?\w*\s*[:\s]?\s*\n?\s*(\d{2}[./\-]\d{2}[./\-]\d{4})",
        text
    )
    if match:
        data["date_naissance"] = match.group(1).strip()

    # Sexe / Sex
    match = re.search(
        r"[Ss]exe\s*/?\s*[Ss]ex\s*[:\s]?\s*\n?\s*([MFmf])\b",
        text
    )
    if match:
        data["sexe"] = match.group(1).upper()

    # Numero de carte (nouvelle CNI : "No de la carte / Card No")
    match = re.search(
        r"(?:[Nn][°o]\s*(?:de\s*(?:la\s*)?)?(?:carte|card)|[Cc]ard\s*[Nn][o°])\s*[:\s]?\s*\n?\s*([A-Z0-9]{5,15})",
        text, re.IGNORECASE
    )
    if match:
        data["numero"] = match.group(1).strip()

    # --- Etape 2 : Labels francais simples (ancienne CNI) ---

    # Nom : XXXX ou Nom: XXXX
    if not data["nom"]:
        match = re.search(r"[Nn][Oo][Mm]\s*[:\s]\s*([A-ZÀ-Ü]+)", text)
        if match:
            data["nom"] = match.group(1).strip()

    # Prenom : Xxxx
    if not data["prenom"]:
        match = re.search(r"[Pp]r[ée]nom[s]?\s*[:\s]\s*([A-ZÀ-Üa-zà-ü]+)", text)
        if match:
            data["prenom"] = match.group(1).strip()

    # Date de naissance - chercher la date apres "naissance" ou "birth" ou "Ne(e) le"
    if not data["date_naissance"]:
        match = re.search(
            r"(?:[Nn][ée](?:\(e\))?\s*(?:le)?|[Nn]aissance|[Bb]irth)\s*[:\s]?\s*\n?\s*(\d{2}[./\-]\d{2}[./\-]\d{4})",
            text
        )
        if match:
            data["date_naissance"] = match.group(1).strip()

    # Fallback date : premiere date trouvee dans le texte
    if not data["date_naissance"]:
        match = re.search(r"(\d{2}[/.\-]\d{2}[/.\-]\d{4})", text)
        if match:
            data["date_naissance"] = match.group(1)

    # Numero : N° XXXX ou No XXXX
    if not data["numero"]:
        match = re.search(r"(?:N[°o]|No|Carte\s*N)\s*[:\s]?\s*([A-Z0-9]{5,15})", text, re.IGNORECASE)
        if match:
            data["numero"] = match.group(1)

    # Sexe simple
    if not data["sexe"]:
        match = re.search(r"[Ss]exe\s*[:\s]\s*([MFmf])", text)
        if match:
            data["sexe"] = match.group(1).upper()

    # --- Etape 3 : MRZ de la CNI (2 lignes de 36 caracteres) ---
    mrz_lines = re.findall(r"[A-Z0-9<]{30,36}", text)
    if len(mrz_lines) >= 2:
        line1 = mrz_lines[-2]
        line2 = mrz_lines[-1]

        # Ligne 1 CNI : IDFRA + nom
        if not data["nom"] and "ID" in line1[:5]:
            nom_part = line1[5:].split("<<")[0].replace("<", " ").strip()
            if nom_part:
                data["nom"] = nom_part

        # Ligne 2 CNI : positions connues
        if len(line2) >= 30:
            if not data["date_naissance"]:
                dob = line2[0:6]
                if dob.isdigit():
                    annee = int(dob[0:2])
                    annee = 1900 + annee if annee > 30 else 2000 + annee
                    data["date_naissance"] = f"{dob[4:6]}/{dob[2:4]}/{annee}"
            if not data["sexe"] and len(line2) > 7:
                if line2[7] in ("M", "F"):
                    data["sexe"] = line2[7]

    # --- Etape 4 : Fuzzy matching pour les champs encore non detectes ---
    fuzzy_find_field(text, LABELS_CNI, data)

    return data


def parse_passeport(text):
    """
    Parse le texte d'un passeport.
    Gere les labels bilingues (francais/anglais) des vrais passeports,
    puis tente la MRZ, puis fallback regex simples.
    """
    data = {
        "type_document": "Passeport",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "numero": None,
        "nationalite": None,
        "sexe": None,
    }

    # --- Etape 1 : Labels bilingues des vrais passeports ---

    # Nom / Surname - cherche le texte sur la ligne suivante
    match = re.search(
        r"[Nn]om\s*/?\s*[Ss]urname[s]?\s*\n\s*(.+)",
        text
    )
    if match:
        data["nom"] = match.group(1).strip()

    # Prenoms / Given names
    match = re.search(
        r"[Pp]r[ée]nom[s]?\s*/?\s*[Gg]iven\s*[Nn]ame[s]?\s*\n\s*(.+)",
        text
    )
    if match:
        data["prenom"] = match.group(1).strip()

    # Numero du passeport / Passport No
    match = re.search(
        r"[Pp]ass[ae]port\s*/?\s*[Pp]assport\s*[Nn][o°]?\s*\n?\s*([A-Z0-9]{5,12})",
        text
    )
    if not match:
        match = re.search(
            r"[Nn][°o]\s*du\s*[Pp]ass[ae]port\s*/?\s*[Pp]assport\s*[Nn][o°]?\s*\n?\s*([A-Z0-9]{5,12})",
            text
        )
    if match:
        data["numero"] = match.group(1).strip()

    # Date de naissance / Date of Birth
    match = re.search(
        r"[Dd]ate\s*de\s*naissance\s*/?\s*[Dd]ate\s*of\s*[Bb]?\w*\s*\n?\s*(\d{2}[./\-]\d{2}[./\-]\d{4})",
        text
    )
    if match:
        data["date_naissance"] = match.group(1).strip()

    # Sexe / Sex
    match = re.search(
        r"[Ss]exe\s*/?\s*[Ss]ex\s*\n?\s*([MFmf])\b",
        text
    )
    if match:
        data["sexe"] = match.group(1).upper()

    # Nationalite / Nationality
    match = re.search(
        r"[Nn]a[lt]iona[lï]it[ée]\s*/?\s*[Nn]\w*\s*\n?\s*(.+)",
        text
    )
    if match:
        data["nationalite"] = match.group(1).strip()

    # --- Etape 2 : MRZ si les champs manquent ---
    mrz_lines = re.findall(r"[A-Z0-9<]{30,44}", text)

    if len(mrz_lines) >= 2:
        line1 = mrz_lines[-2]
        line2 = mrz_lines[-1]

        # Ligne 1 : P<PAYS<<NOM<<PRENOM
        if not data["nom"]:
            parts = line1.split("<<")
            if len(parts) >= 2:
                nom_part = parts[0]
                if len(nom_part) > 5:
                    data["nom"] = nom_part[5:].replace("<", " ").strip()
                data["prenom"] = parts[1].replace("<", " ").strip()

        # Ligne 2 : numero, nationalite, date naissance
        if len(line2) >= 20:
            if not data["numero"]:
                data["numero"] = line2[0:9].replace("<", "")
            if not data["nationalite"]:
                data["nationalite"] = line2[10:13].replace("<", "")
            if not data["date_naissance"]:
                dob = line2[13:19]
                if dob.isdigit():
                    annee = int(dob[0:2])
                    annee = 1900 + annee if annee > 30 else 2000 + annee
                    data["date_naissance"] = f"{dob[4:6]}/{dob[2:4]}/{annee}"
            if not data["sexe"] and len(line2) > 20:
                if line2[20] in ("M", "F"):
                    data["sexe"] = line2[20]

    # --- Etape 3 : Fallback regex simples si toujours vide ---
    if not data["nom"]:
        match = re.search(r"[Nn][Oo][Mm]\s*[:\s]\s*([A-ZÀ-Ü]+)", text)
        if match:
            data["nom"] = match.group(1).strip()

    if not data["prenom"]:
        match = re.search(r"[Pp]r[ée]nom[s]?\s*[:\s]\s*([A-ZÀ-Üa-zà-ü]+)", text)
        if match:
            data["prenom"] = match.group(1).strip()

    if not data["date_naissance"]:
        # Chercher toutes les dates et prendre celle apres "naissance" ou "birth"
        dates = re.findall(r"(\d{2}[./\-]\d{2}[./\-]\d{4})", text)
        naissance_pos = None
        for m in re.finditer(r"(?:naissance|birth)", text, re.IGNORECASE):
            naissance_pos = m.end()
            break
        if naissance_pos and dates:
            for d_match in re.finditer(r"(\d{2}[./\-]\d{2}[./\-]\d{4})", text):
                if d_match.start() > naissance_pos:
                    data["date_naissance"] = d_match.group(1)
                    break
        elif dates:
            data["date_naissance"] = dates[0]

    if not data["numero"]:
        match = re.search(r"(?:N[°o]\s*|No\s*)\s*([A-Z0-9]{5,12})", text, re.IGNORECASE)
        if match:
            data["numero"] = match.group(1)

    if not data["sexe"]:
        match = re.search(r"\b[Ss]exe?\s*[:/]?\s*[Ss]ex\s*\n?\s*([MFmf])\b", text)
        if not match:
            match = re.search(r"\b([MF])\s*$", text, re.MULTILINE)
        if match:
            data["sexe"] = match.group(1).upper()

    # --- Etape 4 : Fuzzy matching pour les champs encore non detectes ---
    fuzzy_find_field(text, LABELS_PASSEPORT, data)

    return data


def parse_certificat_scolarite(text):
    """
    Parse le texte d'un certificat de scolarite.
    Gere les vrais certificats avec leurs formats varies :
    - "certifie que M./Mme NOM Prenom..."
    - Labels "Nom :" / "Prenom :" sur des lignes separees
    - "Etudiant(e) : NOM Prenom"
    - Numero etudiant
    """
    data = {
        "type_document": "Certificat de scolarite",
        "nom": None,
        "prenom": None,
        "annee_universitaire": None,
        "etablissement": None,
        "numero_etudiant": None,
        "formation": None,
        "date_naissance": None,
    }

    # --- Etape 1 : Patterns courants dans les vrais certificats ---

    # "certifie que M./Mme/Mlle NOM Prenom" (le plus courant)
    match = re.search(
        r"(?:certifie\s*que|atteste\s*que)\s+(?:M[r.]?|Mme|Mlle|Monsieur|Madame)\s+([A-ZÀ-Ü][\w\-]+)\s+([A-ZÀ-Üa-zà-ü][\w\-]+)",
        text, re.IGNORECASE
    )
    if match:
        data["nom"] = match.group(1).strip()
        data["prenom"] = match.group(2).strip()

    # "M./Mme NOM Prenom" sans "certifie que"
    if not data["nom"]:
        match = re.search(
            r"(?:M[r.]?|Mme|Mlle|Monsieur|Madame)\s+([A-ZÀ-Ü]{2,})\s+([A-ZÀ-Üa-zà-ü][\w\-]+)",
            text
        )
        if match:
            data["nom"] = match.group(1).strip()
            data["prenom"] = match.group(2).strip()

    # "Etudiant(e) : NOM Prenom" ou "Nom de l'etudiant : XXX"
    if not data["nom"]:
        match = re.search(
            r"[Éé]tudiant[e]?\s*[:\s]\s*([A-ZÀ-Ü]{2,})\s+([A-ZÀ-Üa-zà-ü][\w\-]+)",
            text
        )
        if match:
            data["nom"] = match.group(1).strip()
            data["prenom"] = match.group(2).strip()

    # --- Etape 2 : Labels classiques (Nom : / Prenom :) ---

    if not data["nom"]:
        # "Nom :" ou "Nom de famille :" suivi du nom (meme ligne ou suivante)
        match = re.search(
            r"[Nn]om\s*(?:de\s*famille)?\s*[:\s]\s*\n?\s*([A-ZÀ-Ü][\w\s\-]+)",
            text
        )
        if match:
            data["nom"] = match.group(1).strip().split("\n")[0].strip()

    if not data["prenom"]:
        match = re.search(
            r"[Pp]r[ée]nom[s]?\s*[:\s]\s*\n?\s*([A-ZÀ-Üa-zà-ü][\w\s\-]+)",
            text
        )
        if match:
            data["prenom"] = match.group(1).strip().split("\n")[0].strip()

    # --- Etape 3 : Annee universitaire ---

    # "annee universitaire 2023-2024" ou "2023/2024" ou "au titre de l'annee 2024-2025"
    match = re.search(r"(\d{4})\s*[/\-]\s*(\d{4})", text)
    if match:
        data["annee_universitaire"] = f"{match.group(1)}-{match.group(2)}"

    # --- Etape 4 : Etablissement ---

    # "Universite XXX" ou "Ecole XXX" ou "Institut XXX" ou "Faculte XXX"
    match = re.search(
        r"(?:[Uu]niversit[ée]|[Éé]cole|[Ii]nstitut|[Ff]acult[ée]|IUT|UFR)\s*(?:de\s*|d['\u2019])?(.+?)(?:\n|$)",
        text
    )
    if match:
        data["etablissement"] = match.group(0).strip()

    # --- Etape 5 : Numero etudiant ---

    # "N etudiant : XXXXX" ou "Numero etudiant : XXXXX" ou "INE : XXXXX"
    match = re.search(
        r"(?:[Nn][°o]?\s*[ée]tudiant|[Nn]um[ée]ro\s*[ée]tudiant|INE|[Nn][°o]\s*inscription)\s*[:\s]\s*\n?\s*([A-Z0-9]{5,15})",
        text, re.IGNORECASE
    )
    if match:
        data["numero_etudiant"] = match.group(1).strip()

    # --- Etape 6 : Formation / Diplome ---

    # "inscrit(e) en Master 1 Big Data" ou "formation : XXX"
    match = re.search(
        r"(?:inscrit[e]?\s*en|formation|dipl[oô]me|parcours|fili[eè]re)\s*[:\s]?\s*\n?\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if match:
        data["formation"] = match.group(1).strip()

    # --- Etape 7 : Date de naissance (parfois present sur les certificats) ---

    match = re.search(
        r"(?:[Nn][ée](?:\(e\))?\s*(?:le)?|[Nn]aissance)\s*[:\s]?\s*(\d{2}[./\-]\d{2}[./\-]\d{4})",
        text
    )
    if match:
        data["date_naissance"] = match.group(1).strip()

    # --- Etape 8 : Fuzzy matching pour les champs encore non detectes ---
    fuzzy_find_field(text, LABELS_CERTIFICAT, data)

    return data


# --- Fonction principale ---

PARSERS = {
    "cni": parse_cni,
    "passeport": parse_passeport,
    "certificat": parse_certificat_scolarite,
}


def extract_document(image_path, doc_type):
    """
    Extrait les donnees d'un document selon son type.

    Args:
        image_path: chemin vers l'image du document
        doc_type: type de document ("cni", "passeport", "certificat")

    Returns:
        dict avec les champs extraits + le texte brut
    """
    if doc_type not in PARSERS:
        raise ValueError(f"Type de document inconnu : {doc_type}. Choix : {list(PARSERS.keys())}")

    raw_text = extract_text(image_path)
    parsed = PARSERS[doc_type](raw_text)
    parsed["texte_brut"] = raw_text

    return parsed
