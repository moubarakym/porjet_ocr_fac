"""
Tests unitaires pour le module de pretraitement d'images (ocr/preprocess.py).

Ces tests travaillent sur des images synthetiques (bandes sombres simulant des
lignes de texte) pour verifier la geometrie du redressement (_deskew)
independamment de Tesseract : pas besoin d'OCR reel pour valider que
l'inclinaison detectee est bien corrigee, et non amplifiee.
"""

import cv2
import numpy as np
import pytest

from ocr.preprocess import _deskew, _resize_if_small, TARGET_MIN_DIMENSION


def _make_text_like_image(angle_deg=0.0, size=(600, 900)):
    """
    Construit une image avec plusieurs bandes horizontales sombres sur fond
    clair (simulant des lignes de texte regulierement espacees), puis la
    fait tourner de angle_deg. Sert a tester _deskew sans dependre de
    Tesseract.
    """
    h, w = size
    img = np.full((h, w), 255, dtype=np.uint8)
    for y in range(80, h - 80, 60):
        cv2.rectangle(img, (60, y), (w - 60, y + 20), 0, thickness=-1)

    if angle_deg != 0:
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
        img = cv2.warpAffine(img, matrix, (w, h), borderValue=255)

    return img


def _measure_skew_angle(gray):
    """Re-mesure l'angle d'inclinaison residuel (meme methode que _deskew).
    Le modulo 90 rend la mesure independante de la convention de signe
    utilisee par cv2.minAreaRect selon la version d'OpenCV installee (voir
    le commentaire de _deskew dans ocr/preprocess.py)."""
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1] % 90
    if angle > 45:
        angle = angle - 90
    return angle


class TestDeskew:
    def test_image_droite_quasi_inchangee(self):
        """Une image deja droite ne doit pas se retrouver fortement tournee."""
        img = _make_text_like_image(angle_deg=0.0)
        corrected = _deskew(img)
        angle = _measure_skew_angle(corrected)
        assert abs(angle) < 1.0

    def test_inclinaison_positive_corrigee_dans_le_bon_sens(self):
        """
        Regression : _deskew doit REDUIRE l'inclinaison detectee, pas la
        doubler. Bug precedemment present : cv2.getRotationMatrix2D etait
        appele avec +angle au lieu de -angle, ce qui tournait l'image une
        seconde fois dans le meme sens (8 degres -> 16 degres residuels)
        au lieu de la redresser (8 degres -> ~0 degre residuel).
        """
        img = _make_text_like_image(angle_deg=8.0)
        angle_avant = _measure_skew_angle(img)
        assert abs(angle_avant - 8.0) < 1.0  # sanity check sur l'image de test

        corrected = _deskew(img)
        angle_apres = _measure_skew_angle(corrected)
        assert abs(angle_apres) < 2.0, (
            f"angle residuel trop grand ({angle_apres:.1f} degres) : la correction "
            "semble avoir amplifie l'inclinaison au lieu de l'annuler"
        )

    def test_inclinaison_negative_corrigee(self):
        img = _make_text_like_image(angle_deg=-6.0)
        corrected = _deskew(img)
        angle_apres = _measure_skew_angle(corrected)
        assert abs(angle_apres) < 2.0

    def test_image_peu_de_contenu_non_modifiee(self):
        """Si trop peu de pixels sombres pour estimer un angle fiable, on
        renvoie l'image telle quelle plutot que de risquer une rotation
        aleatoire."""
        img = np.full((200, 200), 255, dtype=np.uint8)
        result = _deskew(img)
        assert np.array_equal(result, img)


class TestResizeIfSmall:
    def test_image_trop_petite_est_agrandie(self):
        img = np.zeros((100, 150), dtype=np.uint8)
        resized = _resize_if_small(img)
        assert min(resized.shape[:2]) > min(img.shape[:2])

    def test_image_assez_grande_non_modifiee(self):
        img = np.zeros((1500, 2000), dtype=np.uint8)
        resized = _resize_if_small(img)
        assert resized.shape == img.shape
