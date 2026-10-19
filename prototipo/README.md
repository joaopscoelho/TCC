# Analisador de codigo acessivel - prototipo (TCC II)

Implementa a arquitetura descrita no documento **"TCC - Analise Critica e
Proposta de Evolucao"** (secoes 7, 8, 12 e 13). Nao substitui o documento:
consulte-o para o raciocinio por tras de cada decisao.

## Estado atual

- **Fase 1 (nucleo de analise estatica): funcionando.** Tree-sitter, regras
  de pontos criticos, aviso de erro de sintaxe, varredura de projeto
  inteiro e agrupamento da saida por funcao envolvente.
- **Fase 2, parte deterministica: funcionando.** Mapa estrutural do projeto
  (`analisador/contexto`): definicoes, imports e grafo local de chamadas
  entre arquivos.
- **Fase 2, parte LLM: implementada para modelo local (Ollama), NAO
  validada com modelo real.** Ver "O que foi e o que nao foi validado".
  A implementacao para a API do Claude esta adiada: por ora so modelos
  locais e abertos.
- **Fase 4, fala via NVDA (so Windows): implementada, NAO validada com o
  NVDA real.** Ver "Fala via NVDA (Windows)".
- Fase 3 (formatacao acessivel definitiva) e CLI de navegacao: pastas
  criadas com docstrings, sem implementacao.

O escopo de analise e o **projeto inteiro**, nao um arquivo isolado.

## Como rodar

Windows (PowerShell):

```powershell
cd prototipo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH = "."
pytest testes/ -v
```

Se a pasta `.venv` ja existir e tiver sido criada em Linux ou macOS (tem
`bin/` em vez de `Scripts/`), apague-a antes: ela e ignorada pelo git e o
Windows nao a usa.

Atalho no Windows: `powershell -ExecutionPolicy Bypass -File .\preparar_windows.ps1`
faz os passos acima (acha o Python mesmo sem PATH), roda os testes, confere o
NVDA e a DLL e grava tudo em `preparar_windows.log`. Com `-Falar`, o NVDA
fala uma frase de teste.

macOS ou Linux:

```bash
cd prototipo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest testes/ -v
```

Analise estatica (sem modelo, sem rede):

```bash
PYTHONPATH=. python -m analisador caminho/do/projeto
PYTHONPATH=. python -m analisador caminho/do/projeto --json
```

## Explicacao com modelo local (Ollama)

1. Instalar o Ollama (ollama.com) e abrir o aplicativo.
2. Baixar o modelo padrao, pensado para 16 GB de memoria:

```bash
ollama pull qwen3:8b
```

3. Rodar com `--explicar`:

```bash
PYTHONPATH=. python -m analisador caminho/do/projeto --explicar
PYTHONPATH=. python -m analisador caminho/do/projeto --explicar --modelo qwen3:14b
PYTHONPATH=. python -m analisador caminho/do/projeto --explicar --max-regioes 3
```

Cada explicacao leva de segundos a minutos no hardware local; o progresso
vai para a saida de erro ("Gerando explicacao 2 de 5..."). Se o Ollama nao
estiver no ar ou o modelo nao tiver sido baixado, o erro e dito em palavras,
a analise estatica e entregue mesmo assim e o codigo de saida e 2.

Opcoes: `--modelo`, `--host`, `--contexto` (padrao 8192 tokens),
`--max-regioes`. Tambem valem as variaveis `ANALISADOR_MODELO` e
`OLLAMA_HOST`.

Modelos candidatos para 16 GB (tamanhos segundo a biblioteca do Ollama;
confira com `ollama list` e meca no seu Mac):

- `qwen3:8b` - padrao. Cabe com folga, treinado em 119 idiomas.
- `qwen3:14b` - mais qualidade, ocupa mais memoria.
- `gpt-oss:20b` - cerca de 14 GB: cabe no papel, mas deixa pouca folga para
  o sistema, e avaliacao independente (Bi et al., 2025, arXiv:2508.12461)
  aponta fraqueza fora do ingles.

## Modelo em nuvem (Ollama cloud)

Alem dos modelos locais, o mesmo cliente chama modelos hospedados no
ollama.com, como o `gemma4:31b`. A pagina do modelo lista tambem as tags
`gemma4:cloud` e `gemma4:31b-cloud`. **O codigo analisado sai do seu
computador neste modo.** A documentacao do Ollama diz que prompts e respostas
da nuvem nao sao usados para treinar modelos e nao informa prazo de retencao.
Teste com codigo de exemplo, nunca com codigo privado, e registre no texto do
TCC que o argumento de privacidade da execucao local nao vale para este modo.

1. Crie uma chave de API em ollama.com/settings/keys.
2. Defina a chave so na sessao do terminal. Nunca no codigo, em arquivo
   versionado ou em conversa:

```powershell
$env:OLLAMA_API_KEY = "cole-a-chave-aqui"
```

3. Confira o nome exato do modelo na lista do servidor e rode:

