import sys
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
import io
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

def test_page_fingerprint_includes_tail_and_links():
    class Response:
        url='https://example.com/'
        def __init__(self,text):self.text=text
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return self.text.encode()
    def fetch(tail,link):
        markup='<main><h1>News</h1><p>'+('x'*1700)+tail+'</p><a href="'+link+'">Read more</a></main>'
        with patch.object(c,'public_open',return_value=Response(markup)):
            return c.fetch_page({'id':'x','url':'https://example.com/','name':'Example'})['articles'][0]['content_hash']
    assert fetch('old','/a')==fetch('old','/a')
    assert fetch('old','/a')!=fetch('new','/a')
    assert fetch('old','/a')!=fetch('old','/b')

def test_actual_open_rejects_dns_rebinding_before_socket():
    public=[(2,1,6,'',('93.184.216.34',80))];private=[(2,1,6,'',('127.0.0.1',80))]
    with patch.object(c.socket,'getaddrinfo',side_effect=[public,private]),patch.object(c.socket,'socket') as sock:
        with pytest.raises(ValueError,match='Non-public'):c.public_open('http://example.com/',timeout=1)
        sock.assert_not_called()

def test_actual_redirect_never_connects_to_private_target():
    sent=[];sock=MagicMock();sock.getpeername.return_value=('93.184.216.34',80)
    sock.sendall.side_effect=lambda data:sent.append(data)
    sock.makefile.return_value=io.BytesIO(b'HTTP/1.1 302 Found\r\nLocation: http://rebound.test/private\r\nContent-Length: 0\r\n\r\n')
    def dns(host,port,**kwargs):return [(2,1,6,'',('127.0.0.1' if host=='rebound.test' else '93.184.216.34',port))]
    with patch.object(c.socket,'getaddrinfo',side_effect=dns),patch.object(c.socket,'socket',return_value=sock) as factory:
        with pytest.raises(ValueError,match='Non-public'):c.public_open('http://example.com/start',timeout=1)
        assert factory.call_count==1
    assert b'GET /start ' in b''.join(sent);assert b'/private' not in b''.join(sent)

def test_https_retains_hostname_verification():
    conn=c.PinnedHTTPSConnection('example.com');assert conn._context.check_hostname
    with patch.object(c.PinnedHTTPConnection,'connect'),patch.object(conn._context,'wrap_socket',return_value=object()) as wrap:
        conn.sock=object();conn.connect();assert wrap.call_args.kwargs['server_hostname']=='example.com'
