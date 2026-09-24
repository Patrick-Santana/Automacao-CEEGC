# config/constants.py

# Tipos de Relatórios ARPE suportados
TIPOS_RELATORIO = {
    'QUALIDADE_TRIMESTRAL': '📊 Relatório de Qualidade (Trimestral)',
    'QUALIDADE_SEMESTRAL': '📈 Relatório de Qualidade (Semestral)',
    'ACOMPANHAMENTO': '📋 Relatório de Acompanhamento (Comunicação)',
    'DIRETA': '🔍 Relatório de Fiscalização Direta',
}

# Concessionárias
CONCESSIONARIAS = {
    'CELPE': 'Companhia Energética de Pernambuco (Celpe)',
    'COPERGAS': 'Companhia Pernambucana de Gás (Copergás)'
}

# Incisos da Resolução ARPE nº 034/2006
INCISOS_RESOLUCAO = {
    'I': 'Prazo Máximo para Atendimento a Pedido de Ligação',
    'II': 'Prazo Máximo para Atendimento a Pedido de Religação',
    'III': 'Prazo Máximo para Religação de Usuário com Corte Indevido',
    'IV': 'Tempo Máximo de Interrupção para Manutenção Programada',
    'V': 'Prazo para Devolução de Valores por Erros de Faturamento',
    'VI': 'Prazo Máximo para Troca de Medidor',
    'VII': 'Prazo Máximo para Verificação de Pressão e/ou PCS do Gás',
    'VIII': 'Tempo Médio de Elaboração de Estudos e Orçamentos'
}

# Colunas das planilhas
COL_FISCALIZACOES = {
    'ID': 'ID',
    'MUNICIPIO': 'Município',
    'TIPO': 'Tipo',
    'PERIODO': 'Período',
    'PROCESSO_ADM': 'Processo Administrativo',
    'DATA': 'Data',
    'RELATORIO_GERADO': 'Relatório Gerado'
}

COL_NAO_CONFORMIDADES = {
    'ID_FISCALIZACAO': 'ID Fiscalização',
    'INCISO': 'Inciso',
    'INDICADOR': 'Indicador',
    'DESCRICAO': 'Descrição',
    'FUNDAMENTACAO': 'Fundamentação',
    'QUANTIDADE': 'Quantidade',
    'NOME_FOTO': 'Nome da Foto',
    'JUSTIFICATIVA': 'Justificativa Concessionária',
    'STATUS': 'Status Acatamento',
    'PLANO_ACAO': 'Plano de Ação'
}

COL_UNIDADES = {
    'MUNICIPIO': 'Município',
    'UNIDADE': 'Unidade'
}

# Placeholders dos templates
PLACEHOLDERS = {
    'ID': '{{ID}}',
    'MUNICIPIO': '{{MUNICIPIO}}',
    'DATA': '{{DATA}}',
    'PERIODO': '{{PERIODO}}',
    'PROCESSO_ADM': '{{PROCESSO_ADM}}',
    'CONCESSIONARIA': '{{CONCESSIONARIA}}',
    'TOTAL_NCS': '{{TOTAL_NCS}}',
    'DT_SOLICITACAO': '{{DT_SOLICITACAO}}',
    'DT_ENCERRAMENTO': '{{DT_ENCERRAMENTO}}',
    'PRAZO_TIPO': '{{PRAZO_TIPO}}',
    'MOTIVO_ENCERRA': '{{MOTIVO_ENCERRA}}'
}