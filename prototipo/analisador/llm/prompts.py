"""
Prompts da Fase 2 (secoes 7, 8 e 13 do documento): visao geral do projeto
e explicacao por regiao de codigo.

Duas decisoes de projeto moram aqui e merecem ser lidas antes de mexer:

1. As regras de acessibilidade ficam NO PROMPT, e nao so numa etapa de
   pos-processamento. Pedir ao modelo a forma certa de primeira produz um
   texto melhor do que limpar um texto errado depois. A Fase 3 vai
   conferir se o modelo obedeceu; ela nao precisa consertar tudo.

2. A regra de negocio deduzida de nomes e SEMPRE marcada com a palavra
   fixa MARCADOR_INFERENCIA. Quem ouve a explicacao por sintese de voz nao
   consegue "ver" que um trecho e suposicao; precisa ouvir isso. E, por
   ser uma palavra fixa, a Fase 3 consegue contar quantas vezes ela
   aparece e verificar se a marcacao foi feita.

Os textos enviados ao modelo levam acentuacao completa: modelos
multilingues escrevem melhor em portugues quando o prompt esta em
portugues correto. Ja as mensagens de erro e o relatorio estatico da CLI
seguem sem acento, como o restante do prototipo.
"""
from analisador.contexto.trechos import MAX_LINHAS_PADRAO, trecho_da_regiao
from analisador.llm.base import Mensagem

#: Palavra fixa que abre toda frase que e deducao, e nao fato do codigo.
MARCADOR_INFERENCIA = "Inferência:"

MAX_FRASES_VISAO_GERAL = 8
MAX_FRASES_REGIAO = 12
MAX_ARQUIVOS_NO_PROMPT = 40
MAX_DEFINICOES_POR_ARQUIVO = 15
MAX_ENTRADAS_NO_PROMPT = 10
MAX_DEPENDENCIAS_NO_PROMPT = 15
MAX_REGIOES_NO_PROMPT = 5

DESCRICAO_TIPO = {
    "chamada_dependencia_externa": "chamada a dependência externa, como banco de dados, arquivo ou rede",
    "try_except": "tratamento de exceção",
    "condicional_aninhado": "condicionais aninhados em vários níveis",
    "laco_aninhado": "laços aninhados",
    "literal_em_condicional": "valor fixo usado em uma condição",
}

DESCRICAO_DEFINICAO = {"funcao": "função", "metodo": "método", "classe": "classe"}

PROMPT_SISTEMA = (
    "Você explica código-fonte Python para programadores com deficiência visual, "
    "que ouvem a sua resposta em um leitor de tela com síntese de voz. Eles não "
    "veem a tela: a explicação precisa ser compreensível apenas ouvindo, de uma "
    "só vez, sem voltar atrás.\n"
    "\n"
    "Regras de conteúdo:\n"
    "- Use somente as informações fornecidas na mensagem do usuário: nomes, "
    "trechos de código, chamadas e pontos críticos. Não invente comportamento "
    "que não esteja no código.\n"
    "- Explique primeiro o que o trecho faz e depois por que cada ponto crítico "
    "merece atenção.\n"
    "- Quando você deduzir a regra de negócio a partir de nomes de variáveis, "
    "de funções ou de valores fixos, e não de uma condição explícita no código, "
    f"comece essa frase com a palavra \"{MARCADOR_INFERENCIA}\". Nunca apresente "
    "uma dedução como se fosse um fato.\n"
    "- Se uma informação necessária não estiver disponível, diga que ela não "
    "está disponível.\n"
    "\n"
    "Regras de forma, todas obrigatórias:\n"
    "- Escreva em português brasileiro, com palavras do Brasil: \"arquivo\" e "
    "não \"ficheiro\", \"tela\" e não \"ecrã\", \"você\" e não \"tu\".\n"
    "- Escreva em texto corrido, com frases curtas de no máximo vinte palavras.\n"
    "- Não use tabelas, listas com marcadores, numeração de itens, títulos, "
    "negrito, itálico, crases, blocos de código nem símbolos decorativos. Use "
    "apenas letras, números e pontuação comum.\n"
    "- Escreva o nome de cada função ou variável uma única vez e depois diga "
    "\"esta função\" ou \"ela\". Não leia o código linha por linha e não "
    "soletre símbolos como parênteses, colchetes ou chaves.\n"
    "- Organize a fala com marcas faladas, como \"Primeiro\", \"Em seguida\" e "
    "\"Por fim\".\n"
    "- Cite o número de uma linha apenas quando isso ajudar a localizar o trecho."
)


def _legivel(qualificado: str) -> str:
    """"persistencia.py::Repo.salvar" vira "Repo.salvar (arquivo persistencia.py)".

    O item nao pode conter virgula: ele vai dentro de listas separadas por
    virgula, e "X, no arquivo Y, Z, no arquivo W" nao diz onde cada item
    termina -- nem para o modelo, nem para quem ouve."""
    if "::" not in qualificado:
        return qualificado
    arquivo, nome = qualificado.split("::", 1)
    if nome == "<codigo de modulo>":
        return f"código de módulo (arquivo {arquivo})"
    return f"{nome} (arquivo {arquivo})"


