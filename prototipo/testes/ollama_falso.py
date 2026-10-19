"""
Servidor HTTP falso que reproduz o formato DOCUMENTADO da API nativa do
Ollama (/api/chat e /api/tags), para testar o cliente sem modelo real.

Limite assumido: isto valida o cliente contra a documentacao, nao contra um
Ollama de verdade. Formatos de erro que a documentacao nao descreve (modelo
ausente em /api/chat) sao simulados de forma plausivel e tratados pelo
cliente de modo defensivo.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # cliente que desistiu por timeout nao deve poluir a saida dos testes


class OllamaFalso:
    def __init__(self):
        self.requisicoes = []
        self.cabecalhos = []
        self.exigir_chave = None  # se definida, exige "Authorization: Bearer <chave>"
        self.modelos = [{"name": "qwen3:8b", "digest": "sha256:abc123"}]
        self.status_chat = 200
        self.atraso_s = 0
        self.resposta_chat = {
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": "Texto de teste."},
            "done": True, "done_reason": "stop",
            "prompt_eval_count": 120, "eval_count": 30,
        }
        self._servidor = None

    @property
    def url(self) -> str:
        host, porta = self._servidor.server_address
        return f"http://{host}:{porta}"

    def iniciar(self):
        fake = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _responder(self, status, dados):
                corpo = json.dumps(dados).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def _autorizado(self):
                fake.cabecalhos.append(dict(self.headers))
                if fake.exigir_chave is None:
                    return True
                if self.headers.get("Authorization") == f"Bearer {fake.exigir_chave}":
                    return True
                self._responder(401, {"error": "unauthorized"})
                return False

            def do_GET(self):
                fake.requisicoes.append(("GET", self.path, None))
                if not self._autorizado():
                    return
                if self.path == "/api/tags":
                    self._responder(200, {"models": fake.modelos})
                else:
                    self._responder(404, {"error": "not found"})

            def do_POST(self):
                tamanho = int(self.headers.get("Content-Length", 0))
                corpo = json.loads(self.rfile.read(tamanho) or b"{}")
                fake.requisicoes.append(("POST", self.path, corpo))
                if not self._autorizado():
                    return
                if fake.atraso_s:
                    time.sleep(fake.atraso_s)
                if self.path == "/api/chat":
                    self._responder(fake.status_chat, fake.resposta_chat)
                else:
                    self._responder(404, {"error": "not found"})

        self._servidor = _Servidor(("127.0.0.1", 0), Manipulador)
        threading.Thread(target=self._servidor.serve_forever,
                         kwargs={"poll_interval": 0.01}, daemon=True).start()
        return self

    def parar(self):
        self._servidor.shutdown()
        self._servidor.server_close()

    def corpos_de_chat(self):
        return [c for m, p, c in self.requisicoes if m == "POST" and p == "/api/chat"]
