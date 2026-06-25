# Specifications Techniques

## Architecture logicielle

L'application suit une architecture en **couches** (layered architecture) simple :

```
┌─────────────────────────────────────┐
│        Interface (Streamlit)        │  ← Couche Presentation
│         app.py                      │
├─────────────────────────────────────┤
│        Logique metier               │  ← Couche Metier
│   ocr/extractor.py                  │
│   comparator/compare.py             │
├─────────────────────────────────────┤
│        Traitement d'images          │  ← Couche Traitement
│   ocr/preprocess.py                 │
├─────────────────────────────────────┤
│        Donnees                      │  ← Couche Donnees
│   data/reference.xlsx               │
│   (fichier Excel via pandas)        │
└─────────────────────────────────────┘
```

Le flux de donnees est unidirectionnel :
**Image** → **Pretraitement** → **OCR** → **Parsing** → **Comparaison** → **Affichage**

## Choix technologiques et justifications

### Langage : Python 3.12

- Langage de reference pour le traitement de donnees et le machine learning.
- Ecosysteme riche en bibliotheques OCR et data science.
- Facilite de prototypage rapide.

### OCR : Tesseract (via pytesseract)

- Moteur OCR open source le plus utilise, maintenu par Google.
- Supporte plus de 100 langues dont le francais.
- Gratuit, contrairement aux API cloud (Google Vision, AWS Textract).
- **Limite** : moins precis que les solutions cloud sur les documents complexes, mais suffisant pour notre cas d'usage.

### Pretraitement d'images : OpenCV

- Bibliotheque standard pour le traitement d'images en Python.
- Permet d'ameliorer la qualite de l'image avant OCR (debruitage, seuillage).
- Bien documentee et largement utilisee dans l'industrie.

### Manipulation de donnees : pandas + openpyxl

- pandas est le standard pour la manipulation de donnees tabulaires en Python.
- openpyxl permet la lecture/ecriture de fichiers Excel (.xlsx).
- Choix d'Excel comme format de reference car c'est le format le plus courant en entreprise.

### Comparaison floue : rapidfuzz

- Bibliotheque de fuzzy matching rapide (implementee en C++).
- Permet de tolerer les erreurs OCR legeres (caractere mal reconnu, espace en trop).
- Utilise la distance de Levenshtein normalisee pour calculer un score de similarite.

### Interface : Streamlit

- Framework Python pour creer des interfaces web rapidement.
- Pas besoin de connaitre HTML/CSS/JavaScript.
- Ideal pour les projets data science et prototypes.
- Rechargement automatique du code en developpement.

### Conteneurisation : Docker

- Garantit que l'application fonctionne de la meme maniere partout.
- Simplifie l'installation (Tesseract, dependances systeme, Python).
- Docker Compose pour orchestrer le service.

### Tests : PyTest

- Framework de test le plus populaire en Python.
- Syntaxe simple et claire.
- Decouverte automatique des tests.

## Tableau recapitulatif

| Composant | Technologie | Justification |
|---|---|---|
| Langage | Python 3.12 | Standard data science, ecosysteme riche |
| OCR | Tesseract 5 | Open source, multilingue, gratuit |
| Pretraitement | OpenCV | Standard traitement d'images |
| Donnees | pandas + Excel | Format universel, simple a manipuler |
| Matching flou | rapidfuzz | Rapide, tolerance aux erreurs OCR |
| Interface | Streamlit | Prototypage rapide, pas de frontend |
| Conteneurisation | Docker | Reproductibilite, installation simplifiee |
| Tests | PyTest | Standard Python, syntaxe claire |

## Dependances du projet

Fichier `requirements.txt` :
```
pytesseract==0.3.10
opencv-python-headless==4.9.0.80
Pillow==10.2.0
pandas==2.2.0
openpyxl==3.1.2
rapidfuzz==3.6.1
streamlit==1.31.0
pytest==8.0.0
```
