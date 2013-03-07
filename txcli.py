from sys import stderr

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

agent = Agent(reactor)

class Client(object):

    def __init__(self, url, headers = None):
        self.url = url
        self.method = 'GET'
        if headers is None:
            headers = {}
        self.headers = headers

        self._response = None
        self._response_body = None

    @property
    def _request_headers(self):
        return Headers(self.headers)

    @property
    def responseHeaders(self):
        return tuple(self._response.headers.getAllRawHeaders())

    @property
    def response(self):
        return self._response

    @property
    def responseBody(self):
        return self._response_body

    def run(self):
        self._response = None
        self._response_body = None

        self._main_deffered = agent.request(self.method, self.url, self._request_headers, None)
        self._main_deffered.addCallback(self._receive)
        self._main_deffered.addErrback(self._error)

    def _error(self, error):
        stderr.write('err: %s\n' % error.getErrorMessage())

    def _body_receiver_error(self, error):
        msg = error.getErrorMessage().strip()
        if msg!='':
            stderr.write('err: %s\n' % msg)
        pass

    def _receive(self, response):
        """Response received """
        self._response = response
        self.received()

        self._receive_body()

    def _receive_body(self):
        """Start receiving the body"""

        parent_self = self
        def dataReceived( chunk):
            parent_self._chunk_received(chunk)
        def connectionLost( error):
            parent_self._body_receiver_error(error)
            self._bodyFinished()

        self._response_body = ''
        body_receiver = Protocol()
        body_receiver.dataReceived = dataReceived
        body_receiver.connectionLost = connectionLost

        self._response.deliverBody(body_receiver)

    def _chunk_received(self, chunk):
        self._response_body = self._response_body + chunk
        self.chunkReceived(chunk)


    def _bodyFinished(self):
        """Body received"""
        self.bodyFinished()

    # handlers
    def received(self):
        """Fired after the response is received, but before the body"""
        pass

    def bodyFinished(self):
        """Fired when the body is completed"""
        pass

    def chunkReceived(self, chunk):
        """Fire after each body chunk is received,
        useful for progress if response length is available"""
        pass


class RedirectError(Exception): pass

class CommonClient(Client):

    # contains memo for responses with permanent rediretion
    _redirect_registry = {}

    # contains all url passed in redirection
    history = tuple()

    def _bodyFinished(self):
        self.finished()

    def _receive(self, response):
        self._response = response

        code = response.code

        if code==302 or code==301:
            # don't receive body if redirect
            try:
                location = dict(self.responseHeaders)['Location'][0]
            except (KeyError, IndexError):
                raise RedirectError, 'Location not announced'

            self.history = self.history + (self.url,)
            self.redirected(self.url, location)

            if code==301:
                self.__class__._redirect_registry[self.url]=location

            self.url = location

            self.run()

        else:
            self._receive_body()


    # handlers
    def finished(self):
        """Implement to be fired when the request body is received,
        If there is a redirection, it fires on the last response"""
        pass

    def redirected(self, from_, to_):
        """Implement to be fired on each redirection, but before sending the new request"""
        pass
