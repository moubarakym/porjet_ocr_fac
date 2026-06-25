# Expression des Besoins

## Contexte

Dans le cadre de la gestion administrative, de nombreux organismes (universites, administrations, entreprises) doivent verifier l'identite de leurs usagers a partir de documents physiques (CNI, passeport, certificats). Ce processus est souvent manuel, lent et sujet a des erreurs humaines.

L'objectif de ce projet est de developper une application capable d'automatiser l'extraction d'informations depuis des documents numerises, puis de verifier la coherence de ces informations avec une base de donnees de reference.

## Objectifs fonctionnels

1. **Extraire automatiquement les donnees** d'un document d'identite numerise (image) grace a la reconnaissance optique de caracteres (OCR).
2. **Comparer les donnees extraites** avec les informations presentes dans une base de reference (fichier Excel).
3. **Detecter et signaler les incoherences** entre les deux sources de donnees.
4. **Fournir une interface utilisateur** simple permettant de visualiser les resultats.

## Types de documents supportes

- Carte Nationale d'Identite (CNI)
- Passeport (avec lecture de la zone MRZ)
- Certificat de Scolarite

## Contraintes techniques

- L'application doit fonctionner dans un environnement Docker.
- Le moteur OCR doit supporter la langue francaise.
- L'interface doit etre accessible via un navigateur web.
- Les donnees de reference sont fournies sous forme de fichier Excel (.xlsx).

## Acteurs

| Acteur | Description |
|---|---|
| Utilisateur | Personne qui uploade un document et consulte les resultats |
| Systeme OCR | Module qui extrait le texte des images |
| Base de reference | Fichier Excel contenant les donnees attendues |

## Cas d'utilisation principaux

1. L'utilisateur uploade une image de document.
2. L'utilisateur selectionne le type de document.
3. Le systeme extrait les donnees via OCR.
4. Le systeme compare les donnees avec la base de reference.
5. Le systeme affiche les resultats : champs extraits, correspondances, incoherences.
6. L'utilisateur peut charger un fichier de reference personnalise.
