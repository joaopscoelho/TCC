"""
Fixture: persistencia do cadastro, com dependencia externa de banco e
tratamento de excecao (secao 12 do documento).
"""
from regras_negocio import validar_contratacao


class RepositorioFuncionario:
    def __init__(self, conexao):
        self.conexao = conexao

    def salvar(self, funcionario, setor):
        try:
            self.conexao.execute(
                "INSERT INTO funcionario (nome, setor_id) VALUES (?, ?)",
                (funcionario.nome, setor.id),
            )
        except Exception as erro:
            raise RuntimeError(f"Falha ao salvar: {erro}")


def contratar_funcionario(funcionario, setor, empresa, repositorio):
    if not validar_contratacao(funcionario, setor, empresa):
        raise ValueError("Contratacao nao permitida para este setor")
    repositorio.salvar(funcionario, setor)
