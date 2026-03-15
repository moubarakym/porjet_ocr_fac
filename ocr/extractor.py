"""
Module d'extraction de donnees depuis les documents d'identite.
Utilise Tesseract OCR puis des expressions regulieres pour parser les champs.
"""

import re
import pytesseract
from PIL import Image

from ocr.preprocess import preprocess_image, preprocess_image_from_array


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
