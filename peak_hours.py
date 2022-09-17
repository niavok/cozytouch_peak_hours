#!/usr/bin/python3
import urllib.request
import json
import argparse
import configparser

class Config:
    loaded : bool = False
    scan_mode : bool = True
    file_path : str = ""
    login : str = ""
    password : str = ""
    atlantic_url=u'https://api.groupe-atlantic.com/'

config = Config()

def ParseArguments():
    parser = argparse.ArgumentParser(description='Water heater control to avoid peak hours.')
    parser.add_argument('command', choices={'scan', 'run'}, default='run',
                    help='scan to display the current state, run to execute the heater control.')
    parser.add_argument('--config', '-c', default='config.cfg')

    args = parser.parse_args()
    config.scan_mode = args.command == 'scan'
    config.file_path = args.config

def LoadConfig():

    config_file = configparser.ConfigParser()
    config_file.read(config.file_path)

    if len(config_file.sections()) == 0:
        print("Fail to open or read config file '"+config.file_path+"'")
        return False

    if 'Access' not in config_file:
        print("Fail to find 'Access section in config file")
        return False

    config.login = config_file['Access']['Login']
    config.password = config_file['Access']['Password']

    config.loaded = True
    return True

def GetToken():
    url = config.atlantic_url + "token"
    print(url)
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', 'Basic czduc0RZZXdWbjVGbVV4UmlYN1pVSUM3ZFI4YTphSDEzOXZmbzA1ZGdqeDJkSFVSQkFTbmhCRW9h')
    body  = {
        'grant_type':'password',
        'username':config.login,
        'password':config.password
    }
    data = urllib.parse.urlencode(body).encode("utf-8")
    raw_response = ""
    try:
        raw_response = urllib.request.urlopen(req, data)
    except urllib.error.HTTPError as err:
        print('error' + str(err))
        print(err.read().decode())
        return

    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))

    print(response)


ParseArguments()
LoadConfig()

if config.loaded:
   GetToken()