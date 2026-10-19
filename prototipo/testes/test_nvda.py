"""
Fala via NVDA e opcao --falar da CLI, sem NVDA, sem DLL e sem Windows:
a DLL e substituida por um objeto falso e o falador da CLI por um falso.
Nada aqui prova que o NVDA de verdade fala; isso so se confere no Windows,
com o NVDA aberto (ver README, "O que nao foi validado").
"""
import json
import sys

import pytest

import analisador.__main__ as cli
import analisador.nvda.cliente as cliente
from analisador.analise import analisar
from analisador.nvda import (
    ErroDllNaoEncontrada, ErroFala, ErroFaladorIndisponivel, Falador, NvdaFalador,
    criar_falador,
)
from testes.test_explicacao import LLMFalso

RPC_SERVIDOR_INDISPONIVEL = 1722


class DllFalsa:
    """Imita as funcoes exportadas pelo nvdaControllerClient.dll."""

    def __init__(self, em_execucao=0, fala=0, cancela=0):
        self.em_execucao = em_execucao
        self.fala = fala
        self.cancela = cancela
        self.faladas = []
        self.cancelamentos = 0

    def nvdaController_testIfRunning(self):
        return self.em_execucao

    def nvdaController_speakText(self, texto):
        self.faladas.append(texto)
        return self.fala

    def nvdaController_cancelSpeech(self):
        self.cancelamentos += 1
        return self.cancela


class FaladorFalso(Falador):
    def __init__(self, erro_verificar=None, erro_falar=None, eventos=None):
        self.erro_verificar = erro_verificar
        self.erro_falar = erro_falar
        self.eventos = eventos if eventos is not None else []
        self.faladas = []

    def verificar(self):
        self.eventos.append("verificar")
        if self.erro_verificar is not None:
            raise self.erro_verificar

    def falar(self, texto):
        self.eventos.append("falar")
        if self.erro_falar is not None:
            raise self.erro_falar
        self.faladas.append(texto)


# ------------------------------------------------------------ NvdaFalador

def test_verificar_aceita_nvda_em_execucao():
    NvdaFalador(biblioteca=DllFalsa()).verificar()


def test_verificar_diz_em_palavras_quando_o_nvda_nao_responde():
    falador = NvdaFalador(biblioteca=DllFalsa(em_execucao=RPC_SERVIDOR_INDISPONIVEL))
    with pytest.raises(ErroFaladorIndisponivel) as erro:
        falador.verificar()
    mensagem = str(erro.value)
    assert "NVDA" in mensagem and "aberto" in mensagem
    assert str(RPC_SERVIDOR_INDISPONIVEL) in mensagem


def test_falar_envia_o_texto_inteiro_em_uma_chamada():
    dll = DllFalsa()
    texto = "Regiao 1 de 2: salvar.\nPonto critico 1 de 1: tratamento de excecao."
    NvdaFalador(biblioteca=dll).falar(texto)
    assert dll.faladas == [texto]


def test_falar_ignora_texto_vazio():
    dll = DllFalsa()
    falador = NvdaFalador(biblioteca=dll)
    falador.falar("")
    falador.falar("   \n ")
    assert dll.faladas == []


def test_falha_ao_falar_vira_erro_de_fala_nao_de_indisponibilidade():
    falador = NvdaFalador(biblioteca=DllFalsa(fala=5))
    with pytest.raises(ErroFala) as erro:
        falador.falar("ola")
    assert not isinstance(erro.value, ErroFaladorIndisponivel)
    assert "erro 5" in str(erro.value)


def test_cancelar_interrompe_a_fala_e_falha_em_palavras():
    dll = DllFalsa()
    NvdaFalador(biblioteca=dll).cancelar()
    assert dll.cancelamentos == 1
    with pytest.raises(ErroFala, match="interromper"):
        NvdaFalador(biblioteca=DllFalsa(cancela=5)).cancelar()


def test_descricao_identifica_o_backend():
    assert NvdaFalador(biblioteca=DllFalsa()).descricao()["backend"] == "nvda"


# ---------------------------------------------------------- localizar a DLL

@pytest.fixture
def pasta_bibliotecas(tmp_path, monkeypatch):
    monkeypatch.setattr(cliente, "PASTA_BIBLIOTECAS", tmp_path)
    monkeypatch.delenv(cliente.VARIAVEL_DLL, raising=False)
    return tmp_path


