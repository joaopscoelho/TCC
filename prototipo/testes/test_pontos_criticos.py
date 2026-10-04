"""
Teste de ponta a ponta da Fase 1: dado o arquivo de fixture (cadastro de
funcionario/empresa/setor, secao 12 do documento), confirma que as regras
de pontos criticos encontram o que se espera.
"""
from pathlib import Path

from analisador.parser.ast_parser import parse_file
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
