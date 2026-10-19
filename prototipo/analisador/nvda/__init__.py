"""
Fase 4 (secao 13 do documento). Fala: entrega o texto formatado diretamente
ao leitor de tela, que o fala (metodo 4.5.1 do TCC original).

- base.py: interface Falador e erros.
- cliente.py: NvdaFalador, wrapper em ctypes do nvdaControllerClient.dll.
  Roda apenas em Windows, com o NVDA aberto.

Fora do Windows nao ha falador: o NVDA nao existe nesses sistemas, e a CLI
diz isso em palavras em vez de fingir que falou.
"""
from analisador.nvda.base import ErroFala, ErroFaladorIndisponivel, Falador  # noqa: F401
from analisador.nvda.cliente import ErroDllNaoEncontrada, NvdaFalador  # noqa: F401


def criar_falador(backend: str = "nvda", **opcoes) -> Falador:
    """Cria o falador do backend pedido. Ponto unico de troca de falador."""
    if backend == "nvda":
        return NvdaFalador(**opcoes)
    raise ValueError(
        f"Backend de fala desconhecido: {backend!r}. Disponivel por ora: 'nvda'.")
