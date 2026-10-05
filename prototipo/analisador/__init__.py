"""
Analisador de codigo acessivel -- prototipo do TCC II.

Arquitetura por fases (secao 13 do documento "TCC - Analise Critica e
Proposta de Evolucao"):

- parser/           Fase 1: AST via Tree-sitter, erros de sintaxe, varredura
- pontos_criticos/  Fase 1: regras deterministicas e agrupamento
- contexto/         Fase 2: mapa estrutural e grafo local de chamadas
- analise.py        orquestracao das fases deterministicas
- llm/              Fase 2: explicacao via API do Claude
- formatacao/       Fase 3: texto acessivel
- nvda/, cli/       Fase 4: fala via NVDA e navegacao por etapas
"""
