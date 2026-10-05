"""
Fixture: relatorios que atravessam os outros dois modulos, para exercitar
o grafo de chamadas entre arquivos (secao 7 do documento).
"""
from persistencia import contratar_funcionario
from regras_negocio import setor_no_limite


def setores_sobrecarregados(empresas):
    encontrados = []
    for empresa in empresas:
        for setor in empresa.setores:
            if setor_no_limite(setor):
                encontrados.append(setor)
    return encontrados


def contratar_em_lote(pedidos, repositorio):
    falhas = []
    for pedido in pedidos:
        try:
            contratar_funcionario(pedido.funcionario, pedido.setor,
                                  pedido.empresa, repositorio)
        except ValueError as erro:
            falhas.append(str(erro))
    return falhas
