"""
Fala via NVDA: wrapper em ctypes do nvdaControllerClient.dll (metodo 4.5.1
do TCC original).

O NVDA Controller Client e uma biblioteca do proprio NV Access que envia
texto ao NVDA em execucao. Ela e distribuida a parte (arquivo
controllerClient.zip das versoes do NVDA) sob LGPL 2.1, por isso a DLL nao
vai para o repositorio: ver bibliotecas/LEIA-ME.md.

Decisoes:
- A DLL precisa ter a mesma arquitetura do Python em uso (x64 com Python 64
  bits, por exemplo). O carregamento diz isso em palavras quando falha.
- So as funcoes antigas e estaveis sao usadas (testIfRunning, speakText,
  cancelSpeech). As mais novas (como speakSsml) falham com NVDA antigo.
- Sem DLL, sem Windows ou sem NVDA aberto o erro e dito em palavras, nunca
  silenciado: quem usa a ferramenta sem ver a tela nao teria como perceber
  que o texto nao foi falado.
- Nao ha tentativa de reconexao nem de fala em outro programa: o falador
  falha e a CLI entrega o texto de qualquer forma.
"""
import ctypes
import os
import platform
import struct
import sys
from pathlib import Path

from analisador.nvda.base import ErroFala, ErroFaladorIndisponivel, Falador

NOME_DLL = "nvdaControllerClient.dll"
VARIAVEL_DLL = "NVDA_CONTROLLER_DLL"
PASTA_BIBLIOTECAS = Path(__file__).resolve().parents[2] / "bibliotecas"

FUNCOES = (
    "nvdaController_testIfRunning",
    "nvdaController_speakText",
    "nvdaController_cancelSpeech",
)


class ErroDllNaoEncontrada(ErroFaladorIndisponivel):
    """A nvdaControllerClient.dll nao esta onde a ferramenta procurou."""


def _e_windows() -> bool:
    return sys.platform == "win32"


def _exigir_windows():
    if not _e_windows():
        raise ErroFaladorIndisponivel(
            "O NVDA so existe no Windows: neste sistema "
            f"({sys.platform}) a fala via NVDA nao esta disponivel.")


def arquitetura_python() -> str:
    """Arquitetura do Python em uso: x64, x86 ou arm64 (nome das pastas do zip)."""
    if platform.machine().lower() in ("arm64", "aarch64"):
        return "arm64"
    return "x64" if struct.calcsize("P") == 8 else "x86"


def localizar_dll(caminho=None) -> Path:
    """Acha a DLL: caminho dado, variavel de ambiente ou pasta bibliotecas.

    Um caminho dado de forma explicita (argumento ou variavel) nunca cai em
    outro lugar: se estiver errado, o erro aponta para ele. Sem caminho
    explicito, procura em bibliotecas/ e em bibliotecas/<arquitetura>/.
    """
    explicito = caminho or os.environ.get(VARIAVEL_DLL)
    if explicito:
        candidatos = [Path(explicito)]
    else:
        candidatos = [PASTA_BIBLIOTECAS / NOME_DLL,
                      PASTA_BIBLIOTECAS / arquitetura_python() / NOME_DLL]

    for candidato in candidatos:
        if candidato.is_file():
            return candidato

    procurado = "; ".join(str(c) for c in candidatos)
    raise ErroDllNaoEncontrada(
        f"A biblioteca {NOME_DLL} nao foi encontrada. Procurei em: {procurado}. "
        "Baixe o arquivo controllerClient.zip das versoes do NVDA, extraia e "
        f"copie o {NOME_DLL} da pasta {arquitetura_python()} para "
        f"{PASTA_BIBLIOTECAS}, ou indique o caminho com --dll ou com a "
        f"variavel {VARIAVEL_DLL}.")


def carregar_biblioteca(caminho):
    """Carrega a DLL e declara os tipos das funcoes usadas."""
    _exigir_windows()
    try:
        dll = ctypes.WinDLL(str(caminho))
    except OSError as erro:
        raise ErroFaladorIndisponivel(
            f"Nao foi possivel carregar {caminho}: {erro}. A biblioteca "
            "precisa ter a mesma arquitetura do Python em uso "
            f"({arquitetura_python()}).") from erro

    for nome in FUNCOES:
        if not hasattr(dll, nome):
            raise ErroFaladorIndisponivel(
                f"A biblioteca {caminho} nao oferece a funcao {nome}: o "
                f"arquivo nao parece ser o {NOME_DLL} do NVDA.")

    # error_status_t e um codigo de erro do Windows: 0 e sucesso.
    for nome in FUNCOES:
        getattr(dll, nome).restype = ctypes.c_ulong
    dll.nvdaController_testIfRunning.argtypes = []
    dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
    dll.nvdaController_cancelSpeech.argtypes = []
    return dll


def _descrever_codigo(codigo: int) -> str:
    """Codigo de erro do Windows com a mensagem do sistema, quando existir."""
    formatar = getattr(ctypes, "FormatError", None)  # so existe no Windows
    mensagem = ""
    if formatar is not None:
        try:
            mensagem = formatar(codigo).strip()
        except (OSError, ValueError, OverflowError):
            mensagem = ""
    return f"erro {codigo}: {mensagem}" if mensagem else f"erro {codigo}"


class NvdaFalador(Falador):
    """Fala o texto pelo NVDA que esta em execucao neste computador.

    biblioteca existe para os testes: qualquer objeto com as tres funcoes
    de FUNCOES substitui a DLL, e entao nada exige Windows nem NVDA.
    """

    def __init__(self, caminho_dll=None, biblioteca=None):
        self._caminho = None
        if biblioteca is None:
            _exigir_windows()
            self._caminho = localizar_dll(caminho_dll)
            biblioteca = carregar_biblioteca(self._caminho)
        self._dll = biblioteca

    def verificar(self) -> None:
        codigo = self._dll.nvdaController_testIfRunning()
        if codigo != 0:
            raise ErroFaladorIndisponivel(
                f"Nao foi possivel falar com o NVDA ({_descrever_codigo(codigo)}). "
                "Confira se o NVDA esta aberto e com a fala ligada.")

    def falar(self, texto: str) -> None:
        if not texto or not texto.strip():
            return
        codigo = self._dll.nvdaController_speakText(texto)
        if codigo != 0:
            raise ErroFala(
                f"O NVDA nao aceitou o texto para falar ({_descrever_codigo(codigo)}).")

    def cancelar(self) -> None:
        codigo = self._dll.nvdaController_cancelSpeech()
        if codigo != 0:
            raise ErroFala(
                f"O NVDA nao conseguiu interromper a fala ({_descrever_codigo(codigo)}).")

    def descricao(self) -> dict:
        return {"backend": "nvda",
                "dll": str(self._caminho) if self._caminho else None}
