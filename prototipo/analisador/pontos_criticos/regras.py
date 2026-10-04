"""
Regras de deteccao de pontos criticos sobre a AST (secao 8 do documento
"TCC - Analise Critica e Proposta de Evolucao").

Cada regra e deterministica: nao usa LLM. A saida e uma lista de objetos
PontoCritico {tipo, arquivo, linha, trecho, severidade}, a mesma estrutura
que depois alimenta o prompt do Claude (secao 7 do documento).

Simplificacao conhecida (v1): a deteccao de aninhamento usa a estrutura
sintatica direta (if dentro do block de outro if/elif/else). Padroes
especificos de framework (ex.: on_delete=CASCADE em modelos Django) nao
sao cobertos por esta versao - ver seção 13 (Fase 2+) para evolucao.
"""
from dataclasses import dataclass

DEPENDENCIAS_EXTERNAS = {
    "open", "requests", "urllib", "socket", "execute", "connect",
    "session", "post", "get", "put", "delete", "cursor",
}

PROFUNDIDADE_MINIMA_CONDICIONAL = 3
PROFUNDIDADE_MINIMA_LACO = 2

SEVERIDADE = {
    "chamada_dependencia_externa": 5,
    "try_except": 4,
    "condicional_aninhado": 3,
    "laco_aninhado": 3,
    "literal_em_condicional": 2,
}


@dataclass
class PontoCritico:
    tipo: str
    arquivo: str
    linha: int
    trecho: str
    severidade: int

    def to_dict(self):
        return {
            "tipo": self.tipo,
            "arquivo": self.arquivo,
            "linha": self.linha,
            "trecho": self.trecho,
            "severidade": self.severidade,
        }


def _percorrer(node):
    yield node
    for child in node.children:
        yield from _percorrer(child)


def _texto(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _linha(node) -> int:
    return node.start_point[0] + 1


def _profundidade_maxima(node, tipo_node: str) -> int:
    """Maior profundidade de aninhamento DIRETO de nos do tipo tipo_node a
    partir de node (node incluido, se for desse tipo)."""
    maior_abaixo = 0
    for child in node.children:
        maior_abaixo = max(maior_abaixo, _profundidade_maxima(child, tipo_node))
    return (1 + maior_abaixo) if node.type == tipo_node else maior_abaixo


def _e_raiz_de_cadeia(node, tipos_clausula) -> bool:
    """True se node nao esta diretamente aninhado dentro do corpo de uma
    clausula (if/elif/else, for, while) do mesmo tipo de cadeia -- usado
    para reportar cada cadeia de aninhamento uma unica vez, pelo seu topo."""
    pai = node.parent
    if pai is None or pai.type != "block":
        return True
    avo = pai.parent
    return avo is None or avo.type not in tipos_clausula


def _detectar_condicionais_aninhados(root, source, arquivo, pontos):
    clausulas_if = {"if_statement", "elif_clause", "else_clause"}
    for node in _percorrer(root):
        if node.type == "if_statement" and _e_raiz_de_cadeia(node, clausulas_if):
            profundidade = _profundidade_maxima(node, "if_statement")
            if profundidade >= PROFUNDIDADE_MINIMA_CONDICIONAL:
                pontos.append(PontoCritico(
                    tipo="condicional_aninhado", arquivo=arquivo, linha=_linha(node),
                    trecho=_texto(node, source).splitlines()[0],
                    severidade=SEVERIDADE["condicional_aninhado"],
                ))


def _detectar_lacos_aninhados(root, source, arquivo, pontos):
    clausulas_laco = {"for_statement", "while_statement"}
    for node in _percorrer(root):
        if node.type in clausulas_laco and _e_raiz_de_cadeia(node, clausulas_laco):
            profundidade = max(
                _profundidade_maxima(node, "for_statement"),
                _profundidade_maxima(node, "while_statement"),
            )
            if profundidade >= PROFUNDIDADE_MINIMA_LACO:
                pontos.append(PontoCritico(
                    tipo="laco_aninhado", arquivo=arquivo, linha=_linha(node),
                    trecho=_texto(node, source).splitlines()[0],
                    severidade=SEVERIDADE["laco_aninhado"],
                ))


def _detectar_try_except(root, source, arquivo, pontos):
    for node in _percorrer(root):
        if node.type == "try_statement":
            pontos.append(PontoCritico(
                tipo="try_except", arquivo=arquivo, linha=_linha(node),
                trecho=_texto(node, source).splitlines()[0],
                severidade=SEVERIDADE["try_except"],
            ))


def _nome_chamada(node):
    alvo = node.child_by_field_name("function")
    if alvo is None:
        return None
    if alvo.type == "identifier":
        return alvo.text.decode("utf-8")
    if alvo.type == "attribute":
        attr = alvo.child_by_field_name("attribute")
        return attr.text.decode("utf-8") if attr is not None else None
    return None


def _detectar_dependencias_externas(root, source, arquivo, pontos):
    for node in _percorrer(root):
        if node.type == "call":
            nome = _nome_chamada(node)
            if nome and nome in DEPENDENCIAS_EXTERNAS:
                pontos.append(PontoCritico(
                    tipo="chamada_dependencia_externa", arquivo=arquivo, linha=_linha(node),
                    trecho=_texto(node, source).splitlines()[0],
                    severidade=SEVERIDADE["chamada_dependencia_externa"],
                ))


def _detectar_literais_em_condicional(root, source, arquivo, pontos):
    for node in _percorrer(root):
        if node.type == "if_statement":
            condicao = node.child_by_field_name("condition")
            if condicao is None:
                continue
            tem_literal = any(n.type in ("integer", "float", "string") for n in _percorrer(condicao))
            if tem_literal:
                pontos.append(PontoCritico(
                    tipo="literal_em_condicional", arquivo=arquivo, linha=_linha(node),
                    trecho=_texto(condicao, source),
                    severidade=SEVERIDADE["literal_em_condicional"],
                ))


def identificar_pontos_criticos(root, source: bytes, arquivo: str):
    """Aplica todas as regras sobre a AST de um arquivo e devolve a lista de
    pontos criticos, ordenada por severidade (maior primeiro) -- a mesma
    ordenacao usada na secao 8 do documento para orientar o LLM."""
    pontos = []
    _detectar_condicionais_aninhados(root, source, arquivo, pontos)
    _detectar_lacos_aninhados(root, source, arquivo, pontos)
    _detectar_try_except(root, source, arquivo, pontos)
    _detectar_dependencias_externas(root, source, arquivo, pontos)
    _detectar_literais_em_condicional(root, source, arquivo, pontos)
    pontos.sort(key=lambda p: p.severidade, reverse=True)
    return pontos
