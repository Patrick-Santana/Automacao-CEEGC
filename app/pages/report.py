import streamlit as st

from config.constants import TIPOS_RELATORIO
from controllers import get_controller

st.title("📄 Geração de Relatório")

if 'planilha_principal' not in st.session_state or 'id_fiscalizacao' not in st.session_state:
    st.warning("⚠️ Configure a planilha e selecione uma fiscalização antes.")
    st.stop()

tipo = st.session_state.get('tipo_relatorio', 'QUALIDADE_TRIMESTRAL')
id_fisc = st.session_state['id_fiscalizacao']

col1, col2, col3 = st.columns(3)
col1.metric("🆔 Fiscalização", id_fisc)
col2.metric("📄 Tipo", TIPOS_RELATORIO.get(tipo, tipo).split(' ', 1)[-1])
col3.metric("📎 Planilha", st.session_state['planilha_principal'].name[:20])

st.markdown("---")

if st.button("🚀 Gerar Relatório Word", type="primary", use_container_width=True):
    with st.spinner("Processando dados e gerando documento..."):
        try:
            controller = get_controller(tipo)
            output = controller.gerar(
                excel_path=st.session_state['planilha_principal'],
                id_fisc=id_fisc,
                tipo=tipo,
                copergas_path=st.session_state.get('planilha_copergas'),
            )
        except ValueError as e:
            st.error(str(e))
            output = None

    if output:
        st.balloons()
        st.success(f"✅ Relatório gerado: **{output.name}**")
        with open(output, 'rb') as f:
            st.download_button(
                "📥 Baixar Relatório (.docx)",
                f,
                file_name=output.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

st.markdown("---")
st.caption("Relatórios salvos em `data/output/relatorios/`")