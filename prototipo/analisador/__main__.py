"""
Runner minimo de linha de comando: "python -m analisador <caminho>".

Fase 1 e 2 (secao 13 do documento). Nao e a CLI final: a navegacao por
etapas (listar, proximo, detalhe N, buscar) e a Fase 4, e a formatacao
acessivel definitiva e a Fase 3. Com --falar, o relatorio tambem e entregue
ao NVDA (so Windows, ver analisador/nvda).

Sem --explicar, roda so a analise estatica (sem modelo, sem rede). Com
--explicar, pede a um modelo local (Ollama) a visao geral e a explicacao de
cada regiao; se o modelo nao estiver disponivel, o erro e dito em palavras e
a analise estatica e entregue mesmo assim.

Mesmo provisoria, a saida ja respeita as restricoes de acessibilidade da
secao 8: texto corrido, sem tabelas, sem simbolos decorativos e com a
posicao anunciada em palavras ("ponto critico 1 de 3").
"""
import argparse
import json
import sys

from analisador.analise import analisar
from analisador.explicacao import explicar
from analisador.llm import ErroConfiguracaoLLM, criar_explicador
from analisador.llm.local import CONTEXTO_PADRAO
from analisador.nvda import ErroFala, criar_falador

NOMES_TIPO = {
    "chamada_dependencia_externa": "chamada a dependencia externa",
    "try_except": "tratamento de excecao",
    "condicional_aninhado": "condicional aninhado",
    "laco_aninhado": "laco aninhado",
    "literal_em_condicional": "valor fixo em condicional",
}


def _descrever_tipo(tipo: str) -> str:
    return NOMES_TIPO.get(tipo, tipo.replace("_", " "))


def _plural(quantidade: int, singular: str, plural: str) -> str:
    """Concorda numero e substantivo.

    Em leitura por sintese de voz, construcoes como "1 ponto ou pontos"
    custam tempo e atrapalham a compreensao: a concordancia precisa estar
    resolvida no texto, nao no ouvido de quem escuta."""
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _linhas_erros_sintaxe(resultado):
    if not resultado.erros_sintaxe:
        return []
    quantos = _plural(len(resultado.erros_sintaxe), "erro de sintaxe", "erros de sintaxe")
    linhas = ["", f"Atencao: {quantos}. Nestes arquivos a analise pode estar incompleta."]
    for erro in resultado.erros_sintaxe:
        linhas.append(f"  No arquivo {erro.arquivo}, linha {erro.linha}: {erro.descricao}.")
    return linhas


def relatorio_texto(resultado) -> str:
    """Monta o relatorio estatico em texto corrido, pronto para leitura por voz."""
    mapa = resultado.mapa
    arquivos = _plural(len(mapa.arquivos), "arquivo analisado", "arquivos analisados")
    definicoes = _plural(len(mapa.definicoes), "definicao encontrada", "definicoes encontradas")
    linhas = [f"Analise de {resultado.caminho}.", f"{arquivos}, {definicoes}."]
    linhas.extend(_linhas_erros_sintaxe(resultado))

    if not resultado.grupos:
        linhas.append("")
        linhas.append("Nenhum ponto critico encontrado.")
        return "\n".join(linhas)

    linhas.append("")
    pontos = _plural(len(resultado.pontos), "ponto critico", "pontos criticos")
    regioes = _plural(len(resultado.grupos), "regiao de codigo", "regioes de codigo")
    linhas.append(f"Foram encontrados {pontos}, distribuidos em {regioes}.")

    total_grupos = len(resultado.grupos)
    for indice, grupo in enumerate(resultado.grupos, start=1):
        contexto = mapa.contexto(grupo.arquivo, grupo.linha_inicio)
        linhas.append("")
        quantos = _plural(grupo.total, "ponto critico", "pontos criticos")
        linhas.append(f"Regiao {indice} de {total_grupos}: {grupo.rotulo}, "
                      f"no arquivo {grupo.arquivo}, a partir da linha {grupo.linha_inicio}. "
                      f"{quantos}, severidade maxima {grupo.severidade}.")

        if contexto["chamada_por"]:
            linhas.append("  Esta regiao e chamada por: "
                          + ", ".join(contexto["chamada_por"]) + ".")
        else:
            linhas.append("  Nenhuma outra parte do projeto chama esta regiao. "
                          "Ela e um possivel ponto de entrada do fluxo.")

        if contexto["chamadas_externas"]:
            linhas.append("  Depende de codigo externo ao projeto: "
                          + ", ".join(contexto["chamadas_externas"]) + ".")

        for n, ponto in enumerate(grupo.pontos, start=1):
            linhas.append(f"  Ponto critico {n} de {grupo.total}: "
                          f"{_descrever_tipo(ponto.tipo)}, linha {ponto.linha}, "
                          f"severidade {ponto.severidade}. "
                          f"Trecho: {ponto.trecho.strip()}")

    return "\n".join(linhas)


def _corpo_da_explicacao(explicacao):
    """Linhas de uma Explicacao: o texto, ou o motivo de nao existir."""
    if not explicacao.ok:
        return [f"Nao foi possivel gerar esta explicacao. {explicacao.erro}"]
    linhas = [explicacao.texto]
    linhas.extend(f"Aviso: {aviso}" for aviso in explicacao.avisos)
    return linhas


