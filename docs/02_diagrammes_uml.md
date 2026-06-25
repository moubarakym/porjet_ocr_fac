# Diagrammes UML

## 1. Diagramme de Cas d'Utilisation

```
┌─────────────────────────────────────────────────────────┐
│                  Systeme OCR                            │
│                                                         │
│  ┌──────────────────────┐                               │
│  │ Uploader un document │◄──────────┐                   │
│  └──────────────────────┘           │                   │
│              │                      │                   │
│              ▼                      │                   │
│  ┌──────────────────────────┐       │                   │
│  │ Selectionner le type     │       │                   │
│  │ de document              │       │                   │
│  └──────────────────────────┘       │                   │
│              │                 ┌────┴─────┐             │
│              ▼                 │Utilisateur│             │
│  ┌──────────────────────────┐ └────┬─────┘             │
│  │ Visualiser les donnees   │      │                    │
│  │ extraites                │◄─────┘                    │
│  └──────────────────────────┘      │                    │
│              │                     │                    │
│              ▼                     │                    │
│  ┌──────────────────────────┐      │                    │
│  │ Consulter les resultats  │◄─────┘                    │
│  │ de comparaison           │                           │
│  └──────────────────────────┘      │                    │
│                                    │                    │
│  ┌──────────────────────────┐      │                    │
│  │ Charger un fichier de    │◄─────┘                    │
│  │ reference personnalise   │                           │
│  └──────────────────────────┘                           │
└─────────────────────────────────────────────────────────┘
```

### Description des cas d'utilisation

| Cas d'utilisation | Acteur | Description |
|---|---|---|
| Uploader un document | Utilisateur | Charger une image (PNG, JPG) d'un document d'identite |
| Selectionner le type de document | Utilisateur | Choisir entre CNI, Passeport, Certificat de scolarite |
| Visualiser les donnees extraites | Utilisateur | Voir les champs detectes par l'OCR et le texte brut |
| Consulter les resultats de comparaison | Utilisateur | Voir le score de coherence et les incoherences |
| Charger un fichier de reference | Utilisateur | Optionnel : remplacer le fichier Excel par defaut |

---

## 2. Diagramme de Classes

```
┌─────────────────────────┐     ┌──────────────────────────┐
│      ImagePreprocessor  │     │      OCRExtractor         │
├─────────────────────────┤     ├──────────────────────────┤
│ - image_path: str       │     │ - raw_text: str          │
├─────────────────────────┤     ├──────────────────────────┤
│ + preprocess_image()    │────>│ + extract_text()         │
│ + preprocess_from_array()│    │ + extract_document()     │
└─────────────────────────┘     │ + parse_cni()            │
                                │ + parse_passeport()      │
                                │ + parse_certificat()     │
                                └──────────┬───────────────┘
                                           │
                                           │ donnees extraites
                                           ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│   ReferenceData         │     │     Comparator           │
├─────────────────────────┤     ├──────────────────────────┤
│ - excel_path: str       │     │ - extracted: dict        │
│ - dataframe: DataFrame  │     │ - reference: dict        │
├─────────────────────────┤     ├──────────────────────────┤
│ + load_reference_data() │────>│ + compare_fields()       │
└─────────────────────────┘     │ + find_matching_record() │
                                │ + compare_document()     │
                                │ + normalize()            │
                                └──────────┬───────────────┘
                                           │
                                           │ resultats
                                           ▼
                                ┌──────────────────────────┐
                                │  StreamlitApp (app.py)   │
                                ├──────────────────────────┤
                                │ - doc_type: str          │
                                │ - ref_path: str          │
                                ├──────────────────────────┤
                                │ + upload_document()      │
                                │ + display_results()      │
                                │ + display_incoherences() │
                                └──────────────────────────┘
```

### Relations entre classes

| Classe | Responsabilite |
|---|---|
| ImagePreprocessor | Charger et pretraiter les images (niveaux de gris, seuillage, debruitage) |
| OCRExtractor | Extraire le texte via Tesseract puis parser les champs selon le type de document |
| ReferenceData | Charger et fournir les donnees de reference depuis un fichier Excel |
| Comparator | Comparer les donnees OCR avec la reference, calculer les scores, detecter les incoherences |
| StreamlitApp | Interface web : gestion de l'upload, affichage des resultats |

---

## 3. Diagramme d'Activites

```
        ┌─────────┐
        │  Debut  │
        └────┬────┘
             │
             ▼
   ┌─────────────────────┐
   │ Utilisateur uploade  │
   │ une image            │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Utilisateur choisit  │
   │ le type de document  │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Pretraitement de     │
   │ l'image (OpenCV)     │
   │ - Niveaux de gris    │
   │ - Debruitage         │
   │ - Seuillage adaptatif│
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Extraction du texte  │
   │ brut (Tesseract)     │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Parsing des champs   │
   │ (regex selon type)   │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Affichage des champs │
   │ extraits             │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Chargement de la     │
   │ base de reference    │
   └─────────┬───────────┘
             │
             ▼
   ┌─────────────────────┐
   │ Recherche de la      │
   │ personne (matching)  │
   └─────────┬───────────┘
             │
        ┌────┴────┐
        │ Trouve? │
        └────┬────┘
        Oui  │   Non
     ┌───────┤    │
     ▼       │    ▼
┌──────────┐ │ ┌──────────────────┐
│Comparaison│ │ │ Message: aucune  │
│champ par  │ │ │ correspondance   │
│champ      │ │ └──────────────────┘
└─────┬────┘ │
      │      │
      ▼      │
┌──────────┐ │
│ Calcul   │ │
│ score +  │ │
│ detection│ │
│ incoher. │ │
└─────┬────┘ │
      │      │
      ▼      │
┌──────────┐ │
│ Affichage│ │
│ resultats│ │
└─────┬────┘ │
      │      │
      ▼      │
   ┌─────────┐
   │   Fin   │
   └─────────┘
```
