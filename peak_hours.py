#!/usr/bin/python3
import urllib.request
import json
import argparse
import configparser
import time
import sys
import os
from datetime import datetime, timedelta
from datetime import time as dtime

class Config:
    loaded : bool = False
    command : str = ""
    file_path : str = ""
    log_file_path : str = "cozytouch_peak_hours.log"
    login : str = ""
    password : str = ""
    device_url : str = ""
    absence_ranges = []
    absence_start_margin = 0
    absence_end_margin = 0
    absence_prog_margin = 0
    atlantic_url=u'https://apis.groupe-atlantic.com/'
    cozytouch_url=u'https://ha110-1.overkiz.com/enduser-mobile-web/externalAPI/json/'
    cozytouch_login_url=u'https://ha110-1.overkiz.com/enduser-mobile-web/enduserAPI/'

class Session:
    atlantic_access_token = ""
    atlantic_refresh_token = ""
    atlantic_token_expire_in = 0
    cozytouch_cookies = ""


config = Config()
session = Session()

def Log(message : str):
    PrintAndLog(message, False)

def PrintAndLog(message : str, doPrint = True):
    message_str = str(message)
    line = str(datetime.now()) + " - " + message_str
    if(doPrint):
        print(line)
        sys.stdout.flush()
    log_file = open(os.path.dirname(os.path.realpath(__file__)) + "/" + config.log_file_path, 'a')
    log_file.write(line)
    log_file.write("\n")
    log_file.close()


def ParseArguments():
    parser = argparse.ArgumentParser(description='Water heater control to avoid peak hours.')
    parser.add_argument('command', choices={'scan', 'status', 'run', 'on', 'off'}, default='run',
                    help='scan to display the current state, run to execute the heater control.')
    parser.add_argument('--config', '-c', default='config.cfg')

    args = parser.parse_args()
    config.command = args.command
    config.file_path = args.config

def LoadConfig():

    config_file = configparser.ConfigParser()
    config_file.read(config.file_path)

    if len(config_file.sections()) == 0:
        PrintAndLog("Fail to open or read config file '"+config.file_path+"'")
        return False

    if 'Access' not in config_file:
        PrintAndLog("Fail to find 'Access section in config file")
        return False

    config.login = config_file['Access']['Login']
    config.password = config_file['Access']['Password']

    config.device_url = config_file['Device']['Url']
    config.absence_ranges = json.loads(config_file['Device']['AbsenceRanges'])
    config.absence_start_margin = int(config_file['Device']['AbsenceStartMargin'])
    config.absence_end_margin = int(config_file['Device']['AbsenceEndMargin'])
    config.absence_prog_margin = int(config_file['Device']['AbsenceProgMargin'])

    config.loaded = True
    return True

def GetAtlanticToken():
    url = config.atlantic_url + "token"
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', 'Basic Q3RfMUpWeVRtSUxYOEllZkE3YVVOQmpGblpVYToyRWNORHpfZHkzNDJVSnFvMlo3cFNKTnZVdjBh')
    body  = {
        'grant_type':'password',
        'username': 'GA-PRIVATEPERSON/' + config.login,
        'password':config.password
    }
    data = urllib.parse.urlencode(body).encode("utf-8")
    raw_response = ""
    try:
        raw_response = urllib.request.urlopen(req, data)
    except urllib.error.HTTPError as err:
        PrintAndLog("Fail to connect to server")
        PrintAndLog('error' + str(err))
        PrintAndLog(err.read().decode())
        return False
    except urllib.error.URLError as err:
        PrintAndLog("Fail to resolve URL, check internet connection")
        PrintAndLog('error' + str(err))
        return False

    PrintAndLog("Get Atlantic token: OK")

    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    Log(response)
    session.atlantic_access_token = response['access_token']
    session.atlantic_refresh_token = response['refresh_token']
    session.atlantic_token_expire_in = response['expires_in']
    return True