def test_localiza_a_dll_na_pasta_bibliotecas(pasta_bibliotecas):
    dll = pasta_bibliotecas / cliente.NOME_DLL
    dll.write_bytes(b"")
    assert cliente.localizar_dll() == dll


def test_localiza_a_dll_na_subpasta_da_arquitetura(pasta_bibliotecas):
    subpasta = pasta_bibliotecas / cliente.arquitetura_python()
    subpasta.mkdir()
    dll = subpasta / cliente.NOME_DLL
    dll.write_bytes(b"")
    assert cliente.localizar_dll() == dll


def test_caminho_explicito_vence_a_variavel_e_a_pasta(pasta_bibliotecas, monkeypatch, tmp_path):
    (pasta_bibliotecas / cliente.NOME_DLL).write_bytes(b"")
    da_variavel = tmp_path / "variavel.dll"
    da_variavel.write_bytes(b"")
    monkeypatch.setenv(cliente.VARIAVEL_DLL, str(da_variavel))
    explicito = tmp_path / "explicito.dll"
    explicito.write_bytes(b"")

    assert cliente.localizar_dll(explicito) == explicito
    assert cliente.localizar_dll() == da_variavel


def test_caminho_explicito_errado_nao_cai_em_outro_lugar(pasta_bibliotecas, tmp_path):
    (pasta_bibliotecas / cliente.NOME_DLL).write_bytes(b"")
    errado = tmp_path / "nao_existe.dll"
    with pytest.raises(ErroDllNaoEncontrada) as erro:
        cliente.localizar_dll(errado)
    assert str(errado) in str(erro.value)


def test_dll_ausente_explica_onde_baixar_e_onde_colocar(pasta_bibliotecas):
    with pytest.raises(ErroDllNaoEncontrada) as erro:
        cliente.localizar_dll()
    mensagem = str(erro.value)
    assert "controllerClient.zip" in mensagem
    assert "--dll" in mensagem and cliente.VARIAVEL_DLL in mensagem
    assert str(pasta_bibliotecas) in mensagem


def test_arquitetura_arm64_e_reconhecida(monkeypatch):
    monkeypatch.setattr(cliente.platform, "machine", lambda: "ARM64")
    assert cliente.arquitetura_python() == "arm64"


def test_arquitetura_e_uma_das_pastas_do_zip():
    assert cliente.arquitetura_python() in {"x64", "x86", "arm64"}


# ------------------------------------------------------------ fora do Windows

def test_fora_do_windows_o_erro_diz_que_o_nvda_so_existe_no_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(cliente, "_e_windows", lambda: False)
    dll = tmp_path / cliente.NOME_DLL
    dll.write_bytes(b"")
    with pytest.raises(ErroFaladorIndisponivel, match="so existe no Windows"):
        NvdaFalador(caminho_dll=dll)
    with pytest.raises(ErroFaladorIndisponivel, match="so existe no Windows"):
        cliente.carregar_biblioteca(dll)


@pytest.mark.skipif(sys.platform == "win32", reason="so vale onde nao ha Windows")
def test_criar_falador_neste_sistema_nao_finge_que_fala():
    with pytest.raises(ErroFaladorIndisponivel):
        criar_falador("nvda")


def test_backend_de_fala_desconhecido():
    with pytest.raises(ValueError, match="desconhecido"):
        criar_falador("outro")


# ------------------------------------------------------------------------ CLI

def _usar_falador(monkeypatch, falador, argumentos=None):
    def criar(backend, **opcoes):
        if argumentos is not None:
            argumentos.update(opcoes, backend=backend)
        return falador

    monkeypatch.setattr(cli, "criar_falador", criar)


