"""
Teste de ponta a ponta da Fase 1: dado o arquivo de fixture (cadastro de
funcionario/empresa/setor, secao 12 do documento), confirma que as regras
de pontos criticos encontram o que se espera.
"""
from pathlib import Path

from analisador.parser.ast_parser import parse_file, parse_source
from analisador.pontos_criticos.regras import identificar_pontos_criticos

FIXTURE = Path(__file__).parent / "fixtures" / "exemplo_funcionarios.py"


def test_identifica_pelo_menos_um_de_cada_tipo_esperado():
    root, source = parse_file(FIXTURE)
    pontos = identificar_pontos_criticos(root, source, arquivo=str(FIXTURE))
    tipos_encontrados = {p.tipo for p in pontos}

    esperados = {
        "condicional_aninhado",
        "laco_aninhado",
        "try_except",
        "chamada_dependencia_externa",
        "literal_em_condicional",
    }
    faltando = esperados - tipos_encontrados
    assert not faltando, f"Regras que nao encontraram nada no fixture: {faltando}"


def test_pontos_vem_ordenados_por_severidade_decrescente():
    root, source = parse_file(FIXTURE)
    pontos = identificar_pontos_criticos(root, source, arquivo=str(FIXTURE))
    severidades = [p.severidade for p in pontos]
    assert severidades == sorted(severidades, reverse=True)


def _tipos(codigo: bytes):
    root = parse_source(codigo)
    return {p.tipo for p in identificar_pontos_criticos(root, codigo, "exemplo.py")}


def test_literal_trivial_nao_e_reportado():
    """Idiomas da linguagem nao sao regra de negocio e nao devem gerar item."""
    for codigo in (
        b"def f(itens):\n    if len(itens) == 0:\n        return None\n",
        b"def f(x):\n    if x is None:\n        return False\n",
        b"def f(x):\n    if x == 1:\n        return True\n",
    ):
        assert "literal_em_condicional" not in _tipos(codigo), codigo


def test_literal_de_regra_de_negocio_continua_reportado():
    """Valor fixo especifico do dominio e justamente o que interessa explicar."""
    codigo = b"def f(funcionario):\n    if funcionario.idade >= 18:\n        return True\n"
    assert "literal_em_condicional" in _tipos(codigo)


def test_metodo_de_dicionario_nao_e_dependencia_externa():
    """Rodando o analisador sobre si mesmo, "dicionario.get" aparecia como
    dependencia externa de severidade 5: falso positivo que destroi a
    confianca do usuario na lista."""
    codigo = b'NOMES = {}\n\n\ndef descrever(tipo):\n    return NOMES.get(tipo, tipo)\n'
    assert "chamada_dependencia_externa" not in _tipos(codigo)


def test_verbo_ambiguo_vale_quando_o_arquivo_importa_biblioteca_de_rede():
    codigo = (b"import requests\n\n\ndef consultar(url):\n"
              b"    return requests.get(url)\n")
    assert "chamada_dependencia_externa" in _tipos(codigo)


def test_dependencia_inequivoca_vale_sempre():
    codigo = b'def ler(caminho):\n    return open(caminho).read()\n'
    assert "chamada_dependencia_externa" in _tipos(codigo)
