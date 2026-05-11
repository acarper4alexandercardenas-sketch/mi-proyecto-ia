import asyncio
import json
import os
import ssl
import sys
import base64
import httplib2
import google_auth_httplib2
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Fix certificado corporativo (ssl estándar + httplib2)
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
]

def extraer_cuerpo(payload):
    """Extrae el texto plano del cuerpo del mensaje."""
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    if payload.get('mimeType') == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            texto = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            # Eliminar tags HTML básicos
            import re
            texto = re.sub(r'<[^>]+>', ' ', texto)
            texto = re.sub(r'\s+', ' ', texto).strip()
            return texto
    for part in payload.get('parts', []):
        resultado = extraer_cuerpo(part)
        if resultado:
            return resultado
    return '(sin contenido)'

def get_gmail_service():
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
    return build('gmail', 'v1', http=authorized_http)

def leer_correos(filtro=None, max_correos=5):
    servicio = get_gmail_service()
    query = filtro if filtro else ""

    resultado = servicio.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_correos
    ).execute()

    mensajes = resultado.get('messages', [])
    correos = []

    for mensaje in mensajes:
        msg = servicio.users().messages().get(
            userId='me',
            id=mensaje['id'],
            format='full'
        ).execute()

        headers = msg['payload']['headers']
        asunto = next((h['value'] for h in headers
                      if h['name'] == 'Subject'), 'Sin asunto')
        remitente = next((h['value'] for h in headers
                         if h['name'] == 'From'), 'Desconocido')
        fecha = next((h['value'] for h in headers
                     if h['name'] == 'Date'), 'Sin fecha')

        cuerpo = extraer_cuerpo(msg['payload'])

        correos.append({
            'id': mensaje['id'],
            'asunto': asunto,
            'remitente': remitente,
            'fecha': fecha,
            'cuerpo': cuerpo
        })

    return correos

def eliminar_correos(filtro, max_correos=10, permanente=False):
    servicio = get_gmail_service()

    resultado = servicio.users().messages().list(
        userId='me',
        q=filtro,
        maxResults=max_correos
    ).execute()

    mensajes = resultado.get('messages', [])
    if not mensajes:
        return 0, []

    eliminados = []
    for mensaje in mensajes:
        msg = servicio.users().messages().get(
            userId='me',
            id=mensaje['id'],
            format='metadata',
            metadataHeaders=['Subject', 'From']
        ).execute()

        headers = msg['payload']['headers']
        asunto = next((h['value'] for h in headers
                      if h['name'] == 'Subject'), 'Sin asunto')

        if permanente:
            servicio.users().messages().delete(
                userId='me', id=mensaje['id']
            ).execute()
        else:
            servicio.users().messages().trash(
                userId='me', id=mensaje['id']
            ).execute()

        eliminados.append(asunto)

    return len(eliminados), eliminados

# Crear servidor MCP
app = Server("gmail-mcp")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="leer_correos_gmail",
            description="Lee correos de Gmail con filtro opcional",
            inputSchema={
                "type": "object",
                "properties": {
                    "filtro": {
                        "type": "string",
                        "description": "Filtro de búsqueda (remitente, asunto, etc)"
                    },
                    "max_correos": {
                        "type": "integer",
                        "description": "Número máximo de correos a leer",
                        "default": 5
                    }
                }
            }
        ),
        Tool(
            name="eliminar_correos_gmail",
            description="Mueve correos a la papelera (o los elimina permanentemente) según un filtro de búsqueda",
            inputSchema={
                "type": "object",
                "required": ["filtro"],
                "properties": {
                    "filtro": {
                        "type": "string",
                        "description": "Filtro de búsqueda para seleccionar los correos a eliminar (ej: 'category:promotions', 'from:samsung')"
                    },
                    "max_correos": {
                        "type": "integer",
                        "description": "Número máximo de correos a eliminar",
                        "default": 10
                    },
                    "permanente": {
                        "type": "boolean",
                        "description": "Si es true elimina permanentemente; si es false mueve a la papelera (default: false)",
                        "default": False
                    }
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "leer_correos_gmail":
        filtro = arguments.get("filtro", None)
        max_correos = arguments.get("max_correos", 5)

        correos = leer_correos(filtro, max_correos)

        resultado = f"Encontré {len(correos)} correos:\n\n"
        for i, c in enumerate(correos, 1):
            resultado += f"{i}. {c['asunto']}\n"
            resultado += f"   De: {c['remitente']}\n"
            resultado += f"   Fecha: {c['fecha']}\n"
            resultado += f"   Contenido: {c['cuerpo'][:500]}{'...' if len(c['cuerpo']) > 500 else ''}\n\n"

        return [TextContent(type="text", text=resultado)]

    if name == "eliminar_correos_gmail":
        filtro = arguments.get("filtro")
        max_correos = arguments.get("max_correos", 10)
        permanente = arguments.get("permanente", False)

        cantidad, asuntos = eliminar_correos(filtro, max_correos, permanente)

        accion = "eliminados permanentemente" if permanente else "movidos a la papelera"
        resultado = f"{cantidad} correos {accion}:\n\n"
        for i, asunto in enumerate(asuntos, 1):
            resultado += f"{i}. {asunto}\n"

        return [TextContent(type="text", text=resultado)]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream,
                     app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
