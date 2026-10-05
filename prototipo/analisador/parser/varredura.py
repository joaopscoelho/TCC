"""
Varredura de projeto: descobre os arquivos .py de uma pasta e faz o parse
de todos eles.

Fase 1 (secao 13 do documento). O escopo de analise da ferramenta e o
projeto inteiro, e nao um arquivo isolado: a regra de negocio raramente
mora em um unico arquivo, e o programador com deficiencia visual e
justamente quem tem mais custo para montar essa visao geral navegando
arquivo por arquivo com o leitor de tela (secao 7 do documento).
"""
from dataclasses import dataclass, field
from pathlib import Path

from analisador.parser.ast_parser import erros_de_sintaxe, parse_file

#: Pastas que nunca sao analisadas: ambiente virtual, cache, dependencia de
#: terceiros e metadados de ferramenta nao fazem parte da regra de negocio.
PASTAS_IGNORADAS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", "site-packages", ".tox",
    "node_modules", "build", "dist", ".eggs",
    ".idea", ".vscode",
}


@dataclass
class ArquivoAnalisado:
    """Um arquivo .py do projeto, ja com a AST e os erros de sintaxe."""

    caminho: Path
    relativo: str
    root: object
    source: bytes
    erros_sintaxe: list = field(default_factory=list)

    @property
    def confiavel(self) -> bool:
        """False quando o parse encontrou erro: a AST esta incompleta e as
        regras de pontos criticos podem perder trechos do arquivo."""
        return not self.erros_sintaxe


def descobrir_arquivos(raiz, ignorar=None):
    """Lista os arquivos .py sob raiz, em ordem estavel.

    Aceita tanto um arquivo .py (devolve so ele) quanto uma pasta. A ordem
    e alfabetica pelo caminho relativo, para que dois usuarios que rodam a
    ferramenta no mesmo projeto ouçam os resultados na mesma sequencia.
    """
    raiz = Path(raiz)
    ignorar = PASTAS_IGNORADAS if ignorar is None else set(ignorar)

    if raiz.is_file():
        return [raiz] if raiz.suffix == ".py" else []

    encontrados = []
    for caminho in raiz.rglob("*.py"):
        if any(parte in ignorar for parte in caminho.relative_to(raiz).parts[:-1]):
            continue
        encontrados.append(caminho)
    return sorted(encontrados)


def analisar_arquivo(caminho, raiz=None) -> ArquivoAnalisado:
    """Faz o parse de um arquivo e devolve o ArquivoAnalisado correspondente."""
    caminho = Path(caminho)
    raiz = Path(raiz) if raiz is not None else caminho.parent

    root, source = parse_file(caminho)
    try:
        relativo = str(caminho.relative_to(raiz))
    except ValueError:
        relativo = caminho.name

    return ArquivoAnalisado(
        caminho=caminho,
        relativo=relativo,
        root=root,
        source=source,
        erros_sintaxe=erros_de_sintaxe(root, source, relativo),
    )


def varrer(caminho, ignorar=None):
    """Faz o parse de todos os .py de caminho (arquivo ou pasta)."""
    caminho = Path(caminho)
    raiz = caminho if caminho.is_dir() else caminho.parent
    return [analisar_arquivo(arquivo, raiz=raiz)
            for arquivo in descobrir_arquivos(caminho, ignorar=ignorar)]
