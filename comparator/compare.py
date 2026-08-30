"""
Module de comparaison entre les donnees extraites par OCR
et les donnees de reference (fichier Excel).
"""

import datetime
import re
import unicodedata

import pandas as pd
from rapidfuzz import fuzz


def load_reference_data(excel_path):
    """
    Charge les donnees de reference depuis un fichier Excel.
    Retourne un DataFrame pandas.
    """
    df = pd.read_excel(excel_path)
    # Normaliser les noms de colonnes en minuscules
    df.columns = [col.strip().lower() for col in df.columns]
    return df


def _try_parse_date(value):
    """
    Tente d'interpreter value comme une date, quel que soit son format
    d'origine, et renvoie un objet datetime.date (ou None si value ne
    ressemble a aucun format de date connu).

    Necessaire car reference.xlsx est charge par pandas : une date de
    naissance y devient un Timestamp, dont le str() donne un format ISO
    avec heure ("1995-04-01 00:00:00"), alors que l'OCR produit un format
    francais jour/mois/annee ("01/04/1995") - la MEME date. Sans ce
    parsing, l'ancienne normalisation (simple mise en minuscules +
    uniformisation des separateurs) les laissait aussi differentes l'une
    de l'autre qu'un champ reellement errone, et rapidfuzz ne leur donnait
    qu'un score d'environ 40% ("different") au lieu de 100% - releve
    empiriquement sur un test CNI reel (phpCDwGn0.jpg) ou toutes les autres
    valeurs (nom, prenom, numero, nationalite) correspondaient pourtant.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if hasattr(value, "to_pydatetime"):
        # pandas.Timestamp
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None

    text = str(value).strip()

    # Format ISO produit par str() sur un Timestamp pandas : "1995-04-01"
    # ou "1995-04-01 00:00:00"
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    # Format francais jour/mois/annee, avec separateur '/', '.' ou '-'
    match = re.match(r"^(\d{2})[./\-](\d{2})[./\-](\d{4})$", text)
    if match:
        jour, mois, annee = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime.date(annee, mois, jour)
        except ValueError:
            return None

    return None


def normalize(value):
    """
    Normalise une valeur pour la comparaison :
    - une date (quel que soit son format d'origine - voir _try_parse_date)
      est ramenee a une forme canonique ISO ("aaaa-mm-jj") avant toute
      autre chose, pour que deux dates identiques ecrites differemment
      (Timestamp pandas de la reference vs "jj/mm/aaaa" de l'OCR) obtiennent
      un score de 100% plutot que d'etre comparees comme deux chaines
      quelconques
    - sinon, minuscules, espaces superflus supprimes
    - accents retires (l'OCR confond souvent les caracteres accentues, et la
      reference peut etre saisie avec ou sans accents : "Hélène" et "Helene"
      ne doivent pas etre consideres comme "differents")
    - separateurs de date uniformises ('.', '-' -> '/') : un "15.03.1990" lu
      par l'OCR doit pouvoir etre compare a un "15/03/1990" de reference sans
      perdre de points de similarite a cause du seul separateur
    """
    if value is None:
        return ""
    parsed_date = _try_parse_date(value)
    if parsed_date is not None:
        return parsed_date.isoformat()
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[.\-]", "/", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compare_fields(extracted, reference, fields):
    """
    Compare les champs extraits avec les donnees de reference.

    Args:
        extracted: dict des donnees extraites par OCR
        reference: dict (ou Series pandas) des donnees de reference
        fields: liste des noms de champs a comparer

    Returns:
        liste de dicts avec le detail de chaque comparaison
    """
    results = []

    for field in fields:
        val_ocr = normalize(extracted.get(field))
        val_ref = normalize(reference.get(field))

        if not val_ocr and not val_ref:
            status = "vide"
            score = 100
        elif not val_ocr:
            status = "manquant_ocr"
            score = 0
        elif not val_ref:
            status = "manquant_ref"
            score = 0
        else:
            score = fuzz.ratio(val_ocr, val_ref)
            if score == 100:
                status = "identique"
            elif score >= 80:
                status = "similaire"
            else:
                status = "different"

        results.append({
            "champ": field,
            "valeur_ocr": extracted.get(field, ""),
            "valeur_reference": reference.get(field, ""),
            "score": score,
            "status": status,
        })

    return results


def find_matching_record(extracted, df, key_fields=("nom", "prenom"), threshold=60):
    """
    Cherche dans le DataFrame la ligne qui correspond le mieux aux donnees
    extraites, en combinant plusieurs champs (nom + prenom par defaut) plutot
    qu'un seul champ cle.

    Se baser sur un seul champ ("nom" seul, dans l'ancienne version) est
    fragile : si l'OCR se trompe sur le nom mais lit correctement le prenom
    (ou inversement), ou si deux personnes de la base partagent un nom de
    famille frequent, le mauvais enregistrement (ou aucun) est retrouve. En
    combinant plusieurs champs avec un poids plus fort sur le nom, le
    matching reste robuste a une erreur OCR isolee sur un seul champ.

    Args:
        extracted: dict des donnees extraites
        df: DataFrame de reference
        key_fields: champs utilises pour le matching, par poids decroissant
        threshold: score combine minimum (0-100) pour valider un match

    Returns:
        (index, Series) du meilleur match, ou (None, None) si rien trouve.
    """
    available_fields = [f for f in key_fields if normalize(extracted.get(f))]
    if not available_fields:
        return None, None

    # Le premier champ (nom, par defaut) compte double : c'est le critere
    # d'identification principal, mais il ne doit plus etre le seul.
    weights = [2.0] + [1.0] * (len(available_fields) - 1)

    best_score = -1.0
    best_idx = None

    for idx, row in df.iterrows():
        total_weight = 0.0
        weighted_score = 0.0
        for field, weight in zip(available_fields, weights):
            val_ref = normalize(row.get(field, ""))
            if not val_ref:
                continue
            val_ocr = normalize(extracted.get(field))
            weighted_score += weight * fuzz.ratio(val_ocr, val_ref)
            total_weight += weight

        if total_weight == 0:
            continue

        score = weighted_score / total_weight
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx is not None and best_score >= threshold:
        return best_idx, df.loc[best_idx]

    return None, None


def compare_document(extracted, excel_path):
    """
    Pipeline complet de comparaison :
    1. Charge le fichier Excel de reference
    2. Trouve la ligne correspondante
    3. Compare les champs

    Returns:
        dict avec le resultat de la comparaison
    """
    df = load_reference_data(excel_path)

    # Determiner les champs a comparer selon le type de document
    doc_type = extracted.get("type_document", "")

    if doc_type == "CNI":
        fields = ["nom", "prenom", "date_naissance", "numero", "sexe", "nationalite"]
    elif doc_type == "Passeport":
        fields = ["nom", "prenom", "date_naissance", "numero", "nationalite"]
    elif doc_type == "Certificat de scolarite":
        fields = ["nom", "prenom", "annee_universitaire"]
    elif doc_type == "Titre de sejour":
        fields = ["nom", "prenom", "date_naissance", "numero", "sexe", "nationalite"]
    else:
        fields = ["nom", "prenom"]

    # Chercher la personne correspondante (nom + prenom si disponibles)
    idx, record = find_matching_record(extracted, df, key_fields=("nom", "prenom"))

    if record is None:
        return {
            "match_found": False,
            "message": "Aucune correspondance trouvee dans la base de reference.",
            "comparaisons": [],
        }

    # Comparer les champs
    comparaisons = compare_fields(extracted, record.to_dict(), fields)

    # Calculer le score global
    scores = [c["score"] for c in comparaisons if c["status"] != "vide"]
    score_global = sum(scores) / len(scores) if scores else 0

    # Detecter les incoherences
    incoherences = [c for c in comparaisons if c["status"] in ("different", "manquant_ocr")]

    return {
        "match_found": True,
        "score_global": round(score_global, 1),
        "coherent": len(incoherences) == 0,
        "comparaisons": comparaisons,
        "incoherences": incoherences,
    }
