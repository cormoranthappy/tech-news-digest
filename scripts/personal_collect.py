#!/usr/bin/env python3
"""Fetch only explicitly selected public sources; reuse upstream RSS implementation."""
import argparse
import concurrent.futures
import datetime as dt
import importlib.util
import json
import os
import ipaddress
import socket
import http.client
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPHandler, HTTPSHandler, ProxyHandler
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
import personal_digest as pd


def public_addresses(host,port):
    addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise ValueError('Non-public source address is not allowed')
    return addresses


class PinnedHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        if self._tunnel_host:raise ValueError('Proxy tunnels are not supported for public collection')
        # Resolve once at connection time, validate, then connect to a numeric sockaddr.
        addresses=public_addresses(self.host,self.port)
        last_error=None
        for family,socktype,proto,_,address in addresses:
            sock=socket.socket(family,socktype,proto)
            try:
                sock.settimeout(None if self.timeout is socket._GLOBAL_DEFAULT_TIMEOUT else self.timeout)
                if self.source_address:sock.bind(self.source_address)
                sock.connect(address)
                if not ipaddress.ip_address(sock.getpeername()[0]).is_global:raise ValueError('Non-public connected peer')
                self.sock=sock
                return
            except Exception as error:
                sock.close();last_error=error
        raise last_error or OSError('No reachable public address')


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        PinnedHTTPConnection.connect(self)
        # Keep the original hostname for SNI and standard certificate verification.
        self.sock=self._context.wrap_socket(self.sock,server_hostname=self.host)


class PublicHTTPHandler(HTTPHandler):
    def http_open(self,request):return self.do_open(PinnedHTTPConnection,request)


class PublicHTTPSHandler(HTTPSHandler):
    def https_open(self,request):return self.do_open(PinnedHTTPSConnection,request,context=self._context,check_hostname=self._check_hostname)


def public_url(url):
    pd.canonical_url(url)
    u=urlsplit(url)
    if u.port not in (None,80,443):raise ValueError('Public sources use HTTP(S) standard ports')
    if u.hostname.lower()=='localhost' or u.hostname.lower().endswith(('.local','.localhost')):
        raise ValueError('Local source addresses are not allowed')
    public_addresses(u.hostname,u.port or (443 if u.scheme=='https' else 80))
    return url


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def public_open(request,timeout=25):
    public_url(request.full_url if isinstance(request,Request) else request)
    return build_opener(ProxyHandler({}),PublicHTTPHandler(),PublicHTTPSHandler(),PublicRedirect()).open(request,timeout=timeout)


def load_rss():
    spec = importlib.util.spec_from_file_location('upstream_rss', Path(__file__).with_name('fetch-rss.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TIMEOUT = 20
    module.RETRY_COUNT = 1
    module.urlopen = public_open
    module._get_rss_cache()
    return module


def fetch_page(source):
    req = Request(source['url'], headers={'User-Agent': 'PersonalDailyDigest/1.0 (private RSS and public-page reader)'})
    with public_open(req, timeout=25) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Public page exceeds download limit')
        soup = BeautifulSoup(raw, 'html.parser')
        for node in soup.select('script,style,nav,header,footer,noscript,form'):
            node.decompose()
        main = soup.select_one(source.get('selector', 'main')) or soup.body or soup
        heading = main.find('h1')
        full_body = pd.text(main.get_text(' ', strip=True), 2_000_000)
        body = full_body[:10000]
        if len(body) < 60:
            raise ValueError('Page text unavailable or dynamic; manual source check needed')
        links, seen = [], set()
        for a in main.select('a[href]'):
            label = pd.text(a.get_text(' ', strip=True), 180)
            url = urljoin(response.url, a['href'])
            if url in seen or len(label) < 5 or not url.startswith('http'):
                continue
            seen.add(url)
            links.append({'title': label, 'url': url})
            if len(links) >= 25:
                break
    # These are page-change candidates, never claims that all listed stories are new.
    return {'source_id': source['id'], 'status': 'ok', 'articles': [{
        'title': pd.text(heading.get_text() if heading else source['name']),
        'link': source['url'], 'summary': body, 'date': None,
        'page_watch': True, 'links': links, 'content_hash':pd.digest([full_body,sorted({pd.canonical_url(urljoin(response.url,a['href'])) for a in main.select('a[href]') if urljoin(response.url,a['href']).startswith(('http://','https://'))})]),
    }], 'page_text': body, 'links': links}


def fetch(profile, state_dir):
    pd.validate_profile(profile)
    os.environ['TECH_NEWS_DIGEST_STATE_DIR'] = str(state_dir)
    rss = load_rss()
    cutoff = dt.datetime.now(pd.UTC) - dt.timedelta(days=profile.get('lookback_days', 7))
    def one(source):
        try:
            if source['type'] == 'rss':
                cache = (rss._rss_cache or {}).get(source['url'], {})
                upgrade = any('summary' not in x for x in cache.get('articles', []))
                return rss.fetch_feed_with_retry({**source, 'priority': True, 'topics': source['categories']}, cutoff, no_cache=upgrade)
            if source['type'] == 'page':
                return fetch_page(source)
            raise ValueError('Unsupported source type')
        except Exception as error:
            return {'source_id': source['id'], 'status': 'error', 'error': str(error)[:200], 'articles': []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, pd.enabled_sources(profile).values()))
    rss._flush_rss_cache()
    return {'generated': dt.datetime.now(pd.UTC).isoformat(), 'sources': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = fetch(json.loads(args.profile.read_text()), args.state_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'sources': [{'id': s['source_id'], 'status': s['status'], 'count': len(s['articles']),
                                   'error': s.get('error')} for s in result['sources']]}))


if __name__ == '__main__':
    main()
