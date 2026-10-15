from flask import Flask, request
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import socket

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.expanduser(r"~/Documents/bio-error-data/data/inbox")
TLS = os.path.join(HERE, "_tls")

app = Flask(__name__)
# 这行不能省：不设的话一次上传能把磁盘写满
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>拍卷子</title>
<style>
body{margin:0;font:16px system-ui;background:#111;color:#eee;
     display:flex;flex-direction:column;height:100vh}
#v{width:100%;flex:1;object-fit:contain;background:#000}
#pad{padding:10px 12px calc(12px + env(safe-area-inset-bottom));display:flex;gap:10px}
button{flex:1;padding:16px;font-size:18px;border:0;border-radius:10px;
       background:#2b6cff;color:#fff}
button:disabled{background:#334}
#file{width:100%;padding:12px;box-sizing:border-box}
#msg{padding:10px 12px;background:#1a1a1a;font-size:14px;color:#9cf;min-height:38px}
</style>
<div id=msg>点「开启相机」——需允许摄像头权限</div>
<video id=v autoplay playsinline muted></video>
<div id=pad>
  <button id=cam>开启相机</button>
  <button id=shot disabled>拍照</button>
</div>
<input id=file type=file accept=image/* capture=environment style="display:none">
<script>
const v=document.getElementById('v'),msg=document.getElementById('msg');
const cam=document.getElementById('cam'),shot=document.getElementById('shot');
let stream=null;
const say=t=>msg.textContent=t;

// 相机不可用时（无安全上下文 / 拒绝授权 / 没摄像头）自动露出相册兜底
const fallback=t=>{say(t);document.getElementById('file').style.display='block'};

cam.onclick=async()=>{
  try{
    stream=await navigator.mediaDevices.getUserMedia(
      {video:{facingMode:{ideal:'environment'}}});
    v.srcObject=stream;shot.disabled=false;cam.textContent='相机已开';
    say('对准卷子，点「拍照」');
  }catch(e){fallback('相机不可用（'+e.name+'），改用下面相册上传')}
};

shot.onclick=()=>{
  if(!stream||!v.videoWidth)return;
  const c=document.createElement('canvas');
  c.width=v.videoWidth;c.height=v.videoHeight;
  c.getContext('2d').drawImage(v,0,0);
  c.toBlob(b=>send(b,'image/jpeg'),'image/jpeg',0.9);
  say('上传中…');
};

document.getElementById('file').onchange=function(){
  if(this.files[0]){send(this.files[0],this.files[0].name);say('上传中…')}
};

async function send(blob,name){
  const fd=new FormData();fd.append('photo',blob,name||'photo.jpg');
  try{
    const r=await fetch('/upload',{method:'POST',body:fd});
    say(await r.text());
  }catch(e){say('上传失败：'+e.message)}
}
</script>"""


def lan_ip():
    """取本机局域网 IP，写进证书 SAN，可以少一层证书警告。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ssl_context():
    """自签证书：生成一次落盘，之后复用。

    每次现生成会让手机每次重连都重新弹证书警告。
    """
    cert = os.path.join(TLS, "cert.pem")
    key = os.path.join(TLS, "key.pem")
    # 判存在还不够：生成过程中失败会留下 0 字节的半成品，
    # 那样 ssl.load_cert_chain 报的是看不懂的「PEM lib」错误
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in (cert, key)):
        return cert, key

    import datetime as dt
    import ipaddress
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    ip = lan_ip()
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    now = dt.datetime.now(dt.timezone.utc)
    cert_obj = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(priv.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address(ip)),
            ]),
            critical=False,
        )
        .sign(priv, hashes.SHA256())
    )

    os.makedirs(TLS, exist_ok=True)
    with open(cert, "wb") as fh:
        fh.write(cert_obj.public_bytes(serialization.Encoding.PEM))
    with open(key, "wb") as fh:
        fh.write(
            priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    return cert, key


@app.get("/")
def index():
    return PAGE


@app.post("/upload")
def upload():
    f = request.files["photo"]
    # secure_filename 不能省：f.filename 是客户端给的，里面能有 ../，
    # 直接拼路径就是任意写文件
    name = datetime.now().strftime("%Y%m%d-%H%M%S-") + secure_filename(f.filename)
    path = os.path.join(OUT, name)
    f.save(path)
    return "saved: " + path


if __name__ == "__main__":
    # 这两个是 Werkzeug 热重载器的残留。带着它们启动会让 app.run()
    # 误判成「正在从 reloader 启动」，去 dup 一个早已死掉的 socket 句柄，
    # 报 OSError: [WinError 10038] 操作试图套接字但不是套接字。
    # 它们只存在于进程环境（不在用户级/系统级），换个终端可能就没了——
    # 所以在脚本里自己清掉，而不是指望启动环境干净。
    os.environ.pop("WERKZEUG_RUN_MAIN", None)
    os.environ.pop("WERKZEUG_SERVER_FD", None)
    os.makedirs(OUT, exist_ok=True)
    ctx = ssl_context()
    print("camera: https://%s:8080" % lan_ip())
    app.run(host="0.0.0.0", port=8080, ssl_context=ctx)
