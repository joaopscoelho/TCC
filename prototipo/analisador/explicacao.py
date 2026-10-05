"""
Orquestracao da explicacao: visao geral + uma explicacao por regiao.

Fase 2 (secoes 7 e 13 do documento). Recebe o resultado da analise
estatica e um ExplicadorLLM qualquer; nao sabe se o modelo e local ou em
nuvem. A analise estatica continua sendo a fonte da verdade: o modelo
explica o que o analisador encontrou, e nao decide o que e ponto critico.

Politica de falhas, pensada para quem usa a saida sem ver a tela:
- Erro de configuracao (servidor fora do ar, modelo nao baixado) se
  repetiria em todas as chamadas: a geracao para na hora, antes de gastar
  minutos de processamento, e o erro sobe para a CLI.
- Erro isolado (resposta vazia, prompt grande demais, tempo esgotado)
  afeta so aquela regiao: ela e registrada com o motivo e as demais
  seguem. Uma regiao sem explicacao e declarada, nunca omitida.
"""
import time
from dataclasses import dataclass, field

from analisador.llm.base import ErroConfiguracaoLLM, ErroLLM
from analisador.llm.prompts import mensagens_regiao, mensagens_visao_geral


@dataclass
class Explicacao:
    """Texto gerado para uma parte da analise, ou o motivo de nao existir."""

    titulo: str
    texto: str = None
    erro: str = None
    avisos: list = field(default_factory=list)
    resposta: dict = None

    @property
    def ok(self) -> bool:
        return self.erro is None and bool(self.texto)

    def to_dict(self):
        return {
            "titulo": self.titulo,
            "texto": self.texto,
            "erro": self.erro,
            "avisos": list(self.avisos),
            "resposta": self.resposta,
        }


@dataclass
class ResultadoExplicacao:
    """Visao geral e explicacoes por regiao, com a configuracao do modelo."""

    visao_geral: Explicacao
    regioes: list
    modelo: dict
    duracao_s: float

    def to_dict(self):
        return {
            "modelo": self.modelo,
            "duracao_s": self.duracao_s,
            "visao_geral": self.visao_geral.to_dict(),
            "regioes": [r.to_dict() for r in self.regioes],
        }


def explicar(resultado, llm, max_regioes=None, ao_progredir=None) -> ResultadoExplicacao:
    """Gera a visao geral e a explicacao das regioes mais graves.

    max_regioes limita quantas regioes sao explicadas (as de maior
    severidade vem primeiro). ao_progredir(etapa, total, titulo), se dado,
    e chamado antes de cada geracao: no hardware local, cada uma leva de
    segundos a minutos, e a CLI precisa dizer que ainda esta trabalhando.
    """
    inicio = time.monotonic()
    llm.verificar()

    grupos = resultado.grupos if max_regioes is None else resultado.grupos[:max_regioes]
    total = len(grupos) + 1

    def gerar(etapa, titulo, mensagens):
        if ao_progredir is not None:
            ao_progredir(etapa, total, titulo)
        try:
            resposta = llm.gerar(mensagens)
        except ErroConfiguracaoLLM:
            raise
        except ErroLLM as erro:
            return Explicacao(titulo=titulo, erro=str(erro))

        avisos = list(resposta.avisos)
        if resposta.cortada:
            avisos.append("A resposta foi cortada pelo limite de tamanho "
                          "e pode estar incompleta.")
        return Explicacao(titulo=titulo, texto=resposta.texto, avisos=avisos,
                          resposta=resposta.to_dict())

    if resultado.mapa.arquivos:
        visao_geral = gerar(1, "visao geral do projeto", mensagens_visao_geral(resultado))
    else:
        visao_geral = Explicacao(titulo="visao geral do projeto",
                                 erro="Nenhum arquivo Python foi encontrado.")

    regioes = [
        gerar(i, grupo.rotulo, mensagens_regiao(resultado.mapa, grupo))
        for i, grupo in enumerate(grupos, start=2)
    ]

    return ResultadoExplicacao(
        visao_geral=visao_geral, regioes=regioes, modelo=llm.descricao(),
        duracao_s=round(time.monotonic() - inicio, 2),
    )
