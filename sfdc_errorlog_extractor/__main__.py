
from sfdc_errorlog_extractor.SFDCErrorLogExtractor import SFDCErrorLogExtractor
import sys, subprocess, os, getopt

mswindows = (sys.platform == "win32")

def usage():
  print("errorlog-extraction.py -u <targetusername> -d <debugusername>")

def main(argv):

    if mswindows:
      print(f"Currently only supported for linux/mac. For windows users, deploy via Docker")
      sys.exit()

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
    
    logdir = f"{os.getcwd()}/logs/{debugusername}"
    os.makedirs(logdir, exist_ok=True)

    backupdir = f"{os.getcwd()}/backup"
    os.makedirs(backupdir, exist_ok=True)

    ele = SFDCErrorLogExtractor(targetusername, debugusername, logdir, backupdir)

    ele.startDebugLog()
    ele.retrieve()
    ele.delete()
    #ele.compressLogs()

if __name__ == "__main__":
    main(sys.argv[1:])
