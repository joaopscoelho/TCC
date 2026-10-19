"""
Cliente do Ollama: parametros enviados, erros traduzidos e degradacao.
"""
import socket

import pytest

from analisador.llm import (
    ErroConfiguracaoLLM, ErroContextoExcedido, ErroLLM, ErroModeloAusente,
    ErroRespostaVazia, ErroServidorIndisponivel, ErroTempoEsgotado, Mensagem,
    criar_explicador, estimar_tokens,
)
from analisador.llm.local import (
    HOST_PADRAO, MODELO_PADRAO, VARIAVEL_CHAVE, ExplicadorLocal, normalizar_host,
)

MENSAGENS = [Mensagem("system", "regras"), Mensagem("user", "explique")]


def _porta_fechada() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    return f"http://127.0.0.1:{porta}"


def test_gera_texto_e_envia_os_parametros_de_reprodutibilidade(ollama):
    explicador = ExplicadorLocal(modelo="qwen3:8b", host=ollama.url, contexto=4096, semente=7)
    resposta = explicador.gerar(MENSAGENS)

    assert resposta.texto == "Texto de teste."
    assert resposta.tokens_prompt == 120 and resposta.tokens_resposta == 30
    assert not resposta.cortada

    corpo = ollama.corpos_de_chat()[0]
    assert corpo["model"] == "qwen3:8b"
    assert corpo["stream"] is False
    assert corpo["options"]["num_ctx"] == 4096, "contexto precisa ir na requisicao"
    assert corpo["options"]["seed"] == 7
    assert corpo["options"]["temperature"] == 0.0
    assert [m["role"] for m in corpo["messages"]] == ["system", "user"]


def test_raciocinio_padrao_depende_do_modelo():
    assert ExplicadorLocal(modelo="qwen3:8b").raciocinio is False
    assert ExplicadorLocal(modelo="gpt-oss:20b").raciocinio == "low"


def test_campo_think_e_omitido_quando_raciocinio_e_none(ollama):
    ExplicadorLocal(host=ollama.url, raciocinio=None).gerar(MENSAGENS)
    assert "think" not in ollama.corpos_de_chat()[0]


def test_verificar_devolve_digest_e_registra_na_descricao(ollama):
    explicador = ExplicadorLocal(modelo="qwen3:8b", host=ollama.url)
    assert explicador.verificar() == {"digest": "sha256:abc123"}
    assert explicador.descricao()["digest"] == "sha256:abc123"
    assert explicador.descricao()["semente"] == 42


def test_verificar_aceita_nome_sem_tag(ollama):
    ollama.modelos = [{"name": "qwen3:latest", "digest": "sha256:def"}]
    assert ExplicadorLocal(modelo="qwen3", host=ollama.url).verificar()["digest"] == "sha256:def"


def test_modelo_nao_instalado_diz_como_baixar_e_o_que_ha(ollama):
    explicador = ExplicadorLocal(modelo="gpt-oss:20b", host=ollama.url)
    with pytest.raises(ErroModeloAusente) as info:
        explicador.verificar()
    assert "ollama pull gpt-oss:20b" in str(info.value)
    assert "qwen3:8b" in str(info.value), "deve listar o que esta instalado"


def test_servidor_fora_do_ar_e_erro_de_configuracao():
    # No Windows a recusa em porta fechada pode demorar alguns segundos; com
    # um timeout curto o tempo estoura antes e o erro vira de tempo esgotado,
    # nao de conexao. Em Linux e macOS a recusa e imediata.
    explicador = ExplicadorLocal(host=_porta_fechada(), timeout=15)
    for chamada in (explicador.verificar, lambda: explicador.gerar(MENSAGENS)):
        with pytest.raises(ErroServidorIndisponivel) as info:
            chamada()
        assert isinstance(info.value, ErroConfiguracaoLLM)
        assert "ollama serve" in str(info.value)


def test_404_no_chat_vira_modelo_ausente(ollama):
    ollama.status_chat = 404
    ollama.resposta_chat = {"error": "model 'qwen3:8b' not found"}
    with pytest.raises(ErroModeloAusente) as info:
        ExplicadorLocal(host=ollama.url).gerar(MENSAGENS)
    assert "not found" in str(info.value), "a resposta do servidor deve aparecer"


def test_erro_500_afeta_so_a_chamada_e_nao_e_de_configuracao(ollama):
    ollama.status_chat = 500
    ollama.resposta_chat = {"error": "falha interna"}
    with pytest.raises(ErroLLM) as info:
        ExplicadorLocal(host=ollama.url).gerar(MENSAGENS)
    assert not isinstance(info.value, ErroConfiguracaoLLM)
    assert "falha interna" in str(info.value)


def test_resposta_vazia_por_limite_explica_o_possivel_motivo(ollama):
    ollama.resposta_chat = {"message": {"role": "assistant", "content": ""},
                            "done": True, "done_reason": "length"}
    with pytest.raises(ErroRespostaVazia) as info:
        ExplicadorLocal(host=ollama.url).gerar(MENSAGENS)
    assert "raciocinio" in str(info.value)


def test_resposta_cortada_e_sinalizada_e_nao_escondida(ollama):
    ollama.resposta_chat = {"message": {"role": "assistant", "content": "Comeco da fala"},
                            "done": True, "done_reason": "length",
                            "prompt_eval_count": 10, "eval_count": 1500}
    resposta = ExplicadorLocal(host=ollama.url).gerar(MENSAGENS)
    assert resposta.cortada


