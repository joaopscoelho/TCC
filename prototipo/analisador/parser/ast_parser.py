"""
Carrega um arquivo Python e produz sua arvore sintatica (AST) via Tree-sitter.

Fase 1 do plano de implementacao (secao 13 do documento "TCC - Analise
Critica e Proposta de Evolucao"): este modulo nao depende de nenhum LLM.
"""
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

_LANGUAGE = Language(tspython.language())


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
