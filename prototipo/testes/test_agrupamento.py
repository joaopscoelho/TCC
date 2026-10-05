"""
Reducao de ruido: agrupamento por regiao e colapso de duplicatas.
"""
from analisador.analise import analisar
from analisador.contexto.mapa import construir_mapa
from analisador.parser.ast_parser import parse_file
from analisador.pontos_criticos.agrupamento import agrupar, colapsar_duplicatas
from analisador.pontos_criticos.regras import PontoCritico, identificar_pontos_criticos


def test_try_e_dependencia_externa_viram_uma_unica_regiao(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    grupos = {g.escopo: g for g in resultado.grupos}
    salvar = grupos["persistencia.py::RepositorioFuncionario.salvar"]

    tipos = {p.tipo for p in salvar.pontos}
    assert tipos == {"try_except", "chamada_dependencia_externa"}
    assert salvar.total == 2, "o mesmo trecho nao deve virar duas regioes"
    assert salvar.severidade == 5, "a regiao herda a severidade do ponto mais grave"


def test_agrupamento_reduz_a_quantidade_de_itens_lidos(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    assert len(resultado.grupos) < len(resultado.pontos)
    assert sum(g.total for g in resultado.grupos) == len(resultado.pontos)


def test_grupos_vem_ordenados_por_severidade_decrescente(projeto_exemplo):
    grupos = analisar(projeto_exemplo).grupos
    severidades = [g.severidade for g in grupos]
    assert severidades == sorted(severidades, reverse=True)


def test_rotulo_do_grupo_e_a_assinatura_da_funcao(projeto_exemplo):
    grupos = {g.escopo: g for g in analisar(projeto_exemplo).grupos}
    validar = grupos["regras_negocio.py::validar_contratacao"]
    assert validar.rotulo == "validar_contratacao(funcionario, setor, empresa)"


def test_colapsa_pontos_identicos_em_tipo_e_linha():
    ponto = PontoCritico(tipo="try_except", arquivo="a.py", linha=10,
                         trecho="try:", severidade=4)
    repetido = PontoCritico(tipo="try_except", arquivo="a.py", linha=10,
                            trecho="try:", severidade=4)
    assert len(colapsar_duplicatas([ponto, repetido])) == 1


def test_codigo_de_modulo_cai_no_escopo_de_modulo(tmp_path):
    arquivo = tmp_path / "script.py"
    arquivo.write_text("try:\n    import os\nexcept ImportError:\n    os = None\n",
                       encoding="utf-8")

    root, source = parse_file(arquivo)
    pontos = identificar_pontos_criticos(root, source, "script.py")
    grupos = agrupar(pontos, mapa=construir_mapa(tmp_path))

    assert len(grupos) == 1
    assert grupos[0].rotulo == "<codigo de modulo>"
