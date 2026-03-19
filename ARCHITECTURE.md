# Arquitetura — CcTI Desk

> Última atualização: 2026-03-18

## Visão Geral

**CcTI Desk** é um sistema de service desk interno desenvolvido em **Flask + SQLite**. Segue o padrão *Application Factory* com blueprints organizados por domínio e uma camada de serviços desacoplada das rotas.

---

## Estrutura de Pastas

```
CCTI/
├── run.py                      # Ponto de entrada: carrega .env e chama create_app()
├── requirements.txt            # Dependências Python
├── .env                        # Variáveis de ambiente (nunca commitado)
├── ARCHITECTURE.md             # Este documento
├── instance/                   # Criado em runtime (excluído do git)
│   ├── chamados.db             # Banco SQLite principal (WAL mode)
│   ├── uploads/                # Arquivos anexados a tickets
│   └── backups/                # Backups automáticos do banco (diário às 02h)
└── app/
    ├── __init__.py             # Application Factory (create_app) + registro de blueprints
    ├── config.py               # Classe Config: lê todas as vars de ambiente
    ├── db.py                   # Schema SQL, migrate_db(), get_db(), init_db()
    ├── models.py               # Camada de compatibilidade: re-exporta services/
    ├── constants.py            # Valores válidos de status, prioridade, tipo, transições
    ├── helpers.py              # Utilitários puros (formatação de datas, sanitização)
    ├── extensions.py           # Singletons: CSRFProtect, Limiter
    ├── auth.py                 # Blueprint "auth" + decorators login_required/role_required
    ├── admin.py                # Blueprint "admin" (/admin/users, /admin/categories)
    ├── api.py                  # Blueprint "api" — API REST pública (requer login)
    ├── assets_admin.py         # Blueprint "assets_admin" — gestão de ativos de TI
    ├── reports.py              # Blueprint "reports" — relatórios e gráficos
    ├── kb.py                   # Blueprint "kb" — base de conhecimento
    ├── portal.py               # Blueprint "portal" — acesso externo via token (sem login)
    ├── stock.py                # Blueprint "stock" — estoque de consumíveis
    ├── nf.py                   # Blueprint "nf" — entradas por Nota Fiscal
    ├── catalogo.py             # Blueprint "catalogo" — catálogo de produtos
    ├── notify.py               # Envio de e-mail via SMTP em thread separada
    ├── notifications.py        # Notificações internas (tabela notifications no DB)
    ├── ai_service.py           # Fachada de IA: opening_assistant, resolution_assistant
    ├── scheduler.py            # Jobs agendados via APScheduler
    ├── cli.py                  # Comandos Flask CLI (flask init-db, flask seed…)
    ├── address_book.py         # Presets de endereços de entrega/remetente
    ├── auth/
    │   ├── __init__.py         # Re-exporta decorators
    │   └── decorators.py       # login_required, role_required (sem circular import)
    ├── routes/
    │   ├── __init__.py         # Blueprint "routes" agregador — importa sub-módulos
    │   ├── dashboard.py        # / e /dashboard e /home
    │   ├── tickets.py          # CRUD de chamados, upload, download
    │   ├── queue.py            # /fila, /fila/<id>/assumir, /kanban
    │   ├── workflow.py         # Transferência, reabertura, devolução
    │   ├── comments.py         # Comentários públicos e notas internas
    │   ├── approval.py         # Fluxo de aprovação
    │   ├── search.py           # /search, /busca-avancada, /export.csv
    │   ├── logs.py             # /logs — auditoria com exportação Excel/PDF
    │   ├── groups.py           # Grupos de operadores
    │   ├── webhooks.py         # Configuração de webhooks externos
    │   ├── recurring.py        # Chamados recorrentes agendados
    │   └── api_routes.py       # Endpoints internos: notificações, IA, TMA, busca ⌘K
    ├── services/               # Lógica de negócio desacoplada das rotas
    │   ├── auth_service.py
    │   ├── ticket_service.py   # CRUD principal, numeração, etapas, anexos, SLA
    │   ├── sla_service.py      # Cálculo de deadline e TMA
    │   ├── approval_service.py # Solicitar/aprovar/reprovar tickets
    │   ├── workflow_service.py # Transferências, reabertura, devolução
    │   ├── comment_service.py
    │   ├── webhook_service.py  # CRUD + disparo de eventos HTTP
    │   ├── group_service.py
    │   ├── category_service.py
    │   ├── search_service.py
    │   ├── dashboard_service.py
    │   ├── report_service.py
    │   ├── asset_service.py    # CRUD de ativos, tag auto-increment (IT-NNNN)
    │   ├── stock_service.py
    │   ├── nf_service.py
    │   ├── user_service.py
    │   ├── catalogo_service.py
    │   └── ai/
    │       ├── __init__.py
    │       └── gemini_client.py  # Cliente Gemini via SDK google-genai
    └── agents/
        ├── __init__.py
        ├── tools.py              # Ferramentas dos agentes: buscar KB, tickets similares
        └── operator_team.py      # Pipeline de 3 agentes IA (diagnóstico→checklist→rascunho)
```

