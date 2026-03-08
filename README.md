# OCR - Extraction et Verification de Documents d'Identite

Projet M1 Big Data - Universite Paris 8

Application d'extraction automatique de donnees depuis des pieces d'identite (CNI, Passeport, Certificat de scolarite) via OCR, avec comparaison aux donnees d'une base de reference pour detecter les incoherences.

## Structure du projet

```
projet_innov/
├── app.py                  # Interface Streamlit (point d'entree)
├── ocr/
│   ├── preprocess.py       # Pretraitement d'images (niveaux de gris, seuillage)
│   └── extractor.py        # Extraction OCR + parsing par type de document
├── comparator/
│   └── compare.py          # Comparaison avec la base de reference
├── data/
│   ├── reference.xlsx      # Donnees de reference (fictives)
│   ├── create_reference.py # Script de generation des donnees
│   └── samples/            # Images de test
├── tests/
│   ├── test_extractor.py   # Tests du module OCR
│   └── test_compare.py     # Tests du module de comparaison
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Technologies utilisees

- **Python 3.12**
- **Tesseract OCR** (via pytesseract) : moteur OCR open source
- **OpenCV** : pretraitement d'images
- **pandas** : manipulation des donnees de reference (Excel)
- **rapidfuzz** : comparaison floue de chaines (tolerance aux erreurs OCR)
- **Streamlit** : interface web
- **Docker** : conteneurisation
- **PyTest** : tests unitaires

## Installation et lancement

### Option 1 : Avec Docker (recommande)

```bash
docker-compose up --build
```

L'application sera accessible sur http://localhost:8501

### Option 2 : En local

1. Installer Tesseract OCR :

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-fra
```

2. Installer les dependances Python :

```bash
pip install -r requirements.txt
```

3. Generer les donnees de reference :

```bash
python3 data/create_reference.py
```

4. Lancer l'application :

```bash
streamlit run app.py
```

## Utilisation

1. Ouvrir l'application dans le navigateur (http://localhost:8501)
2. Choisir le type de document dans la barre laterale (CNI, Passeport, Certificat)
3. Uploader une image du document
4. L'application extrait automatiquement les donnees via OCR
5. Les donnees sont comparees avec la base de reference
6. Les incoherences sont affichees en rouge

## Lancer les tests

```bash
python3 -m pytest tests/ -v
```

## Types de documents supportes

| Document | Champs extraits |
|---|---|
| CNI | Nom, Prenom, Date de naissance, Numero, Sexe |
| Passeport | Nom, Prenom, Date de naissance, Numero, Nationalite (MRZ) |
| Certificat de scolarite | Nom, Prenom, Annee universitaire, Etablissement |
