from flask import Flask, request
from datetime import datetime
from werkzeug.utils import secure_filename
import os

OUT = os.path.expanduser(r"~/Documents/bio-error-data/data/inbox")

app = Flask(__name__)
# 这行不能省：不设的话一次上传能把磁盘写满
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

HTML = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>拍卷子</title>
<form method=post enctype=multipart/form-data action=/upload>
<input type=file name=photo accept=image/* required>
<button>上传</button>
</form>"""


@app.get("/")
def index():
    return HTML


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
    os.makedirs(OUT, exist_ok=True)
    app.run(host="0.0.0.0", port=8080)
