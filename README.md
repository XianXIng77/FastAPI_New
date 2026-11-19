# FastAPI 项目架构说明文档

本项目采用面向中大型工程的**分层架构**（对标 Spring Boot / MyBatis 经典分层思想），实现接口协议、业务逻辑、数据访问与底层基础设施的清晰解耦。

目前已定义 `users`、`auth_sessions` 和 `refresh_tokens` 三个模型，并实现注册、登录、访问令牌鉴权、刷新轮换和退出。AT 原文不入库，不需要单独的表。

`auth_sessions` 记录每次登录属于哪个用户、会话最长有效期和撤销时间。`refresh_tokens` 只存令牌的 SHA-256 摘要，用 `session_id` 归属会话；轮换后保留旧摘要和 `consumed_at`，供后续检测重用。

---

## 一、整体请求调用链路

```text
前端 HTTP 请求
   │
   ▼  全局中间件 / 全局异常脱敏 (core/)
api/           ──► Controller 控制层：定义路由、通过 api/deps.py 注入 Session 或校验登录态、返回 HTTP 状态码
   │  传入入参 DTO (schemas/)
   ▼
services/      ──► Service 业务逻辑层：编排业务流程、线程池算密码哈希、统一开启/提交/回滚事务
   │  传入基础字段参数
   ▼
repositories/  ──► Mapper / 仓库层：纯 SQL 组装与执行，不写业务判断，不私自 commit
   │  读写 ORM 实体 (models/)
   ▼
db/            ──► 连接池与会话底座：提供全局连接池、每次请求独立创建 Session、统一登记表模型
   │
   ▼
PostgreSQL 数据库  ◄── 表结构由 models/ 定义，通过 alembic/ 自动生成迁移脚本并建表
```

---

## 二、根目录文件夹职责速查表

### 1. 日常写业务层（新增功能时按顺序改这 5 个目录）

| 目录 | 定位 | 对标 Spring Boot 概念 | 核心职责与代表文件 |
| :--- | :--- | :--- | :--- |
| **`models/`** | 数据库实体层 | `Entity` / `PO` | 定义数据库表结构、主键、唯一索引。新建模型后在 `models/__init__.py` 导入，让 Alembic 能发现它。 |
| **`schemas/`** | 数据契约层 | `DTO` + `VO` | 基于 Pydantic 校验前端入参（如 `UserCreate` 当 DTO）、过滤返回给前端的字段（如 `UserRead` 当 VO，屏蔽密码哈希）。 |
| **`repositories/`** | 数据仓库层 | `Mapper` / `DAO` | 专门写 SQL（SQLAlchemy 链式表达式或原生 SQL），只管存取数据，不写业务规则，不手动提交事务。 |
| **`services/`** | 业务逻辑层 | `Service` (`@Transactional`) | 串联业务步骤（密码加密、多表操作组合）、通过 `async with session.begin():` 统一控制事务边界、抛出业务异常。 |
| **`api/`** | 接口路由层 | `Controller` + 权限门卫 | `api/routes/` 放接口路由；`api/deps.py` 提供数据库会话依赖 `SessionDep`。 |

### 2. 底座支撑层（搭好后日常很少改动）

| 目录 | 定位 | 核心职责与代表文件 |
| :--- | :--- | :--- |
| **`core/`** | 框架内核底座 | **不含任何具体业务代码**（换个新项目也能直接搬走复用）。负责：<br>• `config.py`：读取 `.env` 环境变量与全局配置<br>• `security.py`：密码 Argon2 哈希、JWT 签发与解码等底层安全算法<br>• `exception_handlers.py`：全局异常拦截兜底（如 422 校验错误隐藏敏感输入）<br>• 后续可扩展：`exceptions.py`（全局业务异常基类）、`logging.py`（全局日志）、`middlewares.py`（全站耗时/跨域/`Request-ID`） |
| **`db/`** | 数据库基础设施 | • `session.py`：配置连接池参数（`async_engine`）与会话生产工厂（`AsyncSessionLocal`），每次请求独立生成并归还 `Session`<br>• `base.py`：所有模型继承的公共父类 `Base`，用于登记表结构；目前未启用公共时间字段。 |
| **`utils/`** | 通用工具箱 | 存放与业务、框架配置完全无关的**纯无状态工具函数**（如日期转换、字符串脱敏、随机码生成，单独拷走也能直接运行）。 |

