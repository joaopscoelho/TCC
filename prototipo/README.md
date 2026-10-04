# Analisador de codigo acessivel - prototipo (TCC II)

Implementa a arquitetura descrita no documento **"TCC - Analise Critica e
Proposta de Evolucao"** (secoes 7, 8, 12 e 13). Nao substitui o documento:
consulte-o para o raciocinio por tras de cada decisao.

## Estado atual

- **Fase 1 (nucleo de analise estatica): funcionando.** Tree-sitter +
  regras de pontos criticos (`analisador/parser`, `analisador/pontos_criticos`),
  com testes passando sobre o fixture da secao 12 (`testes/`).
- Fases 2-6: pastas e modulos criados com docstrings, ainda sem
  implementacao (`analisador/contexto`, `analisador/llm`,
  `analisador/formatacao`, `analisador/nvda`, `analisador/cli`).

## Como rodar (Windows, PowerShell)

```powershell
cd prototipo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH = "."
pytest testes/ -v
```

> O ambiente usado para escrever e testar a Fase 1 foi um Linux de
> verificacao (nao fica salvo aqui). No seu Windows, crie seu proprio
> `.venv` com os comandos acima antes de rodar.

## Antes da Fase 2 (API do Claude)

1. Criar conta em console.anthropic.com e configurar billing (separado do
   plano Pro do claude.ai - ver secao 7 do documento para o porque).
2. Copiar `.env.example` para `.env` e colar a chave gerada - o `.env`
   nunca e commitado (ja esta no `.gitignore`).

## Estrutura

```
analisador/
  parser/           Fase 1 - AST via Tree-sitter
  pontos_criticos/  Fase 1 - regras deterministicas (lista fechada, secao 8)
  contexto/         Fase 2 - monta o mapa estrutural para o prompt
  llm/              Fase 2 - interface ExplicadorLLM + implementacao Claude API
  formatacao/       Fase 3 - texto acessivel (sem tabelas/simbolos pesados)
  nvda/             Fase 4 - envio direto de fala via NVDA Controller Client
  cli/              Fase 4 - comandos de terminal e navegacao por etapas
testes/
  fixtures/         codigo de exemplo (cadastro funcionario/empresa/setor, secao 12)
```