def _lista(itens, limite=None) -> str:
    itens = list(itens)
    if not itens:
        return "nenhum"
    texto = ", ".join(itens[:limite] if limite else itens)
    omitidos = len(itens) - limite if limite and len(itens) > limite else 0
    return f"{texto} e mais {omitidos}" if omitidos else texto


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def mensagens_visao_geral(resultado):
    """Mensagens para a visao geral do projeto inteiro."""
    mapa = resultado.mapa
    resumo = mapa.resumo()

    linhas = [
        f"Tarefa: faça a visão geral deste projeto Python em no máximo "
        f"{MAX_FRASES_VISAO_GERAL} frases.",
        "Diga, nesta ordem: qual parece ser o propósito do projeto, por onde o "
        "fluxo começa, com que sistemas externos o código conversa, e por qual "
        "região a revisão deve começar e por quê. O propósito do projeto é "
        "sempre uma dedução: marque-o com a palavra de inferência.",
        "",
        "Dados do projeto, obtidos por análise estática:",
        f"Arquivos analisados: {resumo['total_arquivos']}.",
        f"Definições encontradas: {resumo['total_definicoes']}.",
    ]

    for arquivo in resumo["arquivos"][:MAX_ARQUIVOS_NO_PROMPT]:
        definicoes = _lista(arquivo["definicoes"], MAX_DEFINICOES_POR_ARQUIVO)
        linhas.append(f"Arquivo {arquivo['arquivo']} define: {definicoes}.")
    omitidos = len(resumo["arquivos"]) - MAX_ARQUIVOS_NO_PROMPT
    if omitidos > 0:
        linhas.append(f"Outros {omitidos} arquivos não foram listados.")

    entradas = [_legivel(e) for e in resumo["pontos_de_entrada"]]
    linhas.append(f"Pontos de entrada, que nenhuma outra função do projeto chama: "
                  f"{_lista(entradas, MAX_ENTRADAS_NO_PROMPT)}.")
    linhas.append(f"Dependências externas ao projeto: "
                  f"{_lista(resumo['dependencias_externas'], MAX_DEPENDENCIAS_NO_PROMPT)}.")

    linhas.append(
        f"Pontos críticos encontrados: {len(resultado.pontos)}, "
        f"distribuídos em {_plural(len(resultado.grupos), 'região', 'regiões')} de código.")
    for i, grupo in enumerate(resultado.grupos[:MAX_REGIOES_NO_PROMPT], start=1):
        linhas.append(
            f"Região {i} mais grave: {grupo.rotulo}, no arquivo {grupo.arquivo}, "
            f"gravidade máxima {grupo.severidade} de 5, "
            f"{_plural(grupo.total, 'ponto crítico', 'pontos críticos')}.")

    if resumo["erros_sintaxe"]:
        arquivos = sorted({e["arquivo"] for e in resumo["erros_sintaxe"]})
        linhas.append(
            f"Atenção: há erros de sintaxe em {_lista(arquivos)}. A análise desses "
            "arquivos pode estar incompleta. Avise o ouvinte disso logo no início.")

    return [Mensagem("system", PROMPT_SISTEMA), Mensagem("user", "\n".join(linhas))]


def mensagens_regiao(mapa, grupo, max_linhas_codigo=MAX_LINHAS_PADRAO):
    """Mensagens para a explicacao de uma regiao (funcao, metodo ou modulo)."""
    contexto = mapa.contexto(grupo.arquivo, grupo.linha_inicio)
    definicao = mapa.definicoes.get(grupo.escopo)
    trecho = trecho_da_regiao(mapa, grupo, max_linhas=max_linhas_codigo)

    if definicao is not None:
        tipo = DESCRICAO_DEFINICAO.get(definicao.tipo, definicao.tipo)
        onde = (f"{definicao.assinatura}, {tipo}, no arquivo {grupo.arquivo}, "
                f"da linha {definicao.linha_inicio} à linha {definicao.linha_fim}")
    else:
        onde = f"código que roda no nível do módulo, no arquivo {grupo.arquivo}"

    chamada_por = [_legivel(c) for c in contexto["chamada_por"]]
    chama = [_legivel(c) for c in contexto["chama"]]

    linhas = [
        f"Tarefa: explique esta região de código em no máximo {MAX_FRASES_REGIAO} frases.",
        "Diga primeiro o que a região faz e depois, um a um, os pontos críticos "
        "listados abaixo, do mais grave ao menos grave.",
        "",
        f"Região: {onde}.",
        f"Quem chama esta região: {_lista(chamada_por)}.",
        f"O que esta região chama dentro do projeto: {_lista(chama)}.",
        f"Dependências externas usadas: {_lista(contexto['chamadas_externas'])}.",
    ]

    if not contexto["arquivo_confiavel"]:
        linhas.append("Atenção: este arquivo tem erros de sintaxe e a análise pode estar "
                      "incompleta. Avise o ouvinte disso antes de explicar.")

    linhas.append("")
    linhas.append("Pontos críticos detectados por análise estática:")
    for i, ponto in enumerate(grupo.pontos, start=1):
        descricao = DESCRICAO_TIPO.get(ponto.tipo, ponto.tipo.replace("_", " "))
        linhas.append(f"Ponto {i}: linha {ponto.linha}, gravidade {ponto.severidade} de 5, "
                      f"{descricao}. Trecho: {ponto.trecho.strip()}")

    linhas.append("")
    linhas.append("Código da região, com o número de cada linha:")
    linhas.append(trecho.texto or "(código indisponível)")
    if trecho.omitidas:
        linhas.append(f"[Trecho cortado: {trecho.omitidas} linhas finais não foram enviadas. "
                      "Não afirme nada sobre elas.]")

    return [Mensagem("system", PROMPT_SISTEMA), Mensagem("user", "\n".join(linhas))]
