# Script de soutenance — Vérification automatique de documents d'identité par OCR

Durée cible : 11 minutes maximum (16 diapositives + une démonstration filmée). Temps estimé total ci-dessous : **~9 min 40** à un rythme normal, ce qui laisse encore une bonne marge de sécurité. Les minutages entre parenthèses sont indicatifs — n'hésitez pas à ralentir sur les diapositives 9, 11 et 13 (les plus denses) et à accélérer sur les diapositives de transition (8 et 12).

---

### Diapositive 1 — Titre (≈20 s)

Bonjour à tous. Je vais vous présenter mon projet de Master 1, réalisé dans le cadre du module DNF2ED12 : une application de vérification automatique de documents d'identité par OCR. L'idée est simple : à partir d'une photo de carte d'identité, de passeport, de certificat de scolarité ou de titre de séjour, extraire automatiquement les informations et vérifier qu'elles correspondent à une base de référence.

### Diapositive 2 — Sommaire (≈20 s)

Je vais dérouler la présentation en six parties : le contexte et la problématique, un rapide état de l'art des solutions existantes, l'architecture que j'ai mise en place, les résultats obtenus et le bilan critique, l'extension à un quatrième type de document, et enfin la conclusion et les perspectives.

### Diapositive 3 — Contexte du projet (≈30 s)

Ce projet a été réalisé seul, dans le cadre du Master 1 Informatique, parcours Big Data et Fouille de Données à l'Université Paris 8. J'ai mené l'ensemble de la démarche — expression des besoins, spécifications, réalisation, tests, bilan final — un peu comme sur un vrai projet en entreprise. L'objectif : automatiser une vérification aujourd'hui manuelle, lente, et sujette à l'erreur humaine.

### Diapositive 4 — Le problème à résoudre (≈35 s)

Concrètement, le système doit faire deux choses. D'abord extraire : à partir d'une photo, lire automatiquement le nom, le prénom, la date de naissance, le numéro de document. Ensuite comparer : confronter ces valeurs à une base de référence et signaler toute incohérence, champ par champ. J'ai choisi de couvrir quatre types de documents : carte nationale d'identité, passeport, certificat de scolarité, et titre de séjour. Les difficultés principales sont les libellés qui varient selon le document, le bruit introduit par l'OCR, et la qualité d'image très inégale.

### Diapositive 5 — État de l'art (≈35 s)

Pour l'OCR, j'ai comparé deux approches. D'un côté, les API cloud payantes comme Google Vision ou AWS Textract, très précises mais qui impliquent d'envoyer des documents d'identité sensibles vers un serveur externe. De l'autre, les moteurs open source comme Tesseract, gratuits et utilisables hors-ligne. J'ai retenu Tesseract, justement parce que les données traitées sont sensibles et qu'un traitement local est préférable. En complément, j'utilise OpenCV pour le prétraitement d'image et rapidfuzz pour la comparaison floue, basée sur la distance de Levenshtein.

### Diapositive 6 — Architecture en couches (≈30 s)

L'application est structurée en quatre couches indépendantes : une interface utilisateur avec Streamlit, une couche de logique métier qui contient le parsing des champs et la comparaison, une couche de traitement d'image pour le prétraitement, et une couche de données — un fichier Excel de référence personnalisable. Chaque couche est testable séparément, ce qui a beaucoup aidé pendant le débogage.

### Diapositive 7 — Le pipeline de traitement (≈35 s)

Le traitement se déroule en quatre étapes. D'abord le prétraitement : je génère plusieurs variantes de l'image, avec différents seuillages. Ensuite l'OCR : Tesseract tourne sur chaque variante et chaque configuration, et je retiens celle qui a la meilleure confiance. Puis l'analyse : des expressions régulières adaptées à chaque type de document extraient les champs. Et enfin la comparaison, avec une recherche pondérée dans la base de référence.

### Diapositive 8 — Divider : « Mesurer plutôt que supposer » (≈20 s)

Une fois l'application fonctionnelle de bout en bout, je me suis posé la vraie question : quelle est sa précision réelle ? J'ai donc construit un banc d'essai chiffré — une étape clé, parce qu'elle a révélé des défauts totalement invisibles à la simple lecture du code.

### Diapositive 9 — Le banc d'essai de précision (≈40 s)

Ce banc d'essai repose sur 21 images de test, générées à partir de 3 documents synthétiques dégradés selon 7 profils différents : image propre, rotation, flou, bruit fort, basse résolution, contraste faible, et cumul de dégradations. Cela représente 91 champs à vérifier, avec une vérité terrain connue à l'avance. Le résultat global : on passe de 57 % de précision avant corrections à 79 % après, soit un gain de 22 points.

### Diapositive 10 — Où les corrections ont le plus d'impact (≈35 s)

Dans le détail par type de dégradation, l'impact des corrections varie beaucoup. Le cas le plus spectaculaire, c'est le bruit fort : 0 % de précision avant, 84,6 % après. Les cas de rotation et de cumul de dégradations progressent aussi fortement. En revanche, sur la basse résolution, on observe un léger recul — un effet de bord que j'assume et que je discute dans mes limites.

### Diapositive 11 — Trois défauts cachés (≈50 s)

