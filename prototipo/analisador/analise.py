"""
Orquestracao da analise estatica: amarra parser, contexto e regras.

Fase 1 + parte deterministica da Fase 2 (secao 13 do documento). Este
modulo e o unico ponto que o restante da ferramenta (LLM, formatacao, CLI,
NVDA) precisa conhecer para obter o resultado da analise de um projeto.
"""
from dataclasses import dataclass, field

from analisador.contexto.mapa import construir_mapa
from analisador.pontos_criticos.agrupamento import agrupar
from analisador.pontos_criticos.regras import identificar_pontos_criticos


@dataclass
class ResultadoAnalise:
    """Resultado completo da analise de um projeto."""

    caminho: str
    mapa: object
    pontos: list = field(default_factory=list)
    grupos: list = field(default_factory=list)

    @property
    def erros_sintaxe(self):
        return self.mapa.erros_sintaxe

    def to_dict(self):
        """Forma serializavel -- entrada do prompt da Fase 2 e da saida --json."""
        return {
            "caminho": self.caminho,
            "resumo_projeto": self.mapa.resumo(),
            "pontos": [p.to_dict() for p in self.pontos],
            "grupos": [g.to_dict() for g in self.grupos],
            "contextos": {
                g.escopo: self.mapa.contexto(g.arquivo, g.linha_inicio)
                for g in self.grupos
            },
        }


def analisar(caminho, ignorar=None) -> ResultadoAnalise:
    """Analisa um arquivo ou projeto e devolve pontos criticos com contexto."""
    mapa = construir_mapa(caminho, ignorar=ignorar)

    pontos = []
    for arquivo in mapa.arquivos:
        pontos.extend(identificar_pontos_criticos(
            arquivo.root, arquivo.source, arquivo.relativo))
    pontos.sort(key=lambda p: (-p.severidade, p.arquivo, p.linha))

    return ResultadoAnalise(
        caminho=str(caminho), mapa=mapa, pontos=pontos,
        grupos=agrupar(pontos, mapa=mapa),
    )
