# ENTERPRISE READINESS V13

## O que mudou
- Chamados de categorias agora entram primeiro na fila compartilhada da equipe.
- Operadores continuam vendo apenas as categorias que podem atender.
- Se ninguém assumir em `ASSIGNMENT_TIMEOUT_MINUTES` (padrão: 15), o scheduler faz autoatribuição para um operador elegível.
- A autoatribuição por timeout leva em conta menor carga ativa e quem está há mais tempo sem receber atribuição.
- O aceite manual (`Assumir`) agora coloca o chamado em `EM_ANDAMENTO`.
- Novo comando CLI: `flask assignment-fallback`

## Novas configs
- `ASSIGNMENT_AUTO_FALLBACK_ENABLED=true`
- `ASSIGNMENT_TIMEOUT_MINUTES=15`

## Fluxo
1. Chamado é criado com categoria e fica em `ABERTO` / sem responsável.
2. Equipe elegível vê o chamado na fila e pode clicar em **Assumir**.
3. Se ninguém assumir dentro do prazo, o scheduler autoatribui o chamado.
4. O sistema registra auditoria com `AGUARDANDO_ASSUNCAO` e `ATRIBUIDO_TIMEOUT`.
