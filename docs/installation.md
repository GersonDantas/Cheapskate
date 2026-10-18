# Instalação e recuperação no macOS

## Assistente inicial

O assistente inicial prepara os pré-requisitos para uma instalação completa a
partir de uma cópia local do projeto. Ele funciona antes de haver Python 3.11
na máquina. Obtenha o repositório por clone ou pelo ZIP do GitHub, abra o
diretório e execute:

```sh
bash scripts/bootstrap.sh --dry-run
bash scripts/bootstrap.sh
```

A prévia detecta Homebrew, Python 3.11+, Node.js/npm, pipx, Codex CLI e Claude
Code; mostra o estado de cada um e as instalações necessárias. A segunda
chamada pede confirmação antes de instalar. Se algum pacote precisar de
Homebrew e ele estiver ausente, baixa o instalador do projeto oficial e o
executa. Homebrew instala os pacotes e os casks ausentes. A instalação pode
pedir a senha de administrador e acesso à rede. Após falha nos pacotes ou no
login, reexecute o comando: ele detecta os passos já concluídos. Se a falha
ocorrer na transação do instalador Cheapskate, siga a seção Recuperação.

O assistente prepara Homebrew e `~/.local/bin` no PATH do shell zsh, bash ou
fish, sem substituir outras configurações. Recusa perfis que sejam symlinks.
Abra um novo terminal depois da instalação. Para outro shell, siga a
instalação manual abaixo.
Clientes já presentes são preservados, inclusive quando estão em
`~/.local/bin` fora do PATH inicial.

Após instalar os programas, o assistente consulta `codex login status` e
`claude auth status` sem mostrar ou salvar a saída. Se necessário, abre
`codex login` e `claude auth login` para o usuário autenticar no navegador.
Ele confirma o estado novamente e interrompe se o login não terminar. As
credenciais permanecem sob controle dos próprios clientes.

Por fim, o assistente mostra a prévia do instalador Cheapskate, pede a
confirmação própria dessa etapa, instala instruções e integrações e executa
`check`. Ele não substitui o instalador transacional descrito abaixo.
Homebrew, pacotes externos, perfil de shell e logins persistem após
`rollback` ou `uninstall` do Cheapskate. As versões de clientes registradas em
`dependencies.json` são as testadas, enquanto os casks podem entregar versões
mais novas.

## Prévia e aplicação

Para executar apenas o instalador existente a partir do clone, use um Python
3.11 ou superior disponível no PATH. Prepare manualmente npm, pipx, Codex CLI,
Claude Code e os logins antes desta etapa se não usar o assistente:

```sh
python3 scripts/cheapskate.py install --dry-run
python3 scripts/cheapskate.py install
```

Se `python3` ainda apontar para uma versão antiga, substitua-o por `python3.11`
ou pelo caminho de outro Python 3.11+.

A primeira chamada mostra os arquivos e as instalações externas previstas. Ela
não cria diretórios, locks ou backups, não baixa pacotes e não consulta sessões.
A segunda pede uma confirmação única. `--yes` dispensa a pergunta e mantém as
validações. Para instalar somente instruções, use `--instructions-only`.

O instalador copia uma lista explícita de arquivos para
`~/.config/ai-instructions` e cria um comando em `~/.local/bin/cheapskate`.
O assistente inicial inclui esse diretório no PATH. Na instalação manual,
configure o PATH para invocar o comando pelo nome. Também é possível continuar
usando o caminho do interpretador Python validado a partir do clone.

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
transitivas feita por npm/pipx. O assistente inicial usa os pacotes correntes
do Homebrew; ele não fixa seus artefatos pelo manifesto do Cheapskate. A matriz
de compatibilidade ainda requer um teste independente, especialmente em Intel.
Clientes existentes, modelos e permissões não são atualizados silenciosamente.

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
python3 tests/test_bootstrap.py
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

A coordenação do assistente foi validada com comandos simulados, inclusive sem
Homebrew ou Python e com falhas intermediárias. A instalação real em uma máquina
limpa e os hooks em sessões reais ainda exigem validação independente antes da
release candidate. A medição
quantitativa pertence à próxima fase.

Contratos consultados em 11 de outubro de 2026:

- [Hooks do Codex](https://learn.chatgpt.com/docs/hooks#pretooluse).
- [Hooks do Claude Code](https://code.claude.com/docs/en/hooks#pretooluse-decision-control).
- [RTK v0.46.0](https://github.com/rtk-ai/rtk/releases/tag/v0.46.0).
- [CodeGraph](https://github.com/colbymchenry/codegraph).
- [Graphify 0.9.63](https://pypi.org/project/graphifyy/0.9.63/).
- [Personal Agent Team](https://github.com/GersonDantas/agent-team-configurator).

Contratos do assistente consultados em 18 de outubro de 2026:

- [Instalação do Homebrew](https://docs.brew.sh/Installation) e [shellenv](https://docs.brew.sh/Manpage#shellenv-shell-).
- [Python 3.11](https://formulae.brew.sh/formula/python@3.11), [Node.js](https://formulae.brew.sh/formula/node) e [pipx](https://formulae.brew.sh/formula/pipx) no Homebrew.
- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) e [autenticação](https://learn.chatgpt.com/docs/auth).
- [Instalação do Claude Code](https://code.claude.com/docs/en/setup) e [comandos de autenticação](https://code.claude.com/docs/en/cli-reference).
