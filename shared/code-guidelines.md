# Diretrizes de código

Diretrizes comportamentais para reduzir erros comuns de codificação do LLM. Combine com instruções específicas do projeto conforme necessário.

**Compensação:** essas diretrizes favorecem a cautela em detrimento da velocidade. Para tarefas triviais, use o julgamento.

## 1. Pense antes de codificar

**Não presuma. Não esconda a confusão. Compensações superficiais.**

Antes de implementar:
- Indique explicitamente as suas suposições. Se não tiver certeza, pergunte.
- Se existirem múltiplas interpretações, apresente-as - não escolha silenciosamente.
- Se existir uma abordagem mais simples, diga-o. Empurre para trás quando necessário.
- Se algo não estiver claro, pare. Nomeie o que é confuso. Perguntar.

## 2. Simplicidade em primeiro lugar

**Código mínimo que resolve o problema. Nada especulativo.**

- Não há recursos além do que foi solicitado.
- Sem abstrações para código de uso único.
- Nenhuma “flexibilidade” ou “configurabilidade” que não foi solicitada.
- Sem tratamento de erros para cenários impossíveis.
- Se você escreve 200 linhas e pode ser 50, reescreva.

Pergunte a si mesmo: “Um engenheiro sênior diria que isso é complicado demais?” Se sim, simplifique.

## 3. Alterações Cirúrgicas

**Toque apenas o que você deve. Limpe apenas sua própria bagunça.**

Ao editar o código existente:
- Não "melhore" código, comentários ou formatação adjacentes.
- Não refatore coisas que não estão quebradas.
- Combine o estilo existente, mesmo que você faça de forma diferente.
- Se você notar código morto não relacionado, mencione-o - não o exclua.

Quando suas alterações criam órfãos:
- Remova importações/variáveis/funções que SUAS alterações tornaram não utilizadas.
- Não remova código morto pré-existente, a menos que seja solicitado.

O teste: cada linha alterada deve rastrear diretamente a solicitação do usuário.

## 4. Execução Orientada a Metas

**Definir critérios de sucesso. Faça um loop até ser verificado.**

Transforme tarefas em metas verificáveis:
- "Adicionar validação" → "Escreva testes para entradas inválidas e faça-os passar"
- "Corrigir o bug" → "Escreva um teste que o reproduza e faça-o passar"
- "Refator X" → "Garantir que os testes sejam aprovados antes e depois"

Para tarefas de várias etapas, estabeleça um breve plano:
```
1. [Etapa] → verificar: [verificar]
2. [Etapa] → verificar: [verificar]
3. [Etapa] → verificar: [verificar]
```

Critérios de sucesso fortes permitem que você faça um loop de forma independente. Critérios fracos (“fazer funcionar”) exigem esclarecimento constante.

---

**Essas diretrizes estão funcionando se:** menos alterações desnecessárias nas diferenças, menos reescritas devido a complicações excessivas e perguntas esclarecedoras vierem antes da implementação e não depois de erros.
