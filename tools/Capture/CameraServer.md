# CameraServer

手机拍照上传卷子。`0.0.0.0:8080`，手机浏览器打开 `http://192.168.0.111:8080`。

```bash
python tools/Capture/CameraServer.py
```

存到 `~/Documents/bio-error-data/data/inbox/`（已 gitignore）。

两行不能省：

- `MAX_CONTENT_LENGTH` —— 不设的话一次上传能把磁盘写满
- `secure_filename` —— `f.filename` 是客户端给的，里面能有 `../`，
  直接拼路径就是任意写文件
