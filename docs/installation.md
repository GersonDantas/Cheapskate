# Instalação e recuperação no macOS

O instalador requer Python 3.11 ou superior. O perfil completo requer npm
(com Node.js) e pipx para instalar CodeGraph e Graphify quando estiverem ausentes.
Os clientes Codex CLI e Claude Code devem ser instalados e autenticados pelo
usuário. O Cheapskate registra as versões testadas em `dependencies.json`.

## Prévia e aplicação

Execute a partir do clone:

```sh
python3 scripts/cheapskate.py install --dry-run
python3 scripts/cheapskate.py install
```

A primeira chamada mostra os arquivos e as instalações externas previstas. Ela
não cria diretórios, locks ou backups, não baixa pacotes e não consulta sessões.
A segunda pede uma confirmação única. `--yes` dispensa a pergunta e mantém as
validações. Para instalar somente instruções, use `--instructions-only`.

O instalador copia uma lista explícita de arquivos para
`~/.config/ai-instructions` e cria um comando em `~/.local/bin/cheapskate`.
Esse diretório precisa estar no PATH para invocar o comando pelo nome. Também é
possível continuar usando `python3 scripts/cheapskate.py` a partir do clone.

As entradas globais dos agentes preservam instruções preexistentes em arquivos
regulares. Symlinks para a instalação ativa conhecida são substituídos por
arquivos com backup do link; links para outros destinos geram conflito.
O adaptador instalado do Claude contém as instruções completas para evitar
dependência da resolução de imports através de symlinks. O adaptador com imports
relativos continua disponível no repositório para manutenção.

`CODEX_HOME` e `CLAUDE_CONFIG_DIR` são respeitados. `--home /caminho/absoluto`
permite usar um diretório pessoal alternativo para ensaios isolados. Diretórios
pai que sejam symlinks são recusados; use o caminho físico canônico.

## Dependências e integrações

O perfil completo verifica as versões instaladas. Uma versão externa diferente
do manifesto gera diagnóstico e é preservada. Dependências ausentes são
instaladas em runtimes privados e versionados sob
`~/.local/state/cheapskate/runtime`. Os pacotes principais e os arquivos das
skills são verificados por hash antes do uso.

Os hashes fixam os artefatos principais, não toda a resolução de dependências
transitivas feita por npm/pipx. A matriz de compatibilidade ainda requer um teste
independente, especialmente em Intel. Não existe atualização silenciosa de
clientes, modelos, permissões ou dependências externas já instaladas.

RTK recebe dois adaptadores diferentes:

- Claude: reescreve comandos simples via `updatedInput`, sem conceder permissão.
- Codex: fornece a sugestão RTK no contexto; as instruções orientam o agente a
  usar RTK explicitamente nas próximas chamadas. O hook não reescreve nem aprova
  chamadas, pois o contrato Codex exige `allow` para retornar `updatedInput`.

Composição de shell, redirecionamento e substituição permanecem no fluxo normal.
Hooks RTK nativos ou legados reconhecidos são migrados, com backup, para o
adaptador Cheapskate. Hooks desconhecidos ou com matcher incompatível são
recusados. Outros hooks são preservados.

Abra Codex no terminal e revise o hook em `/hooks`. A confiança é uma escolha do
usuário e não é aplicada pelo instalador. Abra novas sessões dos agentes após a
instalação. `check` confirma arquivos e configuração, mas não comprova que o
runtime de cada agente carregou o hook ou que houve redução de tokens.

CodeGraph é registrado como MCP em ambos os clientes. O instalador não cria
índices. Graphify continua explícito e sob demanda. Skills externas existentes
são preservadas e diferenças de revisão são informadas pelo diagnóstico.

## Plugin opcional da equipe

```sh
python3 scripts/cheapskate.py install --with-team --dry-run
python3 scripts/cheapskate.py install --with-team
```