def CozyTouchLogin():
    # Get JWT Token
    urljwt = config.atlantic_url + "magellan/accounts/jwt"
    reqjwt = urllib.request.Request(urljwt, method='GET')
    reqjwt.add_header('Authorization', 'Bearer '+session.atlantic_access_token)

    jst_raw_response = ""
    try:
        jst_raw_response = urllib.request.urlopen(reqjwt)
    except urllib.error.HTTPError as err:
        PrintAndLog("Fail to get jwt")
        PrintAndLog('error' + str(err))
        PrintAndLog(err.read().decode())
        return False
    except urllib.error.URLError as err:
        PrintAndLog("Fail to resolve URL, check internet connection")
        PrintAndLog('error' + str(err))
        return False
    jwt = jst_raw_response.read().decode(jst_raw_response.info().get_param('charset') or 'utf-8').replace('"', '')
    PrintAndLog("Get jst token: OK")
    Log(jwt)

    # Cozytouch login
    url = config.cozytouch_login_url + "login"
    Log("POST: "+url)
    req = urllib.request.Request(url, method='POST')
    body  = {
        'jwt':jwt
    }
    data = urllib.parse.urlencode(body).encode("utf-8")
    raw_response  = ""
    try:
        raw_response = urllib.request.urlopen(req, data)
    except urllib.error.HTTPError as err:
        PrintAndLog("Fail to connect to cosytouch login server")
        PrintAndLog('error' + str(err))
        PrintAndLog(err.read().decode())
        return False
    except urllib.error.URLError as err:
        PrintAndLog("Fail to resolve URL, check internet connection")
        PrintAndLog('error' + str(err))
        return False

    response = raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8')
    Log(response)
    session.cozytouch_cookies = raw_response.info().get_all('Set-Cookie')[0]

    PrintAndLog("Cosytouch login: OK")
    return True

def CozyTouchGet(url):
    url = config.cozytouch_login_url + url
    Log("GET: "+ url)
    req = urllib.request.Request(url, method='GET')
    req.add_header('cache-control', 'no-cache')
    req.add_header('Host', 'ha110-1.overkiz.com')
    req.add_header('Connection', 'Keep-Alive')
    req.add_header('Cookie', session.cozytouch_cookies)

    raw_response  = ""
    try:
        raw_response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as err:
        PrintAndLog("Fail to connect to cosytouch data server: " + url)
        PrintAndLog('error' + str(err))
        PrintAndLog(err.read().decode())
        return False
    except urllib.error.URLError as err:
        PrintAndLog("Fail to resolve URL, check internet connection")
        PrintAndLog('error' + str(err))
        return False

    response_json = (raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    response = json.loads(response_json)

    Log(response_json)
    time.sleep(2) # Wait between requests
    return response

def CozyTouchCommand(command, parameters):
    PrintAndLog("Send command '"+ command + ' ' + str(parameters))
    url = config.cozytouch_url + '../../enduserAPI/exec/apply'
    Log("POST: "+ url)
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
        PrintAndLog("Fail to send command")
        PrintAndLog('error' + str(err))
        PrintAndLog(err.read().decode())
        return False
    except urllib.error.URLError as err:
        PrintAndLog("Fail to resolve URL, check internet connection")
        PrintAndLog('error' + str(err))
        return False
    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))
    Log(response)
    time.sleep(1) # Wait between requests
    return response

def FormatDateTime(date : datetime) -> list:
    return [{ 'month': date.month, 'hour': date.hour, 'year': date.year, 'weekday': date.weekday(), 'day': date.day, 'minute': date.minute, 'second': date.second }]

def ParseDateTime(jsonDateTime : list , now : datetime) -> datetime :

    if jsonDateTime['year'] == '??':
        jsonDateTime['year'] = now.year
    if jsonDateTime['month'] == '??':
        jsonDateTime['month'] = now.month
    if jsonDateTime['day'] == '??':
        jsonDateTime['day'] = now.day
    if jsonDateTime['hour'] == '??':
        jsonDateTime['hour'] = now.hour
    if jsonDateTime['minute'] == '??':
        jsonDateTime['minute'] = now.minute
    if jsonDateTime['second'] == '??':
        jsonDateTime['second'] = now.second

    try:
        return datetime(jsonDateTime['year'], jsonDateTime['month'], jsonDateTime['day'], jsonDateTime['hour'], jsonDateTime['minute'], jsonDateTime['second'])
    except ValueError:
        PrintAndLog('Fail to parse date, use now')
        return now

