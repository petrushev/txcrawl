from twisted.internet import reactor
from tests import httpclient

if __name__=='__main__':
    reactor.callLater(0, httpclient.suite)
    reactor.run()
