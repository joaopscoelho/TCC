"""
Agrupamento dos pontos criticos por regiao de codigo.

Motivacao (secoes 7 e 8 do documento): a lista crua de pontos criticos
repete a mesma regiao varias vezes. No fixture da secao 12, o "try" da
linha 21 e a chamada "conexao.execute" da linha 22 sao o mesmo trecho e
chegavam ao usuario como dois itens independentes. Em leitura linear por
sintese de voz, cada item repetido e tempo gasto sem informacao nova.

A solucao adotada nao descarta pontos: reorganiza a saida por funcao
envolvente, de modo que o usuario ouca "nesta funcao existem N pontos
criticos" e so depois o detalhe de cada um. Nada e perdido, e a navegacao
por etapas da Fase 4 passa a ter uma unidade natural (a funcao).
"""
from dataclasses import dataclass, field

ESCOPO_MODULO = "<codigo de modulo>"


@dataclass
class GrupoPontos:
    """Pontos criticos de uma mesma regiao (funcao, metodo ou modulo)."""

    arquivo: str
    escopo: str
    rotulo: str
    linha_inicio: int
    pontos: list = field(default_factory=list)

    @property
    def severidade(self) -> int:
        """Severidade do grupo e a do seu ponto mais grave."""
        return max((p.severidade for p in self.pontos), default=0)

    @property
    def total(self) -> int:
        return len(self.pontos)

    def to_dict(self):
        return {
            "arquivo": self.arquivo,
            "escopo": self.escopo,
            "rotulo": self.rotulo,
            "linha_inicio": self.linha_inicio,
            "severidade": self.severidade,
            "total": self.total,
            "pontos": [p.to_dict() for p in self.pontos],
        }


def colapsar_duplicatas(pontos):
    """Remove pontos identicos em tipo e linha, preservando a ordem.

    Duas regras podem alcancar o mesmo no (por exemplo um "for" que e ao
    mesmo tempo raiz de cadeia e corpo de outra cadeia). O usuario nao tem
    como distinguir dois itens com tipo e linha iguais, logo repetir e so
    ruido.
    """
    vistos = set()
    unicos = []
    for ponto in pontos:
        chave = (ponto.arquivo, ponto.tipo, ponto.linha)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(ponto)
    return unicos


def agrupar(pontos, mapa=None):
    """Agrupa pontos criticos por funcao envolvente.

    Com o mapa do projeto (analisador.contexto.mapa), o rotulo do grupo e a
    assinatura da funcao; sem ele, o agrupamento cai para o arquivo, de modo
    que as regras continuem utilizaveis isoladamente nos testes.

    A ordem final e por severidade do grupo (maior primeiro) e, em empate,
    por arquivo e linha -- a mesma ordenacao da lista plana, para que a
    sequencia que o usuario ouve nao mude entre as duas visoes.
    """
    grupos = {}
    for ponto in colapsar_duplicatas(pontos):
        definicao = mapa.envolvente(ponto.arquivo, ponto.linha) if mapa is not None else None

        if definicao is not None:
            chave = definicao.qualificado
            rotulo = definicao.assinatura
            linha_inicio = definicao.linha_inicio
        else:
            chave = f"{ponto.arquivo}::{ESCOPO_MODULO}"
            rotulo = ESCOPO_MODULO
            linha_inicio = ponto.linha

        grupo = grupos.get(chave)
        if grupo is None:
            grupo = GrupoPontos(arquivo=ponto.arquivo, escopo=chave,
                                rotulo=rotulo, linha_inicio=linha_inicio)
            grupos[chave] = grupo
        grupo.pontos.append(ponto)
        grupo.linha_inicio = min(grupo.linha_inicio, linha_inicio)

    for grupo in grupos.values():
        grupo.pontos.sort(key=lambda p: (-p.severidade, p.linha))

    return sorted(grupos.values(),
                  key=lambda g: (-g.severidade, g.arquivo, g.linha_inicio))