def Scan():
    if not GetAtlanticToken():
        return False
    if not CozyTouchLogin():
        return False
    
    setup = CozyTouchGet('setup')

    if not setup:
        return False
    gateway = setup['gateways'][0]
    if gateway['alive']:
        PrintAndLog("Gateway: OK")
    else:
        PrintAndLog("Gateway not alive")

    PrintAndLog("Devices:")
    for device in setup['devices']:
        label = device['label']
        widget = device['widget']
        deviceURL = device['deviceURL']
        PrintAndLog("  - "+ label + ": "+ widget)
        PrintAndLog("    - deviceURL: "+ deviceURL)
    return True

def GetDateError():
    now_date = datetime.now()
    if not CozyTouchCommand('refreshDateTime', []) : return False
    
    setup = CozyTouchGet('setup')

    if not setup : return False
    for device in setup['devices']:
        if device['deviceURL'] != config.device_url:
            continue
        states = device['states']
        for state in states:
            if state['name'] == "core:DateTimeState":
                PrintAndLog('Date: '+ str(state['value']))
                distant_date = ParseDateTime(state['value'], now_date)
                if not distant_date:
                    return False
                date_error = distant_date - now_date
                PrintAndLog('Date error: '+ str(date_error)+')')
                return date_error
    return False

def PrintDeviceStatus(updateDateIfNeeded = True):
    now_date = datetime.now()
    date_error = None
    if not CozyTouchCommand('refreshDateTime', []) : return False
    if not CozyTouchCommand('refreshAbsenceMode', []) : return False
    if not CozyTouchCommand('refreshHeatingStatus', []) : return False
    if not CozyTouchCommand('refreshMiddleWaterTemperatureIn', []) : return False
    if not CozyTouchCommand('refreshMiddleWaterTemperature', []) : return False
    if not CozyTouchCommand('refreshV40WaterVolumeEstimation', []) : return False
    if not CozyTouchCommand('refreshNumberOfShowerRemaining', []) : return False
    if not CozyTouchCommand('refreshRemainingHotWater', []) : return False

    setup = CozyTouchGet('setup')

    if not setup : return False
    for device in setup['devices']:
        if device['deviceURL'] != config.device_url:
            continue
        PrintAndLog(device['label'])
        states = device['states']
        for state in states:
            if state['name'] == "modbuslink:DHWAbsenceModeState":
                PrintAndLog('  * AbsenceModeState: '+ state['value'])
            elif state['name'] == "modbuslink:MiddleWaterTemperatureState":
                PrintAndLog('  * Temperature: '+ str(state['value']))
            elif state['name'] == "core:ExpectedNumberOfShowerState":
                PrintAndLog('  * ExpectedNumberOfShower: '+ str(state['value']))
            elif state['name'] == "core:DateTimeState":
                PrintAndLog('  * Date:')
                PrintAndLog('      + Raw: '+ str(state['value']))
                distant_date = ParseDateTime(state['value'], now_date)
                if(distant_date):
                    date_error = distant_date - now_date
                    PrintAndLog('      + Date: '+ str(distant_date)+')')
                    PrintAndLog('      + Error from now: '+ str(date_error)+')')
                else:
                    PrintAndLog('      + Invalid date')
            elif state['name'] == "core:ControlWaterTargetTemperatureState":
                PrintAndLog('  * Target temperature: '+ str(state['value']))
            elif state['name'] == "core:HeatingStatusState":
                PrintAndLog('  * Heating: '+ str(state['value']))
            elif state['name'] == "core:AbsenceEndDateState":
                PrintAndLog('  * AbsenceEndDate:')
                PrintAndLog('      + Raw: '+ str(state['value']))
                PrintAndLog('      + Date: '+ str(ParseDateTime(state['value'], now_date)))
            elif state['name'] == "core:AbsenceStartDateState":
                PrintAndLog('  * AbsenceStartDate:')
                PrintAndLog('      + Raw: '+ str(state['value']))
                PrintAndLog('      + Date: '+ str(ParseDateTime(state['value'], now_date)))
            elif state['name'] == "modbuslink:MiddleWaterTemperatureState":
                PrintAndLog('  * Temperature 1: '+ str(state['value']))
            elif state['name'] == "core:MiddleWaterTemperatureInState":
                PrintAndLog('  * Temperature 2: '+ str(state['value']))
            elif state['name'] == "core:V40WaterVolumeEstimationState":
                PrintAndLog('  * V40WaterVolumeEstimation: '+ str(state['value']))
            elif state['name'] == "core:RemainingHotWaterState":
                PrintAndLog('  * core:RemainingHotWaterState: '+ str(state['value']))
            elif state['name'] == "core:NumberOfShowerRemainingState":
                PrintAndLog('  * NumberOfShowerRemainingState: '+ str(state['value']))

            #elif "Absence" in state['name']:
            #    PrintAndLog('  - '+ state['name']+': '+ str(state['value']))
            #elif "Temperature" in state['name']:
            #    PrintAndLog('  - '+ state['name']+': '+ str(state['value']))
            #elif "Heating" in state['name']:
            #    PrintAndLog('  - '+ state['name']+': '+ str(state['value']))

    #if updateDateIfNeeded:
    #    if abs(date_error) > timedelta(minutes=10):
    #        PrintAndLog('Date error too high, try to update date')
    #        if not CozyTouchCommand('setDateTime', FormatDateTime(datetime.now())):
    #            return False
    #        PrintDeviceStatus(False)
    
    return True

