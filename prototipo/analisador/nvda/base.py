"""
Interface trocavel de fala (Fase 4, secao 13 do documento).

O restante da ferramenta so precisa saber que existe algo capaz de falar um
texto. Hoje a unica implementacao real e o NVDA (cliente.py). A interface
existe para que outros sistemas possam ser acrescentados sem tocar na CLI,
e para que os testes usem um falador falso, sem leitor de tela.

Dois tipos de falha, como em llm/base.py:
- ErroFaladorIndisponivel: se repetiria em toda chamada (NVDA fechado, DLL
  ausente, sistema que nao e Windows). Quem usa deve parar e avisar na hora,
  antes de gastar minutos gerando um texto que ninguem vai ouvir.
- ErroFala: falha numa chamada isolada, com o falador ja verificado.
"""
from abc import ABC, abstractmethod


class ErroFala(Exception):
    """Falha ao entregar um texto para ser falado."""


class ErroFaladorIndisponivel(ErroFala):
    """O falador nao pode ser usado agora e nao vai poder na proxima chamada."""


class Falador(ABC):
    """Contrato minimo de quem fala um texto para o usuario."""

    @abstractmethod
    def falar(self, texto: str) -> None:
        """Entrega o texto para ser falado. Texto vazio nao faz nada."""

    def cancelar(self) -> None:
        """Interrompe a fala em andamento, se houver."""

    def verificar(self) -> None:
        """Confere antes do uso se o falador responde.

        Levanta ErroFaladorIndisponivel se nao responder.
        """

    def descricao(self) -> dict:
        """Parametros que identificam esta configuracao, para registro."""
        return {}
