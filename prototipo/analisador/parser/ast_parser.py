"""
Carrega codigo Python e produz sua arvore sintatica (AST) via Tree-sitter.

Fase 1 do plano de implementacao (secao 13 do documento "TCC - Analise
Critica e Proposta de Evolucao"): este modulo nao depende de nenhum LLM.

Alem do parse, expoe a deteccao de erros de sintaxe: o Tree-sitter e
tolerante a falhas e devolve uma arvore parcial para codigo invalido, o
que faria o analisador seguir em silencio sobre um arquivo incompleto.
Como o publico-alvo da ferramenta nao enxerga a tela do editor, o aviso
de codigo invalido precisa ser explicito (secoes 7 e 8 do documento).
"""
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

_LANGUAGE = Language(tspython.language())


@dataclass
class ErroSintaxe:
    """Trecho que o Tree-sitter nao conseguiu reconhecer."""

    arquivo: str
    linha: int
    descricao: str
    trecho: str

    def to_dict(self):
        return {
            "arquivo": self.arquivo,
            "linha": self.linha,
            "descricao": self.descricao,
            "trecho": self.trecho,
        }


def parse_source(source: bytes):
    """Faz o parse de um codigo-fonte Python (em bytes) e devolve o no raiz da AST."""
    parser = Parser(_LANGUAGE)
    tree = parser.parse(source)
    return tree.root_node


def parse_file(caminho):
    """Le um arquivo .py do disco e devolve (no raiz, bytes do codigo-fonte)."""
    caminho = Path(caminho)
    source = caminho.read_bytes()
    return parse_source(source), source


def percorrer(node):
    """Gera node e todos os seus descendentes, em pre-ordem."""
    yield node
    for child in node.children:
        yield from percorrer(child)


def texto_do_no(node, source: bytes) -> str:
    """Trecho de codigo-fonte correspondente a node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def linha_do_no(node) -> int:
    """Linha inicial de node, contada a partir de 1 (como o editor mostra)."""
    return node.start_point[0] + 1


def erros_de_sintaxe(root, source: bytes, arquivo: str):
    """Lista os pontos onde o parse falhou.

    Dois casos sao reportados: nos do tipo ERROR (trecho que nao casou com
    nenhuma regra da gramatica) e nos marcados como is_missing (token que a
    gramatica esperava e nao encontrou, por exemplo um ":" ausente). Fora
    desses casos a arvore e confiavel para as regras da Fase 1.
    """
    erros = []
    if not root.has_error:
        return erros

    for node in percorrer(root):
        if node.is_missing:
            erros.append(ErroSintaxe(
                arquivo=arquivo,
                linha=linha_do_no(node),
                descricao=f"token ausente: {node.type}",
                trecho=texto_do_no(node.parent, source).splitlines()[0] if node.parent else "",
            ))
        elif node.type == "ERROR":
            primeira_linha = texto_do_no(node, source).splitlines()
            erros.append(ErroSintaxe(
                arquivo=arquivo,
                linha=linha_do_no(node),
                descricao="trecho nao reconhecido pela gramatica Python",
                trecho=primeira_linha[0] if primeira_linha else "",
            ))

    erros.sort(key=lambda e: e.linha)
    return erros
