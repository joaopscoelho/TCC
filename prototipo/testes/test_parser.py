"""
Fase 1: parse, deteccao de erro de sintaxe e varredura de projeto.
"""
from analisador.parser.ast_parser import erros_de_sintaxe, parse_source
from analisador.parser.varredura import descobrir_arquivos, varrer

CODIGO_VALIDO = b"def soma(a, b):\n    return a + b\n"
CODIGO_INVALIDO = b"def soma(a, b:\n    return a + b\n"


def test_codigo_valido_nao_gera_erro_de_sintaxe():
    root = parse_source(CODIGO_VALIDO)
    assert not root.has_error
    assert erros_de_sintaxe(root, CODIGO_VALIDO, "valido.py") == []


def test_codigo_invalido_gera_erro_com_linha():
    root = parse_source(CODIGO_INVALIDO)
    erros = erros_de_sintaxe(root, CODIGO_INVALIDO, "invalido.py")
    assert erros, "arvore com has_error deveria produzir pelo menos um erro"
    assert erros[0].linha == 1
    assert erros[0].arquivo == "invalido.py"


def test_varredura_encontra_os_tres_arquivos_do_projeto(projeto_exemplo):
    encontrados = descobrir_arquivos(projeto_exemplo)
    nomes = sorted(c.name for c in encontrados)
    assert nomes == ["persistencia.py", "regras_negocio.py", "relatorios.py"]


def test_varredura_ignora_pastas_de_ambiente(tmp_path):
    (tmp_path / "codigo.py").write_text("def f():\n    pass\n", encoding="utf-8")
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "dependencia.py").write_text("def g():\n    pass\n", encoding="utf-8")

    encontrados = descobrir_arquivos(tmp_path)
    assert [c.name for c in encontrados] == ["codigo.py"]


def test_arquivo_com_erro_e_marcado_como_nao_confiavel(projeto_quebrado):
    analisados = varrer(projeto_quebrado)
    assert len(analisados) == 1
    assert not analisados[0].confiavel
    assert analisados[0].erros_sintaxe


def test_arquivos_validos_sao_confiaveis(projeto_exemplo):
    for analisado in varrer(projeto_exemplo):
        assert analisado.confiavel, f"{analisado.relativo} deveria estar sem erro"
