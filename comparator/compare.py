"""
Module de comparaison entre les donnees extraites par OCR
et les donnees de reference (fichier Excel).
"""

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


def normalize(value):
    """Normalise une valeur pour la comparaison (minuscules, sans espaces superflus)."""
    if value is None:
        return ""
    return str(value).strip().lower()


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


def find_matching_record(extracted, df, key_field="nom"):
    """
    Cherche dans le DataFrame la ligne qui correspond le mieux
    aux donnees extraites, en se basant sur un champ cle.

    Returns:
        (index, Series) du meilleur match, ou (None, None) si rien trouve.
    """
    val_ocr = normalize(extracted.get(key_field))
    if not val_ocr:
        return None, None

    best_score = 0
    best_idx = None

    for idx, row in df.iterrows():
        val_ref = normalize(row.get(key_field, ""))
        score = fuzz.ratio(val_ocr, val_ref)
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_score >= 60:
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
        fields = ["nom", "prenom", "date_naissance", "numero", "sexe"]
    elif doc_type == "Passeport":
        fields = ["nom", "prenom", "date_naissance", "numero", "nationalite"]
    elif doc_type == "Certificat de scolarite":
        fields = ["nom", "prenom", "annee_universitaire"]
    else:
        fields = ["nom", "prenom"]

    # Chercher la personne correspondante
    idx, record = find_matching_record(extracted, df, key_field="nom")

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
