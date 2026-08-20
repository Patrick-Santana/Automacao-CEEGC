# config/constants.py
COL_FISCALIZACOES = {
    'ID': 'ID',
    'MUNICIPIO': 'Município',
    'TIPO': 'Tipo',               # valor esperado: "Celpe/Copergás" (ou "Energia e Gás")
    'DATA': 'Data',
    'RELATORIO_GERADO': 'Relatório Gerado'
}

COL_NAO_CONFORMIDADES = {
    'ID_FISCALIZACAO': 'ID Fiscalização',
    'DESCRICAO': 'Descrição',
    'NOME_FOTO': 'Nome da Foto'
}

COL_UNIDADES = {
    'MUNICIPIO': 'Município',
    'UNIDADE': 'Unidade'
}

COL_ENVIO_DOCS = {
    'ID_FISCALIZACAO': 'ID Fiscalização',
    'DOCUMENTO': 'Documento',
    'STATUS': 'Status'
}

COL_COMPESA = {   # mantido nome original da planilha Copergás
    'DT_SOLICITACAO': 'Dt Solicitação RA',
    'DT_ENCERRAMENTO': 'Dt Encerramento RA',
    'PRAZO_TIPO': 'Prazo Tipo Sol RA',
    'MOTIVO_ENCERRA': 'Motivo Encer RA'
}

TEMPLATE_PLACEHOLDERS = {
    'ID': '{{ID}}',
    'MUNICIPIO': '{{MUNICIPIO}}',
    'DATA': '{{DATA}}',
    'TIPO': '{{TIPO}}',
    'UNIDADE': '{{UNIDADE}}',
    'NUM_NCS': '{{NUM_NCS}}',
    'DT_SOLICITACAO': '{{DT_SOLICITACAO}}',
    'DT_ENCERRAMENTO': '{{DT_ENCERRAMENTO}}',
    'PRAZO_TIPO': '{{PRAZO_TIPO}}',
    'MOTIVO_ENCERRA': '{{MOTIVO_ENCERRA}}'
}