### 3. 工程配套与其他目录

| 目录 | 定位 | 说明 |
| :--- | :--- | :--- |
| **`alembic/`** | 数据库版本迁移 | 相当于 Flyway。自动扫描 `models/` 的变更生成迁移脚本（存于 `alembic/versions/`），执行命令即可在数据库自动建表/改表，日常无需手写。 |
| **`tests/`** | 自动化测试 | 提供 `pytest` + 内存数据库测试夹具，供新增接口后编写测试时使用。 |

---

### 4. 接口响应约定

- **业务接口**：在路由声明 `response_model=ApiResponse[数据类型]`，用 `ApiResponse[数据类型].success(data)` 返回 `code`、`msg` 和 `data`。业务码不替代 HTTP 状态码，现有异常响应保持不变。
- **注册**：`POST /auth/register` 接收 JSON：`email`、`username`、`password`（15–128 字符）。HTTP `201`，统一响应的 `data` 返回账号资料，不返回密码；邮箱或用户名重复返回 `409`。
- **登录**：`POST /auth/login` 接收 JSON：`email`、`password`。成功时从统一响应的 `data` 读取 `access_token`、`refresh_token`、`token_type` 和 `expires_in`，无效凭据统一返回 `401`。
- **当前用户**：`GET /auth/me` 接收请求头 `Authorization: Bearer <access_token>`，先校验 JWT，再到 Redis 检查会话，最后查库读取当前仍启用的用户资料。成功时 `data` 返回 `id`、`email` 和 `username`；缺少令牌、令牌或会话过期、会话已撤销、账号停用均返回 `401`。刷新令牌不能用来访问这个接口。
- **刷新**：`POST /auth/refresh` 接收 JSON：`{"refresh_token":"<refresh_token>"}`，不需要 Access Token。成功时用 `data` 里的两枚新令牌替换本地旧值。刷新不会延长会话的最长有效期，也不会立即撤销旧 Access Token；重用已消费的 Refresh Token 会撤销其整个会话，使该会话的所有令牌失效。客户端应避免并发刷新或用同一枚旧令牌自动重试，收到 `401` 后重新登录。
- **退出**：`POST /auth/logout` 携带尚未过期的 Access Token，无需请求体。成功时返回统一响应，`data` 为 `null`。后端撤销当前会话，此会话的所有 Access Token 和 Refresh Token 都失效，其他设备的会话不受影响。用同一枚尚未过期的 JWT 重复退出也返回 `200`；客户端收到成功响应后清除本地令牌。

联调前先在空的开发库完成下文的建表流程，再用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成签名密钥，将输出填入本地 `.env` 的 `JWT_SECRET_KEY`，不要提交或分享。默认 Access Token 有效期 15 分钟、Refresh Token 7 天、会话最长 30 天。当前接口以 JSON 返回双令牌用于 API 联调；接入网页时不要把令牌存入 `localStorage`。

在 `/docs` 测试时，先注册和登录，再把 `data.access_token` 粘贴到 **Authorize**（不加 `Bearer` 前缀），执行 `GET /auth/me`。然后调用刷新接口，用返回的新 Access Token 更新 **Authorize**，再执行 `POST /auth/logout`。退出后用该会话的 Access Token 请求 `/auth/me`，或用其 Refresh Token 请求 `/auth/refresh`，均应返回 `401`。其他需要登录的接口可以声明 `current_user: CurrentUserDep` 复用同一套校验。

