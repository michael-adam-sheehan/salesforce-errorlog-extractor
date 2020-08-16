import pytest, requests, responses, json
from datetime import timedelta, datetime, timezone
from unittest import TestCase, mock
from testfixtures.popen import MockPopen
from sfdc_errorlog_extractor.SFDCErrorLogExtractor import SFDCErrorLogExtractor

@pytest.fixture
def mock_response(monkeypatch):

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)


class TestSFDCErrorLogExtractor(TestCase):

    authSuccessResponse = {
        'status': 0,
        'result': {
            'username': 'admin@teegrep-dev01.com',
            'id': '00D3t000003zpo7EAA',
            'connectedStatus': 'Connected',
            'accessToken': '000000000000000000000000',
            'instanceUrl': 'https://na123.salesforce.com',
            'clientId': 'PlatformCLI',
            'alias': 'teegrep-dev01'
        }
    }
    authErrorResponse = {
        'status': 1,
        'name': 'NoOrgFound',
        'message': 'No org configuration found for name admin@teegrep-dev1.com',
        'exitCode': 1,
        'commandName': 'OrgDisplayCommand',
        'stack': 'NoOrgFound: No org configuration found for name admin@teegrep-dev1.com\n    at Function.create (/usr/local/lib/sfdx/node_modules/salesforce-alm/node_modules/@salesforce/command/node_modules/@salesforce/core/lib/sfdxError.js:141:16)\n    at AuthInfo.loadAuthFromConfig (/usr/local/lib/sfdx/node_modules/salesforce-alm/node_modules/@salesforce/command/node_modules/@salesforce/core/lib/authInfo.js:577:49)',
        'warnings': [
          'The error message \"NoOrgFound\" has been deprecated and will be removed in v46 or later.  It will become \"NamedOrgNotFound\".'
        ]
    }

    dateformat = '%Y-%m-%dT%H:%M:%S.000%z'
    expiryDateNow = (datetime.now(timezone.utc)).strftime(dateformat)
    debugQueryPositiveResultNotExpired = {
      'size': 1, 
      'totalSize': 1, 
      'done': True, 
      'queryLocator': None, 
      'entityTypeName': 
      'TraceFlag', 
      'records': [{
        'attributes': {
          'type': 'TraceFlag', 
          'url': '/services/data/v49.0/tooling/sobjects/TraceFlag/7tf3t000002ZOoaAAG'
        }, 
        'Id': '7tf3t000002ZOoaAAG', 
        'ApexCode': 'FINEST', 
        'ApexProfiling': 'FINEST', 
        'Callout': 'FINEST', 
        'Database': 'FINEST', 
        'DebugLevel': {
          'attributes': {
            'type': 'DebugLevel', 
            'url': '/services/data/v49.0/tooling/sobjects/DebugLevel/7dl3t000000TqYnAAK'
          }, 
          'DeveloperName': 'SFDXDebugLevel'
        }, 
        'ExpirationDate': expiryDateNow, 
        'StartDate': expiryDateNow,
        'System': 'FINEST', 
        'TracedEntity': {
          'attributes': {
            'type': 'Name', 
            'url': '/services/data/v49.0/tooling/sobjects/User/0053t000008EMNzAAO'
          }, 
          'Username': 'admin@teegrep-dev01.com'
        }, 
        'Validation': 'FINEST', 
        'Visualforce': 'FINEST', 
        'Workflow': 'FINEST', 
        'LogType': 'USER_DEBUG'
      }]
    }

    @mock.patch('subprocess.Popen')
    @responses.activate
    def test_startDebugLog_traceflag_present(self, mock_popen):
        print(TestSFDCErrorLogExtractor.authSuccessResponse)
        popenMock = mock.Mock()
        attrs = {'communicate.return_value': (json.dumps(TestSFDCErrorLogExtractor.authSuccessResponse), 'error'), 'returncode': 0}
        popenMock.configure_mock(**attrs)
        mock_popen.return_value = popenMock
        url = 'https://na123.salesforce.com/services/data/v49.0/tooling/query/?q=SELECT+Id%2C+ApexCode%2C+ApexProfiling%2C+Callout%2C+Database%2C+DebugLevel.DeveloperName%2C+ExpirationDate%2C+StartDate%2C+System%2C+TracedEntity.UserName%2C+Validation%2C+Visualforce%2C+Workflow%2C+LogType+FROM+TraceFlag+WHERE+TracedEntity.UserName%3D%27testuser%40test-sfdc-errorlog.com%27'
        body = ''
        responses.add(
            responses.GET, url,
            body=json.dumps(TestSFDCErrorLogExtractor.debugQueryPositiveResultNotExpired), status=200,
            content_type='application/json'
        )

        """Checks if traceflag is already set"""
        ele = SFDCErrorLogExtractor(targetusername='testuser@test-sfdc-errorlog.com', debugusername='testuser@test-sfdc-errorlog.com', logdir='../logs', datadir='../data')
        ele.startDebugLog()
        assert True
