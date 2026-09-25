import streamlit as st
from controllers.file_controller import FileController

st.title("📤 Upload de Arquivos")

st.markdown("### 1. Planilha Principal")
planilha = FileController.upload_planilha_principal()
if planilha:
    st.session_state['planilha_principal'] = planilha
    st.success(f"✅ Carregada: **{planilha.name}**")

st.markdown("---")
st.markdown("### 2. Planilha Complementar Copergás (opcional)")
copergas = FileController.upload_planilha_copergas()
if copergas:
    st.session_state['planilha_copergas'] = copergas
    st.success(f"✅ Carregada: **{copergas.name}**")