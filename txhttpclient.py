from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers
from twisted.python import log

pool = HTTPConnectionPool(reactor, persistent=False)

class BasicHTTPClientProtocol(object):

    def __init__(self, url, headers=None, wait=False):
        if headers is None:
            headers = {}

        self._url = url
        self._requestHeaders = Headers(headers)
        self._responseHeaders = None
        self._responseBody = None
        self._responseCode = None

        if not wait:
            self.run()

    @property
    def url(self):
        return self._url

    @property
    def requestHeaders(self):
        return self._requestHeaders

    @property
    def responseHeaders(self):
        return self._responseHeaders

    @property
    def responseBody(self):
        return self._responseBody

    @property
    def responseCode(self):
        return self._responseCode

    def run(self):
        self._responseHeaders = None
        self._responseBody = None

        agent = Agent(reactor, pool=pool)
        d = agent.request('GET', self.url, self.requestHeaders, None)
        d.addCallback(self._receive)
        d.addErrback(self._error)

    def _error(self, exception):
        #exception.printTraceback()
        msg = exception.getErrorMessage()
        if msg!='':
            log.err('%s @ %s: %s' % (self.__class__.__name__, self.url, msg))

    def _receive(self, response):
        self._responseHeaders = dict(response.headers.getAllRawHeaders())
        self._responseCode = response.code
        self.headersReceived()

        self._receiveBody(response)

    def _receiveBody(self, response):
        protocol = self
        def dataReceived(chunk):
            protocol._responseBody = protocol._responseBody + chunk
        def connectionLost(_):
            protocol.responseComplete()

        self._responseBody = ''
        bodyReceiver = Protocol()
        bodyReceiver.dataReceived = dataReceived
        bodyReceiver.connectionLost = connectionLost

        response.deliverBody(bodyReceiver)

    #public event handlers

    def headersReceived(self):
        """Called when all response headers are received"""
        pass

    def responseComplete(self):
        """Called when the response is complete with its body"""
        pass

class RedirectError(Exception): pass

class CommonHTTPClientProtocol(BasicHTTPClientProtocol):

    # contains memo for responses with permanent rediretion
    _redirectRegistry = {}

    # contains all url passed in redirection
    history = []

    def run(self):
        # check for permanent redirects
        url = self.url
        while url in self._redirectRegistry:
            self.history.append(url)
            newUrl = self._redirectRegistry[url]
            self.redirect(url, newUrl)
            url = newUrl

        self._url = url

        BasicHTTPClientProtocol.run(self)

    def _receive(self, response):
        self._responseHeaders = dict(response.headers.getAllRawHeaders())
        self._responseCode = response.code
        self.headersReceived()

        if response.code==302 or response.code==301:
            # don't receive body if redirect
            try:
                location = dict(self.responseHeaders)['Location'][0]
            except (KeyError, IndexError):
                raise RedirectError, 'Location not announced'

            url = self.url
            if url in self.history:
                raise RedirectError, 'Circular reference: '+' -> '.join(self.history) + ' -> ' + url
            self.history.append(url)
            self.redirected(url, location)

            if response.code==301:
                self.__class__._redirectRegistry[self.url]=location

            self._url = location
            self.run()

        else:
            self._receiveBody(response)

    #public event handlers

    def redirected(self, from_, to_):
        """Called each time redirection occures"""
        pass