class AbsenceRange:
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __str__(self):
        return "(" + str(self.start) + ", " + str(self.end) + ")"

def TimeWithOffset(time, offset):
    date = datetime.combine(datetime.now().date(), time) + offset
    return date.time()

def GetNextAbsenceRange(current_datetime):
    current_time = current_datetime.time()
    next_absence_start_datetime = None
    next_absence_end_datetime = None

    for absence_range in config.absence_ranges:
        start_time = TimeWithOffset(dtime.fromisoformat(absence_range[0]) , timedelta(minutes = -config.absence_start_margin))

        absence_start_datetime = None

        if start_time >= current_time:
            # absence start the same day
            absence_start_datetime = datetime.combine(current_datetime.date(), start_time)
        else:
            absence_start_datetime = datetime.combine(current_datetime.date() + timedelta(days=1), start_time)

        if not next_absence_start_datetime or absence_start_datetime < next_absence_start_datetime:
            next_absence_start_datetime = absence_start_datetime

            end_time = TimeWithOffset(dtime.fromisoformat(absence_range[1]), timedelta(minutes = config.absence_end_margin))
            if end_time >= start_time:
                # absence end same day
                next_absence_end_datetime = datetime.combine(next_absence_start_datetime.date(), end_time)
            else:
                next_absence_end_datetime = datetime.combine(next_absence_start_datetime.date() + timedelta(days=1), end_time)

    return AbsenceRange(next_absence_start_datetime, next_absence_end_datetime)

def GetCurrentAbsenceRange(current_datetime):
    current_time = current_datetime.time()

    for absence_range in config.absence_ranges:
        start_time = TimeWithOffset(dtime.fromisoformat(absence_range[0]), timedelta(minutes = -config.absence_start_margin))

        absence_start_datetime = None
        absence_end_datetime = None

        if start_time >= current_time:
            # absence start the previous day, for example it's 17h and start is 22h, the potential current start at 22h yesterday
            absence_start_datetime = datetime.combine(current_datetime.date() - timedelta(days=1), start_time)
        else:
            # else the potential current start is today, for example it's 17h and the start is 14h
            absence_start_datetime = datetime.combine(current_datetime.date(), start_time)

        end_time = TimeWithOffset(dtime.fromisoformat(absence_range[1]), timedelta(minutes = config.absence_end_margin))
        if end_time >= start_time:
            # end the same day it start
            absence_end_datetime = datetime.combine(absence_start_datetime.date(), end_time)
        else:
            # end the next day it start
            absence_end_datetime = datetime.combine(absence_start_datetime.date() + timedelta(days=1), end_time)



        if current_datetime > absence_start_datetime and current_datetime < absence_end_datetime:
            PrintAndLog("Currently in range " + str(absence_range))
            #DEBUG return AbsenceRange(absence_start_datetime, current_datetime + timedelta(minutes=1 - config.absence_end_margin))
            return AbsenceRange(absence_start_datetime, absence_end_datetime)
        else:
            PrintAndLog("Currenlty not in range" + str(absence_range))
    return None


