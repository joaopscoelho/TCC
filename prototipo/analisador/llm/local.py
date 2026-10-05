"""
Modelo local via Ollama (API nativa), sem nenhuma dependencia nova.

Fase 2 (secao 13 do documento). Usa a API nativa (/api/chat) e nao o
endpoint compativel com a OpenAI por um motivo concreto: a documentacao do
Ollama afirma que "a API da OpenAI nao tem como definir o tamanho de
contexto do modelo". Em maquinas com menos de 24 GiB o contexto padrao do
Ollama e de 4k tokens, e um prompt com codigo passa disso facilmente. Na
API nativa, num_ctx vai em "options" por requisicao.

Reprodutibilidade: temperatura zero e semente fixa, registradas em
descricao(). Isso torna as execucoes comparaveis, mas nao garante saida
identica byte a byte entre versoes do Ollama ou entre hardwares diferentes.

Limitacao conhecida (v1): este cliente foi testado contra um servidor
falso que reproduz o formato documentado, nao contra um modelo real.
"""
import json
import os
import socket
import time
import urllib.error
import urllib.request

from analisador.llm.base import (
    ErroContextoExcedido, ErroLLM, ErroModeloAusente, ErroRespostaVazia,
    ErroServidorIndisponivel, ErroTempoEsgotado, ExplicadorLLM, RespostaLLM,
    estimar_tokens,
)

HOST_PADRAO = "http://127.0.0.1:11434"

#: Padrao para 16 GB de memoria unificada: cabe com folga (cerca de 5 GB),
#: e a familia Qwen3 foi treinada em 119 idiomas, o que importa para o
#: portugues brasileiro. Alternativas maiores (qwen3:14b, gpt-oss:20b)
#: ficam por conta do usuario via --modelo.
MODELO_PADRAO = "qwen3:8b"

CONTEXTO_PADRAO = 8192
RESPOSTA_MAXIMA_PADRAO = 1500
SEMENTE_PADRAO = 42
TIMEOUT_PADRAO_S = 600

#: Fracao do contexto a partir da qual avisamos que o prompt pode ter sido
#: cortado pelo servidor (heuristica: a documentacao nao descreve o que
#: acontece quando o prompt excede o contexto).
LIMITE_AVISO_CONTEXTO = 0.95

_AUTO = "auto"


def normalizar_host(valor) -> str:
    """Aceita "host:porta", URL completa ou vazio (padrao)."""
    valor = (valor or "").strip() or HOST_PADRAO
    if "://" not in valor:
        valor = "http://" + valor
    return valor.rstrip("/")


def _com_tag(nome: str) -> str:
    """"qwen3" e "qwen3:latest" sao o mesmo modelo."""
    return nome if ":" in nome else f"{nome}:latest"


def _raciocinio_padrao(modelo: str):
    """Explicar codigo nao precisa de cadeia de raciocinio longa, e ela
    consome o limite de resposta antes de aparecer texto. A familia
    gpt-oss nao aceita desligar o raciocinio, so reduzir o nivel."""
    return "low" if modelo.startswith("gpt-oss") else False


