import time
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout, ConnectionError
from typing import Optional, Dict, Any

from utils.logger import ProjectLogger


# Delay mínimo de espera por tipo de fallo antes de reintentar
_DELAY_MIN_SERVIDOR = 30.0   # 500/502/503/504: el servidor necesita recuperarse
_DELAY_MIN_RED      = 15.0   # Timeout/ConnectionError: la red/sesión necesita limpiarse
_DELAY_MIN_RATE     = 60.0   # 429: respetar el límite de tasa


class HTTPClient:
    """Cliente HTTP centralizado con políticas unificadas de resiliencia."""

    # Errores que merecen reintento (Timeouts, Caídas temporales del server, Limitadores de tasa)
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, logger: ProjectLogger, max_retries: int = 3, timeout: int = 15, backoff_factor: float = 2.0):
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_factor = backoff_factor
        self.session = self._nueva_sesion()

    def _nueva_sesion(self) -> requests.Session:
        """Crea una sesión HTTP limpia con headers y pool de conexiones correctos."""
        s = requests.Session()
        # User-Agent identificable — algunas APIs rechazan solicitudes sin él
        s.headers.update({
            'User-Agent': 'MP-Licitaciones-Pipeline/5.0 (Python/requests)',
            'Accept': 'application/json',
            'Connection': 'keep-alive',
        })
        # Pool pequeño — no necesitamos concurrencia, pero queremos control explícito
        adapter = HTTPAdapter(
            pool_connections=2,
            pool_maxsize=2,
            max_retries=0,  # Los reintentos los manejamos nosotros
        )
        s.mount('https://', adapter)
        s.mount('http://',  adapter)
        return s

    def _renovar_sesion(self):
        """Cierra la sesión actual (y sus conexiones TCP) y abre una nueva limpia.

        Crítico para recuperarse de timeouts: una conexión TCP que expiró queda
        en estado indefinido en el pool. Reutilizarla produce cascadas de fallos.
        """
        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._nueva_sesion()

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._request_with_retry('GET', url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self._request_with_retry('POST', url, **kwargs)

    def head(self, url: str, **kwargs) -> requests.Response:
        return self._request_with_retry('HEAD', url, **kwargs)

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault('timeout', self.timeout)
        intentos = 0

        while True:
            renovar_sesion = False
            try:
                response = self.session.request(method, url, **kwargs)

                if response.status_code not in self.RETRYABLE_STATUS:
                    response.raise_for_status()
                    return response

                codigo = response.status_code
                if codigo == 429:
                    error_msg = "demasiadas solicitudes (429) — límite de tasa alcanzado"
                    retry_after = response.headers.get('Retry-After')
                    delay = float(retry_after) if (retry_after and retry_after.isdigit()) \
                            else _DELAY_MIN_RATE
                else:
                    error_msg = f"error del servidor ({codigo})"
                    # El servidor está bajo presión: dale tiempo real para recuperarse
                    delay = max(_DELAY_MIN_SERVIDOR,
                                self.backoff_factor ** intentos * _DELAY_MIN_SERVIDOR)

            except Timeout:
                # La sesión TCP puede estar corrupta — renovar antes del siguiente intento
                error_msg = f"sin respuesta en {self.timeout}s (timeout)"
                delay = max(_DELAY_MIN_RED, self.backoff_factor ** intentos * _DELAY_MIN_RED)
                renovar_sesion = True

            except ConnectionError:
                error_msg = "no se pudo conectar al servidor"
                delay = max(_DELAY_MIN_RED, self.backoff_factor ** intentos * _DELAY_MIN_RED)
                renovar_sesion = True

            except requests.exceptions.HTTPError as e:
                raise e   # 4xx que no son 429, no se reintenta
            except RequestException as e:
                raise e

            intentos += 1

            if intentos > self.max_retries:
                self.logger.error(
                    f"❌ API Mercado Público no respondió tras {self.max_retries} intentos "
                    f"({error_msg})"
                )
                raise requests.exceptions.RetryError(
                    f"Se excedieron reintentos. Último error: {error_msg}"
                )

            if renovar_sesion:
                self._renovar_sesion()

            self.logger.warning(
                f"⚠️ API Mercado Público — {error_msg} "
                f"(reintento {intentos}/{self.max_retries}, esperando {delay:.0f}s...)"
            )
            time.sleep(delay)

    def close(self):
        """Cierra la sesión y libera conexiones TCP."""
        self.session.close()
