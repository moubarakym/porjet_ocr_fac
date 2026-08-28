"""
Tests unitaires pour le module d'extraction OCR.
On teste les fonctions de parsing sur du texte simule
(pas besoin d'image reelle pour les tests unitaires).
"""

import pytest
from PIL import Image

from ocr.extractor import (
    parse_cni,
    parse_passeport,
    parse_certificat_scolarite,
    _ocr_with_confidence,
)


class TestOcrTimeout:
    """
    Sur une image tres degradee (bruit important), Tesseract peut rester
    bloque tres longtemps. pytesseract leve alors un RuntimeError simple
    ("Tesseract process timeout") plutot qu'une exception dediee.
    _ocr_with_confidence doit absorber ce cas (et les erreurs Tesseract
    classiques) et renvoyer un resultat vide plutot que de laisser
    l'exception remonter et bloquer tout le pipeline.
    """

    def test_timeout_renvoie_resultat_vide(self, monkeypatch):
        import ocr.extractor as extractor_module

        def fake_image_to_data(*args, **kwargs):
            raise RuntimeError("Tesseract process timeout")

        monkeypatch.setattr(
            extractor_module.pytesseract, "image_to_data", fake_image_to_data
        )

        img = Image.new("L", (10, 10), color=255)
        text, conf = _ocr_with_confidence(img, "fra+eng", "--oem 1 --psm 6")

        assert text == ""
        assert conf == -1.0

    def test_erreur_tesseract_renvoie_resultat_vide(self, monkeypatch):
        import ocr.extractor as extractor_module

        def fake_image_to_data(*args, **kwargs):
            raise extractor_module.pytesseract.TesseractError(1, "erreur simulee")

        monkeypatch.setattr(
            extractor_module.pytesseract, "image_to_data", fake_image_to_data
        )

        img = Image.new("L", (10, 10), color=255)
        text, conf = _ocr_with_confidence(img, "fra+eng", "--oem 1 --psm 6")

        assert text == ""
        assert conf == -1.0


class TestParseCNI:
    def test_extraction_nom(self):
        text = "Nom : DUPONT\nPrenom : Jean\nNe le 15/03/1990"
        result = parse_cni(text)
        assert result["nom"] == "DUPONT"

    def test_extraction_prenom(self):
        text = "Nom : DUPONT\nPrenom : Jean\nNe le 15/03/1990"
        result = parse_cni(text)
        assert result["prenom"] == "Jean"

    def test_extraction_date_naissance(self):
        text = "Nom : DUPONT\nPrenom : Jean\nNe le 15/03/1990"
        result = parse_cni(text)
        assert result["date_naissance"] == "15/03/1990"

    def test_extraction_numero(self):
        text = "Carte N° ABC123456789\nNom : MARTIN"
        result = parse_cni(text)
        assert result["numero"] == "ABC123456789"

    def test_champs_manquants(self):
        text = "Texte sans information utile"
        result = parse_cni(text)
        assert result["nom"] is None
        assert result["prenom"] is None
        assert result["date_naissance"] is None

    def test_type_document(self):
        result = parse_cni("Nom : TEST")
        assert result["type_document"] == "CNI"

    def test_date_avec_points(self):
        text = "Nom : DUPONT\n22.07.1995"
        result = parse_cni(text)
        assert result["date_naissance"] == "22.07.1995"


class TestParsePasseport:
    def test_mrz_parsing(self):
        """Test avec une zone MRZ simulee."""
        mrz = (
            "P<FRADUPONT<<JEAN<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
            "ABC12345607FRA9003155M2503151<<<<<<<<<<<<<<<0\n"
        )
        result = parse_passeport(mrz)
        assert result["type_document"] == "Passeport"
        assert result["nom"] == "DUPONT"
        assert result["prenom"] == "JEAN"

    def test_fallback_regex(self):
        """Test sans MRZ, avec du texte classique."""
        text = "Nom : BERNARD\nPrenom : Pierre\nDate de naissance : 01/12/1988"
        result = parse_passeport(text)
        assert result["nom"] == "BERNARD"
        assert result["prenom"] == "Pierre"
        assert result["date_naissance"] == "01/12/1988"

    def test_champs_vides(self):
        result = parse_passeport("")
        assert result["nom"] is None
        assert result["prenom"] is None


class TestParseCertificat:
    def test_extraction_civilite(self):
        text = "Certifie que M. MOREAU Lucas est inscrit pour 2024-2025"
        result = parse_certificat_scolarite(text)
        assert result["nom"] == "MOREAU"
        assert result["prenom"] == "Lucas"

    def test_annee_universitaire(self):
        text = "Annee universitaire 2024-2025\nM. PETIT Marie"
        result = parse_certificat_scolarite(text)
        assert result["annee_universitaire"] == "2024-2025"

    def test_annee_avec_slash(self):
        text = "Annee 2023/2024\nNom : DUPONT"
        result = parse_certificat_scolarite(text)
        assert result["annee_universitaire"] == "2023-2024"

    def test_etablissement(self):
        text = "M. DUPONT Jean\nUniversite Paris 8"
        result = parse_certificat_scolarite(text)
        assert result["etablissement"] is not None
        assert "Paris 8" in result["etablissement"]
