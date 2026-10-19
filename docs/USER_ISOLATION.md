# 用户登录与文件隔离

内置账户 `chenbo` / `chenbo`、`chenshuai` / `chenshuai`（用户名 / 初始密码）。无数据库、无注册流程。

首次启动时，旧聊天、录音、图片、提示词、背景、题库、实验结果、配置和日志复制到 chenbo。旧文件保留，不再作为运行时数据源。chenshuai 不继承任何旧内容、模型选择或 API Key。已存在的用户目录永不自动覆盖；迁移先写临时目录，全部完成才重命名。

```text
data/users/
  chenbo/                       # chenshuai 使用相同的独立目录结构
    account.json                # PBKDF2 加盐密码摘要
    settings.json               # 模型、密钥、ASR、音频、快捷键、上下文等配置
    sessions_index.json
    storage/YYYY/MM/*.json      # 会话及其配置、提示词快照
    voices/
    screenshots/<session-id>/
    prompt_scenes.json
    prompt_lab/
      prompts.json
      background.json
      questions.json
      data/runs/
      data/prompt_history/
    logs/
```

## 边界与职责

- `backend/auth/bootstrap.py`：首次创建账户与迁移。旧 `config.py` / `.env.local` 仅在首次迁移 chenbo 时读取。chenshuai 从代码定义的无凭据默认配置创建。
- `backend/auth/session.py`：密码校验、HttpOnly/SameSite Cookie、登录/退出接口、统一 ASGI 鉴权。所有 `/api` HTTP、SSE、WebSocket 均要求登录，仅登录接口公开。API 响应禁止缓存。
- `backend/services/user_workspace.py`：唯一用户上下文入口。认证后的用户名决定目录，客户端不能指定目录。缺少认证上下文时直接报错，绝不回退共享数据。每人拥有独立的配置、当前会话、录音实例、生成状态、实验任务和锁。
- 业务服务通过 `user_state()`、`user_config()`、`user_path()` 访问当前用户。ContextVar 的生命周期覆盖完整流式响应；后台任务和 `asyncio.to_thread` 保留创建者的上下文。音频采集实例保留自己的文件目录和日志器。
- 前端仅在确认登录后挂载业务页面。布局、设备和多模型显示偏好以 `voice:<用户名>:` 命名空间保存。旧浏览器偏好只迁移给 chenbo。请求及图片/语音连接携带页面身份用于检测旧标签页，服务端仍以 Cookie 身份为准。

“共享背景”现在指**同一个用户的多个会话之间共享**，不跨用户共享。相同默认代码或内置输出协议不属于可变用户资料；用户的提示词模板、场景、背景和会话配置均独立持久化。

## 配置和运行

模型配置仍通过原有设置界面修改，保存到当前用户的 `settings.json`，不再改写源码或公共环境变量。原先没有界面的配置（例如 `SONIOX_CONFIG`、`VOLCENGINE_CONFIG`、`DOUBAO_REALTIME`、`NOISE_REDUCTION`、`DEFAULT_SESSION_CONFIG`）在各自的 `settings.json` 编辑后重启服务生效。`DOUBAO_REALTIME` 的字段为 `app_id` 和 `access_token`。

使用原来的 `./start.sh` 启动。此简单实现采用单个后端进程，登录会话存在内存中，最长七天；重启后需要重新登录。不要配置多个 Uvicorn worker。退出或切换账户会清理当前账户的录音；切换时完整刷新页面并通知其他标签页清理旧状态。同一个浏览器 Cookie 环境使用一个登录账户，要同时使用两个账户请用不同浏览器或独立浏览器配置。

前端浏览器偏好仍保存在该浏览器，已按用户分区；其余用户可变数据保存在上述目录。监听端口、HTTPS 证书、应用代码、依赖和 tokenizer 缓存属于服务设施，不是用户配置。

## 验证

```sh
.venv/bin/python -m unittest discover -s backend/test -p 'test_*.py'
node --test frontend/test/*.test.js
cd frontend && npm run build
```

`test_user_isolation.py` 在临时目录验证未登录访问、身份伪造、跨用户会话和附件、提示词/配置/背景/实验结果、迁移幂等、路径穿越、退出失效，以及并发 SSE、后台任务和线程的用户归属。测试不调用真实模型服务。

## 显式同步已有账号配置

管理员需要让已有账号使用相同的服务凭据和模型时，可先停止后端，再运行：

```sh
python scripts/sync_user_settings.py --source /secure/settings.json --users-root data/users --backup-root /secure/settings-backups
```

源文件使用已配置账号的 `settings.json`，通过 SSH 等私密渠道传输，不提交 Git。脚本先备份所有账号的原配置，再同步完整服务设置，重建当前模型的 `api_config`，不修改密码、会话、提示词及个人背景。同步后重启后端，使内存缓存重新加载；用户需要重新登录。没有私人提示词模板时，新会话也会使用已配置的默认模型。此操作仅影响当前已有账号，不改变新账号的空配置策略。