def ProgAbsence(absence_range):
    PrintAndLog("Program absence "+ absence_range.str())
    if not GetAtlanticToken():
        return False
    if not CozyTouchLogin():
        return False

    #CozyTouchCommand('refreshAbsenceMode', [])
    #CozyTouchCommand('refreshDateTime', [])

    dateError = GetDateError()

    if not CozyTouchCommand('setAbsenceStartDate', FormatDateTime(absence_range.start - timedelta(minutes = config.absence_start_margin) + dateError)):
        return False
    if not CozyTouchCommand('setAbsenceEndDate', FormatDateTime(absence_range.end + timedelta(minutes = config.absence_end_margin) + dateError)):
        return False

    PrintDeviceStatus()
    return True


def ProgOn():
    PrintAndLog("Program boiler on")
    if not GetAtlanticToken():
        return False
    if not CozyTouchLogin():
        return False

    current_datetime = datetime.now()
    dateError = GetDateError()

    if not CozyTouchCommand('setAbsenceStartDate', FormatDateTime(current_datetime + dateError - timedelta(days = 5*365))):
        return False
    if not CozyTouchCommand('setAbsenceEndDate', FormatDateTime(current_datetime + dateError - timedelta(days = 5 * 365))):
        return False

    PrintDeviceStatus()
    return True

def ProgOff():
    PrintAndLog("Program boiler off")
    if not GetAtlanticToken():
        return False
    if not CozyTouchLogin():
        return False

    current_datetime = datetime.now()
    dateError = GetDateError()

    if not CozyTouchCommand('setAbsenceStartDate', FormatDateTime(current_datetime + dateError - timedelta(days = 5 * 365))):
        return False
    if not CozyTouchCommand('setAbsenceEndDate', FormatDateTime(current_datetime + dateError + timedelta(days = 5 * 365))):
        return False

    PrintDeviceStatus()
    return True

def WaitForDateTime(target_datetime):
    current_datetime = datetime.now()
    while current_datetime < target_datetime:
        missing_time = target_datetime - current_datetime
        PrintAndLog("Wait for "+str(missing_time) + " to " + str(target_datetime))
        time.sleep(missing_time.total_seconds())
        current_datetime = datetime.now()

def Run():

    while not Status(): # To check if connection works
        PrintAndLog("Fail to get run initial status. Retry in 5 minutes")
        time.sleep(5*60) # Wait between retry

    while True:
        current_datetime = datetime.now()

        # Check if in Absence range and set the on/off state
        current_absence_range = GetCurrentAbsenceRange(current_datetime)
        next_absence_range = GetNextAbsenceRange(current_datetime)
        PrintAndLog("Current range is " + str(current_absence_range))
        PrintAndLog("Next range is " + str(next_absence_range))
        if current_absence_range:
            # Try to put off
            while current_absence_range.end > datetime.now():
                if not ProgOff():
                    PrintAndLog("Fail to program off. Retry in 5 minutes")
                    time.sleep(5*60) # Wait between retry
                else:
                    break
            WaitForDateTime(current_absence_range.end)

        else:
            # Try to put on
            while next_absence_range.start > datetime.now():
                if not ProgOn():
                    PrintAndLog("Fail to program on. Retry in 5 minutes")
                    time.sleep(5*60) # Wait between retry
                else:
                    break
            WaitForDateTime(next_absence_range.start)

def Status():
    if not GetAtlanticToken():
        return False
    if not CozyTouchLogin():
        return False
    if not PrintDeviceStatus():
        return False
    return True

ParseArguments()
LoadConfig()

PrintAndLog("==============")
PrintAndLog("Run command: "+ config.command)
PrintAndLog("--------------")

if config.loaded:
    if config.command == "scan":
        if not Scan():
            PrintAndLog("Fail to scan")
    elif config.command == "run":
        Run()
    elif config.command == "on":
        ProgOn()
    elif config.command == "off":
        ProgOff()
    elif config.command == "status":
        if not Status():
            PrintAndLog("Fail to get status")

PrintAndLog("--------------")
PrintAndLog("Command "+ config.command + " done")
PrintAndLog("==============")
