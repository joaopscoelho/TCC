"""
Fase 2 (parte deterministica): estrutura do arquivo e mapa do projeto.
"""
from analisador.contexto.estrutura import (
    definicao_envolvente, extrair_definicoes, extrair_imports,
)
from analisador.contexto.mapa import construir_mapa
from analisador.parser.ast_parser import parse_file


def test_extrai_funcoes_classes_e_metodos(projeto_exemplo):
    arquivo = projeto_exemplo / "persistencia.py"
    root, source = parse_file(arquivo)
    definicoes = extrair_definicoes(root, source, "persistencia.py")

    por_nome = {d.nome: d for d in definicoes}
    assert por_nome["RepositorioFuncionario"].tipo == "classe"
    assert por_nome["salvar"].tipo == "metodo"
    assert por_nome["contratar_funcionario"].tipo == "funcao"
    assert por_nome["salvar"].qualificado == "persistencia.py::RepositorioFuncionario.salvar"
    assert por_nome["salvar"].pai == "persistencia.py::RepositorioFuncionario"


def test_assinatura_preserva_os_parametros(projeto_exemplo):
    root, source = parse_file(projeto_exemplo / "regras_negocio.py")
    definicoes = extrair_definicoes(root, source, "regras_negocio.py")
    validar = next(d for d in definicoes if d.nome == "validar_contratacao")
    assert validar.assinatura == "validar_contratacao(funcionario, setor, empresa)"


def test_definicao_envolvente_escolhe_a_mais_interna(projeto_exemplo):
    arquivo = projeto_exemplo / "persistencia.py"
    root, source = parse_file(arquivo)
    definicoes = extrair_definicoes(root, source, "persistencia.py")

    salvar = next(d for d in definicoes if d.nome == "salvar")
    envolvente = definicao_envolvente(definicoes, salvar.linha_inicio + 1)
    assert envolvente.nome == "salvar", "metodo deve vencer a classe que o contem"


def test_linha_fora_de_qualquer_definicao_nao_tem_envolvente(projeto_exemplo):
    root, source = parse_file(projeto_exemplo / "regras_negocio.py")
    definicoes = extrair_definicoes(root, source, "regras_negocio.py")
    assert definicao_envolvente(definicoes, 1) is None


def test_extrai_imports_com_modulo_e_nomes(projeto_exemplo):
    root, source = parse_file(projeto_exemplo / "relatorios.py")
    imports = extrair_imports(root, source, "relatorios.py")
    modulos = {i.modulo for i in imports}
    assert modulos == {"persistencia", "regras_negocio"}
    assert any("contratar_funcionario" in i.nomes for i in imports)


def test_grafo_liga_chamadas_entre_arquivos(projeto_exemplo):
    mapa = construir_mapa(projeto_exemplo)

    chamador = "persistencia.py::contratar_funcionario"
    alvo = "regras_negocio.py::validar_contratacao"
    assert alvo in mapa.grafo[chamador], "import entre arquivos deveria ser resolvido"
    assert chamador in mapa.chamadores[alvo]


def test_grafo_prefere_definicao_do_proprio_arquivo(projeto_exemplo):
    mapa = construir_mapa(projeto_exemplo)
    chamadas = mapa.grafo["persistencia.py::contratar_funcionario"]
    assert "persistencia.py::RepositorioFuncionario.salvar" in chamadas


def test_pontos_de_entrada_sao_os_nao_chamados(projeto_exemplo):
    entradas = construir_mapa(projeto_exemplo).pontos_de_entrada()
    assert "relatorios.py::contratar_em_lote" in entradas
    assert "relatorios.py::setores_sobrecarregados" in entradas
    assert "regras_negocio.py::validar_contratacao" not in entradas


def test_construtor_nao_e_ponto_de_entrada(projeto_exemplo):
    """__init__ e chamado pela linguagem, nao pelo nome: no grafo parecia
    nao ter chamador e entrava na visao geral como "por onde o fluxo comeca"."""
    entradas = construir_mapa(projeto_exemplo).pontos_de_entrada()
    assert "persistencia.py::RepositorioFuncionario.__init__" not in entradas


def test_dependencias_externas_sao_so_o_que_sai_do_projeto(projeto_exemplo):
    externas = construir_mapa(projeto_exemplo).dependencias_externas()
    assert "self.conexao.execute" in externas, "acesso a banco e dependencia externa"
    assert "validar_contratacao" not in externas, "definido no projeto"
    assert "len" not in externas, "nome embutido do Python nao e dependencia externa"
    assert "str" not in externas
    assert not any(e.endswith(".append") for e in externas), "metodo de colecao e ruido"


def test_contexto_de_uma_linha_tem_o_que_o_prompt_precisa(projeto_exemplo):
    mapa = construir_mapa(projeto_exemplo)
    salvar = mapa.definicoes["persistencia.py::RepositorioFuncionario.salvar"]
    contexto = mapa.contexto("persistencia.py", salvar.linha_inicio + 1)

    assert contexto["escopo"] == "metodo"
    assert contexto["definicao"]["nome"] == "salvar"
    assert "persistencia.py::contratar_funcionario" in contexto["chamada_por"]
    assert "self.conexao.execute" in contexto["chamadas_externas"]
    assert contexto["arquivo_confiavel"] is True


CODIGO_COM_CHAMADA_DE_MODULO = """\
def validar(x):
    return x > 0


def processar(x):
    return validar(x)


def principal():
    return processar(1)


if validar(5):
    principal()
"""


def test_chamada_de_nivel_de_modulo_nao_quebra_o_contexto(tmp_path):
    """Regressao: funcao chamada por outra funcao E pelo codigo de modulo
    colocava None e texto no mesmo conjunto, e sorted() levantava TypeError."""
    (tmp_path / "app.py").write_text(CODIGO_COM_CHAMADA_DE_MODULO, encoding="utf-8")
    mapa = construir_mapa(tmp_path)

    contexto = mapa.contexto("app.py", 2)
    assert "app.py::processar" in contexto["chamada_por"]
    assert "app.py::<codigo de modulo>" in contexto["chamada_por"]
    assert all(isinstance(c, str) for c in contexto["chamada_por"])


def test_idioma_main_conta_como_ponto_de_entrada(tmp_path):
    """Regressao: funcao chamada so pelo codigo de modulo nao era ponto de
    entrada, e a lista inteira saia vazia no exemplo acima."""
    (tmp_path / "app.py").write_text(CODIGO_COM_CHAMADA_DE_MODULO, encoding="utf-8")
    entradas = construir_mapa(tmp_path).pontos_de_entrada()
    assert entradas == ["app.py::principal"]


def test_contexto_do_proprio_codigo_de_modulo(tmp_path):
    (tmp_path / "app.py").write_text(CODIGO_COM_CHAMADA_DE_MODULO, encoding="utf-8")
    contexto = construir_mapa(tmp_path).contexto("app.py", 13)
    assert contexto["escopo"] == "modulo"
    assert "app.py::principal" in contexto["chama"]
