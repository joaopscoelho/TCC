"""
Fase 2 (secao 13 do documento). Interface ExplicadorLLM (trocavel, secao 7)
e as implementacoes de modelo.

- base.py: interface, mensagens, resposta e hierarquia de erros.
- prompts.py: prompt de visao geral e prompt por regiao, com as regras de
  acessibilidade e a marcacao de incerteza embutidas.
- local.py: modelo local via Ollama, custo zero (implementado).

A implementacao para a API do Claude (ANTHROPIC_API_KEY, ver .env.example)
fica adiada: por ora o projeto usa apenas modelos locais e abertos.
"""
from analisador.llm.base import (  # noqa: F401
    ErroConfiguracaoLLM, ErroContextoExcedido, ErroLLM, ErroModeloAusente,
    ErroRespostaVazia, ErroServidorIndisponivel, ErroTempoEsgotado,
    ExplicadorLLM, Mensagem, RespostaLLM, estimar_tokens,
)
from analisador.llm.local import ExplicadorLocal


def criar_explicador(backend: str = "local", **opcoes) -> ExplicadorLLM:
    """Cria o explicador do backend pedido. Ponto unico de troca de modelo."""
    if backend == "local":
        return ExplicadorLocal(**opcoes)
    raise ValueError(
        f"Backend desconhecido: {backend!r}. Disponivel por ora: 'local'.")
