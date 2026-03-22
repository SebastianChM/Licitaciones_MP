import time
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from typing import Optional, Dict, Any

from utils.logger import ProjectLogger

class HTTPClient:
    """Cliente HTTP centralizado con políticas unificadas de resiliencia."""
    
    # Errores que merecen reintento (Timeouts, Caídas temporales del server, Limitadores de tasa)
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}
    
    def __init__(self, logger: ProjectLogger, max_retries: int = 3, timeout: int = 15, backoff_factor: float = 2.0):
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_factor = backoff_factor
        self.session = requests.Session()
        
    def get(self, url: str, **kwargs) -> requests.Response:
        """Envoltorio GET resiliente"""
        return self._request_with_retry('GET', url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """Envoltorio POST resiliente"""
        return self._request_with_retry('POST', url, **kwargs)
        
    def head(self, url: str, **kwargs) -> requests.Response:
        """Envoltorio HEAD resiliente"""
        return self._request_with_retry('HEAD', url, **kwargs)

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault('timeout', self.timeout)
        intentos = 0
        
        while True:
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code not in self.RETRYABLE_STATUS:
                    response.raise_for_status() 
                    return response
                    
                error_msg = f"HTTP {response.status_code} ({response.reason})"
                
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after and retry_after.isdigit():
                        delay = float(retry_after)
                    else:
                        delay = min((self.backoff_factor ** intentos) * 2.0, 60.0)
                else:
                    delay = float(self.backoff_factor ** intentos)
                    
            except (Timeout, ConnectionError) as e:
                error_msg = f"Network Error ({type(e).__name__}): {str(e)}"
                delay = float(self.backoff_factor ** intentos)
            except requests.exceptions.HTTPError as e:
                raise e # 4xx que no son 429
            except RequestException as e:
                raise e
            
            intentos += 1
            if intentos > self.max_retries:
                self.logger.error(f"❌ Fallaron los {self.max_retries} intentos HTTP hacia {url} | Razón Final: {error_msg}")
                raise requests.exceptions.RetryError(f"Se excedieron reintentos hacia {url}. Último error: {error_msg}")
            
            self.logger.warning(f"⚠️ {error_msg} al consultar {url}. Reintento {intentos}/{self.max_retries} en {delay}s...")
            time.sleep(delay)
            
    def close(self):
        """Cierra la sesión persistente"""
        self.session.close()