Ce banc d'essai a permis de découvrir trois défauts cachés. Premièrement, un blocage de Tesseract : sur une image très bruitée, l'OCR pouvait tourner indéfiniment. J'ai corrigé cela avec un timeout de 20 secondes. Deuxièmement, une inclinaison doublée : la correction de rotation s'appliquait dans le même sens que l'inclinaison au lieu du sens inverse — un problème de signe, corrigé en appliquant l'angle inverse. Troisièmement, un changement de convention dans OpenCV : la fonction minAreaRect a changé la façon dont elle renvoie l'angle depuis la version 4.9, ce qui cassait mon hypothèse initiale. J'ai corrigé cela en normalisant l'angle vers le bon intervalle.

### Diapositive 12 — Divider : un quatrième type de document (≈20 s)

Après ce premier travail de fiabilisation, j'ai étendu le système à un quatrième type de document : le titre de séjour. Aucun parseur n'existait pour ce format. En le confrontant à de vraies photographies, et non plus seulement à des images synthétiques, j'ai découvert cinq nouveaux défauts, plus subtils : le système ne plantait pas, il se trompait silencieusement.

### Diapositive 13 — Cinq défauts découverts (≈55 s)

Ces cinq défauts sont : l'ordre du texte qui ne correspondait pas à la mise en page réelle, corrigé en reconstruisant le texte à partir des positions réelles des mots ; les fonds de sécurité, ces motifs guillochés qui perturbaient la lecture, corrigés en isolant chaque canal de couleur ; une collision entre deux champs qui récupéraient la même valeur, corrigée en marquant les deux lignes comme utilisées ; le format récent de carte d'identité 2021, où les libellés sont groupés sur une ligne et les valeurs sur la suivante, qui nécessitait une expression régulière dédiée ; et enfin une lecture de la zone MRZ du passeport qui mélangeait deux blocs de lecture indépendants. Le principe suivi à chaque fois : mieux vaut ne rien extraire que d'extraire une valeur fausse.

### Diapositive 14 — Tests automatisés (≈30 s)

Pour garantir qu'aucune de ces corrections n'introduit de régression ailleurs, j'ai écrit une suite de 41 tests automatisés avec pytest, qui passent tous à 100 %. Ils couvrent l'extraction, la comparaison, l'OCR, le prétraitement, et l'intégration du pipeline complet. C'est ce filet de sécurité qui m'a permis de corriger le deuxième bug de rotation avec confiance, sans craindre de casser autre chose.

### Démonstration (≈35 s, entre la diapositive 14 et la 15)

À ce stade, tout ce qui vient d'être décrit (les corrections, les 41 tests) reste abstrait. Une courte démonstration filmée de l'application le rend concret avant de conclure.

*Ce que dit la voix off, pendant que le screencast tourne :* « Concrètement, voici l'application. J'uploade une carte nationale d'identité, je sélectionne le bon type de document, et le système extrait automatiquement les champs — nom, prénom, numéro — puis les compare à la base de référence. » *(laisser le montage couper le temps de traitement réel, qui prend une quinzaine de secondes)* « Le score de cohérence s'affiche, avec le détail champ par champ. »

**Notes pratiques (ne pas dire à l'oral) :**
- Filmer en amont, pas en direct pendant l'enregistrement de la voix : le traitement OCR prend 15 à 30 secondes par image (plusieurs variantes de prétraitement x plusieurs configurations Tesseract), donc couper ce temps mort au montage plutôt que de le laisser tel quel.
- Choisir un document qui fonctionne bien pour rester fluide : la CNI ou le certificat de scolarité, pas le titre de séjour (son extraction a un trou connu — champs date de naissance, numéro et nationalité non détectés sur les photos réelles testées — inutile de le montrer ici, il est déjà mentionné comme limite au chapitre 5 du mémoire et n'a pas sa place dans une démo qui doit rassurer).
- Lancer l'appli avec `streamlit run app.py`, avoir l'image de test prête à uploader avant de démarrer l'enregistrement d'écran.

### Diapositive 15 — Conclusion et perspectives (≈40 s)

Pour conclure : j'ai livré un système qui extrait et compare automatiquement quatre types de documents, un pipeline testé par 41 tests automatisés, un gain de 22 points de précision grâce à une démarche de mesure objective, et huit défauts identifiés, corrigés et documentés. Pour la suite, plusieurs perspectives : étendre le banc d'essai chiffré au titre de séjour, ajouter une correction de perspective pour les photos prises de travers, remplacer le fichier Excel par une vraie base de données, et ajouter du chiffrement pour un usage en conditions réelles.

### Diapositive 16 — Remerciements (≈10 s)

Merci de votre attention. Je suis à votre disposition pour vos questions.

---

**Conseils pour le jour J**

Chronométrez-vous au moins une fois à voix haute avant la soutenance — le rythme réel dépend beaucoup du stress et des pauses. Si vous devez couper pour gagner du temps, les diapositives 10 et 13 sont les plus faciles à raccourcir (elles reprennent des graphiques déjà lisibles à l'écran, vous pouvez résumer sans tout redire), et la démonstration peut descendre à 20-25 s si besoin. Gardez les diapositives 9, 11 et 15 quasi intégrales : ce sont celles qui montrent le mieux la démarche et les résultats.

Pour la démo : enregistrez-la à part (screencast de l'appli en train de traiter un document), avant d'enregistrer la voix off finale. Vous pourrez alors accélérer ou couper le temps de traitement au montage, caler votre commentaire dessus, et recommencer autant de fois que nécessaire sans avoir à refaire toute la présentation — c'est justement l'avantage de ne pas être en direct devant un jury.
