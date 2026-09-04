from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import json, re, uuid

BASE = Path(__file__).resolve().parent
DB = BASE / 'database' / 'registros.json'
DB.parent.mkdir(exist_ok=True)
if not DB.exists(): DB.write_text('[]', encoding='utf-8')


def read_db():
    try:
        data=json.loads(DB.read_text(encoding='utf-8'))
        return data if isinstance(data,list) else []
    except Exception:
        return []

def write_db(data):
    tmp=DB.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(DB)

def clean(v): return str(v or '').strip()

def json_bytes(obj): return json.dumps(obj,ensure_ascii=False).encode('utf-8')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(BASE),**kwargs)
    def end_json(self,obj,status=200):
        b=json_bytes(obj); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Methods','GET,POST,DELETE,OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/': self.path='/templates/index.html'
        elif path=='/api/registros': return self.end_json(read_db())
        elif path.startswith('/api/registros/'):
            rid=path.rsplit('/',1)[-1]; item=next((x for x in read_db() if x.get('id')==rid),None)
            return self.end_json(item or {'ok':False,'message':'Registro no encontrado'}, 200 if item else 404)
        return super().do_GET()
    def do_POST(self):
        if urlparse(self.path).path!='/api/registros': return self.end_json({'ok':False,'message':'Ruta no encontrada'},404)
        try:
            n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception: return self.end_json({'ok':False,'message':'JSON inválido'},400)
        required=['tipoServicio','empresa','dni','nombres','apellidos','celular','codigoDispositivo','placa','contactos']
        missing=[k for k in required if not data.get(k)]
        if missing:return self.end_json({'ok':False,'message':'Faltan datos obligatorios','fields':missing},400)
        dni=re.sub(r'\D','',clean(data['dni'])); cel=re.sub(r'\D','',clean(data['celular']))
        if len(dni)!=8:return self.end_json({'ok':False,'message':'El DNI debe tener 8 dígitos'},400)
        if len(cel)!=9:return self.end_json({'ok':False,'message':'El celular debe tener 9 dígitos'},400)
        contactos=data.get('contactos')
        if not isinstance(contactos,list) or not 1<=len(contactos)<=3:return self.end_json({'ok':False,'message':'Debe registrar entre 1 y 3 contactos'},400)
        contacts=[]
        for c in contactos:
            nombre=clean(c.get('nombre')); tel=re.sub(r'\D','',clean(c.get('telefono')))
            if not nombre or not clean(c.get('parentesco')) or len(tel)!=9:return self.end_json({'ok':False,'message':'Datos de contacto incompletos'},400)
            contacts.append({'nombre':nombre,'parentesco':clean(c.get('parentesco')),'telefono':tel,'tipo':clean(c.get('tipo')) or 'Familiar'})
        item={'id':'ALC-'+datetime.now().strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:6].upper(),'fechaRegistro':datetime.now().isoformat(timespec='seconds'),'estado':'Registrado','tipoServicio':clean(data['tipoServicio']),'empresa':clean(data['empresa']),'conductor':{'dni':dni,'nombres':clean(data['nombres']),'apellidos':clean(data['apellidos']),'celular':cel},'vehiculo':{'placa':clean(data['placa']).upper(),'codigoDispositivo':clean(data['codigoDispositivo']).upper()},'dispositivo':{'estado':'Pendiente de conexión física','conectado':False},'contactos':contacts}
        db=read_db(); db.append(item); write_db(db); return self.end_json({'ok':True,'registro':item},201)
    def do_DELETE(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/registros/'): return self.end_json({'ok':False,'message':'Ruta no encontrada'},404)
        rid=path.rsplit('/',1)[-1]; db=read_db(); new=[x for x in db if x.get('id')!=rid]
        if len(new)==len(db): return self.end_json({'ok':False,'message':'Registro no encontrado'},404)
        write_db(new); return self.end_json({'ok':True})

if __name__=='__main__':
    print('AlcoLock disponible en http://127.0.0.1:5000')
    ThreadingHTTPServer(('0.0.0.0',5000),Handler).serve_forever()
