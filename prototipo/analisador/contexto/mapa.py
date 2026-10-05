"""
Mapa estrutural do projeto: junta a estrutura de todos os arquivos e
resolve o grafo local de chamadas.

Fase 2 (secoes 7 e 13 do documento). Este mapa e a entrada do prompt de
visao geral e, para cada ponto critico, permite responder as perguntas que
o leitor de tela torna caras: em que funcao este trecho esta, quem chama
essa funcao e o que ela chama.

Simplificacao conhecida (v1): a resolucao de chamadas e por nome simples,
com prioridade para o proprio arquivo e depois para os arquivos
importados. Nao ha inferencia de tipos, logo "obj.salvar()" liga a
qualquer "salvar" definido no projeto se nao houver candidato melhor; a
ambiguidade fica registrada em "ambiguas" em vez de ser escondida.
"""
import builtins
from dataclasses import dataclass, field
from pathlib import Path

from analisador.contexto.estrutura import (
    extrair_chamadas, extrair_definicoes, extrair_imports, definicao_envolvente,
)
from analisador.pontos_criticos.agrupamento import ESCOPO_MODULO
from analisador.parser.varredura import varrer


#: Nomes embutidos no Python (len, str, ValueError, ...). Chamar um deles
#: nao e "depender de codigo externo" no sentido que interessa ao usuario.
NOMES_EMBUTIDOS = set(dir(builtins))

#: Metodos de colecao da propria linguagem. Sem inferencia de tipos nao da
#: para saber se "x.append(...)" e uma lista ou um objeto do dominio, mas
#: listar todos eles como dependencia externa enche a visao geral de ruido.
#: Limitacao conhecida (v1): "get" fica fora desta lista porque tambem
#: nomeia requisicao HTTP, que e dependencia externa de verdade.
METODOS_DE_COLECAO = {
    "append", "extend", "insert", "pop", "remove", "clear", "add", "discard",
    "keys", "values", "items", "setdefault", "copy", "sort", "reverse",
    "join", "split", "splitlines", "strip", "lstrip", "rstrip", "replace",
    "format", "lower", "upper", "title", "startswith", "endswith", "count",
}


def _e_dependencia_externa(chamada, locais) -> bool:
    """True quando a chamada sai do projeto e do proprio Python."""
    if chamada.nome in locais:
        return False
    if chamada.nome in NOMES_EMBUTIDOS:
        return False
    if chamada.nome in METODOS_DE_COLECAO:
        return False
    return True


def _chave_modulo(arquivo: str) -> str:
    """Chave do grafo para o codigo que roda no nivel do modulo.

    Chamadas feitas fora de qualquer funcao nao tem definicao de origem.
    Guarda-las como None misturava None e texto nos conjuntos do grafo e
    quebrava qualquer ordenacao (TypeError em contexto())."""
    return f"{arquivo}::{ESCOPO_MODULO}"


def _e_de_modulo(chave: str) -> bool:
    return chave.endswith(f"::{ESCOPO_MODULO}")


def _modulos_do_arquivo(relativo: str):
    """Nomes de modulo pelos quais um arquivo pode ser importado."""
    partes = Path(relativo).with_suffix("").parts
    if partes and partes[-1] == "__init__":
        partes = partes[:-1]
    if not partes:
        return []
    completo = ".".join(partes)
    return [completo, partes[-1]]