def test_prompt_grande_demais_e_recusado_sem_chamar_o_servidor(ollama):
    explicador = ExplicadorLocal(host=ollama.url, contexto=100, resposta_maxima=50)
    with pytest.raises(ErroContextoExcedido) as info:
        explicador.gerar([Mensagem("user", "x" * 1000)])
    assert "--contexto" in str(info.value)
    assert ollama.requisicoes == [], "nao deve gastar uma chamada que ia truncar"


def test_aviso_quando_o_prompt_ocupa_quase_todo_o_contexto(ollama):
    ollama.resposta_chat["prompt_eval_count"] = 3950
    resposta = ExplicadorLocal(host=ollama.url, contexto=4096).gerar(MENSAGENS)
    assert resposta.avisos and "contexto" in resposta.avisos[0]


def test_tempo_esgotado_e_erro_da_regiao_nao_de_configuracao(ollama):
    ollama.atraso_s = 0.8
    with pytest.raises(ErroTempoEsgotado) as info:
        ExplicadorLocal(host=ollama.url, timeout=0.2).gerar(MENSAGENS)
    assert not isinstance(info.value, ErroConfiguracaoLLM)


@pytest.mark.parametrize("entrada, esperado", [
    ("", HOST_PADRAO),
    (None, HOST_PADRAO),
    ("localhost:11434", "http://localhost:11434"),
    ("http://servidor:1234/", "http://servidor:1234"),
])
def test_normalizar_host(entrada, esperado):
    assert normalizar_host(entrada) == esperado


def test_variaveis_de_ambiente_e_argumentos_explicitos(monkeypatch):
    monkeypatch.setenv("ANALISADOR_MODELO", "modelo-do-ambiente")
    monkeypatch.setenv("OLLAMA_HOST", "maquina:9999")
    do_ambiente = ExplicadorLocal()
    assert do_ambiente.modelo == "modelo-do-ambiente"
    assert do_ambiente.host == "http://maquina:9999"

    explicito = ExplicadorLocal(modelo="outro", host="http://x:1")
    assert explicito.modelo == "outro" and explicito.host == "http://x:1"


def test_modelo_padrao_sem_ambiente(monkeypatch):
    monkeypatch.delenv("ANALISADOR_MODELO", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    explicador = ExplicadorLocal()
    assert explicador.modelo == MODELO_PADRAO
    assert explicador.host == HOST_PADRAO


def test_fabrica():
    assert isinstance(criar_explicador("local"), ExplicadorLocal)
    with pytest.raises(ValueError):
        criar_explicador("inexistente")


def test_estimativa_de_tokens_e_conservadora():
    assert estimar_tokens("a" * 30) == 10
    assert estimar_tokens("") == 0
    assert estimar_tokens("ab") == 1


# ------------------------------------------------------------ nuvem do Ollama

def test_chave_explicita_vai_no_cabecalho_authorization(ollama):
    ExplicadorLocal(host=ollama.url, chave="segredo").gerar(MENSAGENS)
    assert ollama.cabecalhos[-1]["Authorization"] == "Bearer segredo"


def test_chave_do_ambiente_nao_vai_para_servidor_que_nao_e_a_nuvem(monkeypatch, ollama):
    monkeypatch.setenv(VARIAVEL_CHAVE, "segredo")
    ExplicadorLocal(host=ollama.url).gerar(MENSAGENS)
    assert "Authorization" not in ollama.cabecalhos[-1]


def test_nuvem_sem_chave_para_na_hora_sem_chamar_a_rede(monkeypatch):
    monkeypatch.delenv(VARIAVEL_CHAVE, raising=False)
    explicador = ExplicadorLocal(host="https://ollama.com", modelo="gemma4:31b")
    assert explicador.nuvem
    for chamada in (explicador.verificar, lambda: explicador.gerar(MENSAGENS)):
        with pytest.raises(ErroConfiguracaoLLM) as info:
            chamada()
        assert VARIAVEL_CHAVE in str(info.value) and "settings/keys" in str(info.value)


def test_nuvem_le_a_chave_do_ambiente_e_nao_a_expoe_na_descricao(monkeypatch):
    monkeypatch.setenv(VARIAVEL_CHAVE, "segredo-do-ambiente")
    explicador = ExplicadorLocal(host="https://ollama.com", modelo="gemma4:31b")
    descricao = explicador.descricao()
    assert descricao["nuvem"] is True
    assert "segredo-do-ambiente" not in str(descricao)


def test_servidor_local_nao_e_nuvem():
    assert not ExplicadorLocal(host="http://127.0.0.1:11434").nuvem
    assert not ExplicadorLocal(host="https://ollama.com.exemplo.net").nuvem


def test_chave_recusada_e_erro_de_configuracao_e_para_a_geracao(ollama):
    ollama.exigir_chave = "certa"
    explicador = ExplicadorLocal(host=ollama.url, chave="errada")
    for chamada in (explicador.verificar, lambda: explicador.gerar(MENSAGENS)):
        with pytest.raises(ErroConfiguracaoLLM) as info:
            chamada()
        assert "401" in str(info.value) and "chave" in str(info.value)


def test_chave_certa_e_aceita(ollama):
    ollama.exigir_chave = "certa"
    explicador = ExplicadorLocal(host=ollama.url, chave="certa")
    assert explicador.verificar() == {"digest": "sha256:abc123"}
    assert explicador.gerar(MENSAGENS).texto == "Texto de teste."
