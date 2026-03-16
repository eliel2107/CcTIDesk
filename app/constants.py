"""
Constantes de negócio centralizadas.
Todos os serviços e rotas importam daqui — nunca definem constantes próprias.
"""

STATUSES = [
    "ABERTO", "EM_ANDAMENTO", "AGUARDANDO_FORNECEDOR", "AGUARDANDO_APROVACAO",
    "ENVIADO", "AGUARDANDO_CONFIRMACAO", "AGUARDANDO_INFO", "CONCLUIDO", "CANCELADO",
]

CLASSIFICATIONS = ["REQUISICAO", "INCIDENTE"]
TYPES = ["COMPRA", "ENVIO"]
PRIORITIES = ["BAIXA", "MEDIA", "ALTA", "URGENTE"]

QUEUE_VISIBLE_STATUSES = [
    "ABERTO", "EM_ANDAMENTO", "AGUARDANDO_FORNECEDOR", "AGUARDANDO_APROVACAO",
    "ENVIADO", "AGUARDANDO_CONFIRMACAO", "AGUARDANDO_INFO",
]

FINAL_STATUSES = ["CONCLUIDO", "CANCELADO"]
LOCKED_STATUSES = {"AGUARDANDO_CONFIRMACAO", "CONCLUIDO"}

SUGGESTED_STEPS = {
    "COMPRA": [
        "Coletar especificação/quantidade",
        "Cotação / fornecedor",
        "Aprovação (centro de custo)",
        "Pedido criado + link",
        "Entrega / conferência",
        "Concluído",
    ],
    "ENVIO": [
        "Confirmar destinatário/endereço/telefone",
        "Preparar equipamento + checklist",
        "Postar / transportadora",
        "Registrar rastreio",
        "Confirmar recebimento",
        "Concluído",
    ],
}

# Mapa de transições válidas por status
TRANSICOES_VALIDAS = {
    "ABERTO":                 ["EM_ANDAMENTO", "AGUARDANDO_FORNECEDOR", "AGUARDANDO_APROVACAO", "AGUARDANDO_INFO", "CANCELADO"],
    "EM_ANDAMENTO":           ["AGUARDANDO_FORNECEDOR", "AGUARDANDO_APROVACAO", "ENVIADO", "AGUARDANDO_INFO", "AGUARDANDO_CONFIRMACAO", "CANCELADO"],
    "AGUARDANDO_FORNECEDOR":  ["EM_ANDAMENTO", "ENVIADO", "CANCELADO"],
    "AGUARDANDO_APROVACAO":   ["ABERTO", "CANCELADO"],
    "ENVIADO":                ["EM_ANDAMENTO", "AGUARDANDO_CONFIRMACAO", "CONCLUIDO", "CANCELADO"],
    "AGUARDANDO_INFO":        ["EM_ANDAMENTO", "ABERTO", "CANCELADO"],
    "AGUARDANDO_CONFIRMACAO": ["ABERTO", "EM_ANDAMENTO"],
    "CONCLUIDO":              ["ABERTO"],
    "CANCELADO":              ["ABERTO"],
}
