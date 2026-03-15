# Deploy online

## Render
1. Suba o projeto para o GitHub.
2. No Render, crie um novo Web Service.
3. Conecte o repositório.
4. Use:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn run:app --bind 0.0.0.0:$PORT`
5. Defina as variáveis:
   - `SECRET_KEY`
   - `ADMIN_DEFAULT_EMAIL`
   - `ADMIN_DEFAULT_PASSWORD`

## Railway
1. Crie um novo projeto a partir do GitHub.
2. Configure as mesmas variáveis de ambiente.
3. O comando de start pode ser:
   - `gunicorn run:app --bind 0.0.0.0:$PORT`

## Observação
O banco SQLite funciona bem para demonstração e portfólio. Em produção, o ideal é migrar para PostgreSQL.
