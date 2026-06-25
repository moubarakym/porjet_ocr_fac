# Bilan de Conformite

## Correspondance besoins / realisation

| Besoin exprime | Specification | Realisation | Statut |
|---|---|---|---|
| Extraire les donnees d'un document numerise | US-3 : Extraction OCR | Module `ocr/extractor.py` avec Tesseract + regex | Conforme |
| Supporter CNI, Passeport, Certificat | US-2 : Selection du type | 3 parseurs dedies (parse_cni, parse_passeport, parse_certificat) | Conforme |
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
| README complet | Oui | README_PROJET.md |

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
| Realisation des tests (PyTest) | Oui | tests/ (28 tests, 100% de reussite) |
| Rapport de tests avec resultats | Oui | docs/05_plan_tests.md |
| Validation finale | Oui | Ce document |

## Limites et axes d'amelioration

- **Precision OCR** : Tesseract peut avoir du mal avec des documents de mauvaise qualite (flous, tordus). Un pretraitement plus avance (correction de perspective, detection de contours) pourrait ameliorer les resultats.
- **Types de documents** : seuls 3 types sont supportes. L'ajout de la Carte Vitale et de la Carte de Sejour necessiterait d'ecrire de nouveaux parseurs.
- **Base de donnees** : le fichier Excel pourrait etre remplace par une vraie base de donnees (SQLite ou PostgreSQL) pour gerer de plus grands volumes.
- **Securite** : les documents d'identite contiennent des donnees sensibles. En production, il faudrait chiffrer les donnees et ne pas stocker les images.

## Conclusion

Le projet repond a l'ensemble des besoins exprimes et des consignes du module DNF2ED12. Les 28 tests unitaires et d'integration passent a 100%. L'application est fonctionnelle, dockerisee, et documentee.
