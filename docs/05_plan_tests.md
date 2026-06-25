# Plan de Tests et Rapport de Tests

## Plan de tests

### Tests unitaires

Testent les fonctions individuellement, avec des donnees simulees (pas besoin d'images reelles).

| ID | Module | Fonction testee | Description |
|---|---|---|---|
| TU-01 | extractor | parse_cni() | Extraction du nom depuis un texte CNI |
| TU-02 | extractor | parse_cni() | Extraction du prenom |
| TU-03 | extractor | parse_cni() | Extraction de la date de naissance |
| TU-04 | extractor | parse_cni() | Extraction du numero de carte |
| TU-05 | extractor | parse_cni() | Gestion des champs manquants |
| TU-06 | extractor | parse_cni() | Verification du type de document |
| TU-07 | extractor | parse_cni() | Date avec format points (JJ.MM.AAAA) |
| TU-08 | extractor | parse_passeport() | Parsing d'une zone MRZ |
| TU-09 | extractor | parse_passeport() | Fallback regex sans MRZ |
| TU-10 | extractor | parse_passeport() | Gestion texte vide |
| TU-11 | extractor | parse_certificat() | Extraction nom/prenom avec civilite |
| TU-12 | extractor | parse_certificat() | Extraction annee universitaire (tiret) |
| TU-13 | extractor | parse_certificat() | Extraction annee universitaire (slash) |
| TU-14 | extractor | parse_certificat() | Extraction de l'etablissement |
| TU-15 | compare | normalize() | Mise en minuscules |
| TU-16 | compare | normalize() | Suppression des espaces |
| TU-17 | compare | normalize() | Gestion de None |
| TU-18 | compare | normalize() | Gestion des nombres |
| TU-19 | compare | compare_fields() | Champs identiques (score 100) |
| TU-20 | compare | compare_fields() | Champs differents (score < 80) |
| TU-21 | compare | compare_fields() | Champs similaires (erreur legere) |
| TU-22 | compare | compare_fields() | Champ manquant cote OCR |
| TU-23 | compare | find_matching_record() | Match exact dans le DataFrame |
| TU-24 | compare | find_matching_record() | Match approximatif (erreur OCR) |
| TU-25 | compare | find_matching_record() | Aucune correspondance |

### Tests d'integration

Testent le pipeline complet avec un fichier Excel reel.

| ID | Description |
|---|---|
| TI-01 | Comparaison document coherent (tous les champs correspondent) |
| TI-02 | Comparaison document incoherent (prenom et date differents) |
| TI-03 | Comparaison sans correspondance dans la base |

### Tests fonctionnels

Verification manuelle de l'interface Streamlit.

| ID | Scenario | Resultat attendu |
|---|---|---|
| TF-01 | Upload d'une image PNG valide | L'image s'affiche, l'extraction se lance |
| TF-02 | Upload d'un fichier non-image | Message d'erreur |
| TF-03 | Changement de type de document | Le parseur change en consequence |
| TF-04 | Upload d'un Excel personnalise | Les nouvelles donnees sont utilisees pour la comparaison |
| TF-05 | Document avec tous les champs corrects | Score 100%, message vert |
| TF-06 | Document avec incoherences | Incoherences listees en rouge |

---

## Rapport de tests

### Execution des tests unitaires et d'integration

```
$ python3 -m pytest tests/ -v

tests/test_compare.py::TestNormalize::test_minuscules PASSED
tests/test_compare.py::TestNormalize::test_espaces PASSED
tests/test_compare.py::TestNormalize::test_none PASSED
tests/test_compare.py::TestNormalize::test_nombre PASSED
tests/test_compare.py::TestCompareFields::test_champs_identiques PASSED
tests/test_compare.py::TestCompareFields::test_champs_differents PASSED
tests/test_compare.py::TestCompareFields::test_champ_similaire PASSED
tests/test_compare.py::TestCompareFields::test_champ_manquant_ocr PASSED
tests/test_compare.py::TestFindMatchingRecord::test_match_exact PASSED
tests/test_compare.py::TestFindMatchingRecord::test_match_approximate PASSED
tests/test_compare.py::TestFindMatchingRecord::test_no_match PASSED
tests/test_compare.py::TestCompareDocument::test_comparaison_coherente PASSED
tests/test_compare.py::TestCompareDocument::test_comparaison_incoherente PASSED
tests/test_compare.py::TestCompareDocument::test_aucune_correspondance PASSED
tests/test_extractor.py::TestParseCNI::test_extraction_nom PASSED
tests/test_extractor.py::TestParseCNI::test_extraction_prenom PASSED
tests/test_extractor.py::TestParseCNI::test_extraction_date_naissance PASSED
tests/test_extractor.py::TestParseCNI::test_extraction_numero PASSED
tests/test_extractor.py::TestParseCNI::test_champs_manquants PASSED
tests/test_extractor.py::TestParseCNI::test_type_document PASSED
tests/test_extractor.py::TestParseCNI::test_date_avec_points PASSED
tests/test_extractor.py::TestParsePasseport::test_mrz_parsing PASSED
tests/test_extractor.py::TestParsePasseport::test_fallback_regex PASSED
tests/test_extractor.py::TestParsePasseport::test_champs_vides PASSED
tests/test_extractor.py::TestParseCertificat::test_extraction_civilite PASSED
tests/test_extractor.py::TestParseCertificat::test_annee_universitaire PASSED
tests/test_extractor.py::TestParseCertificat::test_annee_avec_slash PASSED
tests/test_extractor.py::TestParseCertificat::test_etablissement PASSED

======================== 28 passed in 0.94s ========================
```

### Tableau recapitulatif

| Type de test | Nombre | Passes | Echecs | Taux de reussite |
|---|---|---|---|---|
| Tests unitaires (parsing) | 14 | 14 | 0 | 100% |
| Tests unitaires (comparaison) | 11 | 11 | 0 | 100% |
| Tests d'integration | 3 | 3 | 0 | 100% |
| **Total** | **28** | **28** | **0** | **100%** |

### Analyse

- **Parsing CNI** : les expressions regulieres detectent correctement les champs dans les formats courants. Les formats de date avec points et slashs sont supportes.
- **Parsing Passeport** : la lecture MRZ fonctionne sur les zones bien formatees. Le fallback regex prend le relais si la MRZ n'est pas lisible.
- **Parsing Certificat** : la detection fonctionne avec les formats "M./Mme NOM Prenom" et les formats classiques.
- **Comparaison** : le matching flou (rapidfuzz) permet de tolerer les erreurs OCR legeres tout en detectant les vraies incoherences.
