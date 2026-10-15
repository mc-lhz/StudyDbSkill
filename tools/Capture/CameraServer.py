from flask import Flask, request
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import socket
import shutil

OUT = os.path.expanduser(r"~/Documents/bio-error-data/data/inbox")

app = Flask(__name__)
# 上传大小不设上限（按要求）。
# 只在「磁盘真的快满了」时拦一下，避免写满盘影响系统和 cpolar；
# 这不是文件大小限制，想连它一起去掉就删掉 _disk_ok 及其调用。
app.config["MAX_CONTENT_LENGTH"] = None

# 上传前至少给磁盘留这么多余量
DISK_RESERVE = 200 * 1024 * 1024

# 不加 capture 属性：手机上点开是菜单（拍照 / 照片图库 / 浏览），两种都行。
# 加了 capture="environment" 后 Android 会强制只开相机，拍完想选图库里的就不行了。
PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>拍卷子</title>
<style>
body{margin:0;padding:14px;font:16px system-ui;background:#111;color:#ddd;
     -webkit-text-size-adjust:100%;text-size-adjust:100%}
#msg{padding:7px 9px;background:#1a1a1a;border-radius:7px;color:#9cf;
     font-size:13px;word-break:break-all;margin-bottom:10px;min-height:32px}
/* iOS Safari：input/select/textarea 字号 <16px 时，聚焦会把整页放大。
   布局可以紧凑，但这个必须 16px，否则用户每次点它页面都跳一下。 */
#file{font-size:16px;padding:7px;border-radius:7px;background:#222;color:#eee;
      border:1px solid #444;width:100%;box-sizing:border-box}
button{margin-top:8px;padding:8px 12px;font-size:16px;border:0;
       border-radius:7px;background:#2b6cff;color:#fff}
</style>
<div id=msg>选一张或多张上传</div>
<input id=file type=file accept=image/* multiple onchange="up(this)">
<button onclick="location.reload()">再传一批</button>
<script>
// 卷子照片不需要 1200 万像素——长边压到 2000px 重编码成 JPEG，
// 体积通常降到十分之一，多选也不会撞 413
const MAX=2000;

async function shrink(file){
  const bmp=await createImageBitmap(file,{imageOrientation:'from-image'});
  const sc=Math.min(1,MAX/Math.max(bmp.width,bmp.height));
  const c=document.createElement('canvas');
  c.width=Math.round(bmp.width*sc); c.height=Math.round(bmp.height*sc);
  c.getContext('2d').drawImage(bmp,0,0,c.width,c.height);
  const blob=await new Promise(r=>c.toBlob(r,'image/jpeg',0.85));
  return blob||file;
}

async function up(el){
  const fs=[...el.files]; if(!fs.length) return;
  const m=document.getElementById('msg');
  m.textContent='压缩中… '+fs.length+' 张';
  const fd=new FormData();
  let before=0,after=0;
  for(const f of fs){
    before+=f.size;
    let b;
    try{b=await shrink(f)}catch(e){b=f}   // 压缩不了就传原图
    after+=b.size;
    const n=f.name.replace(/\.\w+$/,'')+'.jpg';
    fd.append('photo',b,n);
  }
  m.textContent='上传中… '+Math.round(before/1048576)+'MB → '+Math.round(after/1048576)+'MB';
  try{
    const r=await fetch('/upload',{method:'POST',body:fd});
    m.textContent=await r.text();
  }catch(e){m.textContent='上传失败：'+e.message}
}
</script>"""


@app.errorhandler(413)
def too_large(_):
    return "上传被拒。", 413


@app.get("/")
def index():
    return PAGE


def disk_ok(nbytes):
    return nbytes <= shutil.disk_usage(OUT).free - DISK_RESERVE


@app.post("/upload")
def upload():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    items = request.files.getlist("photo")

    incoming = sum(f.content_length or 0 for f in items if f.filename)
    if incoming and not disk_ok(incoming):
        return "磁盘空间不足：剩余 %.1f GB，本次需要 %.1f GB。" % (
            shutil.disk_usage(OUT).free / 2**30,
            incoming / 2**30,
        )

    saved, skipped = [], 0
    for i, f in enumerate(items, 1):
        # 没有 filename 的是空表单字段，不是文件。不静默吞掉，要计数报出来
        if not f.filename:
            skipped += 1
            continue
        # secure_filename 不能省：f.filename 是客户端给的，里面能有 ../，
        # 直接拼路径就是任意写文件。
        # 序号是为了同一次多选里同名文件不互相覆盖
        name = "%s-%02d-%s" % (stamp, i, secure_filename(f.filename))
        f.save(os.path.join(OUT, name))
        saved.append(name)
    if not saved:
        return "没有收到文件（收到 %d 个空字段）。浏览器上传正常；curl 传非 ASCII 文件名会失败。" % skipped
    msg = "saved %d: %s" % (len(saved), ", ".join(saved))
    if skipped:
        msg += "（跳过 %d 个空字段）" % skipped
    return msg


if __name__ == "__main__":
    # 这两个是 Werkzeug 热重载器的残留。带着它们启动会让 app.run()
    # 误判成「正在从 reloader 启动」，去 dup 一个早已死掉的 socket 句柄，
    # 报 OSError: [WinError 10038] 操作试图套接字但不是套接字。
    # 它们只存在于进程环境（不在用户级/系统级），换个终端可能就没了——
    # 所以在脚本里自己清掉，而不是指望启动环境干净。
    os.environ.pop("WERKZEUG_RUN_MAIN", None)
    os.environ.pop("WERKZEUG_SERVER_FD", None)
    os.makedirs(OUT, exist_ok=True)
    print("upload: http://%s:8080" % socket.gethostbyname(socket.gethostname()))
    app.run(host="0.0.0.0", port=8080)
