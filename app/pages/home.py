import streamlit as st

st.title("🏠 Sistema de Relatórios ARPE")
st.markdown("""
<div style="background: linear-gradient(135deg, #001F54 0%, #003B80 100%);
            padding: 30px; border-radius: 12px; color: white; margin-bottom: 20px;">
    <h2 style="color: white; margin: 0;">⚡ Fiscalização Celpe e Copergás</h2>
    <p style="font-size: 16px; margin-top: 10px;">
        Sistema automatizado para geração de relatórios de fiscalização dos serviços
        públicos delegados de <b>energia elétrica</b> e <b>gás canalizado</b> em Pernambuco.
    </p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("### 📊 Qualidade Trim.")
    st.caption("Indicadores a cada 3 meses")
with col2:
    st.markdown("### 📈 Qualidade Sem.")
    st.caption("Consolidação de 6 meses")
with col3:
    st.markdown("### 📋 Acompanhamento")
    st.caption("Resolutividade das NCs")
with col4:
    st.markdown("### 🔍 Direta")
    st.caption("Vistoria in loco")

st.markdown("---")
st.info("👉 **Comece pelo menu lateral → Upload** para enviar a planilha.")