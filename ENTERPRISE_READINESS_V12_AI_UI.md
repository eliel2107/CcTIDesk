
# V12 — IA visível na abertura e na resolução

## O que entrou
- Botão `🤖 Assistente IA` na abertura do chamado
- Botão `✨ Gerar documentação com IA` na tela do chamado
- Rotas JSON para consultar o Gemini sem bloquear o fluxo principal
- Persistência de rascunhos em `ticket_ai_insights` e histórico em `ai_jobs`

## Como testar
1. Configure `AI_ASSIST_ENABLED=true` e `AI_API_KEY` no `.env`
2. Abra um novo chamado e clique em `Assistente IA`
3. Em um chamado existente, use `Gerar documentação com IA`
4. Verifique `ticket_ai_insights` no banco

## Observações
- Sem chave ou com IA desativada, a UI some e o sistema continua funcionando
- O texto gerado é um rascunho para revisão humana
