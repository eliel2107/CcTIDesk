# CcTI Desk

Sistema interno de Service Desk para gestão de chamados, ativos de TI, estoque e entradas fiscais — desenvolvido em Python com Flask e SQLite.

> **Stack:** Python 3.11+ · Flask 3 · SQLite (WAL) · Jinja2 · Chart.js · APScheduler · Gemini AI (opcional)

---

## Demonstração

### Login e tela inicial

Tela de autenticação com validação de credenciais e rate limiting para proteção contra força bruta.

![Login](img/Menu_Login.png)

Menu inicial reformulado com acesso rápido aos principais módulos do sistema, adaptado ao perfil do usuário logado.

| Antes | Depois |
|---|---|
| ![Inicio](img/Inicio.png) | ![Inicio Melhorias](img/Inicio_Melhorias.png) |

### Dashboard

Visão consolidada com KPIs de chamados, aging, top responsáveis, funil de status e gráficos interativos.

![Dashboard](img/Dashboard.png)

Dashboard de ativos com filtro por base/localização, exibindo distribuição por status e tipo em tempo real.

| Antes | Depois |
|---|---|
| ![Dash Ativos](img/Dash_Ativos.png) | ![Dash Ativos Melhorias](img/Dash_Ativos_Melhorias.gif) |

### Chamados

Fila operacional com novos filtros, ordenação e indicadores visuais de SLA e prioridade.

| Antes | Depois |
|---|---|
| ![Fila](img/Fila_Chamados.png) | ![Fila Melhoria](img/Fila_Chamados_Melhoria.png) |

Listagem em cards com informações resumidas e visualização Kanban por status.

| Lista de cards | Kanban |
|---|---|
| ![Lista](img/Lista_Cards_Chamados.png) | ![Kanban](img/Kanban.gif) |

Abertura de chamado com seleção de categoria e formulário dinâmico. Tratamento com checklist, comentários, anexos e histórico completo.

| Abertura | Tratamento |
|---|---|
| ![Abertura](img/Abertura_Chamado.png) | ![Tratamento](img/Tratamento_Chamado.png) |

Demonstração do fluxo completo de chamados com as melhorias aplicadas — transferência, devolução ao solicitante e finalização com confirmação.

![Chamados — melhorias](img/Chamados_Melhorias.gif)

### Ativos

Cadastro de ativos com tag, tipo, modelo, serial, base e responsável. Demo completo do ciclo de vida com histórico de movimentações.

| Cadastro | Demo completo |
|---|---|
| ![Cadastro Ativo](img/Ativo_cadastro.png) | ![Ativos](img/AtivoDemo.gif) |

### Estoque

Gestão de consumíveis com alertas de estoque mínimo, movimentações e vínculo de consumo por chamado.

![Estoque — melhorias](img/Estoque_Melhorias.gif)

### Entradas de NF

Fluxo de entrada por nota fiscal em lote: rascunho → revisão de itens → confirmação atômica com geração de ativos e movimentação de estoque.

![Entrada NF — melhoria](img/Entrada_NF_melhoria.mp4)

Dashboard de NFs com visão consolidada de entradas, status e valores por período.

![Dashboard NFs — melhorias](img/Dashboard_NFs_Melhorias.gif)

### Usuários e API

Gestão de usuários com controle de perfis (admin, operador, solicitante) e ativação/inativação. API REST com documentação interativa integrada.

| Usuários | API |
|---|---|
| ![Usuários](img/Usuarios.png) | ![API](img/API_Status.gif) |

Criação e edição de usuários com definição de perfil, grupos e categorias de atendimento.

![Gestão de Usuários](img/Ger_User.gif)

### Logs e auditoria

Auditoria completa com filtros por ação, usuário e período, exportação em Excel e PDF.

![Logs — melhorias](img/Logs_melhorias.gif)

### Base de conhecimento

Artigos vinculados a categorias de chamados, sugeridos automaticamente na abertura e no tratamento.

![Base de Conhecimento — melhorias](img/BasedeConhecimento_Melhorias.gif)

### Busca global

Busca unificada em chamados, ativos, usuários e base de conhecimento com resultados em tempo real.

![Busca](img/BuscaGeral.gif)

---

## Funcionalidades

### Chamados e fluxo de trabalho

