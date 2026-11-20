import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


logger = logging.getLogger("uvicorn.error")
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


@asynccontextmanager
async def open_scheduler() -> AsyncIterator[None]:
    """为本次应用运行创建、启动并关闭调度器。"""
    scheduler = AsyncIOScheduler(timezone=BEIJING_TIMEZONE)

    @scheduler.scheduled_job(
        CronTrigger.from_crontab("* * * * *", timezone=BEIJING_TIMEZONE),
        id="log_beijing_time",
        max_instances=1,
    )
    async def log_beijing_time() -> None:
        """每分钟开始时记录一次北京时间。"""
        now = datetime.now(BEIJING_TIMEZONE)
        logger.info("当前北京时间 %s", now.strftime("%Y-%m-%d %H:%M:%S"))

    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()
        # 让事件循环执行 APScheduler 已排队的关闭回调。
        await asyncio.sleep(0)