---

## Fluxo de uma Requisição

```
Browser
  │
  ├─ HTTP Request
  │
  ▼
Flask WSGI (Werkzeug)
  │
  ├─ flask-limiter          (rate limit por IP)
  ├─ before_app_request     (auth.py: carrega g.user da sessão via get_db())
  │
  ▼
Blueprint / View Function
  ├─ @login_required        (verifica g.user)
  ├─ @role_required(...)    (verifica g.user["role"])
  │
  ├─ Chama services/        (lógica de negócio isolada)
  │     ├─ get_db()         (conexão SQLite reutilizada via flask.g)
  │     ├─ SQL parametrizado (? placeholders)
  │     └─ db.commit()
  │
  ├─ notify_async()         (e-mail em thread daemon)
  ├─ fire_webhooks()        (HTTP POST em thread daemon)
  ├─ notifications.*        (INSERT em tabela notifications)
  │
  └─ Response (render_template ou jsonify ou redirect)
        │
  teardown_appcontext: db.close_db()
```

---

## Banco de Dados

**SQLite** com WAL journal mode, `foreign_keys=ON`, `synchronous=NORMAL`.

Localização: `instance/chamados.db`

### Tabelas Principais

| Tabela | Descrição |
|---|---|
| `tickets` | Chamados com todos os campos de negócio, SLA, aprovação |
| `users` | Usuários (admin / operador / solicitante) |
| `categories` | Categorias com SLA, checklist, aprovação e campos visíveis |
| `assets` | Ativos de TI com tag auto-incrementada (IT-NNNN) |
| `ticket_log` | Histórico de eventos por ticket |
| `ticket_steps` | Checklist de etapas por ticket |
| `ticket_comments` | Comentários públicos e notas internas |
| `ticket_transfers` | Histórico de transferências |
| `attachments` | Arquivos anexados |
| `notifications` | Notificações internas por usuário |
| `kb_articles` | Artigos da base de conhecimento |
| `portal_tokens` | Tokens de acesso externo por ticket |
| `webhooks` | Destinos HTTP para eventos do sistema |
| `recurring_tickets` | Definições de chamados recorrentes |
| `operator_groups` / `group_members` / `group_categories` | Grupos de operadores |
| `stock_produtos` / `stock_movimentacoes` | Estoque de consumíveis |
| `entradas_nf` / `entradas_nf_itens` / `entradas_nf_assets` | Notas Fiscais |
| `catalogo_produtos` | Catálogo de referência |
| `ai_jobs` / `ticket_ai_insights` | Jobs e resultados de IA por ticket |

### Migrações

Sem ORM. Migrações incrementais via `app/db.py:migrate_db()` usando `PRAGMA table_info()` + `ALTER TABLE ADD COLUMN` condicional. Executadas automaticamente no startup da aplicação.

---

## Sistema de IA

### Endpoints

| Endpoint | Método | Autenticação | Descrição |
|---|---|---|---|
| `/api/ai/opening-assistant` | POST | `@login_required` | Melhora descrição ao abrir chamado |
| `/api/ai/tickets/<id>/resolution-draft` | POST | `@login_required` + operador/admin | Gera rascunho de documentação da resolução |
| `/api/ai/tickets/<id>/operator-assist` | POST | `@login_required` + operador/admin | Pipeline de 3 agentes |

