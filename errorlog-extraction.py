#!/usr/bin/env python3

# Limitations
# Each debug log must be 20 MB or smaller.
# System debug logs are retained for 24 hours.
# Monitoring debug logs are retained for seven days.
# If you generate more than 1,000 MB of debug logs in a 15-minute window, your trace flags are disabled.

# Limit log size, remove log after use

from urllib.parse import quote_plus
import requests
import re
import sys
import getopt
import os
import json
import pytz
import datetime
from datetime import timedelta
from datetime import datetime
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError
import csv
import subprocess
import time
import calendar

apiVersion = '49.0'


class ApexLogMonitor():

    _limitsToCheck = [
        'DailyApiRequests',
        'DailyAsyncApexExecutions',
        'DailyBulkApiRequests',
        'DailyStreamingApiEvents'
    ]

    def __init__(self, targetusername, debugusername, logdir, datadir):
        self.limitThreshold = .50
        self.targetusername = targetusername
        self.debugusername = debugusername
        try:
            self._auth = self._getAuth()
            self._token = self._getToken()
            self._client = self._getClient()
        except:
            e = sys.exc_info()[0]
            raise AuthFailed(e)
        self._logdir = logdir
        self._datadir = datadir
        self.apexLogIds = []

    #
    # SFDX Token contains following fields: username, id, connectedStatus, instanceUrl, clientId
    #
    def _getAuth(self):
        sfdxCmd = f"sfdx force:org:display --targetusername={self.targetusername} --json"
        try:
            p = subprocess.Popen(sfdxCmd, shell=True,
                                 stdout=subprocess.PIPE, encoding='utf-8')
            result = p.communicate()[0].strip()
            p.stdout.close()
            return json.loads(result)['result']
        except:
            e = sys.exc_info()[0]
            print(f"SFDX Auth retrieval failed: {e}")

    def _getToken(self):
        return {
            'token_type': 'Bearer',
            'access_token': self._auth['accessToken']
        }

    def _getClient(self):
        return OAuth2Session(self._auth['clientId'], token=self._token)

    def startDebugLog(self):
        query = f"SELECT Id, ApexCode, ApexProfiling, Callout, Database, DebugLevel.DeveloperName, ExpirationDate, StartDate, System, TracedEntity.UserName, Validation, Visualforce, Workflow, LogType FROM TraceFlag WHERE TracedEntity.UserName='{self.debugusername}'"
        url = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/query/?q={quote_plus(query)}"

        debugQueryResult = json.loads(self._client.request('GET', url).text)

        dateformat = '%Y-%m-%dT%H:%M:%S.%f%z'
        traceDebugId = ''
        for result in debugQueryResult['records']:
            if result['DebugLevel']['DeveloperName'] == 'SFDXDebugLevel':
                traceDebugId = result['Id']
                ts = int(datetime.strptime(
                    result['ExpirationDate'], dateformat).timestamp())
                if (int(datetime.now().timestamp()) - ts) < 900:
                    print(
                        f"Debug TraceFlag has expiry > 15min not resetting for {self.debugusername}")
                    return

        dateformat = '%Y-%m-%dT%H:%M:%S.%f%z'
        expiryDate = (datetime.utcnow() + timedelta(minutes=30)
                      ).strftime(dateformat)

        url = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/sobjects/TraceFlag"

        body = ''
        if traceDebugId:
            body = {'ExpirationDate': f"{expiryDate}"}
            url += f"/{traceDebugId}"
        else:
            userQuery = f"SELECT Id FROM User WHERE username='{self.debugusername}'"
            userQueryUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/query?q={quote_plus(userQuery)}"
            userQueryResult = json.loads(self._client.request('GET', userQueryUrl).text)
            
            tracedEntityId = ''
            for result in userQueryResult['records']:
                tracedEntityId = result['Id']

            debugQueryResult = json.loads(self._client.request('GET', url).text) 
            body = {
              'ExpirationDate': f"{expiryDate}",
              'ApexCode': 'FINEST',
              'ApexProfiling': 'FINEST',
              'Callout': 'FINEST',
              'Database': 'FINEST',
              'DebugLevelId': '7dl1W000000KzQe',
              'System': 'FINE',
              'TracedEntityId': tracedEntityId,
              'Validation': 'INFO',
              'Visualforce': 'FINER',
              'Workflow': 'FINER',
              'LogType': 'USER_DEBUG'
            }

            print(body)
            response = self._client.request('POST', url, json=body, headers={
                                        'Content-Type': 'application/json'})

            if response.status_code == '200':
              print(f"Debug TraceFlag set for {self.debugusername}")
            else:
              print(
                f"Error unable to setup Debug TraceFlag for {self.debugusername}. Error: {response.text} Body: {body}")

    def retrieve(self):

        query = f"SELECT Application,DurationMilliseconds,Id,LastModifiedDate,Location,LogLength,LogUserId,Operation,Request,StartTime,Status,SystemModstamp FROM ApexLog WHERE LogUser.UserName = '{self.debugusername}' ORDER BY LastModifiedDate DESC"
        url = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/tooling/query/?q={quote_plus(query)}"

        apexLogQueryResult = json.loads(self._client.request('GET', url).text)

        if 'records' in apexLogQueryResult:
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
            raise LogError(
                f"Error No Results Returned. Result: {apexLogQueryResult}")

    def getApexLog(self, id):

        logBodyUrl = f"{self._auth['instanceUrl']}/services/data/v{apiVersion}/sobjects/ApexLog/{id}/Body"
        response = self._client.request('GET', logBodyUrl)
        if response:
            return response.text
        else:
            raise LogError('No Log Content')

    def delete(self):
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

        compressFilesCmd = f"zip {self._datadir}/{self.debugusername}.{datetime.now().strftime('%Y%m%d%H%M')}.zip {self._logdir}/*.txt"
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
        print(f"del: {delResult}")


class LogError(Exception):
    def __init__(self, message):
        super(LogError, self).__init__(message)


class AuthFailed(Exception):
    def __init__(self, message):
        super(AuthFailed, self).__init__(message)

def usage():
  print("errorlog-extraction.py -u <targetusername> -d <debugusername>")

def main(argv):
    logdir = f"{os.environ['HOME']}/logs"
    datadir = logdir
    subprocess.call(f"mkdir -p {logdir}", shell=True)

    try:
      opts, args = getopt.getopt(sys.argv[1:],"u:d:h",["targetusername=", "debugusername="])
    except getopt.GetoptError:
      print('errorlog-extraction.py -u <targetusername> -d <debugusername>')
      sys.exit(2)

    targetusername = None
    debugusername = None

    for opt, arg in opts:
      if opt == '-h':
        usage()
        sys.exit()
      elif opt in ("-u", "--targetusername"):
        targetusername = arg
      elif opt in ("-d", "--debugusername"):
        debugusername = arg

    if not targetusername:
      print('Please supply a targetusername for logging into sfdc org')
      usage()
      sys.exit(2)
    if not debugusername:
      print('Please supply a debug username for pulling logs')
      usage()
      sys.exit(2)

    apm = ApexLogMonitor(targetusername, debugusername, logdir, datadir)

    #apm.startDebugLog()
    apm.retrieve()
    apm.delete()
    #apm.compressLogs()


if __name__ == "__main__":
    main(sys.argv[1:])
