#!/usr/bin/python3
from tkinter import Label
import urllib.request
import json
import argparse
import configparser
import time

class Config:
    loaded : bool = False
    command : str = ""
    file_path : str = ""
    login : str = ""
    password : str = ""
    device_url : str = ""
    atlantic_url=u'https://api.groupe-atlantic.com/'
    cozytouch_url=u'https://ha110-1.overkiz.com/enduser-mobile-web/externalAPI/json/'
    cozytouch_login_url=u'https://ha110-1.overkiz.com/enduser-mobile-web/enduserAPI/'

class Session:
    atlantic_access_token = ""
    atlantic_refresh_token = ""
    atlantic_token_expire_in = 0
    cozytouch_cookies = ""


config = Config()
session = Session()

def ParseArguments():
    parser = argparse.ArgumentParser(description='Water heater control to avoid peak hours.')
    parser.add_argument('command', choices={'scan', 'status', 'run'}, default='run',
                    help='scan to display the current state, run to execute the heater control.')
    parser.add_argument('--config', '-c', default='config.cfg')

    args = parser.parse_args()
    config.command = args.command
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

    config.device_url = config_file['Device']['Url']

    config.loaded = True
    return True

def GetAtlanticToken():
    url = config.atlantic_url + "token"
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
        print("Fail to connect to server")
        print('error' + str(err))
        print(err.read().decode())
        return

    print("Get Atlantic token: OK")

    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    session.atlantic_access_token = response['access_token']
    session.atlantic_refresh_token = response['refresh_token']
    session.atlantic_token_expire_in = response['expires_in']

def CozyTouchLogin():
    # Get JWT Token
    urljwt = config.atlantic_url + "gacoma/gacomawcfservice/accounts/jwt"
    reqjwt = urllib.request.Request(urljwt, method='GET')
    reqjwt.add_header('Authorization', 'Bearer '+session.atlantic_access_token)
    
    jst_raw_response = ""
    try:
        jst_raw_response = urllib.request.urlopen(reqjwt)
    except urllib.error.HTTPError as err:
        print("Fail to get jwt")
        print('error' + str(err))
        print(err.read().decode())
        return
    jwt = jst_raw_response.read().decode(jst_raw_response.info().get_param('charset') or 'utf-8').replace('"', '')
    print("Get jst token: OK")

    # Cozytouch login
    url = config.cozytouch_login_url + "login"
    req = urllib.request.Request(url, method='POST')
    body  = {
        'jwt':jwt
    }
    data = urllib.parse.urlencode(body).encode("utf-8")
    raw_response  = ""
    try:
        raw_response = urllib.request.urlopen(req, data)
    except urllib.error.HTTPError as err:
        print("Fail to connect to cosytouch login server")
        print('error' + str(err))
        print(err.read().decode())
        return

    #response = raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8')
    #print(response)
    session.cozytouch_cookies = raw_response.info().get_all('Set-Cookie')[0]

    print("Cosytouch login: OK")

def CozyTouchGet(url):
    url = config.cozytouch_url + url
    req = urllib.request.Request(url, method='GET')
    req.add_header('cache-control', 'no-cache')
    req.add_header('Cookie', session.cozytouch_cookies)

    raw_response  = ""
    try:
        raw_response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as err:
        print("Fail to connect to cosytouch data server")
        print('error' + str(err))
        print(err.read().decode())
        return
    
    response_json = (raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    response = json.loads(response_json)
    
    #print(response_json)
    time.sleep(1) # Wait between requests
    return response

def CozyTouchCommand(command, parameters):

    url = config.cozytouch_url + '../../enduserAPI/exec/apply'
    req = urllib.request.Request(url, method='POST')
    req.add_header('cache-control', 'no-cache')
    req.add_header('Cookie', session.cozytouch_cookies)
    req.add_header('Content-type', 'application/json')

    body  = {
        'actions': [ 
            {
                'deviceURL': config.device_url,
                'commands': [
                    {
                        'name' : command,
                        'parameters' : parameters
                    }
                ]
            }
        ]
    }

    jsondata = json.dumps(body)
    jsondataasbytes = jsondata.encode('utf-8')   # needs to be bytes
    raw_response = ""
    try:
        raw_response = urllib.request.urlopen(req, jsondataasbytes)
    except urllib.error.HTTPError as err:
        print("Fail to send command")
        print('error' + str(err))
        print(err.read().decode())
        return
    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    print(response)
    time.sleep(1) # Wait between requests
    return response


def Scan():
    GetAtlanticToken()
    CozyTouchLogin()
    CozyTouchGet('refreshAllStates')
    setup = CozyTouchGet('getSetup')
    gateway = setup['setup']['gateways'][0]
    if gateway['alive']:
        print("Gateway: OK")
    else:
        print("Gateway not alive")

    print("Devices:")
    for device in setup['setup']['devices']:
        label = device['label']
        widget = device['widget']
        deviceURL = device['deviceURL']
        print("  - "+ label + ": "+ widget)
        print("    - deviceURL: "+ deviceURL)

def PrintDeviceStatus():
    devices = CozyTouchGet('../../enduserAPI/setup/devices')
    for device in devices:
        if device['deviceURL'] != config.device_url:
            continue
        print(device['label'])
        states = device['states']
        for state in states:
            if state['name'] == "modbuslink:DHWAbsenceModeState":
                print('  - AbsenceModeState: '+ state['value'])
            if state['name'] == "modbuslink:MiddleWaterTemperatureState":
                print('  - Temperature: '+ str(state['value']))
            if state['name'] == "core:ExpectedNumberOfShowerState":
                print('  - ExpectedNumberOfShower: '+ str(state['value']))
            if state['name'] == "core:DateTimeState":
                print('  - Date: '+ str(state['value']))
            if "Absence" in state['name']:
                print('  - '+ state['name']+': '+ str(state['value']))
            if "Temperature" in state['name']:
                print('  - '+ state['name']+': '+ str(state['value']))
            if "Heating" in state['name']:
                print('  - '+ state['name']+': '+ str(state['value']))
                

def Run():
    GetAtlanticToken()
    CozyTouchLogin()
    CozyTouchCommand('refreshAbsenceMode', [])
    CozyTouchCommand('refreshDateTime', [])


    PrintDeviceStatus()
    #CozyTouchCommand('setAbsenceMode', ["on"]) 
    CozyTouchCommand('setAbsenceStartDate', [{ 'month': 9, 'hour': 18, 'year': 2022, 'weekday': 5, 'day': 17, 'minute': 00, 'second': 00 }]) 
    CozyTouchCommand('setAbsenceEndDate', [{ 'month': 9, 'hour': 19, 'year': 2022, 'weekday': 5, 'day': 17, 'minute': 00, 'second': 00 }]) 
    
    CozyTouchCommand('setExpectedNumberOfShower', [2]) 
    

    CozyTouchCommand('refreshAbsenceMode', [])
    PrintDeviceStatus()

def Status():
    GetAtlanticToken()
    CozyTouchLogin()
    CozyTouchCommand('refreshDateTime', [])
    CozyTouchCommand('refreshAbsenceMode', [])
    CozyTouchCommand('refreshHeatingStatus', [])
    CozyTouchCommand('refreshMiddleWaterTemperatureIn', []) 
    CozyTouchCommand('refreshMiddleWaterTemperature', []) 
    
    CozyTouchGet('refreshAllStates')
    PrintDeviceStatus()

ParseArguments()
LoadConfig()

if config.loaded:
    if config.command == "scan":
        Scan()
    elif config.command == "run":
        Run()
    elif config.command == "status":
        Status()