def test_cli_falar_imprime_e_fala_o_mesmo_texto(monkeypatch, capsys, projeto_exemplo):
    falador = FaladorFalso()
    _usar_falador(monkeypatch, falador)
    codigo = cli.main([str(projeto_exemplo), "--falar"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert len(falador.faladas) == 1
    assert falador.faladas[0].strip() == saida.strip()
    assert "Regiao 1 de 4" in falador.faladas[0]


def test_cli_confere_o_nvda_antes_de_analisar_e_fala_depois(monkeypatch, projeto_exemplo):
    eventos = []
    _usar_falador(monkeypatch, FaladorFalso(eventos=eventos))
    original = cli.analisar

    def analisar_registrando(*a, **k):
        eventos.append("analisar")
        return original(*a, **k)

    monkeypatch.setattr(cli, "analisar", analisar_registrando)
    cli.main([str(projeto_exemplo), "--falar"])
    assert eventos == ["verificar", "analisar", "falar"]


def test_cli_repassa_o_caminho_da_dll(monkeypatch, projeto_exemplo):
    argumentos = {}
    _usar_falador(monkeypatch, FaladorFalso(), argumentos)
    cli.main([str(projeto_exemplo), "--falar", "--dll", "C:/x/nvda.dll"])
    assert argumentos == {"backend": "nvda", "caminho_dll": "C:/x/nvda.dll"}


def test_cli_fala_a_explicacao_do_modelo(monkeypatch, projeto_exemplo):
    falador = FaladorFalso()
    _usar_falador(monkeypatch, falador)
    monkeypatch.setattr(cli, "criar_explicador", lambda *a, **k: LLMFalso())
    codigo = cli.main([str(projeto_exemplo), "--explicar", "--falar"])
    assert codigo == 0
    assert "Explicacao 0." in falador.faladas[0]


def test_cli_nvda_fora_do_ar_entrega_o_texto_e_codigo_3(monkeypatch, capsys, projeto_exemplo):
    erro = ErroFaladorIndisponivel("Nao foi possivel falar com o NVDA (erro 1722).")
    falador = FaladorFalso(erro_verificar=erro)
    _usar_falador(monkeypatch, falador)
    codigo = cli.main([str(projeto_exemplo), "--falar"])

    saida = capsys.readouterr()
    assert codigo == 3
    assert "erro 1722" in saida.err
    assert "apenas como texto" in saida.err
    assert "Regiao 1 de 4" in saida.out, "o relatorio deve sair mesmo sem fala"
    assert falador.faladas == []


def test_cli_sem_dll_nem_windows_entrega_o_texto_e_codigo_3(monkeypatch, capsys, projeto_exemplo):
    def sem_falador(*a, **k):
        raise ErroDllNaoEncontrada("A biblioteca nvdaControllerClient.dll nao foi encontrada.")

    monkeypatch.setattr(cli, "criar_falador", sem_falador)
    codigo = cli.main([str(projeto_exemplo), "--falar"])

    saida = capsys.readouterr()
    assert codigo == 3
    assert "nao foi encontrada" in saida.err
    assert "Regiao 1 de 4" in saida.out


def test_cli_falha_na_fala_depois_de_imprimir_da_codigo_3(monkeypatch, capsys, projeto_exemplo):
    falador = FaladorFalso(erro_falar=ErroFala("O NVDA nao aceitou o texto."))
    _usar_falador(monkeypatch, falador)
    codigo = cli.main([str(projeto_exemplo), "--falar"])

    saida = capsys.readouterr()
    assert codigo == 3
    assert "nao aceitou" in saida.err
    assert "Regiao 1 de 4" in saida.out


def test_cli_erro_do_modelo_tem_prioridade_no_codigo_de_saida(monkeypatch, projeto_exemplo):
    from analisador.llm import ErroModeloAusente

    erro = ErroFaladorIndisponivel("NVDA fechado.")
    _usar_falador(monkeypatch, FaladorFalso(erro_verificar=erro))
    monkeypatch.setattr(cli, "criar_explicador",
                        lambda *a, **k: LLMFalso(erro_verificar=ErroModeloAusente("x")))
    assert cli.main([str(projeto_exemplo), "--explicar", "--falar"]) == 2


def test_cli_falar_com_json_e_recusado(capsys, projeto_exemplo):
    with pytest.raises(SystemExit) as saida:
        cli.main([str(projeto_exemplo), "--falar", "--json"])
    assert saida.value.code == 2
    assert "--falar" in capsys.readouterr().err


def test_cli_sem_falar_nao_cria_falador(monkeypatch, capsys, projeto_exemplo):
    def nao_deve_ser_chamado(*a, **k):
        raise AssertionError("sem --falar nao pode tocar no NVDA")

    monkeypatch.setattr(cli, "criar_falador", nao_deve_ser_chamado)
    assert cli.main([str(projeto_exemplo)]) == 0
    assert "Regiao 1 de 4" in capsys.readouterr().out


def test_cli_json_continua_igual_sem_falar(capsys, projeto_exemplo):
    cli.main([str(projeto_exemplo), "--json"])
    dados = json.loads(capsys.readouterr().out)
    assert dados["caminho"] == str(projeto_exemplo)
    assert len(dados["grupos"]) == len(analisar(projeto_exemplo).grupos)