```powershell
(Invoke-RestMethod https://ollama.com/api/tags).models.name | Select-String gemma
python -m analisador caminho\do\projeto --explicar --host https://ollama.com --modelo gemma4:31b
```

A chave so e enviada ao host `ollama.com`. Sem a chave o erro aparece na hora,
e uma chave recusada (401 ou 403) interrompe a geracao. Na API direta o nome do
modelo e o da lista do servidor (`gemma4:31b`); no aplicativo ou na CLI do
Ollama instalado o sufixo e `:cloud` (`gemma4:31b-cloud`). Os limites de uso
dependem do plano: ver ollama.com/pricing e ollama.com/settings/usage.

## Fala via NVDA (Windows)

Requisitos: Windows, Python e NVDA com a mesma arquitetura da DLL, NVDA
aberto e a DLL `nvdaControllerClient.dll` do NV Access (LGPL 2.1, por isso
fora do git). Passo a passo em `bibliotecas/LEIA-ME.md`.

```powershell
python -m analisador caminho\do\projeto --falar
python -m analisador caminho\do\projeto --explicar --falar
python -m analisador caminho\do\projeto --falar --dll C:\outro\nvdaControllerClient.dll
```

O relatorio e impresso como sempre e tambem enviado ao NVDA em uma unica
chamada. O NVDA e conferido **antes** da analise e do modelo, para o erro
aparecer em segundos. Se o NVDA, a DLL ou o Windows faltarem, o erro e
dito em palavras, o relatorio sai so como texto e o codigo de saida e 3
(codigo 2 continua sendo falha do modelo e tem prioridade). `--falar` nao
se combina com `--json`.

Fora do Windows nao ha falador: o NVDA nao existe em macOS nem em Linux.
A interface `Falador` (`analisador/nvda/base.py`) deixa espaco para outro
sistema de fala, ainda nao implementado.

## O que foi e o que nao foi validado

Validado por testes automatizados (122 testes, sem modelo, rede, NVDA nem
Windows): analise estatica, grafo de chamadas, montagem dos prompts,
orquestracao, politica de falhas e CLI (com um LLM falso); cliente do
Ollama contra um servidor HTTP falso que reproduz o formato documentado
da API; falador do NVDA contra uma DLL falsa, busca da DLL e opcao
`--falar` da CLI com um falador falso; chave de API da nuvem enviada so ao
host `ollama.com`.

**Nao validado:**

- NVDA: em 18/10/2026 a DLL x64 carregou e `testIfRunning` respondeu com o
  NVDA aberto, e o autor informou que o NVDA esta funcionando. Ainda sem
  registro: a versao do NVDA; se o relatorio inteiro vai em uma chamada ou
  ha limite de tamanho; se chamadas seguidas se enfileiram ou se
  interrompem; se o terminal, ao imprimir o mesmo texto, faz o NVDA falar
  em duplicidade; e o que acontece com o Windows bloqueado (a documentacao
  do NV Access manda conferir isso antes de enviar texto).
- Nuvem do Ollama: uma execucao real em 18/10/2026 (gemma4:31b, host
  ollama.com, projeto_exemplo, duas regioes) funcionou. O nome do modelo, a
  chave e o campo `think: false` foram aceitos, e a geracao levou 3,4
  segundos no total. O formato real do erro de chave recusada nao foi
  conferido.
- Nenhum teste rodou contra um Ollama local. O formato de resposta de erro
  para modelo ausente nao esta descrito na documentacao do Ollama; o
  cliente trata de forma defensiva (status 404 e mensagem do servidor),
  mas o comportamento real precisa ser conferido.
- A qualidade das explicacoes em portugues brasileiro e a obediencia do
  modelo as regras de acessibilidade do prompt nao foram medidas de forma
  sistematica. Uma amostra de tres textos do gemma4:31b na nuvem manteve o
  marcador de inferencia, usou frases de ate vinte palavras e nao usou
  simbolos decorativos, mas deixou um sublinhado em um nome de funcao e deu
  a uma gravidade uma justificativa que nao consta nos dados enviados. A
  medicao sistematica e o trabalho da Fase 3 (verificar a saida) e da
  avaliacao comparativa de modelos.
- O campo `think` (raciocinio) foi escolhido por modelo a partir da
  documentacao (`False` por padrao, `"low"` para gpt-oss). So o `False` com
  gemma4:31b na nuvem foi exercitado.

## Estrutura

