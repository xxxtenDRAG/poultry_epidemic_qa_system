"""数据库初始化：自动建库 + 建表（服务启动时调用）。

MySQL 必须先存在才能连接，故先用 root 连接默认库创建目标库，
再通过 SQLAlchemy 的 metadata.create_all 建表（session/message/document）。
"""
import pymysql
from sqlalchemy import create_engine

from core.config import settings
from db.session import Base, engine
from db import models  # noqa: F401  确保模型被注册到 metadata


def init_db() -> None:
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            charset="utf8mb4",
        )
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        conn.close()
    except pymysql.MySQLError as e:
        raise RuntimeError(
            f"无法连接 MySQL（{settings.MYSQL_HOST}:{settings.MYSQL_PORT}）：{e}。"
            "请确认 MySQL 已启动、.env 中 MYSQL_PASSWORD 正确。"
        ) from e

    # 已建的库无法通过 create_all 改表结构；开发阶段直接重建表便于迭代
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成 ✅")