def relatorio_explicado(resultado, explicacao) -> str:
    """Monta o relatorio com a explicacao do modelo, em texto corrido."""
    linhas = [f"Analise de {resultado.caminho}."]
    linhas.extend(_linhas_erros_sintaxe(resultado))

    linhas.append("")
    linhas.append("Visao geral do projeto.")
    linhas.extend(_corpo_da_explicacao(explicacao.visao_geral))

    explicadas = len(explicacao.regioes)
    total = len(resultado.grupos)
    for indice, (grupo, item) in enumerate(zip(resultado.grupos, explicacao.regioes), start=1):
        quantos = _plural(grupo.total, "ponto critico", "pontos criticos")
        linhas.append("")
        linhas.append(f"Regiao {indice} de {total}: {grupo.rotulo}, no arquivo "
                      f"{grupo.arquivo}. {quantos}, severidade maxima {grupo.severidade}.")
        linhas.extend(_corpo_da_explicacao(item))

    if explicadas < total:
        linhas.append("")
        linhas.append(f"Explicacao gerada para {explicadas} de {total} regioes, "
                      "as de maior gravidade.")

    modelo = explicacao.modelo.get("modelo", "desconhecido")
    linhas.append("")
    linhas.append(f"Explicacao gerada pelo modelo {modelo}, em {explicacao.duracao_s} "
                  "segundos. Texto gerado por modelo de linguagem pode conter erros: "
                  "confira no codigo antes de decidir.")
    return "\n".join(linhas)


def _progresso(etapa, total, titulo):
    """Avisa em stderr que o modelo ainda esta trabalhando (leva minutos)."""
    print(f"Gerando explicacao {etapa} de {total}: {titulo}.", file=sys.stderr, flush=True)


def _configurar_saida():
    """Garante UTF-8: a explicacao do modelo vem acentuada, e a saida
    redirecionada para arquivo no Windows usa por padrao outra codificacao."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m analisador",
        description="Analisa um arquivo ou projeto Python e lista os pontos "
                    "criticos com o contexto estrutural de cada um.",
    )
    parser.add_argument("caminho", help="arquivo .py ou pasta do projeto")
    parser.add_argument("--json", action="store_true",
                        help="imprime o resultado em JSON")
    parser.add_argument("--explicar", action="store_true",
                        help="pede a um modelo local (Ollama) a visao geral e a "
                             "explicacao de cada regiao")
    parser.add_argument("--modelo", default=None,
                        help="modelo do Ollama (padrao: variavel ANALISADOR_MODELO "
                             "ou qwen3:8b)")
    parser.add_argument("--host", default=None,
                        help="endereco do Ollama (padrao: variavel OLLAMA_HOST ou "
                             "127.0.0.1:11434)")
    parser.add_argument("--contexto", type=int, default=CONTEXTO_PADRAO,
                        help=f"janela de contexto em tokens (padrao: {CONTEXTO_PADRAO})")
    parser.add_argument("--max-regioes", type=int, default=None,
                        help="explica so as N regioes mais graves")
    parser.add_argument("--falar", action="store_true",
                        help="alem de imprimir, fala o relatorio pelo NVDA "
                             "(so Windows, com o NVDA aberto)")
    parser.add_argument("--dll", default=None,
                        help="caminho do nvdaControllerClient.dll (padrao: variavel "
                             "NVDA_CONTROLLER_DLL ou a pasta bibliotecas)")
    args = parser.parse_args(argv)
    if args.falar and args.json:
        parser.error("--falar nao se combina com --json: JSON nao serve para ouvir.")

    _configurar_saida()

    # O NVDA e conferido antes da analise e do modelo: se nao estiver no ar,
    # o erro aparece em segundos, nao depois de minutos de geracao.
    falador = None
    erro_fala = None
    if args.falar:
        try:
            falador = criar_falador("nvda", caminho_dll=args.dll)
            falador.verificar()
        except ErroFala as erro:
            falador = None
            erro_fala = str(erro)
            print(f"Erro: {erro_fala}", file=sys.stderr)
            print("O relatorio sera entregue apenas como texto.", file=sys.stderr)

    resultado = analisar(args.caminho)

    explicacao = None
    erro_explicacao = None
    if args.explicar:
        try:
            explicador = criar_explicador("local", modelo=args.modelo, host=args.host,
                                          contexto=args.contexto)
            explicacao = explicar(resultado, explicador, max_regioes=args.max_regioes,
                                  ao_progredir=_progresso)
        except ErroConfiguracaoLLM as erro:
            erro_explicacao = str(erro)
            print(f"Erro: {erro_explicacao}", file=sys.stderr)
            print("A explicacao nao foi gerada. Segue a analise estatica.", file=sys.stderr)

    if args.json:
        dados = resultado.to_dict()
        if explicacao is not None:
            dados["explicacao"] = explicacao.to_dict()
        if erro_explicacao is not None:
            dados["erro_explicacao"] = erro_explicacao
        print(json.dumps(dados, ensure_ascii=False, indent=2))
    else:
        if explicacao is not None:
            texto = relatorio_explicado(resultado, explicacao)
        else:
            texto = relatorio_texto(resultado)
        print(texto)
        if falador is not None:
            try:
                falador.falar(texto)
            except ErroFala as erro:
                erro_fala = str(erro)
                print(f"Erro: {erro_fala}", file=sys.stderr)

    if erro_explicacao is not None:
        return 2
    return 3 if erro_fala is not None else 0


if __name__ == "__main__":
    sys.exit(main())
