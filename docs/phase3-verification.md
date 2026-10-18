# Verificação da Fase 3

Data: 11 de outubro de 2026.

## Implementação

Coleta por braço com modelo solicitado/observado, versão, hashes, uso nativo e
normalizado, duração, status e resposta. Falhas e execuções parciais são mantidas.
Runner com teto de execuções, timeout de grupos de processos, ausência de retry
próprio, relatório JSON/Markdown e gates de comparabilidade e revisão humana.

O protocolo documenta cinco condições e delimita que a suíte atual automatiza
somente a comparação textual. O smoke local verifica RTK, seus hooks e a
inicialização do MCP CodeGraph sem inferência de modelos ou criação de índice.

## Evidências observadas

- Testes de parsing: turnos, cache, replays com ID, dados ausentes, falha parcial
  e JSON inválido.
- Dez testes de avaliação e vinte testes do instalador passaram.
- Teste de timeout confirma encerramento de subprocessos descendentes.
- Teste de teto confirma recusa antes de qualquer execução de inferência.
- Revisão pendente ou identidade desconhecida não libera percentuais no relatório.
- Busca web, outras ferramentas e tipos desconhecidos de evento impedem a
  comparação textual; respostas e raciocínio normais continuam aceitos.
- Os testes anteriores do instalador, wrappers e sanitizador seguem passando.
- RTK: saída sintética passou de 754 para 240 bytes e de 29 para 5 linhas.
  Os cinco títulos esperados foram preservados. A medida refere-se a output,
  não a tokens enviados a um provedor ou a cobrança.
- Hooks: sugestão Codex e updatedInput Claude funcionaram em execução direta
  com RTK real, sem permissionDecision.
- CodeGraph: MCP initialize respondeu e não foi criado índice.

## Piloto sintético com clientes

Foi selecionado o caso `direct-answer`, com uma repetição e até quatro execuções
planejadas (duas por cliente). O Codex executou o par; o Claude foi identificado
como desconectado e não houve tentativa de inferência nele.

| Cliente/condição | Input, incluindo cache | Cache de leitura | Output | Total observado |
|---|---:|---:|---:|---:|
| Codex baseline | 14791 | 11776 | 35 | 14826 |
| Codex candidato | 15377 | 11776 | 39 | 15416 |
| Claude baseline/candidato | indisponível | indisponível | indisponível | indisponível |

O modelo solicitado foi `gpt-6-sol`, com esforço medium. A identificação do
modelo resolvido não foi exposta nos eventos coletados e a revisão de qualidade
permanece pendente. Esses valores brutos não constituem um par elegível para
alegar economia. O candidato contém mais instruções que o baseline histórico;
essa comparação não isola os componentes de otimização.

Uma primeira tentativa sob rede restrita falhou no Codex e foi preservada. A
execução com acesso à rede produziu os valores acima. Não houve substituição
silenciosa de modelos.

O consultor revisou a instrumentação e retornou `proceed` após a correção da
classificação de ferramentas e eventos desconhecidos. Essa aprovação refere-se
ao coletor e aos gates de relatório, sem validar economia representativa.

## Pendências

Autenticar Claude Code para executar seu par. Validar carregamento/trust de hooks
em sessões reais, navegação via MCP e cenários com grafos, além de qualidade e
repetições representativas. A instalação limpa em outra máquina e Intel também
continuam pendentes. Não existe evidência de redução representativa de tokens
ou cobrança nesta fase; existe evidência do funcionamento da instrumentação.
