"""
Orquestracao da explicacao e CLI, com um LLM falso: nenhum teste aqui
depende de modelo, rede ou Ollama.
"""
import json

import pytest

import analisador.__main__ as cli
from analisador.analise import analisar
from analisador.explicacao import explicar
from analisador.llm import (
    ErroModeloAusente, ErroRespostaVazia, ErroServidorIndisponivel, ExplicadorLLM,
    RespostaLLM,
)


class LLMFalso(ExplicadorLLM):
    def __init__(self, falhas=None, erro_verificar=None, cortar=False):
        self.chamadas = []
        self.falhas = falhas or {}
        self.erro_verificar = erro_verificar
        self.cortar = cortar

    def verificar(self):
        if self.erro_verificar is not None:
            raise self.erro_verificar
        return {}

    def gerar(self, mensagens):
        indice = len(self.chamadas)
        self.chamadas.append(mensagens)
        if indice in self.falhas:
            raise self.falhas[indice]
        return RespostaLLM(texto=f"Explicacao {indice}.", modelo="falso",
                           motivo_fim="length" if self.cortar else "stop")

    def descricao(self):
        return {"backend": "falso", "modelo": "falso"}


def test_uma_chamada_de_visao_geral_e_uma_por_regiao(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    llm = LLMFalso()
    explicacao = explicar(resultado, llm)

    assert len(llm.chamadas) == 1 + len(resultado.grupos)
    assert "visão geral" in llm.chamadas[0][1].conteudo
    assert explicacao.visao_geral.texto == "Explicacao 0."
    assert [r.titulo for r in explicacao.regioes] == [g.rotulo for g in resultado.grupos]
    assert all(r.ok for r in explicacao.regioes)


def test_max_regioes_explica_so_as_mais_graves(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    llm = LLMFalso()
    explicacao = explicar(resultado, llm, max_regioes=2)
    assert len(llm.chamadas) == 3
    assert [r.titulo for r in explicacao.regioes] == [g.rotulo for g in resultado.grupos[:2]]


def test_erro_isolado_nao_derruba_as_outras_regioes(projeto_exemplo):
    llm = LLMFalso(falhas={2: ErroRespostaVazia("modelo devolveu vazio")})
    explicacao = explicar(analisar(projeto_exemplo), llm)

    falhou = explicacao.regioes[1]
    assert not falhou.ok and "vazio" in falhou.erro
    assert explicacao.regioes[0].ok and explicacao.regioes[2].ok


def test_erro_de_configuracao_na_verificacao_aborta_antes_de_gerar(projeto_exemplo):
    llm = LLMFalso(erro_verificar=ErroModeloAusente("modelo x ausente"))
    with pytest.raises(ErroModeloAusente):
        explicar(analisar(projeto_exemplo), llm)
    assert llm.chamadas == []


def test_erro_de_configuracao_durante_a_geracao_aborta(projeto_exemplo):
    llm = LLMFalso(falhas={1: ErroServidorIndisponivel("caiu")})
    with pytest.raises(ErroServidorIndisponivel):
        explicar(analisar(projeto_exemplo), llm)


def test_resposta_cortada_vira_aviso(projeto_exemplo):
    explicacao = explicar(analisar(projeto_exemplo), LLMFalso(cortar=True))
    assert any("cortada" in a for a in explicacao.visao_geral.avisos)


def test_progresso_e_anunciado_a_cada_etapa(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    eventos = []
    explicar(resultado, LLMFalso(), ao_progredir=lambda e, t, titulo: eventos.append((e, t)))
    total = len(resultado.grupos) + 1
    assert eventos == [(i, total) for i in range(1, total + 1)]


def test_projeto_sem_arquivos_nao_chama_o_modelo(tmp_path):
    llm = LLMFalso()
    explicacao = explicar(analisar(tmp_path), llm)
    assert llm.chamadas == []
    assert "Nenhum arquivo Python" in explicacao.visao_geral.erro


def test_resultado_e_serializavel(projeto_exemplo):
    dados = explicar(analisar(projeto_exemplo), LLMFalso()).to_dict()
    json.dumps(dados, ensure_ascii=False)
    assert dados["modelo"]["backend"] == "falso"


# ----------------------------------------------------------------------- CLI

def test_cli_explicar_imprime_visao_geral_regioes_e_modelo(monkeypatch, capsys, projeto_exemplo):
    monkeypatch.setattr(cli, "criar_explicador", lambda *a, **k: LLMFalso())
    codigo = cli.main([str(projeto_exemplo), "--explicar"])

    saida = capsys.readouterr()
    assert codigo == 0
    assert "Visao geral do projeto." in saida.out
    assert "Explicacao 0." in saida.out
    assert "Regiao 1 de 4: salvar" in saida.out
    assert "Explicacao gerada pelo modelo falso" in saida.out
    assert "Gerando explicacao 1 de 5" in saida.err, "progresso vai para stderr"


def test_cli_max_regioes_declara_o_que_ficou_de_fora(monkeypatch, capsys, projeto_exemplo):
    monkeypatch.setattr(cli, "criar_explicador", lambda *a, **k: LLMFalso())
    cli.main([str(projeto_exemplo), "--explicar", "--max-regioes", "1"])
    assert "para 1 de 4 regioes" in capsys.readouterr().out


def test_cli_sem_modelo_entrega_a_analise_estatica_e_codigo_2(monkeypatch, capsys, projeto_exemplo):
    erro = ErroModeloAusente("modelo x ausente, rode ollama pull x")
    monkeypatch.setattr(cli, "criar_explicador", lambda *a, **k: LLMFalso(erro_verificar=erro))
    codigo = cli.main([str(projeto_exemplo), "--explicar"])

    saida = capsys.readouterr()
    assert codigo == 2
    assert "modelo x ausente" in saida.err
    assert "Regiao 1 de 4" in saida.out, "a analise estatica deve ser entregue mesmo assim"
    assert "Erro:" not in saida.out


def test_cli_json_com_explicacao(monkeypatch, capsys, projeto_exemplo):
    monkeypatch.setattr(cli, "criar_explicador", lambda *a, **k: LLMFalso())
    cli.main([str(projeto_exemplo), "--explicar", "--json"])
    dados = json.loads(capsys.readouterr().out)
    assert dados["explicacao"]["visao_geral"]["texto"] == "Explicacao 0."


def test_cli_sem_explicar_nao_cria_explicador(monkeypatch, capsys, projeto_exemplo):
    def nao_deve_ser_chamado(*a, **k):
        raise AssertionError("sem --explicar nao pode tocar no modelo")

    monkeypatch.setattr(cli, "criar_explicador", nao_deve_ser_chamado)
    assert cli.main([str(projeto_exemplo)]) == 0
    assert "Regiao 1 de 4" in capsys.readouterr().out
