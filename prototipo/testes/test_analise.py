"""
Orquestracao e runner: analise de ponta a ponta sobre o projeto fixture.
"""
import json

from analisador.__main__ import relatorio_texto
from analisador.analise import analisar

SIMBOLOS_PROIBIDOS = ("|", "+--", "===", "***", "```")


def test_analise_de_projeto_cobre_os_tres_arquivos(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    arquivos = {p.arquivo for p in resultado.pontos}
    assert arquivos == {"regras_negocio.py", "persistencia.py", "relatorios.py"}


def test_resultado_e_serializavel_em_json(projeto_exemplo):
    dados = analisar(projeto_exemplo).to_dict()
    texto = json.dumps(dados, ensure_ascii=False)
    assert "resumo_projeto" in texto
    assert dados["resumo_projeto"]["total_arquivos"] == 3
    assert dados["contextos"], "cada regiao deve levar seu contexto para o prompt"


def test_relatorio_anuncia_a_posicao_em_palavras(projeto_exemplo):
    texto = relatorio_texto(analisar(projeto_exemplo))
    assert "Regiao 1 de" in texto
    assert "Ponto critico 1 de" in texto


def test_relatorio_concorda_numero_e_substantivo(projeto_exemplo):
    """Leitura por voz nao tolera "1 ponto ou pontos criticos"."""
    texto = relatorio_texto(analisar(projeto_exemplo))
    assert "1 ponto critico," in texto
    assert " ou pontos" not in texto
    assert "arquivos analisados" in texto


def test_relatorio_nao_usa_tabela_nem_simbolo_decorativo(projeto_exemplo):
    texto = relatorio_texto(analisar(projeto_exemplo))
    for simbolo in SIMBOLOS_PROIBIDOS:
        assert simbolo not in texto, f"saida nao deve conter {simbolo!r}"


def test_relatorio_avisa_sobre_erro_de_sintaxe(projeto_quebrado):
    texto = relatorio_texto(analisar(projeto_quebrado))
    assert "de sintaxe" in texto
    assert "analise pode estar incompleta" in texto
    assert "incompleto.py" in texto, "o aviso precisa dizer qual arquivo"


def test_projeto_sem_ponto_critico_diz_isso_explicitamente(tmp_path):
    (tmp_path / "simples.py").write_text("def soma(a, b):\n    return a + b\n",
                                         encoding="utf-8")
    texto = relatorio_texto(analisar(tmp_path))
    assert "Nenhum ponto critico encontrado." in texto
