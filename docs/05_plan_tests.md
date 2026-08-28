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
| TU-26 | compare | normalize() | Insensibilite aux accents (Helene/Hélène) |
| TU-27 | compare | normalize() | Uniformisation des separateurs de date (./- vs /) |
| TU-28 | compare | normalize() | Accents et separateurs combines |
| TU-29 | compare | find_matching_record() | Desambiguation par prenom (deux personnes au meme nom) |
| TU-30 | compare | find_matching_record() | Match ponderee robuste a une erreur OCR sur un seul champ |
| TU-31 | extractor | _ocr_with_confidence() | Timeout Tesseract gere proprement (pas d'exception propagee) |
| TU-32 | extractor | _ocr_with_confidence() | Erreur Tesseract generique geree proprement |
| TU-33 | preprocess | _deskew() | Image deja droite quasi inchangee |
| TU-34 | preprocess | _deskew() | Inclinaison positive correctement annulee (non doublee) |
| TU-35 | preprocess | _deskew() | Inclinaison negative correctement annulee |
| TU-36 | preprocess | _deskew() | Image avec trop peu de contenu laissee inchangee |
| TU-37 | preprocess | _resize_if_small() | Image trop petite agrandie |
| TU-38 | preprocess | _resize_if_small() | Image assez grande non modifiee |

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
tests/test_compare.py::TestNormalize::test_accents PASSED
tests/test_compare.py::TestNormalize::test_separateurs_date_uniformises PASSED
tests/test_compare.py::TestNormalize::test_accents_et_dates_combines PASSED
tests/test_compare.py::TestCompareFields::test_champs_identiques PASSED
tests/test_compare.py::TestCompareFields::test_champs_differents PASSED
tests/test_compare.py::TestCompareFields::test_champ_similaire PASSED
tests/test_compare.py::TestCompareFields::test_champ_manquant_ocr PASSED
tests/test_compare.py::TestFindMatchingRecord::test_match_exact PASSED
tests/test_compare.py::TestFindMatchingRecord::test_match_approximate PASSED
tests/test_compare.py::TestFindMatchingRecord::test_no_match PASSED
tests/test_compare.py::TestFindMatchingRecord::test_disambiguation_par_prenom PASSED
tests/test_compare.py::TestFindMatchingRecord::test_match_robuste_a_une_erreur_ocr_sur_un_seul_champ PASSED
tests/test_compare.py::TestCompareDocument::test_comparaison_coherente PASSED
tests/test_compare.py::TestCompareDocument::test_comparaison_incoherente PASSED
tests/test_compare.py::TestCompareDocument::test_aucune_correspondance PASSED
tests/test_extractor.py::TestOcrTimeout::test_timeout_renvoie_resultat_vide PASSED
tests/test_extractor.py::TestOcrTimeout::test_erreur_tesseract_renvoie_resultat_vide PASSED
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
tests/test_preprocess.py::TestDeskew::test_image_droite_quasi_inchangee PASSED
tests/test_preprocess.py::TestDeskew::test_inclinaison_positive_corrigee_dans_le_bon_sens PASSED
tests/test_preprocess.py::TestDeskew::test_inclinaison_negative_corrigee PASSED
tests/test_preprocess.py::TestDeskew::test_image_peu_de_contenu_non_modifiee PASSED
tests/test_preprocess.py::TestResizeIfSmall::test_image_trop_petite_est_agrandie PASSED
tests/test_preprocess.py::TestResizeIfSmall::test_image_assez_grande_non_modifiee PASSED

======================== 41 passed in 0.56s ========================
```

### Tableau recapitulatif

| Type de test | Nombre | Passes | Echecs | Taux de reussite |
|---|---|---|---|---|
| Tests unitaires (parsing) | 14 | 14 | 0 | 100% |
| Tests unitaires (comparaison) | 16 | 16 | 0 | 100% |
| Tests unitaires (OCR/timeout) | 2 | 2 | 0 | 100% |
| Tests unitaires (pretraitement) | 6 | 6 | 0 | 100% |
| Tests d'integration | 3 | 3 | 0 | 100% |
| **Total** | **41** | **41** | **0** | **100%** |

### Analyse

- **Parsing CNI** : les expressions regulieres detectent correctement les champs dans les formats courants. Les formats de date avec points et slashs sont supportes.
- **Parsing Passeport** : la lecture MRZ fonctionne sur les zones bien formatees. Le fallback regex prend le relais si la MRZ n'est pas lisible.
- **Parsing Certificat** : la detection fonctionne avec les formats "M./Mme NOM Prenom" et les formats classiques.
- **Comparaison** : le matching flou (rapidfuzz) permet de tolerer les erreurs OCR legeres tout en detectant les vraies incoherences. La normalisation insensible aux accents/separateurs et le matching multi-champs pondere (nom + prenom) reduisent les faux negatifs/positifs lors de la recherche dans la base de reference.
- **Robustesse OCR** : un timeout (20s) sur chaque appel Tesseract empeche le pipeline de bloquer indefiniment sur une image trop degradee (bruit important) ; testee par simulation (monkeypatch) de l'erreur levee par pytesseract.
- **Pretraitement (deskew)** : la correction d'inclinaison est testee geometriquement (sans Tesseract) pour garantir qu'elle reduit bien l'angle detecte au lieu de l'amplifier, dans les deux sens de rotation.

---

## Benchmark de precision (avant / apres ameliorations)

### Methodologie

Un jeu de 3 documents synthetiques (2 CNI, 1 certificat de scolarite, texte et champs connus a l'avance) est genere puis degrade selon 7 profils : `clean` (aucune degradation), `rotated` (rotation de 8°), `blur` (flou gaussien), `noise` (bruit gaussien fort), `lowres` (perte de resolution puis upscale), `low_contrast` (contraste reduit), `combined` (rotation + basse resolution + flou + bruit cumules). Cela donne 21 images de test avec verite terrain connue (nom, prenom, date de naissance, numero, etc.), soit 91 champs a verifier au total.

Chaque champ extrait est compare a la valeur attendue via un score de similarite flou (rapidfuzz, seuil 85%), ce qui tolere les variations mineures de casse/ponctuation sans masquer les vraies erreurs.

La version "avant" correspond au pipeline tel qu'il existait avant ce travail d'amelioration (pretraitement simple, OCR mono-configuration, comparaison basique). La version "apres" integre l'ensemble des modifications decrites dans ce document (pretraitement multi-variantes + deskew corrige, OCR multi-configurations avec score de confiance et timeout, comparaison ponderee insensible aux accents).

### Resultats globaux

| Version | Champs corrects | Precision globale |
|---|---|---|
| Avant | 52 / 91 | 57.1% |
| Apres | 72 / 91 | **79.1%** |
| **Gain** | | **+22.0 points** |

### Detail par type de degradation

| Degradation | Avant | Apres |
|---|---|---|
| clean (aucune) | 84.6% | 84.6% |
| rotated (rotation 8°) | 23.1% | 69.2% |
| blur (flou) | 84.6% | 84.6% |
| noise (bruit fort) | 0.0% | 84.6% |
| lowres (basse resolution) | 84.6% | 76.9% |
| low_contrast (contraste faible) | 84.6% | 84.6% |
| combined (cumul) | 38.5% | 69.2% |

### Analyse du benchmark

- **noise** : le gain le plus spectaculaire (0% -> 84.6%). Sans pretraitement adapte, l'OCR ne reconnaissait quasiment aucun champ sur les images bruitees ; le debruitage (CLAHE + `fastNlMeansDenoising`) combine au choix multi-variantes corrige cela presque entierement. C'est aussi cette image-la qui a revele le bug de timeout Tesseract (voir docs/06).
- **rotated / combined** : forte amelioration (23.1% -> 69.2% et 38.5% -> 69.2%) grace a la correction du redressement automatique. Un bug de signe faisait jusqu'ici **doubler** l'inclinaison au lieu de l'annuler (corrige dans `ocr/preprocess.py::_deskew`, voir docs/06) ; un second bug lie a un changement de convention d'angle dans OpenCV >= 4.5 empechait aussi la correction des inclinaisons negatives (egalement corrige).
- **lowres** : leger recul (84.6% -> 76.9%, soit 1 champ sur 13). Cas residuel ou l'agrandissement ne suffit pas a recuperer un detail deja detruit par la sous-resolution (numero de carte tronque, nom non detecte). Limite connue, documentee dans docs/06.
- **clean / blur / low_contrast** : stables, le pipeline ameliore ne degrade pas les cas deja bien geres.

### Limite de couverture : le titre de sejour

Ce plan de tests (tests automatises et benchmark chiffre ci-dessus) a ete etabli avant
l'ajout du titre de sejour comme 4e type de document. Ni les 41 tests, ni les 21 images
du benchmark ne couvrent ce type de document, ni les 5 defauts d'analyse textuelle
identifies lors de son ajout (ordre de lecture, fond de securite, collision de champs,
format de carte 2021, lecture MRZ). Sa validation a ete faite manuellement sur des
documents reels, comme detaille dans docs/06_bilan_conformite.md et le memoire
(chapitre 4, section "Tentatives infructueuses et corrections"). Etendre le benchmark
et les tests automatises a ce 4e type de document est identifie comme piste
d'amelioration.
