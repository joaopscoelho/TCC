"""
Prompts da Fase 2: o que o modelo recebe precisa conter o que ele deve
explicar e as regras de acessibilidade e de incerteza.
"""
from analisador.analise import analisar
from analisador.llm.prompts import (
    MARCADOR_INFERENCIA, PROMPT_SISTEMA, mensagens_regiao, mensagens_visao_geral,
)


def _grupo(resultado, escopo):
    return next(g for g in resultado.grupos if g.escopo == escopo)


def test_prompt_de_sistema_traz_as_regras_de_forma_e_de_conteudo():
    assert "português brasileiro" in PROMPT_SISTEMA
    assert "ficheiro" in PROMPT_SISTEMA, "o exemplo do que evitar precisa estar la"
    assert "tabelas" in PROMPT_SISTEMA
    assert "Não invente" in PROMPT_SISTEMA
    assert MARCADOR_INFERENCIA in PROMPT_SISTEMA


def test_marcador_de_inferencia_e_uma_palavra_fixa_verificavel():
    """A Fase 3 vai procurar este texto na saida; nao pode mudar sem aviso."""
    assert MARCADOR_INFERENCIA == "Inferência:"


def test_visao_geral_tem_papel_system_e_user(projeto_exemplo):
    mensagens = mensagens_visao_geral(analisar(projeto_exemplo))
    assert [m.papel for m in mensagens] == ["system", "user"]
    assert mensagens[0].conteudo == PROMPT_SISTEMA


def test_visao_geral_leva_os_dados_do_projeto(projeto_exemplo):
    texto = mensagens_visao_geral(analisar(projeto_exemplo))[1].conteudo
    assert "Arquivos analisados: 3." in texto
    assert "contratar_em_lote (arquivo relatorios.py)" in texto, "ponto de entrada legivel"
    assert "__init__" not in texto.split("Pontos de entrada")[1].split("\n")[0], \
        "construtor nao e ponto de entrada"
    assert "self.conexao.execute" in texto, "dependencia externa"
    assert "Região 1 mais grave: salvar" in texto
    assert "Pontos críticos encontrados: 6, distribuídos em 4 regiões" in texto


def test_visao_geral_pede_inferencia_para_o_proposito(projeto_exemplo):
    texto = mensagens_visao_geral(analisar(projeto_exemplo))[1].conteudo
    assert "dedução" in texto and "inferência" in texto


def test_regiao_leva_assinatura_chamadores_codigo_e_pontos(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    grupo = _grupo(resultado, "persistencia.py::RepositorioFuncionario.salvar")
    texto = mensagens_regiao(resultado.mapa, grupo)[1].conteudo

    assert "salvar(self, funcionario, setor), método" in texto
    assert "Quem chama esta região: contratar_funcionario (arquivo persistencia.py)" in texto
    assert "Dependências externas usadas: self.conexao.execute" in texto
    assert "gravidade 5 de 5" in texto
    assert "14:" in texto and "self.conexao.execute(" in texto, "codigo com numero de linha"


def test_regiao_sem_chamador_diz_nenhum(projeto_exemplo):
    resultado = analisar(projeto_exemplo)
    grupo = _grupo(resultado, "relatorios.py::contratar_em_lote")
    texto = mensagens_regiao(resultado.mapa, grupo)[1].conteudo
    assert "Quem chama esta região: nenhum." in texto


def test_regiao_de_codigo_de_modulo(tmp_path):
    (tmp_path / "script.py").write_text(
        "try:\n    import os\nexcept ImportError:\n    os = None\n", encoding="utf-8")
    resultado = analisar(tmp_path)
    texto = mensagens_regiao(resultado.mapa, resultado.grupos[0])[1].conteudo
    assert "nível do módulo" in texto


def test_trecho_longo_e_cortado_e_o_modelo_e_avisado(tmp_path):
    corpo = ("def longa(x):\n    try:\n        pass\n    except Exception:\n        pass\n"
             + "    x += 1\n" * 100 + "    return x\n")
    (tmp_path / "longa.py").write_text(corpo, encoding="utf-8")
    resultado = analisar(tmp_path)
    texto = mensagens_regiao(resultado.mapa, resultado.grupos[0], max_linhas_codigo=10)[1].conteudo
    assert "Trecho cortado" in texto
    assert "Não afirme nada sobre elas" in texto


def test_arquivo_com_erro_de_sintaxe_avisa_o_modelo(tmp_path):
    (tmp_path / "misto.py").write_text(
        "def a(x):\n    try:\n        open(x)\n    except Exception:\n        pass\n\n"
        "def b(:\n    pass\n", encoding="utf-8")
    resultado = analisar(tmp_path)
    assert resultado.grupos, "o ponto critico da funcao valida deve sobreviver ao erro"
    texto = mensagens_regiao(resultado.mapa, resultado.grupos[0])[1].conteudo
    assert "erros de sintaxe" in texto and "Avise o ouvinte" in texto


def test_visao_geral_avisa_sobre_erro_de_sintaxe(projeto_quebrado):
    texto = mensagens_visao_geral(analisar(projeto_quebrado))[1].conteudo
    assert "erros de sintaxe em incompleto.py" in texto