### Pipeline de 3 Agentes (`operator_team.py`)

```
Ticket + contexto do banco
        │
        ▼
  Agente 1 — Diagnóstico
  (KB + tickets similares → JSON: diagnóstico, causa, solução, referências)
        │
        ▼
  Agente 2 — Checklist
  (Diagnóstico + etapas padrão da categoria → lista de até 7 etapas)
        │
        ▼
  Agente 3 — Rascunho de Resposta
  (Diagnóstico → texto profissional para o solicitante, ≤120 palavras)
```

**Providers suportados:** Gemini (via `AI_API_KEY`) ou Claude (via `ANTHROPIC_API_KEY`).
Prioridade: Claude > Gemini.

### Variáveis de Ambiente de IA

```env
AI_ASSIST_ENABLED=true
AI_API_KEY=<chave Gemini>
AI_MODEL=gemini-2.5-flash
AI_TIMEOUT_SECONDS=30
AI_MAX_CONTEXT_CHARS=6000
ANTHROPIC_API_KEY=<chave Claude — opcional, prioridade sobre Gemini>
ANTHROPIC_MODEL=claude-haiku-4-5
```

---

## Segurança

| Mecanismo | Implementação |
|---|---|
| Autenticação | Sessão Flask (`session["user_id"]`) + `@login_required` |
| Autorização | `@role_required("admin", "operador")` |
| CSRF | `Flask-WTF CSRFProtect` — ativo em todos os blueprints exceto `api` e `portal` |
| Rate Limiting | `flask-limiter` (300/hora default, 10/min em login) |
| Senhas | `werkzeug.security.generate_password_hash` (Scrypt) |
| Upload | Extensões permitidas: `pdf, png, jpg, jpeg` — máx 10MB |
| Webhooks | Validação de URL: bloqueia localhost, RFC 1918, IPs privados (anti-SSRF) |
| Logout | Via POST com CSRF token (protege contra logout forçado via GET) |
| API REST | Requer sessão ativa (`@login_required`) |

---

## Jobs Agendados (APScheduler)

| Job | Horário | Descrição |
|---|---|---|
| Backup | 02:00 diário | Copia `chamados.db` para `instance/backups/` |
| Digest | 08:00 diário | E-mail resumo do dia anterior para admins |
| Chamados recorrentes | A cada hora | Cria tickets de agendamentos ativos |
| Timeout de assunção | A cada minuto | Libera tickets assumidos mas não atendidos |
| Limpeza de NF | 03:30 diário | Remove rascunhos de NF expirados |

---

## Decisões Técnicas

### Por que SQLite?
Sistema interno com volume moderado de dados. WAL mode suporta concorrência de leitura adequada. Sem necessidade de infraestrutura de banco adicional.

### Por que sem ORM (SQLAlchemy)?
Controle explícito das queries. Migrações incrementais simples. O custo de aprender outro paradigma não justificava para o tamanho do projeto.

### Por que `models.py` existe?
Camada de compatibilidade intencional — re-exporta todos os `services/`. Permite que código legado continue usando `from app.models import create_ticket` enquanto código novo usa `from app.services.ticket_service import create_ticket`.

### Por que APScheduler e não Celery?
Sem dependência de broker externo (Redis/RabbitMQ). Para o volume de jobs (5 jobs, baixa frequência), APScheduler é suficiente. Em ambiente multi-worker (Gunicorn), usar variável `DISABLE_SCHEDULER=true` em workers secundários.

---

## Pontos de Melhoria

| Prioridade | Item | Justificativa |
|---|---|---|
| Alta | Testes automatizados | Cobertura de services/ e rotas críticas |
| Alta | Renomear colunas no schema | `ALTER TABLE` atual não suporta renomear — precisa de migração manual |
| Média | Lock de scheduler em multi-worker | APScheduler sem lock externo dispara N vezes em N workers |
| Média | Paginação na API REST | `/api/tickets` retorna todos os registros |
| Baixa | Extração de `services/` para pacotes menores | `ticket_service.py` é o maior arquivo do projeto |
| Baixa | Validação com Pydantic | Config e inputs de API poderiam usar modelos tipados |
