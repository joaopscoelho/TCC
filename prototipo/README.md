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
- Fases 3 e 4 (formatacao acessivel definitiva, NVDA e CLI de navegacao):
  pastas criadas com docstrings, sem implementacao.

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

## O que foi e o que nao foi validado

Validado por testes automatizados (87 testes, sem modelo nem rede):
analise estatica, grafo de chamadas, montagem dos prompts, orquestracao,
politica de falhas e CLI (com um LLM falso); cliente do Ollama contra um
servidor HTTP falso que reproduz o formato documentado da API.

**Nao validado:**

- Nenhum teste rodou contra um Ollama ou modelo de verdade. O formato de
  resposta de erro para modelo ausente nao esta descrito na documentacao do
  Ollama; o cliente trata de forma defensiva (status 404 e mensagem do
  servidor), mas o comportamento real precisa ser conferido.
- A qualidade das explicacoes em portugues brasileiro e a obediencia do
  modelo as regras de acessibilidade do prompt nao foram medidas. Esse e o
  trabalho da Fase 3 (verificar a saida) e da avaliacao comparativa de
  modelos.
- O campo `think` (raciocinio) foi escolhido por modelo a partir da
  documentacao (`False` para Qwen3, `"low"` para gpt-oss); nao foi testado.

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
  nvda/, cli/         Fase 4 - fala via NVDA e navegacao (vazios)
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
- **Reprodutibilidade.** Temperatura zero e semente fixa, registradas junto
  com o digest do modelo no `--json`. Nao garante saida identica entre
  versoes do Ollama ou hardwares diferentes.
