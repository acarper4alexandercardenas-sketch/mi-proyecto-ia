import os
import ssl

# Deshabilitar SSL antes de importar cualquier librería de red
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
ssl._create_default_https_context = ssl._create_unverified_context

import requests
import urllib3
urllib3.disable_warnings()

# Monkey-patch requests para deshabilitar verificación SSL globalmente
import requests.sessions
_original_request = requests.sessions.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_request(self, method, url, **kwargs)
requests.sessions.Session.request = _patched_request

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
]

if os.path.exists('token.json'):
    os.remove('token.json')
    print("Token anterior eliminado.")

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=8080, open_browser=True)

with open('token.json', 'w') as token:
    token.write(creds.to_json())

print("Nuevo token guardado con permisos de lectura y modificación.")
