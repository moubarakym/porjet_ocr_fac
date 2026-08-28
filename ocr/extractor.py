"""
Module d'extraction de donnees depuis les documents d'identite.
Utilise Tesseract OCR puis des expressions regulieres pour parser les champs.
"""

import os
import re
import shutil
import pytesseract
from pytesseract import Output
from PIL import Image
from rapidfuzz import fuzz

from ocr.preprocess import preprocess_variants, preprocess_variants_from_array


# --- Localisation automatique de tesseract.exe (Windows) ---
# Si tesseract n'est pas dans le PATH (cas frequent apres une installation
# recente sur Windows, PATH pas encore rafraichi), on tente les emplacements
# d'installation par defaut avant d'abandonner.
if shutil.which("tesseract") is None:
    _CANDIDATES = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for _path in _CANDIDATES:
        if os.path.isfile(_path):
            pytesseract.pytesseract.tesseract_cmd = _path
            break


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
    "nationalite": ["Nationalité", "Nationality", "Nationalite", "Nationalité / Nationality", "Nationalite / Nationality"],
}

LABELS_TITRE_SEJOUR = {
    "nom": ["Noms", "Noms Prenoms", "Surnames", "Noms Prenoms / Surnames Forenames", "Nom"],
    "prenom": ["Prenoms", "Prénoms", "Forenames", "Given names", "Prenom"],
    "date_naissance": ["Date de naissance", "Date of birth", "Birth date", "Date de naissance / Birth date"],
    "sexe": ["Sexe", "Sex", "Sexe / Sex"],
    "nationalite": ["Nationalite", "Nationalité", "Nat.", "Nationalite / Nat."],
    # "Numero du titre" a ete retire volontairement : trop proche de
    # "Numero personnel" en fuzzy matching (meme mot "Numero" en tete), ce
    # qui pouvait faire capturer le numero personnel par le champ "numero"
    # (document) avant que "numero_personnel" n'ait sa chance - releve
    # empiriquement (numero_personnel restait "Non detecte" alors que la
    # valeur etait bien presente dans le texte, deja recuperee par erreur
    # par le champ "numero").
    "numero": ["Titre de sejour", "Carte de sejour"],
    "numero_personnel": ["Numero personnel", "Numéro personnel", "Personal number",
                          "Numero personnel / Personal number"],
    "type_titre": ["Cat. du titre", "Type of permit", "Cat. du titre / Type of permit",
                   "Carte de sejour temporaire", "Carte de resident"],
    "date_validite": ["Valable jusqu'au", "Valid until", "Valable jusqu'au / Valid until"],
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

    # Lignes deja utilisees comme source pour un champ precedent dans cet
    # appel. Sans ca, deux champs dont les libelles se ressemblent (ex.
    # "Numero personnel" et "Numero du titre") peuvent tous les deux
    # accrocher la meme ligne OCR et se retrouver avec la meme valeur, dont
    # au moins une forcement fausse.
    used_line_indices = set()

    for field, labels in labels_dict.items():
        if existing_data.get(field):
            continue

        best_score = 0
        best_line_idx = -1

        for i, line in enumerate(lines):
            if i in used_line_indices:
                continue
            # Comparer la ligne entiere ou des segments avec chaque label
            for label in labels:
                line_low, label_low = line.lower(), label.lower()

                # Score sur la ligne entiere (utile si la ligne = juste le label)
                score_full = fuzz.ratio(line_low, label_low)
                # Token sort pour gerer les mots dans un ordre different
                score_token = fuzz.token_sort_ratio(line_low, label_low)

                # Score partiel (le label est contenu dans la ligne avec des
                # erreurs). On ne l'utilise que si la ligne reste raisonnablement
                # courte par rapport au label : sinon, un label court (ex. "Nom",
                # 3 lettres) finit presque toujours par "matcher" par hasard un
                # fragment de n'importe quelle phrase longue (faux positif qui
                # fabrique une valeur a partir de texte sans rapport).
                score_partial = 0
                if len(line_low) <= len(label_low) * 3 + 8:
                    score_partial = fuzz.partial_ratio(line_low, label_low)

                score = max(score_full, score_partial, score_token)

                if score > best_score and score >= FUZZY_THRESHOLD:
                    best_score = score
                    best_line_idx = i

        if best_line_idx >= 0:
            value, value_line_idx = _extract_value_from_lines(lines, best_line_idx, field)
            if value:
                existing_data[field] = value
                used_line_indices.add(best_line_idx)
                # La valeur peut provenir d'une ligne DIFFERENTE de celle du
                # libelle (recherchee dans les lignes suivantes). Sans
                # marquer aussi CETTE ligne comme utilisee, un autre champ
                # dont le libelle est ailleurs pourrait, en cherchant lui
                # aussi dans les lignes suivantes, retomber sur la meme
                # ligne de valeur et se retrouver avec le meme texte que ce
                # champ - constate empiriquement (deux champs recuperant
                # tous les deux "Given names" comme valeur).
                if value_line_idx is not None:
                    used_line_indices.add(value_line_idx)

    return existing_data


def _extract_value_from_lines(lines, label_line_idx, field):
    """
    Extrait la valeur d'un champ a partir de la ligne du label.
    La valeur peut etre sur la meme ligne (apres ':' ou le label) ou sur les lignes suivantes.

    Returns:
        (valeur, indice_de_la_ligne_source) ; (None, None) si rien trouve.
        indice_de_la_ligne_source vaut label_line_idx si la valeur vient de
        la meme ligne que le libelle, ou l'indice de la ligne suivante
        utilisee si la valeur en provient.
    """
    line = lines[label_line_idx]

    # Essayer d'extraire la valeur apres un separateur sur la meme ligne
    # Ex: "Nom : DUPONT" ou "Nom: DUPONT"
    match = re.search(r"[:\s]\s*([A-ZÀ-Üa-zà-ü0-9][\w\s\-./]+)$", line)
    if match:
        candidate = match.group(1).strip()
        # Verifier que ce n'est pas juste un bout du label. Sur une ligne qui
        # regroupe PLUSIEURS libelles colles (ex. carte d'identite 2021 :
        # "Sexe/Sex Nationalite/Nationality Date de naissance/Date of
        # birth"), cette regex "texte apres le dernier separateur" capture
        # presque toujours la fin de la ligne - qui est elle-meme un AUTRE
        # libelle ("Date of birth"), pas une vraie valeur. Sans ce garde-fou
        # (deja present pour la recherche sur les lignes suivantes plus bas,
        # mais absent ici avant ce correctif), un champ texte comme
        # "nationalite" acceptait ce libelle residuel comme si c'etait sa
        # valeur - releve empiriquement.
        if _is_valid_value(candidate, field) and not _looks_like_label(candidate):
            extracted = _extract_typed_value(candidate, field)
            if extracted:
                return extracted, label_line_idx

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
            return extracted, j

    return None, None


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
    elif field in ("numero", "numero_personnel", "numero_etudiant"):
        # Les numeros de document/personnel sont des identifiants
        # majoritairement numeriques. Sans cette contrainte, le fuzzy
        # matching peut accrocher n'importe quel debris de texte OCR
        # (ex. "ercr NN") juste apres le libelle et l'afficher comme si
        # c'etait la vraie valeur, ce qui est pire que "Non detecte".
        num_match = re.search(r"[A-Z0-9]{5,15}", text.upper())
        if num_match:
            candidate = num_match.group(0)
            if sum(c.isdigit() for c in candidate) >= 4:
                return candidate
        return None
    elif field == "nationalite":
        # Un code pays (2-3 lettres, ex. "FRA") ou un seul mot alphabetique
        # (ex. "France", "Française"). Sans cette contrainte stricte, le
        # champ texte generique ci-dessous (qui accepte n'importe quoi des
        # que len >= 2) acceptait toute une ligne de donnees bruitee comme
        # "F -_ FRA .. O01 O4 1995" comme si c'etait la nationalite - releve
        # empiriquement quand le triplet sexe/nationalite/date_naissance
        # combine plus haut echoue a matcher (bruit OCR trop important).
        candidate_clean = text.strip().strip(".,;:!?")
        if re.fullmatch(r"[A-Z]{2,3}", candidate_clean):
            return candidate_clean
        if re.fullmatch(r"[A-ZÀ-Üa-zà-ü\-]{3,25}", candidate_clean):
            return candidate_clean
        return None
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

# Langue(s) Tesseract : francais + anglais, car les CNI/passeports francais
# recents affichent systematiquement les labels dans les deux langues
# ("Nom / Surname", "Date de naissance / Date of birth"...). Utiliser les deux
# packs en meme temps ameliore la reconnaissance de ces documents bilingues.
DEFAULT_LANG = "fra+eng"

# Configurations Tesseract essayees pour chaque variante d'image :
# - psm 6 : bloc de texte uniforme (souvent le mieux adapte aux champs d'un
#   document d'identite, denses et regulierement espaces)
# - psm 3 : segmentation automatique complete (filet de securite si la mise
#   en page est plus eclatee, ex. certificat de scolarite)
OCR_CONFIGS = ("--oem 1 --psm 6", "--oem 1 --psm 3")

# Limite de temps (secondes) par appel Tesseract. Sur une image tres
# degradee (bruit important, texture aleatoire), Tesseract peut rester
# bloque tres longtemps a tenter de segmenter du "texte" dans du bruit.
# Sans limite, un seul document pathologique bloquerait indefiniment tout
# le pipeline (et donc la verification). pytesseract leve un RuntimeError
# ("Tesseract process timeout") au-dela de cette limite : on traite alors
# cette variante/config comme un echec et on continue avec les autres.
OCR_TIMEOUT_SECONDS = 20


# Facteur applique a la hauteur moyenne des caracteres d'une ligne pour
# decider qu'un espace horizontal entre deux mots est une VRAIE rupture
# logique (ex. un libelle colle a la valeur du champ suivant sur la meme
# ligne Tesseract, comme "Moubarak SEXE/SEX NATIONALITE...") plutot qu'un
# simple espace entre mots. Relatif a la hauteur du texte plutot qu'un
# nombre de pixels fixe : reste valable quelle que soit la resolution de
# l'image (l'upscaling de preprocess.py peut faire varier cette hauteur
# d'un facteur 3 selon le document source).
_LINE_GAP_HEIGHT_FACTOR = 2.5
_LINE_GAP_MIN_PIXELS = 25


def _text_from_ocr_data(data):
    """
    Reconstruit un texte "ligne par ligne" a partir du regroupement de mots
    de Tesseract lui-meme (block_num/par_num/line_num), plutot que de
    dependre du texte deja mis en forme par image_to_string.

    Trois avantages concrets :
    - Une seule passe Tesseract suffit (image_to_data fournit le texte ET
      les positions), au lieu d'appeler separement image_to_data et
      image_to_string sur la meme image.
    - On peut couper une ligne Tesseract en deux des qu'un grand espace
      horizontal separe deux mots (cf. _LINE_GAP_HEIGHT_FACTOR) : utile
      quand l'OCR fusionne un libelle et la valeur du champ suivant sur la
      meme ligne physique (releve empiriquement sur un titre de sejour :
      "Moubarak" et "SEXE / SEX NATIONALITE..." colles sur une ligne), ce
      qu'un simple split sur "\\n" ne peut pas detecter.
    - Les lignes sont reordonnees par leur position verticale reelle sur
      l'image (coordonnee "top") plutot que par l'ordre de traversee interne
      de Tesseract : sur une mise en page chargee (photo, drapeau, motifs de
      securite...), Tesseract numerote parfois ses blocs dans un ordre qui
      ne suit pas le haut-vers-le-bas visuel, ce qui deplacait des lignes
      (ex. un libelle) a un endroit incoherent dans le texte final (releve
      empiriquement). Trier par position vertical rend l'ordre du texte
      fidele a l'ordre reel sur le document.
    """
    n = len(data.get("text", []))
    words = [
        {
            "text": data["text"][i].strip(),
            "line_key": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
        }
        for i in range(n)
        if data["text"][i].strip()
    ]
    if not words:
        return ""

    lines_order = []
    lines = {}
    for w in words:
        key = w["line_key"]
        if key not in lines:
            lines[key] = []
            lines_order.append(key)
        lines[key].append(w)

    # Ordonne les lignes par leur position verticale moyenne reelle sur
    # l'image, pas par l'ordre de decouverte dans les donnees Tesseract.
    lines_order.sort(key=lambda key: sum(w["top"] for w in lines[key]) / len(lines[key]))

    out_lines = []
    for key in lines_order:
        # Les mots doivent aussi etre dans l'ordre de lecture gauche-a-droite
        # au sein de la ligne : Tesseract les fournit normalement deja ainsi,
        # mais trier explicitement par "left" evite toute mauvaise surprise.
        line_words = sorted(lines[key], key=lambda w: w["left"])
        avg_height = sum(w["height"] for w in line_words) / len(line_words)
        gap_threshold = max(_LINE_GAP_MIN_PIXELS, avg_height * _LINE_GAP_HEIGHT_FACTOR)

        segments = [[]]
        prev_right = None
        for w in line_words:
            if prev_right is not None and (w["left"] - prev_right) > gap_threshold:
                segments.append([])
            segments[-1].append(w["text"])
            prev_right = w["left"] + w["width"]

        out_lines.extend(" ".join(seg) for seg in segments if seg)

    return "\n".join(out_lines)


def _ocr_with_confidence(pil_image, lang, config):
    """
    Lance Tesseract sur une image et renvoie (texte, confiance moyenne).
    La confiance moyenne (0-100) est calculee a partir des mots reconnus
    avec un score de confiance positif ; -1 si rien n'a ete reconnu ou si
    Tesseract a echoue/depasse le delai autorise.
    """
    try:
        data = pytesseract.image_to_data(
            pil_image, lang=lang, config=config, output_type=Output.DICT,
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except (pytesseract.TesseractError, RuntimeError):
        return "", -1.0

    text = _text_from_ocr_data(data)
    confidences = [
        float(conf)
        for word, conf in zip(data.get("text", []), data.get("conf", []))
        if word.strip() and float(conf) >= 0
    ]
    mean_conf = sum(confidences) / len(confidences) if confidences else -1.0
    return text, mean_conf


# Nombre de variantes (parmi toutes celles testees) dont le texte est
# combine dans le resultat final. Diagnostic effectue sur un titre de
# sejour reel : aucune variante unique ne capture tout le document quand le
# fond est guilloche/colore. Isoler le canal rouge, par exemple, rend le
# bloc nom/prenom tres lisible mais fait completement disparaitre la ligne
# sexe/nationalite/date de naissance (imprimee dans une couleur plus proche
# du rouge) ; une autre variante fait l'inverse. Combiner les meilleures
# variantes au lieu de n'en garder qu'une augmente les chances qu'au moins
# une version contienne correctement chaque champ.
TOP_K_VARIANTS = 3


def _best_ocr_result(variants, lang, configs):
    """
    Essaie plusieurs variantes de pretraitement x configurations Tesseract,
    et combine le texte des meilleures (par confiance moyenne Tesseract)
    plutot que de ne garder qu'un seul "gagnant".

    Les parseurs de champs (regex + fuzzy matching) cherchent un motif
    n'importe ou dans le texte et s'arretent a la premiere correspondance
    valide : leur fournir le texte de plusieurs variantes concatenees (la
    plus fiable en premier) ne les casse pas, et augmente la couverture par
    rapport a un unique pretraitement qui echoue parfois silencieusement
    sur certaines zones du document.

    Returns:
        (texte_combine, confiance_de_la_meilleure_variante)
    """
    scored = []
    for variant_img in variants.values():
        pil_image = Image.fromarray(variant_img)
        for config in configs:
            text, conf = _ocr_with_confidence(pil_image, lang, config)
            if text.strip():
                scored.append((conf, text))

    if not scored:
        return "", -1.0

    scored.sort(key=lambda item: item[0], reverse=True)

    combined_parts = []
    seen_prefixes = set()
    for conf, text in scored:
        if len(combined_parts) >= TOP_K_VARIANTS:
            break
        prefix = text.strip()[:80]
        if prefix in seen_prefixes:
            continue  # quasi-doublon (meme variante testee avec 2 configs)
        seen_prefixes.add(prefix)
        # Chaque bloc est une lecture INDEPENDANTE et COMPLETE du document
        # (pretraitement different), pas un fragment d'un texte unique : les
        # lignes sont dans le bon ordre A L'INTERIEUR de chaque bloc, mais
        # rien ne garantit d'ordre entre deux blocs different. Sans ce
        # marqueur, un libelle qui apparait au debut du 2e bloc peut donner
        # l'impression d'etre "mal place" au milieu du texte final, alors
        # qu'il s'agit simplement du debut d'une autre lecture (releve
        # aupres d'un utilisateur qui a interprete la concatenation comme un
        # texte unique desordonne).
        combined_parts.append(f"--- Lecture (confiance {conf:.0f}%) ---\n{text}")

    return "\n\n".join(combined_parts), scored[0][0]


def extract_text(image_path, lang=DEFAULT_LANG):
    """Extrait le texte brut d'une image via Tesseract, en gardant le
    meilleur resultat parmi plusieurs pretraitements/configurations."""
    variants = preprocess_variants(image_path)
    text, _ = _best_ocr_result(variants, lang, OCR_CONFIGS)
    return text


def extract_text_from_array(img_array, lang=DEFAULT_LANG):
    """Comme extract_text, a partir d'un numpy array deja charge."""
    variants = preprocess_variants_from_array(img_array)
    text, _ = _best_ocr_result(variants, lang, OCR_CONFIGS)
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
        "nationalite": None,
    }

    # --- Etape 0 : Nom/Prenom par recherche de libelle tolerante au bruit ---
    # Meme principe que pour le titre de sejour (_find_label_line +
    # _best_name_token) : plus robuste que la regex unique ci-dessous face
    # a une lettre manquante (ex. "Prénoms" lu "Piénoms", perdant le "r") ou
    # a de la casse variable. Sert de premiere tentative ; la regex
    # existante prend le relais si elle ne trouve rien.
    lines_raw = [
        l.strip() for l in text.split("\n")
        if l.strip() and not l.strip().startswith("---")
    ]

    nom_label_idx = _find_label_line(lines_raw, r"(?i:[Nn]om[s]?\s*[/|\\]\s*[Ss]u[rm]name[s]?)")
    if nom_label_idx is not None:
        for i in range(nom_label_idx + 1, min(nom_label_idx + 4, len(lines_raw))):
            token = _best_name_token(lines_raw[i], allow_lower=False, min_letters=3)
            if token:
                data["nom"] = token
                break

    prenom_label_idx = _find_label_line(
        lines_raw, r"(?i:[Pp]r[ée]?nom[s]?\s*[/|\\]\s*[Gg]iven\s*name[s]?)"
    )
    if prenom_label_idx is not None:
        for i in range(prenom_label_idx + 1, min(prenom_label_idx + 4, len(lines_raw))):
            token = _best_name_token(lines_raw[i], allow_lower=True, min_letters=2)
            if token:
                data["prenom"] = token
                break

    # --- Etape 1 : Labels bilingues (nouvelle CNI francaise) ---
    # Format : "Nom / Surname" suivi du nom sur la meme ligne ou la suivante

    # Nom / Surname (nouvelle CNI)
    if not data["nom"]:
        match = re.search(
            r"[Nn]om\s*/?\s*[Ss]urname[s]?\s*[:\s]?\s*\n?\s*([A-ZÀ-Üa-zà-ü][\w\s\-]+)",
            text
        )
        if match:
            data["nom"] = match.group(1).strip().split("\n")[0].strip()

    # Prenom(s) / Given name(s)
    if not data["prenom"]:
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

    # Numero de document (CNI 2021 : "N° DU DOCUMENT / Document No.")
    # (meme garde-fou "au moins 3 chiffres" que le fallback plus bas : sans
    # ca, un mot voisin sans rapport comme "DATED" (debut de "DATE D'EXPIR"
    # mal OCR juste apres "Document No.") est pris a tort pour le numero.)
    if not data["numero"]:
        label_match = re.search(r"(?i:document\s*no\.?|n[°o]\s*du\s*document)", text)
        if label_match:
            tail = text[label_match.end():label_match.end() + 40]
            for num_match in re.finditer(r"[A-Z0-9]{5,15}", tail):
                candidate = num_match.group(0)
                if sum(c.isdigit() for c in candidate) >= 3:
                    data["numero"] = candidate
                    break

    # CNI 2021 : "Sexe/Sex Nationalite/Nationality Date de naissance/Date of
    # birth" est un en-tete a 3 colonnes, les valeurs correspondantes ("F FRA
    # 01 04 1995") arrivant groupees sur une AUTRE ligne, pas juste apres le
    # libelle sur la meme ligne comme suppose par les regex ci-dessus (qui
    # echouent donc silencieusement sur ce format). On cherche directement le
    # triplet valeur (sexe + code pays 3 lettres + date, avec ou sans
    # separateurs) n'importe ou dans le texte.
    if not data["sexe"] or not data["date_naissance"] or not data["nationalite"]:
        # Tolerant a un peu de bruit OCR entre les 3 valeurs (ex. "F.", "F,",
        # "F -" au lieu de "F ") : un simple "\s+" entre le sexe et le code
        # pays echoue des qu'un caractere parasite s'intercale, ce qui
        # renvoyait toute la detection sexe/nationalite/date_naissance au
        # fuzzy matching (Etape 4) - bien plus fragile sur ce genre de
        # ligne a plusieurs libelles colles (cf. _looks_like_label plus haut).
        combo = re.search(
            r"\b([MF])[^A-Za-z0-9\n]{0,3}([A-Z]{3})[^0-9\n]{0,8}"
            r"(\d{2})[.\s/\-](\d{2})[.\s/\-](\d{4})\b",
            text
        )
        if combo:
            if not data["sexe"]:
                data["sexe"] = combo.group(1)
            if not data["nationalite"]:
                data["nationalite"] = combo.group(2)
            if not data["date_naissance"]:
                data["date_naissance"] = f"{combo.group(3)}/{combo.group(4)}/{combo.group(5)}"

    # Nationalite : libelle bilingue "Nationalite / Nationality" suivi du
    # code pays (souvent 3 lettres, ex. "FRA") sur la meme ligne ou la
    # suivante - repli si le triplet combine ci-dessus n'a pas matche.
    if not data["nationalite"]:
        match = re.search(
            r"(?i:nationalit[ée]\s*/?\s*nationality)\s*[:\s]?\s*\n?\s*([A-Z]{3})\b",
            text
        )
        if match:
            data["nationalite"] = match.group(1)

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
    # (separateur "/./-" OU simple espace, la CNI 2021 imprime souvent les
    # dates sans ponctuation : "01 04 1995")
    if not data["date_naissance"]:
        match = re.search(
            r"(?:[Nn][ée](?:\(e\))?\s*(?:le)?|[Nn]aissance|[Bb]irth)\s*[:\s]?\s*\n?\s*(\d{2}[./\- ]\d{2}[./\- ]\d{4})",
            text
        )
        if match:
            data["date_naissance"] = re.sub(r"\s+", "/", match.group(1).strip())

    # Fallback date : premiere date trouvee dans le texte
    if not data["date_naissance"]:
        match = re.search(r"(\d{2}[/.\-]\d{2}[/.\-]\d{4})", text)
        if match:
            data["date_naissance"] = match.group(1)

    # Numero : N° XXXX ou No XXXX
    # Note : la variante "Carte\s*N" a ete retiree, elle matchait a tort le
    # milieu du mot "NATIONALE" dans "CARTE NATIONALE D'IDENTITE" et
    # renvoyait "ATIONALE" comme faux numero. \b evite aussi un match a
    # l'interieur d'un autre mot.
    if not data["numero"]:
        match = re.search(r"\bN[°o]\b|\bNo\b", text)
        if match:
            # Un vrai numero de document CNI melange lettres ET chiffres
            # (ex. "T7X62TZ79") : on exige au moins 3 chiffres dans le
            # candidat, sinon un mot tout en majuscules sans rapport (ex.
            # "DATED", debut de "DATE D'EXPIR" mal OCR juste apres "Document
            # No.") serait pris a tort pour le numero - releve empiriquement.
            tail = text[match.end():match.end() + 40]
            for num_match in re.finditer(r"[A-Z0-9]{5,15}", tail):
                candidate = num_match.group(0)
                if sum(c.isdigit() for c in candidate) >= 3:
                    data["numero"] = candidate
                    break

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


def _split_into_lectures(text):
    """
    Redecoupe le texte combine (produit par _best_ocr_result) en ses
    lectures individuelles, sur le marqueur "--- Lecture (confiance ...) ---".
    Si le texte ne contient aucun marqueur (ex. dans les tests unitaires qui
    passent un texte "brut" directement), le texte entier est traite comme
    une seule lecture.
    """
    parts = re.split(r"--- Lecture \(confiance [^)]*\) ---\n?", text)
    return [p for p in parts if p.strip()]


def _find_mrz_pair(text):
    """
    Cherche, a l'interieur d'UNE SEULE lecture, deux lignes MRZ adjacentes
    (ligne 1 : nom, ligne 2 : donnees). Chaque ligne candidate est
    "nettoyee" (on retire les caracteres qui ne sont pas des majuscules,
    chiffres ou "<", au lieu de s'arreter au premier caractere parasite
    rencontre) avant d'etre evaluee, ce qui recupere une ligne MRZ lisible
    meme coupee par du bruit OCR isole (espace, minuscule egaree...).

    Returns:
        (ligne1_nettoyee, ligne2_nettoyee) ou (None, None)
    """
    lines = [l for l in text.split("\n") if l.strip()]
    cleaned = [re.sub(r"[^A-Z0-9<]", "", l.upper()) for l in lines]

    line1_idx = None
    for i, c in enumerate(cleaned):
        if c.startswith("P<") and len(c) >= 15:
            line1_idx = i
            break
    if line1_idx is None:
        return None, None

    # La ligne 2 est normalement juste apres la ligne 1 dans le document ;
    # on tolere 1-2 lignes d'ecart (une ligne totalement vide ou meconnue
    # par l'OCR entre les deux, deja observe en pratique).
    for j in range(line1_idx + 1, min(line1_idx + 3, len(cleaned))):
        if len(cleaned[j]) >= 20:
            return cleaned[line1_idx], cleaned[j]

    return None, None


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
    # L'ancienne approche (chercher un bloc ininterrompu de 30 a 44
    # caracteres [A-Z0-9<]) est fragile : un seul caractere parasite au
    # milieu de la vraie ligne MRZ (un espace, une lettre minuscule captee
    # par erreur...) coupe le match bien avant d'atteindre 30 caracteres,
    # et la ligne MRZ - pourtant lisible - est alors ignoree. On nettoie
    # maintenant chaque ligne (on RETIRE les caracteres parasites au lieu
    # de s'arreter dessus) et on cherche la paire ligne1/ligne2 a
    # l'INTERIEUR d'une seule lecture a la fois (cf. _find_mrz_pair) :
    # un texte combine plusieurs lectures independantes du meme document,
    # et prendre "les deux derniers blocs MRZ trouves dans tout le texte"
    # peut associer la ligne 1 d'une lecture a la ligne 2 d'une autre,
    # produisant une paire incoherente.
    # On evalue TOUTES les lectures (pas juste la premiere qui produit une
    # paire) et on garde celle dont la ligne 2 contient le plus de chiffres :
    # la lecture la plus fiable dans l'ensemble n'est pas forcement celle ou
    # la ligne 2 (numero/date/sexe, presque entierement numerique) est la
    # mieux reconnue - releve empiriquement, une lecture peut avoir un tres
    # bon nom/prenom mais une ligne 2 totalement illisible pendant qu'une
    # autre lecture, moins bonne globalement, lit tres bien cette ligne 2.
    best_pair, best_digit_count = (None, None), -1
    for lecture in _split_into_lectures(text):
        candidate_line1, candidate_line2 = _find_mrz_pair(lecture)
        if not candidate_line1 or not candidate_line2:
            continue
        digit_count = sum(c.isdigit() for c in candidate_line2)
        if digit_count > best_digit_count:
            best_digit_count = digit_count
            best_pair = (candidate_line1, candidate_line2)

    line1, line2 = best_pair

    if line1 and line2:
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
        r"(?:[Uu]niversit[ée]|[Éé]cole|[Ii]nstitut|[Ff]acult[ée]|IUT|UFR)\s*(?:de\s*|d['’])?(.+?)(?:\n|$)",
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


def _find_label_line(lines, label_pattern):
    """Renvoie l'indice de la premiere ligne correspondant au motif de
    libelle donne, ou None si aucune ne correspond."""
    for i, line in enumerate(lines):
        if re.search(label_pattern, line):
            return i
    return None


def _best_name_token(line, allow_lower, min_letters):
    """
    Cherche dans une ligne le meilleur jeton "nom" exploitable.

    Une ligne d'OCR bruitee contient souvent plusieurs fragments separes par
    des scories (ex. "MN = Moubarak" : "MN" est un debris, "Moubarak" est le
    vrai prenom). Plutot que de prendre le premier fragment trouve (qui est
    souvent le debris le plus proche du libelle), on liste tous les
    fragments candidats et on garde le plus long : un nom/prenom reel est
    presque toujours plus long qu'un artefact OCR isole.

    Args:
        line: ligne de texte a analyser
        allow_lower: si True, autorise aussi les minuscules (prenom) ; si
            False, n'accepte que des fragments majoritairement majuscules
            (nom de famille, imprime en capitales sur la carte)
        min_letters: nombre minimum de lettres pour qu'un fragment soit
            considere comme un nom plausible plutot qu'un debris

    Returns:
        le meilleur fragment (str) ou None si rien d'assez long
    """
    if allow_lower:
        pattern = r"[A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü\s\-']*"
    else:
        pattern = r"[A-ZÀ-Ü][A-ZÀ-Ü\s\-']*"

    candidates = [c.strip(" -'") for c in re.findall(pattern, line)]
    candidates = [c for c in candidates if sum(ch.isalpha() for ch in c) >= min_letters]
    # Ecarte les fragments qui sont eux-memes un bout d'un AUTRE libelle du
    # document (ex. "SEXE", "DATE DE NAISSANCE"). Filtrer fragment par
    # fragment plutot que rejeter toute la ligne des qu'un libelle y
    # apparait permet de recuperer un vrai nom/prenom meme quand l'OCR l'a
    # fusionne sur la meme ligne qu'un libelle voisin (releve empiriquement
    # avec "Moubarak— = SEXE / SEX NATIONALITE...", ou seul "Moubarak" doit
    # etre garde).
    candidates = [c for c in candidates if not _looks_like_label(c)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Plusieurs fragments substantiels sur la meme ligne : un nom de famille
    # compose (ex. "YAHAYA MOUSSA") se retrouve parfois coupe en deux par
    # une scorie OCR entre les mots (ex. "YAHAYA- | NOUSSAY", releve
    # empiriquement) - les rejoindre est plus fidele que de n'en garder que
    # la moitie la plus longue.
    return " ".join(candidates)


def _scan_name_pair(lines, start, end):
    """
    Cherche dans lines[start:end] une paire nom/prenom : la premiere ligne
    qui ressemble a un nom de famille (majuscules, cf. _best_name_token),
    suivie de la premiere ligne suivante qui ressemble a un prenom.

    On ne rejette pas une ligne entiere au seul motif qu'elle contient AUSSI
    du texte de libelle (ex. "Moubarak— = SEXE / SEX NATIONALITE...", ou
    l'OCR a fusionne le vrai prenom avec le libelle suivant sur une seule
    ligne) : c'est _best_name_token qui filtre fragment par fragment, ce qui
    recupere "Moubarak" dans ce cas au lieu de tout ignorer.

    Returns:
        (nom, prenom, indice_de_la_ligne_nom) ou (None, None, None)
    """
    for i in range(start, end):
        nom = _best_name_token(lines[i], allow_lower=False, min_letters=4)
        if not nom:
            continue
        for j in range(i + 1, min(i + 4, end)):
            prenom = _best_name_token(lines[j], allow_lower=True, min_letters=3)
            if prenom:
                return nom, prenom, i
        return nom, None, i
    return None, None, None


def parse_titre_sejour(text):
    """
    Parse le texte d'un titre de sejour (carte de sejour temporaire, carte de
    resident...). Mise en page bilingue francais/anglais mais structuree
    differemment d'une CNI : les libelles "SEXE / SEX", "NATIONALITE / NAT."
    et "DATE DE NAISSANCE / BIRTH DATE" partagent une meme ligne, avec les
    valeurs correspondantes ("M NER 11 07 2000") sur la ligne suivante, et
    les dates sont ecrites sans separateur (jj mm aaaa).
    """
    data = {
        "type_document": "Titre de sejour",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "numero": None,
        "sexe": None,
        "nationalite": None,
        "numero_personnel": None,
        "type_titre": None,
        "date_validite": None,
    }

    # --- Etape 1 : Nom / Prenom sous le libelle "Noms Prenoms / Surnames Forenames" ---
    # Approche ligne par ligne plutot qu'une regex unique multi-lignes :
    # sur un OCR bruite, il arrive qu'une ou deux lignes de pur bruit
    # s'intercalent entre le libelle et le vrai nom/prenom (releve
    # empiriquement). On cherche donc, dans une fenetre de quelques lignes
    # apres le libelle, la premiere qui contient un jeton assez long pour
    # etre un vrai nom plutot qu'un debris OCR (cf. _best_name_token) - et
    # on ne force RIEN si rien d'assez fiable n'est trouve : un champ
    # "Non detecte" vaut mieux qu'une valeur fausse.
    # Le separateur entre "Prenoms" et "Surnames" varie beaucoup selon l'OCR
    # (" / ", " | ", "/-" sans espace...) : plutot que de lister chaque
    # variante, "[^A-Za-z]*" accepte n'importe quelle suite de caracteres
    # non-alphabetiques entre les deux mots.
    # Les lignes "--- Lecture (confiance ...) ---" sont un marqueur ajoute
    # par _best_ocr_result entre les differentes lectures combinees, pas du
    # texte du document : on les exclut pour ne pas risquer qu'un mot comme
    # "Lecture" soit pris pour un prenom.
    lines_raw = [
        l.strip() for l in text.split("\n")
        if l.strip() and not l.strip().startswith("---")
    ]
    # Sur ce type de document, le nom/prenom est systematiquement le premier
    # champ imprime en haut de la carte (avant meme le libelle "Noms
    # Prenoms / Surnames Forenames" sur certaines lectures ou ce dernier
    # n'est pas capture) - constate empiriquement sur plusieurs lectures
    # reelles : la meilleure lecture (la plus fiable, placee en tete du
    # texte combine par _best_ocr_result) commence quasi-systematiquement
    # par le nom. On essaie donc D'ABORD le tout debut du texte, qui est a
    # la fois le plus simple et le plus fiable, avant de se rabattre sur une
    # recherche ancree au libelle.
    nom, prenom, _ = _scan_name_pair(lines_raw, 0, min(4, len(lines_raw)))
    data["nom"], data["prenom"] = nom, prenom

    if not data["nom"]:
        label_idx = _find_label_line(
            lines_raw,
            r"(?i:[Nn]oms?\s*[Pp]r[ée]noms?[^A-Za-z]*[Ss]urnames?\s*[Ff]orenames?)"
        )
        if label_idx is not None:
            nom, prenom, _ = _scan_name_pair(lines_raw, label_idx + 1, min(label_idx + 6, len(lines_raw)))
            data["nom"], data["prenom"] = nom, prenom

    # Dernier repli : chercher la meme paire n'importe ou dans le reste du
    # texte (utile si le nom n'est ni en tete ni pres du libelle sur cette
    # lecture particuliere).
    if not data["nom"]:
        nom, prenom, _ = _scan_name_pair(lines_raw, 0, len(lines_raw))
        data["nom"], data["prenom"] = nom, prenom

    # --- Etape 2 : Sexe / Nationalite (ex. "M NER") ---
    # Le "[^A-Za-z\n]{0,4}" entre sexe et nationalite tolere quelques
    # caracteres de bruit OCR (ex. "M -_NER", releve empiriquement) sans
    # risquer de sauter sur une trop grande distance (borne a 4 caracteres)
    # et donc de matcher deux lettres M/F et 3 majuscules sans rapport plus
    # loin dans le texte.
    sexe_nat_match = re.search(r"\b([MF])[^A-Za-z\n]{0,4}([A-Z]{3})\b", text)
    if sexe_nat_match:
        data["sexe"] = sexe_nat_match.group(1)
        data["nationalite"] = sexe_nat_match.group(2)

    if not data["sexe"]:
        match = re.search(r"(?i:sexe\s*/?\s*sex)\s*[:\s]?\s*\n?\s*([MFmf])\b", text)
        if match:
            data["sexe"] = match.group(1).upper()

    # --- Etape 3 : Type de titre (ex. "CARTE DE SEJOUR TEMPORAIRE") ---
    type_titre_match = re.search(
        r"(CARTE\s+DE\s+S[ÉEée]JOUR\s*(?:TEMPORAIRE|PERMANENTE?|PLURIANNUELLE)?"
        r"|CARTE\s+DE\s+R[ÉEée]SIDENT[E]?)",
        text, re.IGNORECASE
    )
    if type_titre_match:
        data["type_titre"] = re.sub(r"\s+", " ", type_titre_match.group(1)).strip().upper()

    # --- Etape 4 : Dates (naissance et validite) ---
    # Cherchees par PROXIMITE avec leur contexte respectif (juste apres le
    # sexe/nationalite pour la naissance, juste apres le type de titre pour
    # la validite) plutot que par simple ordre d'apparition dans le texte.
    # Sur un OCR degrade, l'une des deux dates est souvent partiellement
    # illisible (chiffres confondus avec un mot, ex. "11" lu "id") pendant
    # que l'autre reste nette : se fier a "la Nieme date trouvee dans tout
    # le texte" attribuerait alors la seule date propre au mauvais champ.
    def _date_after(pos, window=40):
        if pos is None:
            return None
        tail = text[pos:pos + window]
        m = re.search(r"\b(\d{2})\s+(\d{2})\s+(\d{4})\b", tail)
        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        m = re.search(r"\d{2}[./\-]\d{2}[./\-]\d{4}", tail)
        if m:
            return m.group(0).replace(".", "/").replace("-", "/")
        return None

    if not data["date_naissance"]:
        data["date_naissance"] = _date_after(sexe_nat_match.end() if sexe_nat_match else None)

    if not data["date_validite"]:
        data["date_validite"] = _date_after(type_titre_match.end() if type_titre_match else None)

    # Repli : si l'ancrage contextuel n'a rien donne (libelle lui-meme non
    # capture par l'OCR), on prend simplement les dates dans l'ordre
    # d'apparition, en evitant d'assigner deux fois la meme date.
    if not data["date_naissance"] or not data["date_validite"]:
        dates_sans_sep = ["/".join(d) for d in re.findall(r"\b(\d{2})\s+(\d{2})\s+(\d{4})\b", text)]
        dates_avec_sep = [
            d.replace(".", "/").replace("-", "/")
            for d in re.findall(r"\d{2}[./\-]\d{2}[./\-]\d{4}", text)
        ]
        all_dates = []
        for d in dates_sans_sep + dates_avec_sep:
            if d not in all_dates:
                all_dates.append(d)
        remaining = [d for d in all_dates if d not in (data["date_naissance"], data["date_validite"])]
        if not data["date_naissance"] and remaining:
            data["date_naissance"] = remaining.pop(0)
        if not data["date_validite"] and remaining:
            data["date_validite"] = remaining.pop(0)

    # --- Etape 4 : Numero personnel ---
    # La partie anglaise "Personal Number" est tres souvent deformee par
    # l'OCR ("PERSONAL NUMEER", "PERSONAE-NUMEER"...) : plutot que d'exiger
    # ce texte precis, on accepte n'importe quel bruit (hors chiffres) entre
    # "Numero personnel" et la premiere suite de chiffres, y compris a
    # cheval sur la ligne suivante (le nombre atterrit parfois juste apres
    # un saut de ligne).
    match = re.search(
        r"(?i:[Nn]um[ée]ro\s*personnel)[^\d\n]{0,40}\n?[^\d\n]{0,10}(\d{6,15})",
        text
    )
    if match:
        data["numero_personnel"] = match.group(1).strip()

    # --- Etape 5 : Numero du titre (code alphanumerique, ex. "F7AB7250N") ---
    # Recherche dans les premieres lignes (en-tete du document) un jeton
    # alphanumerique melangeant lettres et chiffres, typique du numero
    # imprime en haut de la carte.
    for candidate in re.findall(r"\b[A-Z0-9]{7,10}\b", text[:200]):
        if any(c.isdigit() for c in candidate) and any(c.isalpha() for c in candidate):
            data["numero"] = candidate
            break

    # --- Etape 6 : Fuzzy matching pour les champs encore non detectes ---
    fuzzy_find_field(text, LABELS_TITRE_SEJOUR, data)

    return data


# --- Fonction principale ---

PARSERS = {
    "cni": parse_cni,
    "passeport": parse_passeport,
    "certificat": parse_certificat_scolarite,
    "titre_sejour": parse_titre_sejour,
}


def extract_document(image_path, doc_type, lang=DEFAULT_LANG):
    """
    Extrait les donnees d'un document selon son type.

    Args:
        image_path: chemin vers l'image du document
        doc_type: type de document ("cni", "passeport", "certificat")
        lang: langue(s) Tesseract (par defaut "fra+eng")

    Returns:
        dict avec les champs extraits + le texte brut
    """
    if doc_type not in PARSERS:
        raise ValueError(f"Type de document inconnu : {doc_type}. Choix : {list(PARSERS.keys())}")

    raw_text = extract_text(image_path, lang=lang)
    parsed = PARSERS[doc_type](raw_text)
    parsed["texte_brut"] = raw_text

    return parsed
