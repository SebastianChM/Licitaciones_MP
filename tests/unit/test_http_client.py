from unittest.mock import MagicMock, patch

import pytest
import requests

from utils import ProjectLogger
from utils.http import HTTPClient


@pytest.fixture
def http_client():
    logger = MagicMock(spec=ProjectLogger)
    return HTTPClient(logger=logger, max_retries=2, timeout=1, backoff_factor=0.1)

def test_retry_ante_timeout_transitorio(http_client):
    # renovar_sesion se mockea como no-op para que self.session no sea reemplazado
    # (si no, el mock de session.request deja de aplicar tras la renovación de sesión)
    with patch.object(http_client.session, 'request') as mock_request, \
         patch.object(http_client, 'renovar_sesion'), \
         patch('utils.http.time.sleep'):
        # Fallo 2 veces por Timeout/ConnectionError, luego éxito 200
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.side_effect = [
            requests.exceptions.Timeout("Read timeout"),
            requests.exceptions.ConnectionError("Connection aborted"),
            mock_response
        ]
        
        response = http_client.get('http://fakeurl.com')
        
        assert response.status_code == 200
        assert mock_request.call_count == 3
        
def test_retry_ante_429(http_client):
    with patch.object(http_client.session, 'request') as mock_request:
        # Falla por 429 Too Many Requests, luego éxito
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {'Retry-After': '0'}
        
        resp_200 = MagicMock()
        resp_200.status_code = 200
        
        mock_request.side_effect = [resp_429, resp_200]
        
        response = http_client.get('http://fakeurl.com')
        assert response.status_code == 200
        assert mock_request.call_count == 2
        
def test_retry_ante_5xx(http_client):
    with patch.object(http_client.session, 'request') as mock_request, \
         patch('utils.http.time.sleep'):
        resp_503 = MagicMock()
        resp_503.status_code = 503
        resp_503.reason = "Service Unavailable"
        
        resp_200 = MagicMock()
        resp_200.status_code = 200
        
        mock_request.side_effect = [resp_503, resp_200]
        
        response = http_client.get('http://fakeurl.com')
        assert response.status_code == 200
        assert mock_request.call_count == 2
        
def test_no_retry_ante_403(http_client):
    with patch.object(http_client.session, 'request') as mock_request:
        resp_403 = MagicMock()
        resp_403.status_code = 403
        resp_403.reason = "Forbidden"
        # MagicMock no lanza raise_for_status por defecto, debemos simularlo
        resp_403.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
        
        mock_request.return_value = resp_403
        
        with pytest.raises(requests.exceptions.HTTPError):
            http_client.get('http://fakeurl.com')
            
        assert mock_request.call_count == 1  # No reintentó
        
def test_agotar_reintentos_lanza_excepcion(http_client):
    with patch.object(http_client.session, 'request') as mock_request, \
         patch('utils.http.time.sleep'):
        resp_500 = MagicMock()
        resp_500.status_code = 500
        mock_request.return_value = resp_500
        
        with pytest.raises(requests.exceptions.RetryError):
            http_client.get('http://fakeurl.com')
            
        # max_retries es 2, significa intento 0, 1, y 2 -> total 3 llamadas
        assert mock_request.call_count == 3
