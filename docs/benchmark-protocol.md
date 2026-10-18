# Protocolo de avaliação

O objetivo é medir consumo observado sem perder qualidade, distinguindo a
redução de saída local da redução de tokens de uma tarefa inteira.

## Condições

| Condição | Componentes | Objetivo |
|---|---|---|
| Básica | Instruções históricas do commit 17a903e | Controle textual reproduzível |
| Concisa | Instruções enxutas e Caveman lite | Avaliar extensão e qualidade das respostas |
| Terminal | Concisa e RTK | Avaliar saída de ferramentas em tarefas com terminal |
| Grafos | Concisa e CodeGraph ou Graphify conforme o cenário | Avaliar recuperação de contexto e custo dos índices |
| Completa | Todas as integrações pertinentes ao cenário | Medir o pacote por tarefa inteira |

A suíte atual automatiza somente a comparação textual entre o baseline
histórico e o bundle atual. O bundle atual inclui políticas de todas as
integrações e pode ser maior que o baseline. Essa comparação não isola o efeito
do Caveman, nem ativa RTK ou grafos, e não equivale às cinco condições completas.
Uma condição concisa isolada e os cenários com ferramentas precisam de fixtures
e validação adicional antes de medir contribuição por componente.

## Piloto instrumental

```sh
python3 scripts/eval-suite.py --ids direct-answer --hosts codex,claude
python3 scripts/eval-suite.py --ids direct-answer --hosts codex,claude \
  --run --max-calls 4 --timeout 75
```

O runner planeja duas execuções por caso e cliente. O teto controla execuções
planejadas dos clientes, não requisições internas ou retries de transporte feitos
pelos clientes. O runner não repete automaticamente. O timeout termina o grupo
de processos e preserva resultados parciais.

Cada cliente é comparado consigo mesmo. Codex usa home temporário, autenticação
copiada com acesso privado, sandbox read-only e configuração pessoal desativada.
Claude usa safe-mode, ferramentas desativadas e sistema explícito. A
autenticação preexistente é utilizada; não existe login automático.

Os prompts sintéticos não contêm dados empresariais. Prompts reais continuam
exigindo revisão prévia e SHA exato. Os resultados ficam em `evals/local/`,
ignorados pelo Git e com permissões privadas. Esses arquivos não devem ser
publicados como estão; erros e metadados podem conter dados locais.

## Rastreabilidade

Por braço, registrar:

- Cliente e sua versão.
- Modelo solicitado e modelos observados, somente quando expostos pelo cliente.
- Esforço solicitado, hash das instruções efetivamente enviadas e hash do prompt.
- Estado, exit code, duração e tentativa efetiva de inferência.
- Uso nativo e representação normalizada, hash e tamanho da resposta.
- Estado da revisão humana, inicialmente pendente.

Por run, registrar hashes dos scripts, manifesto, casos, revisão Git e presença
de alterações locais. O source hash do bundle permite rastrear o candidato mesmo
antes de existir um commit da implementação.

No Codex, agregar apenas `turn.completed.usage`; ignorar snapshots cumulativos
e replays identificáveis por ID. Sem ID, eventos distintos não são deduplicados
pela igualdade dos valores. Input já inclui cache: input não cacheado é a
diferença, quando ambos os campos estão disponíveis.

No Claude, `usage` é a fonte do agregado. Não somar novamente `modelUsage`.
Input comum, cache de leitura e cache de criação são categorias distintas.
Campos ausentes permanecem desconhecidos. Reasoning separado fica desconhecido
quando não há medida própria; não é somado novamente ao output.

## Qualidade e comparação

`report.json` e `report.md` exibem medidas brutas, falhas e motivos de
inelegibilidade. Um percentual de comparação só aparece quando o par terminou,
expôs uso suficiente e o mesmo modelo observado, manteve os controles e passou
por revisão humana vinculada aos hashes das duas respostas.

Uma revisão deve ficar em `reviews.json` no diretório do run. Exemplo de formato:

```json
{
  "direct-answer/1/codex": {
    "status": "passed",
    "before_answer_sha256": "HASH_DA_RESPOSTA_ANTES",
    "after_answer_sha256": "HASH_DA_RESPOSTA_DEPOIS"
  }
}
```

Não marcar como aprovado sem avaliar o aceite do caso. Apresentar as respostas
sem revelar a condição ao revisor quando a avaliação for subjetiva. Depois,
regenerar o relatório:

```sh
python3 scripts/evaluation_report.py evals/local/runs/ID_DO_RUN
```

Modelo desconhecido, alias sem confirmação, falha, uso ausente ou revisão
pendente impedem uma conclusão de economia. Uma única execução válida ainda
não permite generalizar o percentual. Não agregar resultados de clientes,
modelos ou escopos diferentes.

## Ferramentas locais e sessões

```sh
python3 scripts/integration-smoke.py
python3 scripts/integration-smoke.py --run
```

Esse ensaio usa cinco commits sintéticos, valida seus títulos no output normal
e compactado e mede bytes/linhas. O banco RTK fica no diretório temporário por
`RTK_DB_PATH`; o histórico usual não recebe essas medições.

Os hooks são executados diretamente com RTK real, preservando a ausência de
aprovação automática. O MCP recebe somente initialize e é encerrado; a ausência
de índice é verificada. Isso prova funcionamento independente, não carregamento
do hook em uma sessão de agente, uso efetivo do MCP ou navegação em código.

A validação em sessões reais deve abrir ambientes controlados, revisar trust de
hooks, executar a mesma tarefa em cada condição e confirmar as ferramentas nos
eventos. Não usar bypass de trust ou permissões para obter um resultado.

## Antes de apresentar ao CTO

Completar as condições pertinentes em tarefas representativas e repetir
divergências, falhas e casos críticos. Para grafos, registrar separadamente
criação, sincronização e consultas reutilizadas. Medir retrabalho, sucesso e
duração junto com os tokens. Apresentar dispersão e resultados desfavoráveis.

Publicar apenas dados sintéticos ou sanitizados e revisados. Diferenciar bytes
de terminal, tokens observados, estimativa do RTK e custo informado pelo cliente.
Cobrança real exige uma base financeira verificável separada.
