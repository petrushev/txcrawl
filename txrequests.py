from urlparse import urlparse, urlunparse
from collections import namedtuple
from urllib import urlencode

from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.python import log
from twisted.internet.defer import Deferred, succeed
from zope.interface import implements

Response = namedtuple("Response", ('code', 'body', 'headers', 'url', 'redirects'))
_pool = HTTPConnectionPool(reactor, persistent=False)
_cache = {}
_permanent_redirects = {}

class TxRequestsException(Exception): pass
class CyclicRedirect(TxRequestsException): pass
class CorruptRedirect(TxRequestsException): pass

class DictProducer(object):
    implements(IBodyProducer)

    def __init__(self, params):
        self.body = urlencode(params)
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self): pass
    def stopProducing(self): pass

def get(url, headers=None, follow_redirect=True, redirect_history=()):
    agent = Agent(reactor, pool=_pool)
    if headers is None:
        headers = {}

    if url in _cache:
        last_modified = _cache[url][0]
        headers['If-Modified-Since'] = [last_modified]

    if follow_redirect and url in _permanent_redirects:
        print 'here!'
        if redirect_history is None:
            redirect_history = (url,)
        else:
            redirect_history = redirect_history + (url,)
        redirect = _permanent_redirects[url]
        return get(redirect, headers, True, redirect_history)

    headers = Headers(headers)

    d = agent.request('GET', url, headers, None)
    d.addCallback(_receive, url, headers, follow_redirect, redirect_history)
    return d

def post(url, params=None, headers=None, follow_redirect=True):
    agent = Agent(reactor, pool=_pool)
    if headers is None: headers = {}
    headers = Headers(headers)
    if params is None: params = {}
    body = DictProducer(params)

    d = agent.request('POST', url, headers, body)
    d.addCallback(_receive, url, headers, follow_redirect, redirect_history=None)
    return d

def _receive(response, url, headers, follow_redirect, redirect_history):
    d = Deferred()
    headers = dict(response.headers.getAllRawHeaders())
    code = response.code
    length = response.length

    # check for redirects
    if follow_redirect and (code == 302 or code == 301):
        try:
            redirect = headers['Location'][0]
        except KeyError:
            raise CorruptRedirect, 'Received redirect response without Location header'

        parts = list(urlparse(redirect))
        original_parts = list(urlparse(url))

        if parts[0]=='': parts[0] = original_parts[0]
        if parts[1]=='': parts[1] = original_parts[1]

        redirect = urlunparse(parts)

        if code==301:
            _permanent_redirects[url] = redirect

        if redirect_history is None:
            redirect_history = () # comes from post, don't add as history
        else:
            redirect_history = redirect_history + (url,)

        if redirect in redirect_history:
            raise CyclicRedirect, 'Next url has already been in the redirects cycle: ' + redirect

        return get(redirect, headers, True, redirect_history)

    body = ['']
    last_modified = None

    # common closure
    def close(_):
        response = Response(code, body[0], headers, url, redirect_history)
        if last_modified is not None:
            _cache[url] = (last_modified, body[0])
        d.callback(response)

    # check for not modified:
    if code == 304:
        body[0] = _cache[url][1]
        reactor.callLater(0, close, None)
        return d

    # check for caching
    if 'Last-Modified' in headers:
        last_modified = headers['Last-Modified'][0]

    if length == 0:
        reactor.callLater(0, close, None)
        return d

    # retrieve body
    def _receiveChunk(chunk):
        body[0] = body[0] + chunk

    bodyReceiver = Protocol()
    bodyReceiver.dataReceived = _receiveChunk
    bodyReceiver.connectionLost = close

    response.deliverBody(bodyReceiver)

    return d
