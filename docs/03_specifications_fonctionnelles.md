# Specifications Fonctionnelles

## User Stories

### US-1 : Upload de document
**En tant qu'** utilisateur,
**je veux** pouvoir uploader une image de document d'identite,
**afin de** lancer l'extraction automatique des donnees.

**Criteres d'acceptation :**
- Formats acceptes : PNG, JPG, JPEG, BMP, TIFF
- L'image s'affiche apres l'upload
- Un message d'erreur s'affiche si le fichier n'est pas une image valide

---

### US-2 : Selection du type de document
**En tant qu'** utilisateur,
**je veux** pouvoir choisir le type de document (CNI, Passeport, Certificat),
**afin que** le systeme utilise le bon parseur pour extraire les champs.

**Criteres d'acceptation :**
- Liste deroulante avec 3 choix
- Le parseur adapte est utilise selon la selection

---

### US-3 : Extraction OCR
**En tant qu'** utilisateur,
**je veux** que le systeme extraie automatiquement les informations du document,
**afin de** ne pas avoir a les saisir manuellement.

**Criteres d'acceptation :**
- Le texte brut extrait est accessible (section depliable)
- Les champs structures sont affiches (nom, prenom, date de naissance, etc.)
- Les champs non detectes sont indiques comme "Non detecte"

---

### US-4 : Comparaison avec la base de reference
**En tant qu'** utilisateur,
**je veux** que les donnees extraites soient comparees avec la base de reference,
**afin de** verifier leur coherence.

**Criteres d'acceptation :**
- Un score global de coherence est affiche (en %)
- Chaque champ est compare individuellement
- Le statut de chaque champ est indique : identique, similaire, different, manquant
- Un code couleur facilite la lecture (vert/orange/rouge)

---

### US-5 : Detection des incoherences
**En tant qu'** utilisateur,
**je veux** voir clairement les incoherences detectees,
**afin de** pouvoir prendre les mesures correctives.

**Criteres d'acceptation :**
- Les incoherences sont listees separement
- Pour chaque incoherence : champ concerne, valeur OCR, valeur reference, score
- Si aucune incoherence : message de confirmation positif

---

### US-6 : Fichier de reference personnalise
**En tant qu'** utilisateur,
**je veux** pouvoir charger mon propre fichier Excel de reference,
**afin de** comparer avec mes propres donnees.

**Criteres d'acceptation :**
- Upload d'un fichier .xlsx via la barre laterale
- Le fichier par defaut est utilise si rien n'est uploade
- Les donnees de reference sont visualisables dans la sidebar

---

## Cahier des charges resume

| Fonctionnalite | Priorite | Statut |
|---|---|---|
| Upload d'image | Haute | Implemente |
| Selection du type de document | Haute | Implemente |
| Pretraitement d'image | Haute | Implemente |
| Extraction OCR (Tesseract) | Haute | Implemente |
| Parsing CNI (regex) | Haute | Implemente |
| Parsing Passeport (MRZ + fallback) | Haute | Implemente |
| Parsing Certificat de scolarite | Haute | Implemente |
| Comparaison avec Excel | Haute | Implemente |
| Detection des incoherences | Haute | Implemente |
| Interface Streamlit | Haute | Implemente |
| Dockerisation | Moyenne | Implemente |
| Upload de fichier Excel custom | Basse | Implemente |
