# Bilan de Conformite

## Correspondance besoins / realisation

| Besoin exprime | Specification | Realisation | Statut |
|---|---|---|---|
| Extraire les donnees d'un document numerise | US-3 : Extraction OCR | Module `ocr/extractor.py` avec Tesseract + regex | Conforme |
| Supporter CNI, Passeport, Certificat, Titre de sejour | US-2 : Selection du type | 4 parseurs dedies (parse_cni, parse_passeport, parse_certificat_scolarite, parse_titre_sejour) | Conforme |
| Comparer avec une base de reference | US-4 : Comparaison | Module `comparator/compare.py` avec matching flou | Conforme |
| Detecter les incoherences | US-5 : Detection incoherences | Score par champ + liste des incoherences | Conforme |
| Interface utilisateur simple | US-1, US-4 : Interface | Application Streamlit (app.py) | Conforme |
| Fonctionner dans Docker | Contrainte technique | Dockerfile + docker-compose.yml | Conforme |
| Supporter le francais | Contrainte technique | Tesseract avec pack langue `fra` | Conforme |
| Fichier de reference personnalise | US-6 : Upload Excel | Upload dans la sidebar Streamlit | Conforme |

## Correspondance avec les livrables attendus (PDF du projet)

| Livrable demande | Livre | Localisation |
|---|---|---|
| Application fonctionnelle (extraction + comparaison) | Oui | app.py, ocr/, comparator/ |
| Rapport detaillant les techniques OCR et gestion des incoherences | Oui | docs/04_specifications_techniques.md |
| Interface utilisateur | Oui | app.py (Streamlit) |
| Code source structure et heberge | Oui | Repo Git |
| README complet | Oui | README.md |

## Correspondance avec les consignes DNF2ED12 (Partie II)

| Consigne | Document | Localisation |
|---|---|---|
| Expression des besoins | Oui | docs/01_expression_besoins.md |
| Diagrammes UML (cas d'utilisation) | Oui | docs/02_diagrammes_uml.md |
| Diagramme de classes | Oui | docs/02_diagrammes_uml.md |
| Diagramme d'activites | Oui | docs/02_diagrammes_uml.md |
| Specifications fonctionnelles (User Stories) | Oui | docs/03_specifications_fonctionnelles.md |
| Specifications techniques | Oui | docs/04_specifications_techniques.md |
| Plan de tests | Oui | docs/05_plan_tests.md |
| Realisation des tests (PyTest) | Oui | tests/ (41 tests, 100% de reussite) |
| Rapport de tests avec resultats | Oui | docs/05_plan_tests.md |
| Validation finale | Oui | Ce document |

## Travail d'amelioration de la precision de la verification (juin 2026)

Le pipeline initial presentait une precision globale mesuree de seulement **57.1%** (52/91 champs corrects) sur un benchmark synthetique a degradations controlees (voir docs/05_plan_tests.md, section "Benchmark de precision"). Trois defauts caches ont ete identifies et corriges, portant la precision a **79.1%** (72/91), soit **+22.0 points** :

| # | Defaut identifie | Impact | Correction |
|---|---|---|---|
| 1 | Tesseract pouvait bloquer indefiniment sur une image tres degradee (bruit fort), gelant tout le pipeline | Champs de type `noise` a 0% de precision | Timeout de 20s (`OCR_TIMEOUT_SECONDS`) ajoute sur chaque appel Tesseract, avec gestion de l'erreur resultante (`ocr/extractor.py::_ocr_with_confidence`) |
| 2 | Bug de signe dans la correction d'inclinaison (`_deskew`) : la rotation de correction etait appliquee dans le meme sens que l'inclinaison detectee au lieu du sens inverse, ce qui **doublait** l'inclinaison plutot que de l'annuler | Documents tournes lus quasiment illisibles (23.1% de precision sur `rotated`) | `cv2.getRotationMatrix2D` appele avec `-angle` au lieu de `+angle` (`ocr/preprocess.py::_deskew`) |
| 3 | Convention d'angle de `cv2.minAreaRect` differente selon la version d'OpenCV : la version installee (4.9.0.80) renvoie l'angle dans `[0, 90)` et non `(-90, 0]` comme l'ancien code le supposait, si bien que les inclinaisons negatives (photo tournee dans l'autre sens) n'etaient jamais detectees ni corrigees | Sous-ensemble de cas d'inclinaison reelle jamais corrige (gap de robustesse non visible dans le benchmark, qui ne teste qu'une rotation positive) | Normalisation de l'angle mesure vers l'intervalle signe `(-45, 45]` avant application du filtre et de la correction |

Ces trois defauts confirment et detaillent la limite "Precision OCR" deja identifiee plus bas : ils n'etaient pas visibles a l'inspection du code seule et n'ont ete reveles que par la mise en place du benchmark a degradations controlees et de tests de regression geometriques dedies (`tests/test_preprocess.py`). La methodologie complete (jeu de donnees, degradations, resultats detailles par type de degradation) est documentee dans docs/05_plan_tests.md.

## Limites et axes d'amelioration

- **Precision OCR** : malgre les corrections ci-dessus, Tesseract reste perfectible sur les documents de tres mauvaise qualite. Le cas `lowres` (basse resolution) montre encore un leger recul (84.6% -> 76.9%) : l'agrandissement ne recupere pas toujours un detail deja detruit par la sous-resolution. Une correction de perspective (pour les photos prises avec un angle de prise de vue, par opposition a la simple rotation 2D deja corrigee) pourrait ameliorer encore les resultats.
- **Couverture du benchmark** : le jeu de test synthetique ne couvre qu'une rotation positive (8°) ; la correction des inclinaisons negatives (defaut #3 ci-dessus) est validee par test unitaire geometrique mais pas par le benchmark global, qui devrait etre etendu avec un cas de rotation negative.
- **Types de documents** : 4 types sont desormais supportes (CNI, Passeport, Certificat de scolarite, Titre de sejour). Le titre de sejour, ajoute apres la mise en place du benchmark chiffre, n'est valide que sur des documents reels et n'est pas encore couvert par le benchmark ni par les tests automatises (voir docs/05_plan_tests.md). L'ajout d'autres types (Carte Vitale, par exemple) necessiterait d'ecrire de nouveaux parseurs.
- **Base de donnees** : le fichier Excel pourrait etre remplace par une vraie base de donnees (SQLite ou PostgreSQL) pour gerer de plus grands volumes.
- **Securite** : les documents d'identite contiennent des donnees sensibles. En production, il faudrait chiffrer les donnees et ne pas stocker les images.

## Conclusion

Le projet repond a l'ensemble des besoins exprimes et des consignes du module DNF2ED12. Les 41 tests unitaires et d'integration passent a 100%. Un travail dedie d'amelioration de la precision a permis de faire passer la precision de verification de 57.1% a 79.1% (+22.0 points) sur un benchmark a degradations controlees, en corrigeant trois defauts caches du pipeline OCR (timeout, bug de signe de redressement, bug de convention d'angle OpenCV). L'application est fonctionnelle, dockerisee, et documentee.
