#!/usr/bin/env python3

# Limitations
# Each debug log must be 20 MB or smaller.
# System debug logs are retained for 24 hours.
# Monitoring debug logs are retained for seven days.
# If you generate more than 1,000 MB of debug logs in a 15-minute window, your trace flags are disabled.

# Limit log size, remove log after use

from urllib.parse import quote_plus
import sys, subprocess, json, pytz, csv, re
from datetime import timedelta, datetime
from requests_oauthlib import OAuth2Session

apiVersion = '49.0'

class SFDCErrorLogExtractor():

    def __init__(self, targetusername, debugusername, logdir, backupdir, verbose=False):
        self.verbose = verbose
        self.targetusername = targetusername
        self.debugusername = debugusername
        try:
            self._auth = self._getAuth()
            self._token = self._getToken()
            self._client = self._getClient()
        except Exception as e:
            print(e)
            sys.exit()

        self._logdir = logdir
        self._backupdir = backupdir
        self.apexLogIds = []
    #
    # SFDX Token contains following fields: username, id, connectedStatus, instanceUrl, clientId
    #
    def _getAuth(self):
        sfdxCmd = f"sfdx force:org:display --targetusername={self.targetusername} --json"
        auth = {}
        p = subprocess.Popen(sfdxCmd, shell=True,
                                stdout=subprocess.PIPE, encoding='utf-8')
        response = json.loads(p.communicate()[0])
        p.stdout.close()
        if 'result' not in response:
            raise AuthFailed(f"Error no result found in response. Response: {response}")
        auth = response['result']
        if self.verbose:
            print(f"setting auth = {auth}")

        return auth

    def _getToken(self):

        if 'accessToken' not in self._auth:
            raise AuthFailed(f"Error no accesstoken found. auth:{self._auth}")

        return {
            'token_type': 'Bearer',
            'access_token': self._auth['accessToken']
        }

    def _getClient(self):
        if 'clientId'  not in self._auth:
            raise AuthFailed(f"Error no clientId found. auth:{self._auth}")

        return OAuth2Session(self._auth['clientId'], token=self._token)

    def startDebugLog(self):
        debugLevelName = 'SFDXDebugLevel'
        # query for debug trace flag
        query = f"SELECT Id, ApexCode, ApexProfiling, Callout, Database, DebugLevel.DeveloperName, ExpirationDate, StartDate, System, TracedEntity.UserName, Validation, Visualforce, Workflow, LogType FROM TraceFlag WHERE TracedEntity.UserName='{self.debugusername}'"
        url = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/query/?q={quote_plus(query)}"
        debugQueryResult = self._client.request('GET', url).json()
        dateformat = '%Y-%m-%dT%H:%M:%S.%f%z'
        traceDebugId = ''
        # check for both the user debug log type and debug level
        # there can only be 1 USER_DEBUG active at a time
        for result in debugQueryResult['records']:
            ts = int(datetime.strptime(
                    result['ExpirationDate'], dateformat).timestamp())
            if result['LogType'] == 'USER_DEBUG' and (int(datetime.now().timestamp()) - ts) < 900:
                print(f"TraceFlag for DebugLevel: {result['DebugLevel']['DeveloperName']}) detected expiry > 15min not resetting for {self.debugusername}")
                return
            if result['DebugLevel']['DeveloperName'] == debugLevelName:
                traceDebugId = result['Id']
                
        expiryDate = (datetime.utcnow() + timedelta(minutes=30)).strftime(dateformat)
        startDate = (datetime.utcnow() + timedelta(minutes=0)).strftime(dateformat)
        # no traceflag check if debug level is defined 
        if not traceDebugId:
          print(f"No TraceDebugId found. Checking for DebugLevel: {debugLevelName}...")

          queryDebugLevel = f"SELECT Id FROM DebugLevel WHERE DeveloperName = '{debugLevelName}'"
          queryDebugLevelUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/query/?q={quote_plus(queryDebugLevel)}"
          queryDebugLevelResult = self._client.request('GET', queryDebugLevelUrl).json()

          if queryDebugLevelResult['totalSize'] > 0:
            print(f"Found debug level..")
            debugLevelId = queryDebugLevelResult['records'][0]['Id']
          else:
            print(f"DebugLevel: {queryDebugLevel} not found. Creating...")
            body = {
                'ApexCode' : 'FINEST',
                'ApexProfiling': 'FINEST',
                'Callout': 'FINEST',
                'Database': 'FINEST',
                'System': 'FINEST',
                'MasterLabel': debugLevelName,
                'DeveloperName': debugLevelName,
                'Validation': 'FINEST',
                'Visualforce': 'FINEST',
                'Workflow': 'FINEST'
            }
            debugLevelUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/sobjects/DebugLevel"
            debugLevelResult = self._client.request('POST', debugLevelUrl, json=body, headers={
                                            'Content-Type': 'application/json'}).json()

            if debugLevelResult['success'] == True:
                print(f"Successfully created {debugLevelName} ({debugLevelResult})...")
                debugLevelId = debugLevelResult['id']
            else:
                print(f"Error unable to create {debugLevelName}. Error: {debugLevelResult} Body: {body}")
                sys.exit()

          debugQueryResult = self._client.request('GET', url).json()
          userQuery = f"SELECT Id FROM User WHERE username='{self.debugusername}'"
          userQueryUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/query?q={quote_plus(userQuery)}"
          userQueryResult = self._client.request('GET', userQueryUrl).json()
          tracedEntityId = ''
          for result in userQueryResult['records']:
            tracedEntityId = result['Id']

          body = {
            'StartDate': f"{startDate}",
            'ExpirationDate': f"{expiryDate}",
            'ApexCode': 'FINEST',
            'ApexProfiling': 'FINEST',
            'Callout': 'FINEST',
            'Database': 'FINEST',
            'DebugLevelId': debugLevelId,
            'System': 'FINE',
            'TracedEntityId': tracedEntityId,
            'Validation': 'INFO',
            'Visualforce': 'FINER',
            'Workflow': 'FINER',
            'LogType': 'USER_DEBUG'
          }

        traceDebugUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/sobjects/TraceFlag"
        if traceDebugId:
          print(f"TraceDebugId defined setting body to expiration date only.")
          body = {'StartDate': f"{startDate}",'ExpirationDate': f"{expiryDate}"}
          traceDebugUrl += f"/{traceDebugId}"

        traceDebugResult = self._client.request('PATCH', traceDebugUrl, json=body, headers={
            'Content-Type': 'application/json'}).json()

        # patching requests w/tracedebugid doesn't return results
        # TODO: capture request and check status code and remove this conditional
        if not traceDebugId:
            if 'success' in traceDebugResult:
                print(f"Debug TraceFlag set for {self.debugusername}. exiting...")
            else:
                print(f"Error unable to setup Debug TraceFlag for {self.debugusername}. Error: {traceDebugResult} Url: {traceDebugUrl} Body: {body}")
                sys.exit()

    def retrieve(self):
        print(f"Retrieving logs for {self.debugusername}...")
        query = f"SELECT Application,DurationMilliseconds,Id,LastModifiedDate,Location,LogLength,LogUserId,Operation,Request,StartTime,Status,SystemModstamp FROM ApexLog WHERE LogUser.UserName = '{self.debugusername}' ORDER BY LastModifiedDate DESC"
        url = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/query/?q={quote_plus(query)}"

        apexLogQueryResult = self._client.request('GET', url).json()

        if apexLogQueryResult['totalSize'] > 0:
            print(f"Found {len(apexLogQueryResult['records'])} logs")
            for result in apexLogQueryResult['records']:
                format = '%Y-%m-%dT%H:%M:%S.%f%z'
                d = datetime.strptime(
                    result['LastModifiedDate'], format)
                pst = pytz.timezone('America/Los_Angeles')
                print(
                    f"id: {result['Id']} date: {d.astimezone(pst).strftime('%Y%m%d-%H%M%S')}")

                filename = f"{d.astimezone(pst).strftime('%Y%m%d-%H%M%S')}-{result['Id']}.txt"
                with open(f"{self._logdir}/{filename}", 'w') as fh:
                    try:
                        fh.write(self.getApexLog(result['Id']))
                    except:
                        e = sys.exc_info()[0]
                        print(f"Error saving log: {filename} Error: {e}")
                        sys.exit()

                self.apexLogIds.append(result['Id'])
        else:
            print(f"No logs found.")

    def getApexLog(self, id):

        logBodyUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/sobjects/ApexLog/{id}/Body"
        response = self._client.request('GET', logBodyUrl)
        if response:
            return response.text
        else:
            raise LogError('No Log Content')

    def delete(self):
        print(f"Deleting logs from instance...")
        if self.apexLogIds:
            logIdsCsvFile = f"{self._logdir}/apex-logids.csv"
            with open(logIdsCsvFile, 'w') as csvwriter_file:
                csvwriter = csv.writer(csvwriter_file)
                csvwriter.writerow(['Id'])
                for id in self.apexLogIds:
                    csvwriter.writerow([id])

            sfdxCmd = f"sfdx force:data:bulk:delete -s ApexLog -w 5 -f {logIdsCsvFile} --targetusername={self.targetusername}"
            try:
                p = subprocess.Popen(sfdxCmd, shell=True,
                                     stdout=subprocess.PIPE, encoding='utf-8')
                p.wait()
                result = p.communicate()[0].strip()
                p.stdout.close()
                print(f"{result}")
            except:
                e = sys.exc_info()[0]
                print(f"Error deleting logs: {e}")

    def encode_escape(self, val):
        return "'{}'".format(re.sub("[\"]", "\"\"", val))

    def compressLogs(self):

        compressFilesCmd = f"zip {self._backupdir}/{self.debugusername}.{datetime.now().strftime('%Y%m%d%H%M')}.zip {self._logdir}/*.txt"
        try:
            p = subprocess.Popen(compressFilesCmd, shell=True,
                                 stdout=subprocess.PIPE, encoding='utf-8')
            p.wait()
            result = p.communicate()[0].strip()
            p.stdout.close()
            print(f"{result}")
        except:
            e = sys.exc_info()[0]
            print(f"Error deleting logs: {e}")

        p2 = subprocess.Popen(f"rm {self._logdir}/*.txt", shell=True,
                              stdout=subprocess.PIPE, encoding='utf-8')
        p2.wait()
        delResult = p2.communicate()[0].strip()
        p2.stdout.close()
        print(f"Delete output: {delResult}")

class LogError(Exception):
    def __init__(self, message):
        super(LogError, self).__init__(message)

class AuthFailed(BaseException):
    def __init__(self, message):
        super(AuthFailed, self).__init__(message)
