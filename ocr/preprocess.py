"""
Module de pretraitement d'images pour ameliorer la qualite de l'OCR.

Pipeline applique :
1. Mise a l'echelle (les photos trop petites/basse resolution sont agrandies,
   Tesseract est nettement moins fiable en dessous d'une certaine taille de
   caracteres).
2. Redressement automatique (deskew) : corrige les photos prises legerement
   de travers, frequentes quand le document est photographie a la main.
3. Amelioration du contraste (CLAHE) : aide sur les photos avec un eclairage
   inegal ou un contraste faible (ombres, reflets).
4. Debruitage puis seuillage pour obtenir une image nette en noir et blanc.

`preprocess_variants*` genere plusieurs versions pretraitees de la meme
image (seuillage adaptatif, seuillage d'Otsu, niveaux de gris simples) car
selon la qualite du document, l'une ou l'autre donne un bien meilleur
resultat OCR. Le module ocr.extractor essaie ces variantes et garde celle
qui produit le texte le plus fiable, au lieu de se reposer sur un seul
pretraitement fixe qui echoue parfois silencieusement.
"""

import cv2
import numpy as np

# Dimension minimale (plus petit cote) visee avant OCR. En dessous, Tesseract
# perd beaucoup en fiabilite car les caracteres deviennent trop petits.
TARGET_MIN_DIMENSION = 1200
MAX_UPSCALE_FACTOR = 3.0


def _load_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Impossible de charger l'image : {image_path}")
    return img


def _to_gray(img_array):
    """Convertit en niveaux de gris si besoin (gere les images deja en gris)."""
    if img_array.ndim == 2:
        return img_array
    return cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)


def _resize_if_small(gray):
    """Agrandit l'image si elle est trop petite pour un OCR fiable (ne la
    retrecit jamais : retrecir perdrait de l'information utile)."""
    h, w = gray.shape[:2]
    smallest_side = min(h, w)
    if smallest_side <= 0 or smallest_side >= TARGET_MIN_DIMENSION:
        return gray
    factor = min(TARGET_MIN_DIMENSION / smallest_side, MAX_UPSCALE_FACTOR)
    if factor <= 1.01:
        return gray
    return cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def _deskew(gray):
    """
    Detecte et corrige une legere inclinaison de l'image (photo prise de
    travers) en se basant sur l'orientation du contour englobant des pixels
    de texte/contenu sombre.
    """
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return gray  # Pas assez de pixels pour estimer un angle fiable

    raw_angle = cv2.minAreaRect(coords)[-1]
    # cv2.minAreaRect a change de convention d'angle plusieurs fois selon les
    # versions d'OpenCV (par ex. [0, 90) depuis la 4.5, mais de nouveau
    # (-90, 0] avec la 5.0 testee en aout 2026 -- voir memoire, chapitre 4).
    # Plutot que de coder en dur une hypothese liee a une version precise
    # (fragile : elle s'est deja cassee une fois), on se base sur le fait
    # que ces conventions ne different que d'un multiple de 90 degres : le
    # modulo 90 retombe donc sur l'inclinaison reelle quelle que soit la
    # convention utilisee par la version d'OpenCV installee (verifie
    # empiriquement sur les versions 4.9 et 5.0 : 84°/-6° et -82°/-6°
    # donnent tous les deux 8° apres ce calcul pour une image inclinee de
    # 8°). On ramene ensuite ce resultat dans (-45, 45] pour obtenir
    # l'inclinaison signee reelle.
    angle = raw_angle % 90
    if angle > 45:
        angle = angle - 90

    # On ne corrige que les inclinaisons "raisonnables" (photo de travers).
    # Au-dela, l'angle detecte est probablement faux (mise en page complexe,
    # photo/texte multiples) et une rotation forcee ferait plus de mal que de bien.
    if abs(angle) < 0.3 or abs(angle) > 20:
        return gray

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    # cv2.minAreaRect renvoie l'angle d'inclinaison du contenu DANS le meme
    # sens que celui utilise par cv2.getRotationMatrix2D : pour corriger
    # (annuler) cette inclinaison il faut donc tourner de -angle, sinon on
    # tourne deux fois dans le meme sens et on double l'inclinaison au lieu
    # de la supprimer (verifie empiriquement : avec +angle, une photo
    # inclinee de 8° devient totalement illisible pour l'OCR ; avec -angle,
    # elle redevient droite).
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _enhance_contrast(gray):
    """CLAHE (egalisation d'histogramme adaptative) : ameliore le contraste
    localement, utile sur les photos avec ombres/eclairage inegal."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _denoise(gray):
    return cv2.fastNlMeansDenoising(gray, h=10)


def _adaptive_binarize(gray):
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 10
    )


def _otsu_binarize(gray):
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _common_pipeline(img_array):
    """Etapes communes a toutes les variantes : niveaux de gris, mise a
    l'echelle, redressement, contraste, debruitage."""
    gray = _to_gray(img_array)
    gray = _resize_if_small(gray)
    gray = _deskew(gray)
    gray = _enhance_contrast(gray)
    gray = _denoise(gray)
    return gray