- Abertura por solicitante ou operador com categorização obrigatória
- Fluxo de status com validação de transições (ABERTO → EM_ANDAMENTO → ... → CONCLUIDO)
- Aprovação/reprovação por admin quando exigido pela categoria
- Transferência entre operadores com motivo e histórico
- Devolução ao solicitante para complemento de informações
- Finalização com confirmação do solicitante (AGUARDANDO_CONFIRMACAO)
- Reabertura controlada com janela de tempo configurável
- Checklist por chamado (padrão por categoria ou manual)
- Comentários públicos e notas internas
- Anexos com validação de extensão e limite por tipo
- Numeração automática sequencial (REQ-XXXX / INC-XXXX)
- SLA automático por categoria com alerta visual (ok / warning / breach)
- TMA (Tempo Médio de Atendimento) calculado e armazenado

### Fila e atribuição

- Fila operacional com filtros por status, tipo e categoria
- Operadores veem apenas chamados das suas categorias
- Autoatribuição por timeout via scheduler (round-robin por carga)
- Atribuição a grupos de operadores

### Patrimônio e estoque

- Cadastro de ativos com tag, tipo, modelo, serial, local e responsável
- Histórico completo de ciclo de vida do ativo
- Estoque de consumíveis com alerta de mínimo
- Entrada por NF em lote (rascunho → preview → confirmação atômica)
- Catálogo de produtos para agilizar entradas
- Reversão segura de NF confirmada com validações

### Inteligência e relatórios

- Dashboard com KPIs, aging, top responsáveis e funil
- Relatórios exportáveis em XLSX e PDF
- Auditoria completa de logs com filtros e exportação
- Assistente de IA para abertura e documentação de resolução (Gemini)
- Base de conhecimento com artigos vinculados a chamados

### Infraestrutura

- Notificações por e-mail (SMTP assíncrono) e in-app
- Webhooks configuráveis para integração externa
- Chamados recorrentes (diário, semanal, mensal)
- Backup automático diário do banco
- Digest matinal por e-mail
- Portal externo via token para acompanhamento sem login
- API REST JSON

---

## Perfis de acesso

| Perfil | Escopo |
|---|---|
| **admin** | Acesso total — usuários, categorias, aprovações, logs, configurações |
| **operador** | Fila, chamados das suas categorias, ativos, estoque, NF |
| **solicitante** | Abertura e acompanhamento dos próprios chamados |

---

## Segurança

| Proteção | Implementação |
|---|---|
| CSRF | Flask-WTF com token automático em todos os formulários |
| Rate limiting | flask-limiter — login 10/min, chamados 20-60/h, API 300/h |
| Senhas | Hash com Werkzeug (PBKDF2-SHA256) |
| Sessões | Cookie assinado com SECRET_KEY + expiração por inatividade (8h) |
| Uploads | Validação de extensão + `secure_filename` |
| Permissões | Decorators `@login_required` e `@role_required` por rota |
| Banco | PRAGMA foreign_keys=ON, WAL mode, 16 índices de performance |

---

## Arquitetura

O projeto segue uma arquitetura em camadas com separação clara de responsabilidades:

![Arquitetura CcTI Desk](img/ccti_desk_architecture.svg)

