"""
Script pour generer le fichier Excel de donnees de reference (donnees fictives).
A executer une seule fois pour creer data/reference.xlsx
"""

import pandas as pd

data = [
    {
        "nom": "DUPONT",
        "prenom": "Jean",
        "date_naissance": "15/03/1990",
        "numero": "ABC123456",
        "sexe": "M",
        "nationalite": "FRA",
        "annee_universitaire": "2024-2025",
    },
    {
        "nom": "MARTIN",
        "prenom": "Sophie",
        "date_naissance": "22/07/1995",
        "numero": "DEF789012",
        "sexe": "F",
        "nationalite": "FRA",
        "annee_universitaire": "2024-2025",
    },
    {
        "nom": "BERNARD",
        "prenom": "Pierre",
        "date_naissance": "01/12/1988",
        "numero": "GHI345678",
        "sexe": "M",
        "nationalite": "FRA",
        "annee_universitaire": "2023-2024",
    },
    {
        "nom": "PETIT",
        "prenom": "Marie",
        "date_naissance": "30/06/1992",
        "numero": "JKL901234",
        "sexe": "F",
        "nationalite": "FRA",
        "annee_universitaire": "2024-2025",
    },
    {
        "nom": "MOREAU",
        "prenom": "Lucas",
        "date_naissance": "10/11/1997",
        "numero": "MNO567890",
        "sexe": "M",
        "nationalite": "FRA",
        "annee_universitaire": "2024-2025",
    },
]

df = pd.DataFrame(data)
df.to_excel("data/reference.xlsx", index=False)
print(f"Fichier reference.xlsx cree avec {len(df)} enregistrements.")