class ExplicadorLocal(ExplicadorLLM):
    """ExplicadorLLM sobre um servidor Ollama."""

    def __init__(self, modelo=None, host=None, contexto=CONTEXTO_PADRAO,
                 resposta_maxima=RESPOSTA_MAXIMA_PADRAO, semente=SEMENTE_PADRAO,
                 temperatura=0.0, raciocinio=_AUTO, timeout=TIMEOUT_PADRAO_S):
        self.modelo = modelo or os.environ.get("ANALISADOR_MODELO") or MODELO_PADRAO
        self.host = normalizar_host(host or os.environ.get("OLLAMA_HOST"))
        self.contexto = contexto
        self.resposta_maxima = resposta_maxima
        self.semente = semente
        self.temperatura = temperatura
        self.raciocinio = _raciocinio_padrao(self.modelo) if raciocinio == _AUTO else raciocinio
        self.timeout = timeout
        self._digest = None

    # ------------------------------------------------------------------ transporte

    def _mensagem_servidor(self, erro) -> str:
        try:
            corpo = erro.read().decode("utf-8", errors="replace")
        except Exception:
            return ""
        try:
            dados = json.loads(corpo)
            if isinstance(dados, dict) and "error" in dados:
                return str(dados["error"])
        except ValueError:
            pass
        return corpo.strip()

    def _chamar(self, caminho, corpo=None):
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        requisicao = urllib.request.Request(
            self.host + caminho, data=dados,
            method="GET" if corpo is None else "POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=self.timeout) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            detalhe = self._mensagem_servidor(erro)
            if erro.code == 404:
                raise ErroModeloAusente(
                    f"O servidor respondeu 404 para o modelo '{self.modelo}'. "
                    f"Se ele ainda nao foi baixado, rode: ollama pull {self.modelo}. "
                    f"Resposta do servidor: {detalhe or 'vazia'}"
                ) from erro
            raise ErroLLM(f"O Ollama respondeu com erro {erro.code}: {detalhe}") from erro
        except urllib.error.URLError as erro:
            if isinstance(erro.reason, (socket.timeout, TimeoutError)):
                raise ErroTempoEsgotado(
                    f"O Ollama nao respondeu em {self.timeout} segundos.") from erro
            raise ErroServidorIndisponivel(
                f"Nao foi possivel conectar ao Ollama em {self.host}. "
                "Instale o Ollama e abra o aplicativo, ou rode: ollama serve."
            ) from erro
        except (socket.timeout, TimeoutError) as erro:
            raise ErroTempoEsgotado(
                f"O Ollama nao respondeu em {self.timeout} segundos.") from erro
        except ValueError as erro:
            raise ErroLLM("O servidor devolveu uma resposta que nao e JSON valido.") from erro

    # ------------------------------------------------------------------ contrato

    def verificar(self) -> dict:
        dados = self._chamar("/api/tags")
        modelos = dados.get("models") if isinstance(dados, dict) else None
        if not isinstance(modelos, list):
            return {}

        alvo = _com_tag(self.modelo)
        nomes = []
        for item in modelos:
            nome = (item.get("name") or item.get("model") or "") if isinstance(item, dict) else ""
            nomes.append(nome)
            if _com_tag(nome) == alvo:
                self._digest = item.get("digest")
                return {"digest": self._digest}

        disponiveis = ", ".join(sorted(n for n in nomes if n)) or "nenhum"
        raise ErroModeloAusente(
            f"O modelo '{self.modelo}' nao esta instalado no Ollama. "
            f"Baixe com: ollama pull {self.modelo}. Modelos instalados: {disponiveis}."
        )

    def gerar(self, mensagens) -> RespostaLLM:
        mensagens = list(mensagens)
        estimado = sum(estimar_tokens(m.conteudo) for m in mensagens)
        if estimado + self.resposta_maxima > self.contexto:
            raise ErroContextoExcedido(
                f"O prompt tem cerca de {estimado} tokens e a resposta pode usar "
                f"ate {self.resposta_maxima}, mas o contexto configurado e de "
                f"{self.contexto}. Aumente --contexto ou reduza o trecho enviado."
            )

        corpo = {
            "model": self.modelo,
            "messages": [{"role": m.papel, "content": m.conteudo} for m in mensagens],
            "stream": False,
            "options": {
                "num_ctx": self.contexto,
                "num_predict": self.resposta_maxima,
                "seed": self.semente,
                "temperature": self.temperatura,
            },
        }
        if self.raciocinio is not None:
            corpo["think"] = self.raciocinio

        inicio = time.monotonic()
        dados = self._chamar("/api/chat", corpo)
        duracao = round(time.monotonic() - inicio, 2)

        mensagem = dados.get("message") if isinstance(dados, dict) else None
        texto = ((mensagem or {}).get("content") or "").strip()
        motivo = dados.get("done_reason") if isinstance(dados, dict) else None

        if not texto:
            dica = (" O modelo parou por limite de tamanho antes de escrever: o "
                    "raciocinio interno pode ter consumido toda a resposta. "
                    "Aumente a resposta maxima ou reduza o nivel de raciocinio."
                    if motivo == "length" else "")
            raise ErroRespostaVazia(f"O modelo '{self.modelo}' devolveu texto vazio.{dica}")

        tokens_prompt = dados.get("prompt_eval_count")
        avisos = []
        if tokens_prompt is not None and tokens_prompt >= LIMITE_AVISO_CONTEXTO * self.contexto:
            avisos.append(
                f"O prompt usou {tokens_prompt} de {self.contexto} tokens de contexto; "
                "o servidor pode ter cortado parte do codigo. Aumente --contexto.")

        return RespostaLLM(
            texto=texto, modelo=self.modelo, tokens_prompt=tokens_prompt,
            tokens_resposta=dados.get("eval_count"), duracao_s=duracao,
            motivo_fim=motivo, avisos=avisos,
        )

    def descricao(self) -> dict:
        return {
            "backend": "ollama",
            "modelo": self.modelo,
            "host": self.host,
            "digest": self._digest,
            "contexto": self.contexto,
            "resposta_maxima": self.resposta_maxima,
            "semente": self.semente,
            "temperatura": self.temperatura,
            "raciocinio": self.raciocinio,
        }
