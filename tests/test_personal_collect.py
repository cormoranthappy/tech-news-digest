import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from urllib.request import Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import personal_collect as c

@pytest.mark.parametrize('url',['file:///etc/passwd','http://localhost/test','http://service.local/test','https://user:pass@example.com/'])
def test_nonpublic_syntax_rejected(url):
    with pytest.raises(ValueError):c.public_url(url)

def test_dns_private_and_redirect_rejected():
    with patch.object(c.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
        with pytest.raises(ValueError):c.public_url('https://example.com/')
        with pytest.raises(ValueError):c.PublicRedirect().redirect_request(Request('https://example.com/'),None,302,'',{},'http://127.0.0.1/private')

def test_public_destination_allowed():
    with patch.object(c.socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]):
        assert c.public_url('https://example.com/')=='https://example.com/'
