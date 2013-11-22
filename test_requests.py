from nose.twistedtools import reactor, deferred
from nose.tools import raises

import json
from urllib import urlencode

from twisted.internet.task import deferLater
from twisted.internet.error import DNSLookupError
from twisted.web.error import SchemeNotSupported

import txrequests as rq

@deferred(timeout=5)
def test_get():
    d = rq.get('http://httpbin.org/get?test=passed')

    @d.addCallback
    def ok(response):
        assert response.code==200
        assert response.headers['Content-Type']== ['application/json']

        body = json.loads(response.body)
        assert body['args']['test']=='passed'

    return d

@raises(DNSLookupError)
@deferred(timeout=5)
def test_dns_handle():
    return rq.get('http://httpbinsss.org/get?test=passed')

@raises(SchemeNotSupported)
@deferred(timeout=5)
def test_invalid_url():
    return rq.get('a')


@deferred(timeout=5)
def test_not_found():
    d = rq.get('http://httpbin.org/status/404')

    @d.addCallback
    def ok(response):
        assert response.code==404

    return d

@deferred(timeout=15)
def test_redirects():
    d = rq.get('http://httpbin.org/redirect/2')

    @d.addCallback
    def ok(response):
        assert len(response.redirects)==2

    return d

@deferred(timeout=5)
def test_post():
    params = {'test': 'passed'}
    d = rq.post('http://httpbin.org/post', params=params)

    @d.addCallback
    def ok(response):
        assert response.code==200
        assert response.headers['Content-Type']== ['application/json']

        body = json.loads(response.body)
        assert body['data'] == urlencode(params)

    return d

@deferred(timeout=5)
def test_cache():
    url = 'http://httpbin.org/cache'
    assert url not in rq._cache
    d = rq.get(url)

    @d.addCallback
    def ok(response):
        assert 'Last-Modified' in response.headers
        assert url in rq._cache

        assert rq._cache[url][0] == response.headers['Last-Modified'][0]
        assert rq._cache[url][1] == response.body

        del rq._cache[url]

    return d


@deferred(timeout=15)
def test_from_cache():
    url = 'http://httpbin.org/cache'
    assert url not in rq._cache
    d = rq.get(url)

    @d.addCallback
    def ok(response):
        original_body = response.body
        deferLater(reactor, 2, rq.get, url).addCallback(ok2, original_body)

    def ok2(response, original_body):
        assert response.code == 304
        assert response.body == original_body

        del rq._cache[url]

    return d

@deferred(timeout=20)
def test_permanent_redirect():
    url = 'http://httpbin.org/status/301'
    assert url not in rq._permanent_redirects
    d = rq.get(url)

    @d.addCallback
    def ok(response):
        assert url in rq._permanent_redirects
        del rq._permanent_redirects[url]

    return d
