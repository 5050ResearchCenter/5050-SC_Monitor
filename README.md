# 直播间 SC 监听器

基于[blivedm](https://github.com/xfgryujk/blivedm/tree/dev)实时监控 **B站 5050 直播间** 的醒目留言，提取 BV 号并可一键跳转视频。

## 功能
- 实时显示 SC 的用户、金额、内容
- 自动提取消息中的 BV 号（点击即可跳转）
- 自动查询 BV 对应的视频标题和标签
- 使用 SQLite 持久化投稿人的昵称、投稿内容和金额，并在 BV 上悬浮显示累计次数和金额
- 可按配置中的标题/标签黑名单屏蔽投稿；命中后该条 SC 不再显示
- 使用 DeepSeek V4 Flash 思考模式从 SC 文本提取 Steam ID，并在 BV 列点击复制
- 已提取到 BV 号的 SC 会跳过 Steam ID 分析
- DeepSeek 请求最多 16 条并发，HTTP 429 时自动退避重试
- 启动时检查 DeepSeek API token；未填写或认证失败会弹出可关闭的模态警告
- 窗口置顶、清空记录、复制内容、定位上一条点击过的视频
- 支持自定义 SESSDATA（新版本原因或者直播间权限原因，5050不需要就能获取到用户名,故留存cookie配置）

## 快速开始
1. 安装依赖：`uv sync`
2. 获取 SESSDATA：
   - 在浏览器登录B站 → F12 → 应用 → Cookies → 找到 `SESSDATA` 复制
3. 创建配置文件：复制 `sc_config.example.json` 为 `sc_config.json`，填入你的 SESSDATA【可不填】和 `DPSK_API_TOKEN`
4. 运行：`python main.py`

PowerShell DEBUG 运行：`$env:DEBUG="on"; python main.py`。程序会按顺序循环内置的真实 SC 样例；填写 `DPSK_API_TOKEN` 后，每条样例都会经过 DeepSeek 分析。

## 配置
- 房间号、窗口大小等可在 `config.py` 中修改
- UI 颜色主题在 `config.py` 中统一管理
- `sc_config.json` 的 `黑名单关键词` 是字符串数组，匹配标题或任一标签时生效（不区分大小写）
- SC 历史保存在 `data/sc_monitor.sqlite3`

配置了黑名单时，包含 BV 的投稿会等待标题和标签检查完成后再显示，避免命中项在解析期间短暂闪现。

例如 `BV1NoNN6MEse` 的标题包含“啾比”、标签包含“鸣潮”；配置这两个关键词后，该条 SC 会被直接屏蔽，但仍保存在 SQLite 历史中并计入投稿统计。

## 打包
```bash
python build.py
```

输出文件名格式：`5050 SC 监听器 [版本号].exe`

