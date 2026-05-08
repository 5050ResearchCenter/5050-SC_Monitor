# 直播间 SC 监听器

基于[blivedm](https://github.com/xfgryujk/blivedm/tree/dev){target="_blank"}实时监控 **B站 5050 直播间** 的醒目留言，提取 BV 号并可一键跳转视频。

## 功能
- 实时显示 SC 的用户、金额、内容
- 自动提取消息中的 BV 号（点击即可跳转）
- 窗口置顶、清空记录、复制内容、定位上一条点击过的视频
- 支持自定义 SESSDATA（新版本原因或者直播间权限原因，5050不需要就能获取到用户名,故留存cookie配置）

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. blivedm需要自行安装最新分支版本。pip install  git+https://github.com/xfgryujk/blivedm.git@dev
2. 获取 SESSDATA：
   - 在浏览器登录B站 → F12 → 应用 → Cookies → 找到 `SESSDATA` 复制
3. 创建配置文件：复制 `sc_config.example.json` 为 `sc_config.json`，填入你的 SESSDATA【可不填】
4. 运行：`python main.py`

## 配置
- 房间号、窗口大小等可在 `config.py` 中修改
- UI 颜色主题在 `config.py` 中统一管理

## 打包
```bash
pyinstaller --onefile --windowed --add-data "resources/favicon.ico;resources" main.py
