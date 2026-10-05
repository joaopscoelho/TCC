"""
Extracao da estrutura de um arquivo: definicoes, imports e chamadas.

Fase 2 (secao 13 do documento), parte deterministica. Nada aqui usa LLM:
e o material bruto que depois alimenta o prompt, conforme a secao 7 do
documento ("mapa estrutural" + pontos criticos). Separar esta camada do
LLM mantem o nucleo da ferramenta auditavel e testavel sem custo de API.
"""
from dataclasses import dataclass, field

from analisador.parser.ast_parser import linha_do_no, percorrer, texto_do_no

#: Tipos de no do Tree-sitter que introduzem um escopo nomeado.
TIPOS_DEFINICAO = ("function_definition", "class_definition")


@dataclass
class Definicao:
    """Uma funcao, metodo ou classe declarada no projeto."""

    nome: str
    qualificado: str
    tipo: str
    arquivo: str
    linha_inicio: int
    linha_fim: int
    assinatura: str
    pai: str = None

    def contem(self, linha: int) -> bool:
        return self.linha_inicio <= linha <= self.linha_fim

    def to_dict(self):
        return {
            "nome": self.nome,
            "qualificado": self.qualificado,
            "tipo": self.tipo,
            "arquivo": self.arquivo,
            "linha_inicio": self.linha_inicio,
            "linha_fim": self.linha_fim,
            "assinatura": self.assinatura,
            "pai": self.pai,
        }


@dataclass
class Import:
    """Uma declaracao de import do arquivo."""

    arquivo: str
    linha: int
    modulo: str
    nomes: list = field(default_factory=list)
    bruto: str = ""

    def to_dict(self):
        return {
            "arquivo": self.arquivo,
            "linha": self.linha,
            "modulo": self.modulo,
            "nomes": list(self.nomes),
            "bruto": self.bruto,
        }


@dataclass
class Chamada:
    """Uma chamada de funcao/metodo encontrada no codigo."""

    arquivo: str
    linha: int
    nome: str
    expressao: str
    origem: str = None

    def to_dict(self):
        return {
            "arquivo": self.arquivo,
            "linha": self.linha,
            "nome": self.nome,
            "expressao": self.expressao,
            "origem": self.origem,
        }


def nome_chamada(node, source: bytes):
    """Devolve (nome_simples, expressao) de um no de chamada.

    Para "conexao.execute(...)" o nome simples e "execute" e a expressao e
    "conexao.execute". O nome simples e o que permite ligar a chamada a uma
    definicao do proprio projeto; a expressao preserva o objeto chamado,
    que importa para explicar a dependencia externa ao usuario.
    """
    alvo = node.child_by_field_name("function")
    if alvo is None:
        return None, ""

    expressao = texto_do_no(alvo, source)
    if alvo.type == "identifier":
        return expressao, expressao
    if alvo.type == "attribute":
        attr = alvo.child_by_field_name("attribute")
        simples = texto_do_no(attr, source) if attr is not None else None
        return simples, expressao
    return None, expressao


def _coletar_definicoes(node, source, arquivo, pilha, definicoes):
    for filho in node.children:
        if filho.type in TIPOS_DEFINICAO:
            no_nome = filho.child_by_field_name("name")
            nome = texto_do_no(no_nome, source) if no_nome is not None else "<anonimo>"

            if filho.type == "class_definition":
                tipo = "classe"
            elif pilha and pilha[-1].tipo == "classe":
                tipo = "metodo"
            else:
                tipo = "funcao"

            caminho = [d.nome for d in pilha] + [nome]
            no_params = filho.child_by_field_name("parameters")
            params = texto_do_no(no_params, source) if no_params is not None else ""

            definicao = Definicao(
                nome=nome,
                qualificado=f"{arquivo}::{'.'.join(caminho)}",
                tipo=tipo,
                arquivo=arquivo,
                linha_inicio=linha_do_no(filho),
                linha_fim=filho.end_point[0] + 1,
                assinatura=f"{nome}{params}",
                pai=pilha[-1].qualificado if pilha else None,
            )
            definicoes.append(definicao)
            _coletar_definicoes(filho, source, arquivo, pilha + [definicao], definicoes)
        else:
            _coletar_definicoes(filho, source, arquivo, pilha, definicoes)


def extrair_definicoes(root, source: bytes, arquivo: str):
    """Lista as definicoes do arquivo, da mais externa para a mais interna."""
    definicoes = []
    _coletar_definicoes(root, source, arquivo, [], definicoes)
    return definicoes


def definicao_envolvente(definicoes, linha: int):
    """Definicao mais interna que contem a linha, ou None (codigo de modulo).

    "Mais interna" e a de menor intervalo de linhas: um metodo vence a
    classe que o contem, que vence o modulo. E esse nome que o usuario
    precisa ouvir junto com o ponto critico, para saber onde ele esta sem
    navegar o arquivo com o leitor de tela.
    """
    candidatas = [d for d in definicoes if d.contem(linha)]
    if not candidatas:
        return None
    return min(candidatas, key=lambda d: d.linha_fim - d.linha_inicio)


def extrair_imports(root, source: bytes, arquivo: str):
    """Lista os imports do arquivo (import X e from X import Y)."""
    imports = []
    for node in percorrer(root):
        if node.type == "import_statement":
            nomes = [texto_do_no(f, source) for f in node.children
                     if f.type in ("dotted_name", "aliased_import")]
            imports.append(Import(
                arquivo=arquivo, linha=linha_do_no(node), modulo="",
                nomes=nomes, bruto=texto_do_no(node, source),
            ))
        elif node.type == "import_from_statement":
            no_modulo = node.child_by_field_name("module_name")
            modulo = texto_do_no(no_modulo, source) if no_modulo is not None else ""
            nomes = [texto_do_no(f, source) for f in node.children
                     if f.type in ("dotted_name", "aliased_import") and f is not no_modulo]
            if any(f.type == "wildcard_import" for f in node.children):
                nomes.append("*")
            imports.append(Import(
                arquivo=arquivo, linha=linha_do_no(node), modulo=modulo,
                nomes=nomes, bruto=texto_do_no(node, source),
            ))
    return imports


def extrair_chamadas(root, source: bytes, arquivo: str, definicoes=None):
    """Lista as chamadas do arquivo, cada uma com a definicao de origem."""
    if definicoes is None:
        definicoes = extrair_definicoes(root, source, arquivo)

    chamadas = []
    for node in percorrer(root):
        if node.type != "call":
            continue
        simples, expressao = nome_chamada(node, source)
        if not simples:
            continue
        linha = linha_do_no(node)
        origem = definicao_envolvente(definicoes, linha)
        chamadas.append(Chamada(
            arquivo=arquivo, linha=linha, nome=simples, expressao=expressao,
            origem=origem.qualificado if origem is not None else None,
        ))
    return chamadas