打开 [认证测试页](http://127.0.0.1:8000/ui/) 也可以联调这五个接口。登录和刷新会更新页面内存中的令牌；退出后可点「验证退出失效」，检查旧 Access Token 和 Refresh Token 是否都返回 401。请使用测试账号；刷新页面只清除本地令牌，不撤销服务端会话。

请通过 FastAPI 的 `/ui/` 打开测试页，不要直接用 IDE 的静态预览作为接口地址。PyCharm 默认 `63342` 端口的预览会自动跳转到 `http://127.0.0.1:8000/ui/`；如果启动时指定了其他端口，请直接访问那个端口的 `/ui/`。

## 三、核心边界防混淆备忘

1. **`schemas/` vs `models/`**
   - `schemas/` 管 **HTTP 接口收发 JSON 长什么样**（面向前端）；
   - `models/` 管 **数据库表长什么样**（面向 PostgreSQL）。
2. **`core/` vs `utils/`**
   - 需要读 `.env` 配置密钥、依赖 FastAPI 框架或管全局生命周期的底座代码 👉 放 **`core/`**（注意：`core/` 绝不能反向 `import` 业务表或业务模块）；
   - 不依赖任何项目配置、拷到别的脚本里一行不改就能跑的纯小工具 👉 放 **`utils/`**。
3. **全局拦截 vs 登录 Token 拦截**
   - **100% 请求无差别经过的逻辑**（全局异常兜底、请求日志与耗时、CORS 跨域） 👉 做成全局处理放 **`core/`**，注册到 `main.py`；
   - **接口登录态 / 权限校验** 👉 签发与验签算法放 **`core/security.py`**，提取请求头拦截动作写成 `Depends` 放在 **`api/deps.py`**，按需挂载到路由或 `APIRouter`（无需维护路径白名单，且 `/docs` 自动生成小锁按钮）。
4. **`db/session.py` 的共享原则**
   - 全局共享的是**连接池（`async_engine`）**和**会话工厂（`AsyncSessionLocal`）**；
   - `Session` 本身**绝不多请求共用**，每次请求进来由 `get_db()` 单独 `new` 一个独立 `Session`，请求结束自动关闭归还。

---

## 四、日常开发标准流程与常用命令

### 新增一张表及接口的步骤
1. **写表模型**：在 `models/` 下新建实体类（继承 `Base`），并在 `models/__init__.py` 中导入导出。
2. **同步建表**：首次生成迁移时，先确认 `.env` 指向项目专用的空库，并安装 `requirements-migrations.txt` 中的依赖。
   ```bash
   # 1. 自动对比 models 生成迁移脚本（生成后建议点开 alembic/versions/ 扫一眼确认无误，尤其注意字段改名场景）
   alembic revision --autogenerate -m "描述本次表变更"

   # 2. 在 PostgreSQL 中真正执行建表/改表
   alembic upgrade head
   ```
   *(如需撤回上一步迁移：`alembic downgrade -1`)*
3. **写接口契约**：在 `schemas/` 下定义入参 DTO 与出参 VO。
4. **写 SQL 仓库**：在 `repositories/` 下编写数据库读写函数（不写 `commit`）。
5. **写业务逻辑**：在 `services/` 下编排业务与 `async with session.begin():` 事务。
6. **写接口路由**：在 `api/routes/` 下暴露接口，并在 `main.py` 注册路由。

### Redis 会话配置

在本地 `.env` 填写 `REDIS_URL`（示例见 `.env.example`，会话存储需要 Redis 6.2 或更高版本）。留空时应用仍能启动，但需要 Redis 的登录、鉴权、刷新和退出返回 `503`。填好后重启应用，启动时会执行 `PING` 检查连接，检查失败则停止启动。不要将含真实密码的连接地址提交到 Git。

只需登录用户 ID 的路由使用 `CurrentSessionDep`，可直接从返回的 `(user_id, session_id)` 取值，不为鉴权查询 PostgreSQL。需要用户资料的路由（如 `/auth/me`）仍使用 `CurrentUserDep`，它在验签、查 Redis 之后查询用户表。

登录创建 Redis 会话键，按数据库会话的最长有效期过期；上线前已经签发的旧令牌没有 Redis 会话键，需要重新登录。Redis 键缺失时不回源重建。RT 的摘要、轮换和重用检查仍在 PostgreSQL 完成，`refresh_tokens.session_id` 仍用于定位会话。退出和 RT 重用检测会同时撤销 PostgreSQL 会话和 Redis 会话。管理功能停用账号时应调用 `disable_user()`，不要仅手工更新 `users.is_active`，否则只查 Redis 的接口无法立即得知。

Redis 会话键是鉴权依据，不要与可随意淘汰的业务缓存混用；也不要从旧快照或落后的副本恢复并继续信任旧会话键。Redis 故障返回 `503`，不会跳过检查。

### 本地启动与测试命令
```bash
# 启动开发服务器（支持热重载）
uvicorn main:app --reload

# 接口交互文档（启动后浏览器访问）
# Swagger UI（静态资源从项目本地提供，无需外网 CDN）: http://127.0.0.1:8000/docs
# ReDoc:      http://127.0.0.1:8000/redoc

# 运行自动化测试
python -m pytest -q
```
