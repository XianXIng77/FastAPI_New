# FastAPI 项目架构说明文档

本项目采用面向中大型工程的**分层架构**（对标 Spring Boot / MyBatis 经典分层思想），实现接口协议、业务逻辑、数据访问与底层基础设施的清晰解耦。

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
db/            ──► 连接池与会话底座：提供全局连接池、每次请求独立 new 出 Session、挂载公共表字段
   │
   ▼
PostgreSQL 数据库  ◄── 表结构由 models/ 定义，通过 alembic/ 自动生成迁移脚本并建表
```

---

## 二、根目录文件夹职责速查表

### 1. 日常写业务层（新增功能时按顺序改这 5 个目录）

| 目录 | 定位 | 对标 Spring Boot 概念 | 核心职责与代表文件 |
| :--- | :--- | :--- | :--- |
| **`models/`** | 数据库实体层 | `Entity` / `PO` | 定义数据库表结构、主键、唯一索引（如 `models/user.py`）。注意新建表后需在 `models/__init__.py` 导出。 |
| **`schemas/`** | 数据契约层 | `DTO` + `VO` | 基于 Pydantic 校验前端入参（如 `UserCreate` 当 DTO）、过滤返回给前端的字段（如 `UserRead` 当 VO，屏蔽密码哈希）。 |
| **`repositories/`** | 数据仓库层 | `Mapper` / `DAO` | 专门写 SQL（SQLAlchemy 链式表达式或原生 SQL），只管存取数据，不写业务规则，不手动提交事务。 |
| **`services/`** | 业务逻辑层 | `Service` (`@Transactional`) | 串联业务步骤（密码加密、多表操作组合）、通过 `async with session.begin():` 统一控制事务边界、抛出业务异常。 |
| **`api/`** | 接口路由层 | `Controller` + 权限门卫 | `api/routes/` 定义 URL 与请求方式；`api/deps.py` 声明接口共用依赖（如获取数据库会话 `SessionDep`、校验登录令牌 `CurrentUserDep`）。 |

### 2. 底座支撑层（搭好后日常很少改动）

| 目录 | 定位 | 核心职责与代表文件 |
| :--- | :--- | :--- |
| **`core/`** | 框架内核底座 | **不含任何具体业务代码**（换个新项目也能直接搬走复用）。负责：<br>• `config.py`：读取 `.env` 环境变量与全局配置<br>• `security.py`：密码 Argon2 哈希、JWT 签发与解码等底层安全算法<br>• `exception_handlers.py`：全局异常拦截兜底（如 422 校验错误隐藏敏感输入）<br>• 后续可扩展：`exceptions.py`（全局业务异常基类）、`logging.py`（全局日志）、`middlewares.py`（全站耗时/跨域/`Request-ID`） |
| **`db/`** | 数据库基础设施 | • `session.py`：配置连接池参数（`async_engine`）与会话生产工厂（`AsyncSessionLocal`），每次请求独立生成并归还 `Session`<br>• `base.py`：所有 `models` 继承的公共父类 `Base`（统一附带 `created_at`、`updated_at` 公共字段） |
| **`utils/`** | 通用工具箱 | 存放与业务、框架配置完全无关的**纯无状态工具函数**（如日期转换、字符串脱敏、随机码生成，单独拷走也能直接运行）。 |

### 3. 工程配套与其他目录

| 目录 | 定位 | 说明 |
| :--- | :--- | :--- |
| **`alembic/`** | 数据库版本迁移 | 相当于 Flyway。自动扫描 `models/` 的变更生成迁移脚本（存于 `alembic/versions/`），执行命令即可在数据库自动建表/改表，日常无需手写。 |
| **`tests/`** | 自动化测试 | 使用 `pytest` + 内存数据库验证接口状态码、参数拦截、落库结果与异常回滚。 |
| **`crud/`** | 早期遗留空目录 | 轻量级教程常将 `services + repositories` 合并为 `crud`；本项目已升级为更规范的 `services + repositories` 分层，该空目录无需使用，可直接删除。 |

---

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
2. **同步建表**：
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

### 本地启动与测试命令
```bash
# 启动开发服务器（支持热重载）
uvicorn main:app --reload

# 接口交互文档（启动后浏览器访问）
# Swagger UI: http://127.0.0.1:8000/docs
# ReDoc:      http://127.0.0.1:8000/redoc

# 运行自动化测试
python -m pytest -q
```
