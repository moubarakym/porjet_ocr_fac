"""
Interface Streamlit pour l'application OCR.
Permet d'uploader un document, d'extraire les donnees et de les comparer
avec la base de reference.
"""

import os
import tempfile
import streamlit as st
import numpy as np
import cv2
from PIL import Image

from ocr.extractor import extract_document, extract_text
from comparator.compare import compare_document, load_reference_data

# --- Configuration de la page ---
st.set_page_config(
    page_title="OCR - Verification de documents",
    page_icon="🔍",
    layout="wide",
)

st.title("OCR - Extraction et verification de documents")
st.markdown("Application d'extraction de donnees depuis des pieces d'identite "
            "et comparaison avec une base de reference.")

# --- Chemin du fichier de reference ---
REFERENCE_PATH = os.path.join(os.path.dirname(__file__), "data", "reference.xlsx")

# --- Sidebar : parametres ---
st.sidebar.header("Parametres")

doc_type = st.sidebar.selectbox(
    "Type de document",
    options=["cni", "passeport", "certificat"],
    format_func=lambda x: {
        "cni": "Carte Nationale d'Identite",
        "passeport": "Passeport",
        "certificat": "Certificat de Scolarite",
    }[x],
)

st.sidebar.markdown("---")
st.sidebar.subheader("Base de reference")

# Option pour uploader un fichier Excel custom
uploaded_ref = st.sidebar.file_uploader(
    "Charger un fichier Excel de reference (optionnel)",
    type=["xlsx"],
)

if uploaded_ref:
    ref_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name
    with open(ref_path, "wb") as f:
        f.write(uploaded_ref.read())
else:
    ref_path = REFERENCE_PATH

# Afficher les donnees de reference
if os.path.exists(ref_path):
    with st.sidebar.expander("Voir les donnees de reference"):
        df_ref = load_reference_data(ref_path)
        st.dataframe(df_ref, use_container_width=True)

# --- Zone principale ---
st.header("1. Charger un document")

uploaded_file = st.file_uploader(
    "Selectionnez une image de document",
    type=["png", "jpg", "jpeg", "bmp", "tiff"],
)

if uploaded_file is not None:
    # Afficher l'image uploadee
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Document original")
        st.image(image, use_column_width=True)

    # Sauvegarder temporairement pour le traitement
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name)
        tmp_path = tmp.name

    # --- Extraction OCR ---
    st.header("2. Extraction OCR")

    with st.spinner("Extraction en cours..."):
        try:
            result = extract_document(tmp_path, doc_type)
        except Exception as e:
            st.error(f"Erreur lors de l'extraction : {e}")
            st.stop()

    # Afficher le texte brut
    with st.expander("Texte brut extrait par OCR"):
        st.text(result.get("texte_brut", ""))

    # Afficher les champs extraits
    st.subheader("Champs extraits")
    fields_to_show = {k: v for k, v in result.items() if k != "texte_brut"}

    cols = st.columns(3)
    for i, (key, val) in enumerate(fields_to_show.items()):
        with cols[i % 3]:
            display_val = val if val else "Non detecte"
            color = "normal" if val else "off"
            st.metric(label=key.replace("_", " ").title(), value=display_val)

    # --- Comparaison ---
    st.header("3. Comparaison avec la base de reference")

    if not os.path.exists(ref_path):
        st.warning("Aucun fichier de reference trouve. Placez un fichier reference.xlsx dans le dossier data/.")
    else:
        with st.spinner("Comparaison en cours..."):
            comparison = compare_document(result, ref_path)

        if not comparison["match_found"]:
            st.warning(comparison["message"])
        else:
            # Score global
            score = comparison["score_global"]
            if score >= 90:
                st.success(f"Score de coherence global : {score}%")
            elif score >= 70:
                st.warning(f"Score de coherence global : {score}%")
            else:
                st.error(f"Score de coherence global : {score}%")

            # Tableau de comparaison
            st.subheader("Detail de la comparaison")

            for comp in comparison["comparaisons"]:
                col_a, col_b, col_c, col_d = st.columns([2, 3, 3, 2])

                with col_a:
                    st.write(f"**{comp['champ'].replace('_', ' ').title()}**")
                with col_b:
                    st.write(f"OCR : `{comp['valeur_ocr'] or 'N/A'}`")
                with col_c:
                    st.write(f"Ref : `{comp['valeur_reference'] or 'N/A'}`")
                with col_d:
                    if comp["status"] == "identique":
                        st.write("✅ Identique")
                    elif comp["status"] == "similaire":
                        st.write(f"⚠️ Similaire ({comp['score']}%)")
                    elif comp["status"] == "different":
                        st.write("❌ Different")
                    elif comp["status"] == "manquant_ocr":
                        st.write("❌ Non detecte")
                    else:
                        st.write(f"ℹ️ {comp['status']}")

            # Incoherences detectees
            if comparison["incoherences"]:
                st.subheader("Incoherences detectees")
                for inc in comparison["incoherences"]:
                    st.error(
                        f"**{inc['champ']}** : valeur OCR = `{inc['valeur_ocr'] or 'N/A'}` "
                        f"vs reference = `{inc['valeur_reference'] or 'N/A'}` "
                        f"(score : {inc['score']}%)"
                    )
            else:
                st.success("Aucune incoherence detectee. Le document est coherent avec la base de reference.")

    # Nettoyage du fichier temporaire
    os.unlink(tmp_path)
