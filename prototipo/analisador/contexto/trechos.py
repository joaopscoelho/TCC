"""
Extracao do trecho de codigo de uma regiao, para entrar no prompt.

Fase 2 (secao 13 do documento). O modelo so pode explicar o que ve: sem o
codigo, ele inventaria o comportamento a partir dos nomes. As linhas vao
numeradas para que a explicacao consiga apontar onde esta cada ponto.
"""
from dataclasses import dataclass

MAX_LINHAS_PADRAO = 80
FOLGA_MODULO = 3


@dataclass
class Trecho:
    texto: str
    linha_inicio: int
    linha_fim: int
    omitidas: int = 0


def linhas_do_arquivo(source: bytes):
    """Linhas do arquivo contadas como o Tree-sitter conta (so "\\n")."""
    texto = source.decode("utf-8", errors="replace")
    return [linha.rstrip("\r") for linha in texto.split("\n")]


def trecho_da_regiao(mapa, grupo, max_linhas=MAX_LINHAS_PADRAO) -> Trecho:
    """Codigo da regiao com numero de linha, cortado em max_linhas.

    Funcao ou metodo: o corpo inteiro. Codigo de modulo: a faixa que cobre
    os pontos criticos, com uma folga de tres linhas. Se passar do limite,
    o corte e declarado em "omitidas" para o prompt avisar o modelo.
    """
    analisado = mapa.arquivo_analisado(grupo.arquivo)
    if analisado is None:
        return Trecho("", 0, 0)

    linhas = linhas_do_arquivo(analisado.source)
    definicao = mapa.definicoes.get(grupo.escopo)
    if definicao is not None:
        inicio, fim = definicao.linha_inicio, definicao.linha_fim
    else:
        alvos = [p.linha for p in grupo.pontos]
        inicio = max(1, min(alvos) - FOLGA_MODULO)
        fim = max(alvos) + FOLGA_MODULO

    fim = min(fim, len(linhas))
    omitidas = max(0, (fim - inicio + 1) - max_linhas)
    if omitidas:
        fim = inicio + max_linhas - 1

    texto = "\n".join(f"{n}: {linhas[n - 1]}" for n in range(inicio, fim + 1))
    return Trecho(texto=texto, linha_inicio=inicio, linha_fim=fim, omitidas=omitidas)
