import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic
import ssl
import certifi
import os

os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context



# Permisos necesarios
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
]

def autenticar_gmail():
    creds = None
    
    # Si ya existe token guardado lo usa
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file(
            'token.json', SCOPES)
    
    # Si no hay credenciales válidas, solicita login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
         
      
        # Guarda el token para la próxima vez
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def leer_correos(servicio, filtro=None, max_correos=10):
    """Lee correos de Gmail con filtro opcional"""
    
    # Construir query de búsqueda
    query = filtro if filtro else ""
    
    # Obtener lista de correos
    resultado = servicio.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_correos
    ).execute()
    
    mensajes = resultado.get('messages', [])
    
    if not mensajes:
        return []
    
    correos = []
    for mensaje in mensajes:
        # Obtener detalle de cada correo
        msg = servicio.users().messages().get(
            userId='me',
            id=mensaje['id'],
            format='full'
        ).execute()
        
        # Extraer headers
        headers = msg['payload']['headers']
        asunto = next((h['value'] for h in headers 
                      if h['name'] == 'Subject'), 'Sin asunto')
        remitente = next((h['value'] for h in headers 
                         if h['name'] == 'From'), 'Desconocido')
        fecha = next((h['value'] for h in headers 
                     if h['name'] == 'Date'), 'Sin fecha')
        
        # Extraer cuerpo del correo
        cuerpo = ""
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    import base64
                    cuerpo = base64.urlsafe_b64decode(
                        part['body']['data']).decode('utf-8')
                    break
        
        correos.append({
            'asunto': asunto,
            'remitente': remitente,
            'fecha': fecha,
            'cuerpo': cuerpo[:500]  # primeros 500 chars
        })
    
    return correos

def analizar_con_claude(correos, pregunta):
    """Analiza los correos usando Claude API"""
    
    cliente = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)
    
    
    # Construir contexto con los correos
    contexto = "Correos encontrados:\n\n"
    for i, correo in enumerate(correos, 1):
        contexto += f"""
Correo {i}:
→ Asunto: {correo['asunto']}
→ De: {correo['remitente']}
→ Fecha: {correo['fecha']}
→ Contenido: {correo['cuerpo']}
{'─' * 40}
"""
    
    # RAG: contexto + pregunta → Claude
    prompt = f"""
{contexto}

Pregunta del usuario: {pregunta}

Analiza los correos anteriores y responde
la pregunta de forma clara y concisa.
"""
    
    respuesta = cliente.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return respuesta.content[0].text

def main():
    print("=== MCP Gmail + Claude ===\n")
    
    # Autenticar con Gmail
    print("Conectando con Gmail...")
    servicio = autenticar_gmail()
    print("✓ Conectado\n")
    
    while True:
        print("\n¿Qué quieres hacer?")
        print("1. Leer últimos correos")
        print("2. Filtrar correos por remitente")
        print("3. Filtrar correos por asunto")
        print("4. Analizar correos con IA")
        print("5. Salir")
        
        opcion = input("\nElige una opción: ")
        
        if opcion == "1":
            correos = leer_correos(servicio, max_correos=5)
            for c in correos:
                print(f"\n📧 {c['asunto']}")
                print(f"   De: {c['remitente']}")
                print(f"   Fecha: {c['fecha']}")
        
        elif opcion == "2":
            remitente = input("¿De qué remitente? ")
            correos = leer_correos(
                servicio, 
                filtro=f"from:{remitente}",
                max_correos=5
            )
            print(f"\nEncontré {len(correos)} correos")
            for c in correos:
                print(f"\n📧 {c['asunto']}")
                print(f"   Fecha: {c['fecha']}")
        
        elif opcion == "3":
            asunto = input("¿Qué asunto buscas? ")
            correos = leer_correos(
                servicio,
                filtro=f"subject:{asunto}",
                max_correos=5
            )
            print(f"\nEncontré {len(correos)} correos")
            for c in correos:
                print(f"\n📧 {c['asunto']}")
                print(f"   De: {c['remitente']}")
        
        elif opcion == "4":
            filtro = input("Filtro de correos (Enter para todos): ")
            pregunta = input("¿Qué quieres saber de estos correos? ")
            
            print("\nBuscando correos...")
            correos = leer_correos(
                servicio,
                filtro=filtro if filtro else None,
                max_correos=10
            )
            
            if not correos:
                print("No encontré correos con ese filtro")
                continue
            
            print(f"Encontré {len(correos)} correos")
            print("Analizando con Claude...\n")
            
            respuesta = analizar_con_claude(correos, pregunta)
            print(f"Claude dice:\n{respuesta}")
        
        elif opcion == "5":
            print("¡Hasta luego!")
            break

if __name__ == "__main__":
    main()
