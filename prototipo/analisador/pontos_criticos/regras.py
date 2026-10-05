"""
Regras de deteccao de pontos criticos sobre a AST (secao 8 do documento
"TCC - Analise Critica e Proposta de Evolucao").

Cada regra e deterministica: nao usa LLM. A saida e uma lista de objetos
PontoCritico {tipo, arquivo, linha, trecho, severidade}, a mesma estrutura
que depois alimenta o prompt do Claude (secao 7 do documento).

Simplificacao conhecida (v1): verbos ambiguos (get, post, save, query)
so sao reportados em arquivos que importam biblioteca de rede ou de
banco -- sem inferencia de tipos nao da para distinguir "requisicao.get"
de "dicionario.get", e o falso positivo custa mais ao usuario do que a
deteccao perdida.

Simplificacao conhecida (v1): a deteccao de aninhamento usa a estrutura
sintatica direta (if dentro do block de outro if/elif/else). Padroes
especificos de framework (ex.: on_delete=CASCADE em modelos Django) nao
sao cobertos por esta versao - ver seção 13 (Fase 2+) para evolucao.
"""
from dataclasses import dataclass

from analisador.parser.ast_parser import linha_do_no, percorrer, texto_do_no

#: Nomes que caracterizam dependencia externa sem ambiguidade: so
#: aparecem quando o codigo realmente sai para arquivo, rede ou banco.
DEPENDENCIAS_EXTERNAS = {
    "open", "execute", "executemany", "executescript", "connect", "cursor",
    "commit", "rollback", "urlopen", "urlretrieve", "socket", "recv",
    "sendall", "requests",
}

#: Verbos que nomeiam tanto operacao de rede/banco quanto metodo comum de
#: estrutura de dados ("dicionario.get", "lista.pop"). Reportar sempre
#: produz falso positivo grave: rodando o analisador sobre o proprio
#: prototipo, todo "dicionario.get" virava dependencia externa de
#: severidade 5. Por isso so valem quando o arquivo importa alguma
#: biblioteca de rede ou de banco de dados.
DEPENDENCIAS_AMBIGUAS = {
    "get", "post", "put", "patch", "delete", "head", "session", "query",
    "fetchone", "fetchall", "save",
}

#: Bibliotecas cuja presenca nos imports torna os verbos ambiguos crediveis.
MODULOS_DE_REDE_OU_BANCO = {
    "requests", "httpx", "urllib", "urllib3", "http", "aiohttp", "socket",
    "ftplib", "smtplib", "sqlite3", "psycopg2", "psycopg", "pymysql",
    "mysql", "sqlalchemy", "pymongo", "redis", "boto3", "django", "flask",
    "fastapi", "models",
}

#: Literais que NAO caracterizam regra de negocio: sao idiomas da
#: linguagem (lista vazia, indice zero, comparacao com None/booleano).
#: Sem este filtro a regra "literal_em_condicional" dispara em quase todo
#: "if" de codigo real e inunda a saida -- custo direto para quem ouve o
#: resultado em leitor de tela (secao 8 do documento).
LITERAIS_TRIVIAIS = {"0", "1", "-1", "None", "True", "False", '""', "''"}

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


_percorrer = percorrer
_texto = texto_do_no
_linha = linha_do_no


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


def _modulos_importados(root, source: bytes):
    """Nomes de modulo citados nos imports do arquivo.

    Scan deliberadamente local: a Fase 1 nao depende da camada de contexto
    (Fase 2), que extrai os imports de forma completa para o prompt. Aqui
    basta o primeiro segmento de cada nome importado."""
    modulos = set()
    for node in _percorrer(root):
        if node.type in ("import_statement", "import_from_statement"):
            for filho in _percorrer(node):
                if filho.type == "dotted_name":
                    modulos.add(_texto(filho, source).split(".")[0])
    return modulos


def _detectar_dependencias_externas(root, source, arquivo, pontos):
    importados = _modulos_importados(root, source)
    aceita_ambiguas = bool(importados & MODULOS_DE_REDE_OU_BANCO)
    nomes_aceitos = DEPENDENCIAS_EXTERNAS | (DEPENDENCIAS_AMBIGUAS if aceita_ambiguas else set())

    for node in _percorrer(root):
        if node.type == "call":
            nome = _nome_chamada(node)
            if nome and nome in nomes_aceitos:
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
            literais = [_texto(n, source).strip()
                        for n in _percorrer(condicao)
                        if n.type in ("integer", "float", "string")]
            relevantes = [lit for lit in literais if lit not in LITERAIS_TRIVIAIS]
            if relevantes:
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