> O diagrama editável está disponível em [`docs/CcTI_Desk_Arquitetura_v3.drawio`](docs/CcTI_Desk_Arquitetura_v3.drawio) — abra no [draw.io](https://app.diagrams.net).

### Estrutura de diretórios

```
app/
├── __init__.py              # Factory do Flask + registro de blueprints
├── constants.py             # Constantes de negócio centralizadas
├── helpers.py               # Funções utilitárias compartilhadas
├── config.py                # Configuração via variáveis de ambiente
├── db.py                    # Conexão, schema e migrações SQLite
├── extensions.py            # CSRF + Rate Limiter (instâncias)
├── models.py                # Camada de compatibilidade (re-exports)
├── auth/
│   ├── __init__.py          # Blueprint de autenticação (login/logout)
│   └── decorators.py        # @login_required, @role_required
├── routes/                  # 12 módulos de rota por domínio
│   ├── __init__.py          # Blueprint hub
│   ├── tickets.py           # CRUD, detalhes, upload, etapas
│   ├── queue.py             # Fila, kanban
│   ├── workflow.py          # Transferir, reabrir, devolver, finalizar
│   ├── approval.py          # Aprovações
│   ├── comments.py          # Comentários
│   ├── search.py            # Busca global, avançada, export CSV
│   ├── logs.py              # Auditoria, export Excel/PDF
│   ├── groups.py            # Grupos de operadores
│   ├── webhooks.py          # Configuração de webhooks
│   ├── recurring.py         # Chamados recorrentes
│   ├── dashboard.py         # Dashboard, home, index
│   └── api_routes.py        # Endpoints API (notificações, IA, TMA)
├── services/                # 16 serviços de negócio
│   ├── ticket_service.py    # Core: CRUD, status, etapas, anexos
│   ├── sla_service.py       # SLA e TMA
│   ├── approval_service.py  # Aprovação/reprovação
│   ├── workflow_service.py  # Transferência, reabertura, devolução
│   ├── comment_service.py   # Comentários e notas internas
│   ├── webhook_service.py   # Disparo de webhooks
│   ├── group_service.py     # Grupos de operadores
│   ├── category_service.py  # Categorias de chamados
│   ├── search_service.py    # Busca avançada
│   ├── dashboard_service.py # Dashboard e métricas
│   ├── asset_service.py     # Ativos de TI
│   ├── stock_service.py     # Estoque de consumíveis
│   ├── nf_service.py        # Entrada por NF (lote)
│   ├── auth_service.py      # Autenticação
│   ├── user_service.py      # Gestão de usuários
│   ├── catalogo_service.py  # Catálogo de produtos
│   └── ai/                  # Integração com Gemini AI
├── admin.py                 # Gestão de usuários e categorias
├── assets_admin.py          # Interface de ativos
├── stock.py                 # Interface de estoque
├── nf.py                    # Interface de NF
├── catalogo.py              # Interface de catálogo
├── kb.py                    # Base de conhecimento
├── portal.py                # Portal externo via token
├── api.py                   # API REST
├── reports.py               # Relatórios
├── scheduler.py             # Jobs em background
├── notifications.py         # Sistema de notificações in-app
├── notify.py                # Envio de e-mail assíncrono
├── ai_service.py            # Orquestração da IA
├── templates/               # 30+ templates Jinja2
└── static/                  # CSS (design system próprio)
tests/
└── test_smoke.py            # Suite com pytest (30+ casos)
docs/
└── CcTI_Desk_Arquitetura_v3.drawio  # Diagrama de arquitetura
```

---

## Início rápido

### Requisitos

- Python 3.11+
- pip

### Instalação

```bash
git clone <seu-repo>
cd ccti-desk

python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### Executar

```bash
python run.py
```

Acesse em [http://localhost:5000](http://localhost:5000).

**Login padrão:** `admin@local` / `admin123`

> Altere as credenciais via variáveis de ambiente antes de usar em produção.

---

## Configuração

Copie `.env.example` para `.env` e preencha conforme o ambiente:

```env
# Obrigatório em produção
SECRET_KEY=gere-com-python-c-import-secrets-print-secrets-token-hex-32

# Admin padrão (criado na 1ª execução)
ADMIN_DEFAULT_EMAIL=admin@suaempresa.com
ADMIN_DEFAULT_PASSWORD=senha-forte

# SMTP para e-mails (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=chamados@suaempresa.com
SMTP_PASS=senha-de-app
SMTP_FROM=chamados@suaempresa.com
ALERT_TO_EMAILS=ti@suaempresa.com

# URL pública (usada em e-mails e portal)
APP_URL=https://chamados.suaempresa.com

# IA assistida (opcional)
AI_ASSIST_ENABLED=false
AI_API_KEY=
AI_MODEL=gemini-1.5-flash

# Regras de negócio
TICKET_REOPEN_WINDOW_HOURS=48
ASSIGNMENT_TIMEOUT_MINUTES=15
SESSION_LIFETIME_HOURS=8
NF_DRAFT_MAX_AGE_DAYS=30
```

Todas as variáveis disponíveis estão documentadas em [`.env.example`](.env.example).

---

## Testes

```bash
python -m pytest          # execução padrão
python -m pytest -v       # modo detalhado
```

A suíte cobre autenticação, permissões por perfil, criação e validação de chamados, paginação, API, recorrência, backup, digest e regras de negócio. O APScheduler é desabilitado automaticamente durante os testes.

---

## Deploy

### Docker

```bash
docker compose up --build
```

### Render

O projeto inclui `render.yaml` pronto. Basta conectar o repositório e configurar as variáveis de ambiente no painel do Render.

### Produção (gunicorn)

```bash
gunicorn run:app --bind 0.0.0.0:5000
```

Para rate limiting persistente entre workers, configure `RATELIMIT_STORAGE_URI=redis://...`.

---

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.11, Flask 3, Werkzeug, SQLite |
| Frontend | HTML5, CSS3 (design system próprio, dark theme), Chart.js, Vanilla JS |
| Segurança | Flask-WTF (CSRF), flask-limiter, PBKDF2-SHA256 |
| Exportação | openpyxl (XLSX), ReportLab (PDF) |
| Background | APScheduler |
| IA | Google Gemini (opcional) |
| Monitoramento | Sentry (opcional) |
| Deploy | Gunicorn, Docker, Render |
| Testes | pytest |

---

## Licença

MIT — livre para usar, adaptar e distribuir.
