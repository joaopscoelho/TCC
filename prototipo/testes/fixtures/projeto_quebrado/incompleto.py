# Fixture PROPOSITALMENTE invalido: usado para verificar que o analisador
# avisa sobre erro de sintaxe em vez de analisar uma arvore incompleta em
# silencio. Este arquivo nunca e importado.
def calcular_total(itens:
    total = 0
    for item in itens
        total += item.valor
    return total