def preprocess_image(image_path):
    """
    Charge et pretraite une image pour l'OCR (pipeline par defaut :
    mise a l'echelle + redressement + contraste + debruitage + seuillage
    adaptatif). Retourne l'image pretraitee (numpy array).

    Conservee pour compatibilite : utiliser preprocess_variants() permet
    d'obtenir plusieurs variantes et generalement un meilleur resultat.
    """
    img = _load_image(image_path)
    gray = _common_pipeline(img)
    return _adaptive_binarize(gray)


def preprocess_image_from_array(img_array):
    """Pretraite une image deja chargee en memoire (numpy array BGR ou gris)."""
    gray = _common_pipeline(img_array)
    return _adaptive_binarize(gray)


def _color_channel_variants(img_array):
    """
    Isole chaque canal de couleur (bleu, vert, rouge) d'une image couleur.

    Beaucoup de documents d'identite (titres de sejour, certaines CNI)
    impregnent un motif de securite decoratif (guillochage, filigrane) dans
    une couleur specifique en arriere-plan du texte. La conversion en gris
    standard (moyenne ponderee des 3 canaux) melange ce motif au texte et
    degrade fortement l'OCR. En isolant un seul canal, le texte (sombre sur
    les 3 canaux) ressort souvent bien plus net des lors que le motif de
    fond est domine par une couleur complementaire a ce canal.

    Retourne un dict vide si l'image est deja en niveaux de gris.
    """
    if img_array.ndim < 3:
        return {}
    b, g, r = cv2.split(img_array)
    return {"canal_bleu": b, "canal_vert": g, "canal_rouge": r}


def preprocess_variants_from_array(img_array):
    """
    Genere plusieurs variantes pretraitees de la meme image. Selon la
    qualite du document (photo floue, scan net, eclairage inegal, fond de
    securite colore...), une variante peut donner un bien meilleur resultat
    OCR qu'une autre.

    Returns:
        dict {nom_variante: image numpy} ; les variantes "adaptive"/"otsu"/
        "gris" partagent le meme redressement/contraste/debruitage (seul le
        seuillage final differe), les variantes "canal_*" repetent tout le
        pipeline a partir d'un seul canal de couleur isole (utile sur les
        fonds guilloches/colores, cf. _color_channel_variants).
    """
    gray = _common_pipeline(img_array)
    variants = {
        "adaptive": _adaptive_binarize(gray),
        "otsu": _otsu_binarize(gray),
        "gris": gray,  # Parfois Tesseract se debrouille mieux sans binarisation
    }

    for name, channel in _color_channel_variants(img_array).items():
        channel_gray = _common_pipeline(channel)
        variants[name] = channel_gray
        variants[f"{name}_otsu"] = _otsu_binarize(channel_gray)

    return variants


def preprocess_variants(image_path):
    """Comme preprocess_variants_from_array, a partir d'un chemin de fichier."""
    img = _load_image(image_path)
    return preprocess_variants_from_array(img)
