"""
Interface trocavel de LLM e erros comuns (secao 7 do documento).

Toda implementacao (Ollama local agora, API do Claude depois) precisa
apenas cumprir ExplicadorLLM.gerar: receber mensagens, devolver texto. O
restante da ferramenta -- prompts, orquestracao, CLI -- nao sabe qual
modelo esta por tras. Trocar de modelo e trocar uma linha, e e isso que
torna possivel a comparacao entre modelos prevista para o TCC.

Os erros se dividem em dois grupos, porque o tratamento e diferente:
- ErroConfiguracaoLLM: se repetiria em toda chamada (servidor fora do ar,
  modelo nao baixado). A geracao deve parar na hora.
- ErroLLM comum: afeta so aquela regiao (resposta vazia, prompt grande
  demais, tempo esgotado). As demais regioes ainda podem ser explicadas.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ErroLLM(Exception):
    """Falha ao gerar o texto de uma regiao; as outras ainda podem ser tentadas."""


class ErroConfiguracaoLLM(ErroLLM):
    """Falha que se repetiria em toda chamada: a geracao deve ser interrompida."""


class ErroServidorIndisponivel(ErroConfiguracaoLLM):
    """Nao foi possivel conectar ao servidor do modelo."""


class ErroModeloAusente(ErroConfiguracaoLLM):
    """O servidor esta no ar, mas nao tem o modelo pedido."""


class ErroContextoExcedido(ErroLLM):
    """O prompt nao cabe na janela de contexto configurada."""


class ErroRespostaVazia(ErroLLM):
    """O modelo terminou sem produzir texto."""


class ErroTempoEsgotado(ErroLLM):
    """O servidor demorou mais que o limite configurado para responder."""


@dataclass
class Mensagem:
    """Uma mensagem da conversa: papel e "system", "user" ou "assistant"."""

    papel: str
    conteudo: str


@dataclass
class RespostaLLM:
    """Texto gerado e os metadados necessarios para reproduzir e comparar."""

    texto: str
    modelo: str
    tokens_prompt: int = None
    tokens_resposta: int = None
    duracao_s: float = None
    motivo_fim: str = None
    avisos: list = field(default_factory=list)

    @property
    def cortada(self) -> bool:
        """True quando o modelo parou por limite de tamanho, nao por conclusao."""
        return self.motivo_fim == "length"

    def to_dict(self):
        return {
            "modelo": self.modelo,
            "tokens_prompt": self.tokens_prompt,
            "tokens_resposta": self.tokens_resposta,
            "duracao_s": self.duracao_s,
            "motivo_fim": self.motivo_fim,
            "avisos": list(self.avisos),
        }


def estimar_tokens(texto: str) -> int:
    """Estimativa conservadora de tokens: um token a cada tres caracteres.

    Tokenizadores reais ficam entre tres e quatro caracteres por token em
    portugues e piores em codigo. Errar para cima e proposital: a estimativa
    so serve para recusar prompts que provavelmente nao cabem.
    """
    return -(-len(texto) // 3)


class ExplicadorLLM(ABC):
    """Contrato minimo de um modelo de linguagem."""

    @abstractmethod
    def gerar(self, mensagens) -> RespostaLLM:
        """Gera uma resposta para a lista de Mensagem."""

    def verificar(self) -> dict:
        """Confere antes da geracao se o modelo esta acessivel.

        Levanta ErroConfiguracaoLLM se nao estiver. Devolve metadados de
        reproducibilidade (por exemplo o digest do modelo) quando existirem.
        """
        return {}

    def descricao(self) -> dict:
        """Parametros que identificam esta configuracao, para registro."""
        return {}