```
analisador/
  parser/
    ast_parser.py     AST via Tree-sitter, helpers e erros de sintaxe
    varredura.py      descoberta e parse de todos os .py do projeto
  pontos_criticos/
    regras.py         regras deterministicas (lista fechada, secao 8)
    agrupamento.py    agrupa os pontos por funcao envolvente
  contexto/
    estrutura.py      definicoes, imports e chamadas de um arquivo
    mapa.py           MapaProjeto: grafo de chamadas e contexto por linha
    trechos.py        codigo da regiao, com numero de linha, para o prompt
  llm/
    base.py           interface ExplicadorLLM, mensagens, erros
    prompts.py        prompt de visao geral e prompt por regiao
    local.py          ExplicadorLocal: Ollama, sem dependencia nova
  analise.py          orquestracao: parser + contexto + regras
  explicacao.py       orquestracao: visao geral + uma explicacao por regiao
  __main__.py         runner: python -m analisador <caminho> [--explicar]
  formatacao/         Fase 3 - texto acessivel definitivo (vazio)
  nvda/
    base.py           interface Falador e erros
    cliente.py        NvdaFalador: ctypes sobre o nvdaControllerClient.dll
  cli/                Fase 4 - navegacao por etapas (vazio)
bibliotecas/          nvdaControllerClient.dll, baixada a parte (fora do git)
testes/
  conftest.py                    fixtures e servidor Ollama falso
  ollama_falso.py                servidor HTTP falso (formato documentado)
  test_parser.py                 parse, erro de sintaxe, varredura
  test_pontos_criticos.py        regras e filtros de falso positivo
  test_contexto.py               definicoes, imports, grafo, regressoes
  test_agrupamento.py            reducao de ruido na saida
  test_analise.py                ponta a ponta e formato do relatorio
  test_llm_local.py              cliente do Ollama e traducao de erros
  test_prompts.py                conteudo dos prompts
  test_explicacao.py             orquestracao e CLI com LLM falso
  test_nvda.py                   falador do NVDA com DLL falsa e CLI --falar
  fixtures/
    exemplo_funcionarios.py      fixture original, arquivo unico
    projeto_exemplo/             tres arquivos que se importam (secao 12)
    projeto_quebrado/            arquivo invalido de proposito
```

## Decisoes registradas

- **Erro de sintaxe e reportado, nao ignorado.** O Tree-sitter devolve
  arvore parcial para codigo invalido; sem o aviso, a ferramenta analisaria
  um arquivo incompleto em silencio. Como o publico-alvo nao enxerga a tela
  do editor, esse aviso e requisito, nao detalhe.
- **Verbos ambiguos exigem evidencia.** `get`, `post`, `save` e `query` so
  contam como dependencia externa em arquivos que importam biblioteca de
  rede ou de banco. Rodar o analisador sobre o proprio prototipo mostrou
  todo `dicionario.get` classificado como dependencia externa de severidade
  5: falso positivo que destroi a confianca na lista.
- **Literais triviais sao filtrados.** `0`, `1`, `None` e comparacao com
  booleano sao idiomas da linguagem, nao regra de negocio.
- **A saida e agrupada por funcao, nao achatada.** Nenhum ponto e
  descartado no agrupamento.
- **Resolucao de chamadas por nome simples.** Sem inferencia de tipos, a
  prioridade e o proprio arquivo e depois os arquivos importados; casos
  ambiguos ficam registrados em `MapaProjeto.ambiguas`.
- **Codigo de modulo tem chave propria no grafo.** Chamadas fora de qualquer
  funcao eram guardadas como `None`, o que quebrava a ordenacao
  (`TypeError`) quando uma funcao era chamada por outra funcao e pelo
  modulo. Chamadas de modulo (`if __name__ == "__main__": main()`) nao
  contam como chamador ao decidir pontos de entrada, e metodos como
  `__init__` nunca sao pontos de entrada.
- **API nativa do Ollama, nao o endpoint compativel com a OpenAI.** A
  documentacao do Ollama afirma que a API da OpenAI nao tem como definir o
  tamanho de contexto, e o padrao do Ollama abaixo de 24 GiB e 4k tokens.
  A API nativa aceita `num_ctx`, `seed` e `temperature` por requisicao.
- **Prompt grande demais e recusado, nao truncado.** O cliente estima os
  tokens e recusa o que nao cabe no contexto configurado; a documentacao
  nao descreve o que o Ollama faz com um prompt que excede o contexto.
- **Dois tipos de falha.** Erro de configuracao (servidor fora do ar,
  modelo ausente) interrompe tudo na hora; erro isolado (resposta vazia,
  tempo esgotado) afeta so a regiao, que e declarada sem explicacao em vez
  de omitida.
- **Regras de acessibilidade no prompt, nao so no pos-processamento.**
  Pedir a forma certa de primeira produz texto melhor que limpar texto
  errado depois. A Fase 3 vai conferir se o modelo obedeceu.
- **Inferencia tem marcador fixo.** Regra de negocio deduzida de nomes abre
  com a palavra "Inferência:". Quem ouve por sintese de voz nao consegue
  ver que algo e suposicao; precisa ouvir. Por ser palavra fixa, a Fase 3
  pode verificar a marcacao automaticamente.
- **Fala conferida antes, falha dita em palavras.** O NVDA e verificado
  antes da analise. Sem DLL, sem Windows ou sem NVDA aberto nao ha
  substituto silencioso: quem usa sem ver a tela nao perceberia que nada
  foi falado. O texto sai impresso de qualquer forma.
- **Reprodutibilidade.** Temperatura zero e semente fixa, registradas junto
  com o digest do modelo no `--json`. Nao garante saida identica entre
  versoes do Ollama ou hardwares diferentes.
