# CameraServer

手机拍照上传卷子。`0.0.0.0:8080`。

```bash
python tools/Capture/CameraServer.py
```

启动后终端会打印手机要访问的地址，存到 `~/Documents/bio-error-data/data/inbox/`（已 gitignore）。

用的是 `<input type="file" accept="image/*">`，**不加 `capture` 属性**——手机上点开是菜单（拍照 / 照片图库 / 浏览），两种都行。
加了 `capture="environment"` 后 Android 会强制只开相机，拍完想选图库里的就不行了。

不用 HTTPS：调的是系统相机，页面只是文件选择器，不碰 `getUserMedia`。

两行不能省：

- `MAX_CONTENT_LENGTH` —— 不设的话一次上传能把磁盘写满
- `secure_filename` —— `f.filename` 是客户端给的，里面能有 `../`，直接拼路径就是任意写文件

`__main__` 里 pop 掉 `WERKZEUG_RUN_MAIN` / `WERKZEUG_SERVER_FD`：这两个是热重载器残留，带着它们启动会报 `WinError 10038`。
