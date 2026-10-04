"""
Fixture de teste: cadastro de Empresa, Setor e Funcionario (secao 12 do
documento "TCC - Analise Critica e Proposta de Evolucao"), em funcoes
puras (sem framework/ORM) para exercitar as regras da Fase 1.
"""


def validar_contratacao(funcionario, setor, empresa):
    if setor.ativo:
        if funcionario.idade >= 18:
            if funcionario.cpf_valido:
                if setor.empresa_id == empresa.id:
                    return True
    return False


def contratar_funcionario(funcionario, setor, empresa, conexao):
    if not validar_contratacao(funcionario, setor, empresa):
        raise ValueError("Contratacao nao permitida para este setor")

    try:
        conexao.execute(
            "INSERT INTO funcionario (nome, setor_id) VALUES (?, ?)",
            (funcionario.nome, setor.id),
        )
    except Exception as erro:
        raise RuntimeError(f"Falha ao contratar: {erro}")


def setores_no_limite(setores, limite=50):
    encontrados = []
    for setor in setores:
        total = 0
        for _funcionario in setor.funcionarios:
            total += 1
        if total >= limite:
            encontrados.append(setor)
    return encontrados