@dataclass
class MapaProjeto:
    """Estrutura completa do projeto analisado."""

    raiz: str
    arquivos: list = field(default_factory=list)
    definicoes: dict = field(default_factory=dict)
    imports: list = field(default_factory=list)
    chamadas: list = field(default_factory=list)
    grafo: dict = field(default_factory=dict)
    chamadores: dict = field(default_factory=dict)
    ambiguas: list = field(default_factory=list)
    erros_sintaxe: list = field(default_factory=list)

    # ------------------------------------------------------------------ consultas

    def definicoes_do_arquivo(self, arquivo: str):
        return [d for d in self.definicoes.values() if d.arquivo == arquivo]

    def envolvente(self, arquivo: str, linha: int):
        """Definicao que contem (arquivo, linha), ou None se for codigo de modulo."""
        return definicao_envolvente(self.definicoes_do_arquivo(arquivo), linha)

    def arquivo_analisado(self, arquivo: str):
        for a in self.arquivos:
            if a.relativo == arquivo:
                return a
        return None

    def dependencias_externas(self):
        """Chamadas que saem do projeto: banco, rede, arquivo, biblioteca.

        Nomes embutidos do Python e metodos de colecao sao descartados: o
        que interessa ao usuario e saber onde o codigo toca o mundo fora
        dele, nao que uma lista recebeu append (secao 7 do documento)."""
        locais = {d.nome for d in self.definicoes.values()}
        return sorted({c.expressao for c in self.chamadas
                       if _e_dependencia_externa(c, locais)})

    def pontos_de_entrada(self):
        """Funcoes e metodos que ninguem chama dentro do projeto.

        Sao os candidatos a "porta de entrada" da regra de negocio: o fluxo
        comeca por eles, e e por eles que a explicacao de visao geral deve
        comecar (secao 7 do documento).

        Chamadas feitas pelo codigo de modulo (o idioma
        "if __name__ == '__main__': main()") nao contam como chamador: e
        justamente assim que o fluxo de um programa comeca."""
        def chamadores_reais(qualificado):
            return {c for c in self.chamadores.get(qualificado, set())
                    if not _e_de_modulo(c)}

        def e_implicito(nome):
            """__init__, __str__ e afins sao chamados pela propria linguagem
            ("Classe(...)", "str(obj)"), nunca pelo nome: no grafo parecem
            nao ter chamador, e lista-los como entrada engana quem ouve."""
            return nome.startswith("__") and nome.endswith("__")

        return sorted(
            d.qualificado for d in self.definicoes.values()
            if d.tipo in ("funcao", "metodo")
            and not e_implicito(d.nome)
            and not chamadores_reais(d.qualificado)
        )

    def contexto(self, arquivo: str, linha: int):
        """Contexto estrutural de uma linha, no formato que vai para o prompt."""
        definicao = self.envolvente(arquivo, linha)
        analisado = self.arquivo_analisado(arquivo)
        locais = {d.nome for d in self.definicoes.values()}

        if definicao is not None:
            qualificado = definicao.qualificado
            chamadas_no_escopo = [c for c in self.chamadas if c.origem == qualificado]
        else:
            qualificado = _chave_modulo(arquivo)
            chamadas_no_escopo = [c for c in self.chamadas
                                  if c.arquivo == arquivo and c.origem is None]

        return {
            "arquivo": arquivo,
            "linha": linha,
            "escopo": "modulo" if definicao is None else definicao.tipo,
            "definicao": definicao.to_dict() if definicao is not None else None,
            "chama": sorted(self.grafo.get(qualificado, [])),
            "chamada_por": sorted(self.chamadores.get(qualificado, [])),
            "chamadas_externas": sorted({c.expressao for c in chamadas_no_escopo
                                         if _e_dependencia_externa(c, locais)}),
            "imports": [i.bruto for i in self.imports if i.arquivo == arquivo],
            "arquivo_confiavel": analisado.confiavel if analisado is not None else True,
        }

    def resumo(self):
        """Visao geral do projeto, para o prompt de visao geral da Fase 2."""
        return {
            "raiz": self.raiz,
            "total_arquivos": len(self.arquivos),
            "total_definicoes": len(self.definicoes),
            "arquivos": [
                {
                    "arquivo": a.relativo,
                    "definicoes": [d.assinatura for d in self.definicoes_do_arquivo(a.relativo)],
                    "erros_sintaxe": len(a.erros_sintaxe),
                }
                for a in self.arquivos
            ],
            "pontos_de_entrada": self.pontos_de_entrada(),
            "dependencias_externas": self.dependencias_externas(),
            "chamadas_ambiguas": len(self.ambiguas),
            "erros_sintaxe": [e.to_dict() for e in self.erros_sintaxe],
        }


def _indice_modulos(arquivos):
    indice = {}
    for a in arquivos:
        for modulo in _modulos_do_arquivo(a.relativo):
            indice.setdefault(modulo, a.relativo)
    return indice


def _arquivos_importados(imports_do_arquivo, indice_modulos):
    """Arquivos do projeto alcancados pelos imports de um arquivo."""
    alcancados = set()
    for imp in imports_do_arquivo:
        candidatos = [imp.modulo] + list(imp.nomes) if imp.modulo else list(imp.nomes)
        for bruto in candidatos:
            if not bruto:
                continue
            nome = bruto.split(" as ")[0].strip().lstrip(".")
            if nome in indice_modulos:
                alcancados.add(indice_modulos[nome])
            elif nome.split(".")[0] in indice_modulos:
                alcancados.add(indice_modulos[nome.split(".")[0]])
    return alcancados


def construir_mapa(caminho, ignorar=None) -> MapaProjeto:
    """Varre o projeto e monta o mapa estrutural completo."""
    arquivos = varrer(caminho, ignorar=ignorar)
    mapa = MapaProjeto(raiz=str(caminho), arquivos=arquivos)

    por_nome = {}
    for a in arquivos:
        definicoes = extrair_definicoes(a.root, a.source, a.relativo)
        for d in definicoes:
            mapa.definicoes[d.qualificado] = d
            por_nome.setdefault(d.nome, []).append(d)
        mapa.imports.extend(extrair_imports(a.root, a.source, a.relativo))
        mapa.chamadas.extend(extrair_chamadas(a.root, a.source, a.relativo, definicoes))
        mapa.erros_sintaxe.extend(a.erros_sintaxe)

    indice_modulos = _indice_modulos(arquivos)
    importados_por_arquivo = {
        a.relativo: _arquivos_importados(
            [i for i in mapa.imports if i.arquivo == a.relativo], indice_modulos)
        for a in arquivos
    }

    for chamada in mapa.chamadas:
        candidatos = por_nome.get(chamada.nome, [])
        if not candidatos:
            continue

        mesmo_arquivo = [d for d in candidatos if d.arquivo == chamada.arquivo]
        if mesmo_arquivo:
            alvos = mesmo_arquivo
        else:
            importados = importados_por_arquivo.get(chamada.arquivo, set())
            de_importados = [d for d in candidatos if d.arquivo in importados]
            alvos = de_importados or candidatos

        if len(alvos) > 1:
            mapa.ambiguas.append({
                "arquivo": chamada.arquivo, "linha": chamada.linha,
                "nome": chamada.nome,
                "candidatos": sorted(d.qualificado for d in alvos),
            })

        origem = chamada.origem or _chave_modulo(chamada.arquivo)
        for alvo in alvos:
            mapa.grafo.setdefault(origem, set()).add(alvo.qualificado)
            mapa.chamadores.setdefault(alvo.qualificado, set()).add(origem)

    return mapa
