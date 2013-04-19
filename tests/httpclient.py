import json

from twisted.internet import reactor
from twisted.internet.defer import Deferred

from txhttpclient import CommonHTTPClientProtocol

def testOk():
    """Test basic 'ok-200' request"""

    client = CommonHTTPClientProtocol(url='http://httpbin.org/get?test=passed')
    d = Deferred()

    def responseComplete():
        response = json.loads(client.responseBody)

        try:
            assert 'args' in response
            assert 'test' in response['args']
            assert response['args']['test']=='passed'

        except AssertionError, exc:
            d.errback(exc)
        else:
            d.callback('')

    client.responseComplete = responseComplete

    return d

def testNotfound():
    """Test basic 'not found - 404' request"""

    client = CommonHTTPClientProtocol(url='http://httpbin.org/status/404')
    d = Deferred()
    def headersReceived():
        code = client.responseCode

        try:
            assert code==404

        except AssertionError, exc:
            d.errback(exc)
        else:
            d.callback('')

    client.headersReceived = headersReceived

    return d

def success(msg, testName, suiteStatus):
    print testName, 'passed.'
    finaly(suiteStatus)

def failure(err, testName, suiteStatus):
    print testName, 'failure:', err.getErrorMessage()
    suiteStatus['errors'] = suiteStatus['errors'] + 1
    finaly(suiteStatus)

def finaly(suiteStatus):
    suiteStatus['runningTests'] = suiteStatus['runningTests'] - 1
    if suiteStatus['runningTests']==0:
        print suiteStatus['totalTests'] - suiteStatus['errors'], 'of total', suiteStatus['totalTests'], 'tests passed.'
        reactor.stop()

def suite():
    """Main test suite"""
    suiteStatus = {'runningTests': 0, 'errors': 0}

    for functionName, function in globals().iteritems():

        if not functionName.startswith('test'): continue
        functionName = functionName[4:]

        result = function()
        result.addCallback(success, functionName, suiteStatus)
        result.addErrback(failure, functionName, suiteStatus)

        suiteStatus['runningTests'] = suiteStatus['runningTests'] + 1

    suiteStatus['totalTests'] = suiteStatus['runningTests']

if __name__=='__main__':
    reactor.callLater(0, suite)
    reactor.run()