A instalação usa a revisão e o hash do snapshot registrados no manifesto. A
extração ocorre em staging e somente um snapshot completo é promovido. Um plugin
já instalado na versão esperada é preservado, sem repetir os comandos de
registro. A configuração da equipe continua na skill `configurar-equipe`.

Um marketplace com origem diferente é preservado e gera conflito. Adicionar o
plugin depois que `config.toml` passou a ser gerenciado pelo Cheapskate também
gera conflito antes da mutação externa; essa mudança exige reconciliação do
arquivo. Se a equipe for desejada, selecione-a na primeira instalação completa.

O registro externo não pertence à transação de arquivos. Passos concluídos e
pendentes ficam em `external-effects.json`. Se o registro do plugin falhar,
esses efeitos são informados e preservados; a nova execução consulta o estado
antes de retomar. Remover Cheapskate não remove a equipe ou seu marketplace.

## Diagnóstico e atualização

```sh
python3 scripts/cheapskate.py check
python3 scripts/cheapskate.py audit
python3 scripts/cheapskate.py update --dry-run
python3 scripts/cheapskate.py update
```

`check` verifica os arquivos gerenciados e, no perfil completo, ferramentas,
registro de integrações e skills. `audit` também compara com as fontes do clone
usado para executar o comando. Para atualizar fontes, execute `update` a partir
do clone atualizado. O comando instalado compara com sua cópia instalada.

As versões mudam somente após uma alteração explícita do manifesto. Runtimes
gerenciados usam diretórios separados por versão, preservando os anteriores para
recuperação. Uma dependência externa de versão diferente não é substituída.

## Recuperação

```sh
python3 scripts/cheapskate.py rollback --dry-run
python3 scripts/cheapskate.py rollback
python3 scripts/cheapskate.py uninstall --dry-run
python3 scripts/cheapskate.py uninstall
```

`rollback` desfaz somente a última transação de arquivos disponível. Uma operação
interrompida é detectada e precisa de rollback antes de outra instalação.
`uninstall` restaura os originais capturados na primeira instalação, incluindo
modo e symlink. Alterações posteriores bloqueiam a restauração antes de escrever.

O journal e os backups ficam em `~/.local/state/cheapskate`, com acesso privado.
Snapshots são guardados no JSON; podem conter configurações sensíveis e nunca
devem ser publicados. Dependências, snapshots do plugin e diretórios vazios
permanecem após rollback/uninstall. Arquivos alheios não são removidos.

## Validação desta fase

```sh
python3 tests/test_installer.py
sh tests/test-evaluators.sh
python3 tests/test_collect_real_prompts.py
```

Os testes usam diretórios temporários e clientes simulados. A instalação com
ferramentas locais reais e downloads das skills também foi validada em um home
temporário com espaços, cobrindo check/audit, repetição, remoção e rollback.
Execute esse ensaio explicitamente, pois ele acessa a rede:

```sh
python3 tests/smoke_installer.py --run
```

O ensaio reaproveita executáveis presentes no PATH. O registro opcional do
Personal Agent Team também passou no Codex home temporário, incluindo a segunda
instalação. Para reproduzi-lo, acrescente `--with-team`.

A instalação de dependências em uma máquina limpa e os hooks em sessões reais
ainda exigem validação independente antes da release candidate. A medição
quantitativa pertence à próxima fase.

Contratos consultados em 11 de outubro de 2026:

- [Hooks do Codex](https://learn.chatgpt.com/docs/hooks#pretooluse).
- [Hooks do Claude Code](https://code.claude.com/docs/en/hooks#pretooluse-decision-control).
- [RTK v0.46.0](https://github.com/rtk-ai/rtk/releases/tag/v0.46.0).
- [CodeGraph](https://github.com/colbymchenry/codegraph).
- [Graphify 0.9.63](https://pypi.org/project/graphifyy/0.9.63/).
- [Personal Agent Team](https://github.com/GersonDantas/agent-team-configurator).
