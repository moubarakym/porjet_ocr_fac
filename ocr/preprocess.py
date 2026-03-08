"""
Module de pretraitement d'images pour ameliorer la qualite de l'OCR.
Applique des transformations basiques : niveaux de gris, seuillage, debruitage.
"""

import cv2
import numpy as np


def preprocess_image(image_path):
    """
    Charge et pretraite une image pour l'OCR.
    Retourne l'image pretraitee (numpy array).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Impossible de charger l'image : {image_path}")

    # Conversion en niveaux de gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Debruitage
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Seuillage adaptatif (meilleur que le seuillage global pour les documents)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    return binary


def preprocess_image_from_array(img_array):
    """
    Pretraite une image deja chargee en memoire (numpy array BGR).
    """
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return binary
