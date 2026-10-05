"""
Fixture: regras de negocio do cadastro de funcionario (secao 12 do
documento). Nao e importado pelos testes, apenas lido como codigo-fonte.
"""
LIMITE_FUNCIONARIOS_SETOR = 50


def validar_contratacao(funcionario, setor, empresa):
    if setor.ativo:
        if funcionario.idade >= 18:
            if funcionario.cpf_valido:
                if setor.empresa_id == empresa.id:
                    return True
    return False


def setor_no_limite(setor, limite=LIMITE_FUNCIONARIOS_SETOR):
    if len(setor.funcionarios) >= limite:
        return True
    return False
