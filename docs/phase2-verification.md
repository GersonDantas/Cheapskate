# Verificação da Fase 2

Data: 11 de outubro de 2026.

## Entrega

Instalador macOS com `install`, `update`, `check`, `audit`, `rollback` e
`uninstall`; manifesto de artefatos e skills fixados; integração RTK por host;
registro MCP CodeGraph; skills Caveman e Graphify com referências; instalação
opcional do Personal Agent Team sem configurar a equipe.

## Evidências

- 20 testes automatizados em diretórios temporários passaram.
- ShellCheck, validação Python e `git diff --check` passaram.
- Os comparadores de avaliações e o sanitizador continuam passando offline.
- O dry-run na máquina de referência propõe 30 arquivos, sem aplicação.
- Smoke test com executáveis reais e skills baixadas/verificadas passou.
- Instalação em home com espaços, check, audit, repetição idempotente,
  uninstall, rollback e novo check passaram.
- Smoke test do plugin opcional passou em Codex home temporário, sem
  autenticação copiada, configuração de agentes ou chamadas a modelos.

Ferramentas reutilizadas no smoke: RTK 0.46.0, CodeGraph 1.5.0 e Graphify 0.9.63.
Clientes de referência: Codex CLI 0.161.0 e Claude Code 2.1.221.

## Limites da evidência

O smoke não partiu de uma máquina sem npm, pipx ou executáveis. Instalação limpa
de todas as dependências e compatibilidade Intel continuam pendentes. Também
faltam sessões reais para verificar carregamento/trust de hooks e utilização
efetiva do MCP. Os testes desta fase não medem economia de tokens.

O hook Codex fornece orientação para usar RTK explicitamente. O hook Claude
reescreve os argumentos sem conceder permissão. Esses fluxos devem ser avaliados
separadamente no benchmark.

O consultor retornou `proceed` para o código e os testes offline, após corrigir
as integrações. O detalhe de inicialização de CODEX_HOME foi corrigido e o
ensaio real do componente opcional passou depois disso.

## Próximo passo

Preparar sessões controladas de cada cliente, verificar RTK e MCP, e registrar
versões, modelos, hashes, tokens e qualidade por cenário. Manter o estágio como
candidato a piloto até concluir a validação independente e o benchmark.
