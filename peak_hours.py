#!/usr/bin/python3
import urllib.request
import json

atlantic_url=u'https://api.groupe-atlantic.com/'

login = "myemail@gmail.com"
password = "mypassword"

def GetToken():
    url = atlantic_url + "token"
    print(url)
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', 'Basic czduc0RZZXdWbjVGbVV4UmlYN1pVSUM3ZFI4YTphSDEzOXZmbzA1ZGdqeDJkSFVSQkFTbmhCRW9h')
    body  = {
        'grant_type':'password',
        'username':login,
        'password':password
    }
    data = urllib.parse.urlencode(body).encode("utf-8")
    raw_response = ""
    try:
        raw_response = urllib.request.urlopen(req, data)
    except urllib.error.HTTPError as err:
        print('error' + str(err))
        print(err.read().decode())

    response = json.loads(raw_response.read().decode(raw_response.info().get_param('charset') or 'utf-8'))

    print(response)

GetToken()