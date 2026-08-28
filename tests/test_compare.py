"""
Tests unitaires pour le module de comparaison.
"""

import os
import pytest
import pandas as pd
from comparator.compare import (
    normalize,
    compare_fields,
    find_matching_record,
    compare_document,
)


class TestNormalize:
    def test_minuscules(self):
        assert normalize("DUPONT") == "dupont"

    def test_espaces(self):
        assert normalize("  Jean  ") == "jean"

    def test_none(self):
        assert normalize(None) == ""

    def test_nombre(self):
        assert normalize(123) == "123"

    def test_accents(self):
        # L'OCR confond souvent les accents ; la reference peut etre saisie
        # avec ou sans accent. Les deux doivent etre consideres identiques.
        assert normalize("Hélène") == normalize("Helene")
        assert normalize("François") == "francois"

    def test_separateurs_date_uniformises(self):
        # Un OCR peut lire un point ou un tiret a la place du slash dans une
        # date ; cela ne doit pas etre traite comme une difference de valeur.
        assert normalize("15.03.1990") == normalize("15/03/1990")
        assert normalize("15-03-1990") == normalize("15/03/1990")

    def test_accents_et_dates_combines(self):
        assert normalize("  NÉE LE 15.03.1990  ") == normalize("nee le 15/03/1990")


class TestCompareFields:
    def test_champs_identiques(self):
        extracted = {"nom": "DUPONT", "prenom": "Jean"}
        reference = {"nom": "DUPONT", "prenom": "Jean"}
        results = compare_fields(extracted, reference, ["nom", "prenom"])
        assert all(r["status"] == "identique" for r in results)
        assert all(r["score"] == 100 for r in results)

    def test_champs_differents(self):
        extracted = {"nom": "DUPONT"}
        reference = {"nom": "MARTIN"}
        results = compare_fields(extracted, reference, ["nom"])
        assert results[0]["status"] == "different"
        assert results[0]["score"] < 80

    def test_champ_similaire(self):
        # Simuler une erreur OCR legere
        extracted = {"nom": "DUpont"}
        reference = {"nom": "DUPONT"}
        results = compare_fields(extracted, reference, ["nom"])
        assert results[0]["status"] in ("identique", "similaire")
        assert results[0]["score"] >= 80

    def test_champ_manquant_ocr(self):
        extracted = {"nom": None}
        reference = {"nom": "DUPONT"}
        results = compare_fields(extracted, reference, ["nom"])
        assert results[0]["status"] == "manquant_ocr"


class TestFindMatchingRecord:
    def setup_method(self):
        self.df = pd.DataFrame([
            {"nom": "DUPONT", "prenom": "Jean"},
            {"nom": "MARTIN", "prenom": "Sophie"},
            {"nom": "BERNARD", "prenom": "Pierre"},
        ])

    def test_match_exact(self):
        extracted = {"nom": "DUPONT"}
        idx, record = find_matching_record(extracted, self.df)
        assert idx == 0
        assert record["prenom"] == "Jean"

    def test_match_approximate(self):
        extracted = {"nom": "DUPON"}  # Erreur OCR
        idx, record = find_matching_record(extracted, self.df)
        assert idx == 0  # Devrait quand meme matcher DUPONT

    def test_no_match(self):
        extracted = {"nom": "ZZZZZ"}
        idx, record = find_matching_record(extracted, self.df)
        assert idx is None

    def test_disambiguation_par_prenom(self):
        # Deux personnes partagent le meme nom de famille : le seul champ
        # "nom" ne suffit pas a les distinguer. Le prenom (poids plus faible
        # mais pris en compte) doit permettre de selectionner le bon
        # enregistrement plutot que le premier "DUPONT" trouve.
        df = pd.DataFrame([
            {"nom": "DUPONT", "prenom": "Jean"},
            {"nom": "DUPONT", "prenom": "Marie"},
        ])
        extracted = {"nom": "DUPONT", "prenom": "Marie"}
        idx, record = find_matching_record(extracted, df)
        assert idx == 1
        assert record["prenom"] == "Marie"

    def test_match_robuste_a_une_erreur_ocr_sur_un_seul_champ(self):
        # Le prenom est lu correctement mais le nom contient une erreur OCR
        # legere (chiffre 0 a la place de la lettre O) : la combinaison
        # ponderee doit quand meme retrouver le bon enregistrement.
        extracted = {"nom": "DUP0NT", "prenom": "Jean"}
        idx, record = find_matching_record(extracted, self.df)
        assert idx == 0


class TestCompareDocument:
    def setup_method(self):
        """Cree un fichier Excel temporaire pour les tests."""
        self.test_excel = "/tmp/test_reference.xlsx"
        df = pd.DataFrame([
            {
                "nom": "DUPONT",
                "prenom": "Jean",
                "date_naissance": "15/03/1990",
                "numero": "ABC123456",
                "sexe": "M",
                "nationalite": "FRA",
                "annee_universitaire": "2024-2025",
            },
        ])
        df.to_excel(self.test_excel, index=False)

    def test_comparaison_coherente(self):
        extracted = {
            "type_document": "CNI",
            "nom": "DUPONT",
            "prenom": "Jean",
            "date_naissance": "15/03/1990",
            "numero": "ABC123456",
            "sexe": "M",
            "nationalite": "FRA",
        }
        result = compare_document(extracted, self.test_excel)
        assert result["match_found"] is True
        assert result["coherent"] is True
        assert result["score_global"] == 100

    def test_comparaison_incoherente(self):
        extracted = {
            "type_document": "CNI",
            "nom": "DUPONT",
            "prenom": "Marie",  # Mauvais prenom
            "date_naissance": "01/01/2000",  # Mauvaise date
            "numero": "XYZ999999",  # Mauvais numero
            "sexe": "F",
        }
        result = compare_document(extracted, self.test_excel)
        assert result["match_found"] is True
        assert result["coherent"] is False
        assert len(result["incoherences"]) > 0

    def test_aucune_correspondance(self):
        extracted = {
            "type_document": "CNI",
            "nom": "ZZZZZZZ",
            "prenom": "Inconnu",
        }
        result = compare_document(extracted, self.test_excel)
        assert result["match_found"] is False

    def teardown_method(self):
        if os.path.exists(self.test_excel):
            os.remove(self.test_excel)
