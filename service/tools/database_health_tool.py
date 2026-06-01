# database_health_tool.py — 数据库健康检查工具

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from smolagents import tool


@tool
def check_database_health(db_path: str = "memory.db", cleanup_days: int = 0) -> str:
    """Check SQLite database health including size, row counts, and integrity.

    Use this to monitor database status and optionally clean up old data.

    Args:
        db_path: Path to SQLite database file (default: "memory.db")
        cleanup_days: If > 0, delete conversations older than N days (default: 0, no cleanup)

    Returns:
        Database health report including size, table statistics, and integrity check results.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return f"❌ 数据库文件不存在: {db_path}"

    lines = [f"=== 数据库健康检查 ({db_path}) ===\n"]

    # 文件大小
    file_size_mb = db_file.stat().st_size / (1024 ** 2)
    size_status = "⚠️ 数据库较大" if file_size_mb > 100 else "✅ 正常"
    lines.append(f"【文件大小】{size_status}")
    lines.append(f"  大小: {file_size_mb:.2f} MB")
    lines.append("")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 表统计
        lines.append("【表统计】")

        # conversations 表
        cursor.execute("SELECT COUNT(*) FROM conversations")
        conv_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM conversations WHERE session_id IS NOT NULL")
        session_count = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM conversations")
        min_time, max_time = cursor.fetchone()

        lines.append(f"  conversations 表:")
        lines.append(f"    总记录数: {conv_count}")
        lines.append(f"    会话数: {session_count}")
        if min_time and max_time:
            lines.append(f"    时间范围: {min_time[:10]} 至 {max_time[:10]}")

        # 最近活跃度
        cursor.execute("""
            SELECT COUNT(*) FROM conversations
            WHERE timestamp >= datetime('now', '-24 hours')
        """)
        recent_count = cursor.fetchone()[0]
        lines.append(f"    最近 24 小时: {recent_count} 条")

        lines.append("")

        # knowledge 表
        cursor.execute("SELECT COUNT(*) FROM knowledge")
        knowledge_count = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(updated_at) FROM knowledge")
        last_update = cursor.fetchone()[0]

        lines.append(f"  knowledge 表:")
        lines.append(f"    总记录数: {knowledge_count}")
        if last_update:
            lines.append(f"    最后更新: {last_update[:19]}")

        lines.append("")

        # 索引检查
        lines.append("【索引状态】")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND sql IS NOT NULL
        """)
        indexes = cursor.fetchall()
        if indexes:
            lines.append(f"  已创建索引: {len(indexes)} 个")
            for idx in indexes:
                lines.append(f"    - {idx[0]}")
        else:
            lines.append("  ⚠️ 未找到索引，可能影响查询性能")

        lines.append("")

        # 完整性检查
        lines.append("【完整性检查】")
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        if integrity_result == "ok":
            lines.append("  ✅ 数据库完整性正常")
        else:
            lines.append(f"  ❌ 完整性检查失败: {integrity_result}")

        lines.append("")

        # 查询性能测试
        lines.append("【性能测试】")
        import time

        # 测试简单查询
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        cursor.fetchone()
        query_time_ms = (time.time() - start) * 1000

        perf_status = "✅ 快速" if query_time_ms < 100 else "⚠️ 较慢"
        lines.append(f"  简单查询耗时: {query_time_ms:.2f} ms {perf_status}")

        lines.append("")

        # 数据清理（如果指定了 cleanup_days）
        if cleanup_days > 0:
            lines.append(f"【数据清理】删除 {cleanup_days} 天前的对话")

            cutoff_date = (datetime.now() - timedelta(days=cleanup_days)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM conversations
                WHERE timestamp < ?
            """, (cutoff_date,))
            old_count = cursor.fetchone()[0]

            if old_count > 0:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE timestamp < ?
                """, (cutoff_date,))
                conn.commit()
                lines.append(f"  ✅ 已删除 {old_count} 条旧记录")

                # 执行 VACUUM 回收空间
                cursor.execute("VACUUM")
                new_size_mb = db_file.stat().st_size / (1024 ** 2)
                saved_mb = file_size_mb - new_size_mb
                lines.append(f"  ✅ 已回收空间: {saved_mb:.2f} MB")
                lines.append(f"  新大小: {new_size_mb:.2f} MB")
            else:
                lines.append(f"  ℹ️ 没有需要清理的旧数据")

            lines.append("")

        # 健康评分
        lines.append("【健康评分】")
        issues = []

        if file_size_mb > 100:
            issues.append(f"数据库文件较大 ({file_size_mb:.1f} MB)")

        if query_time_ms > 100:
            issues.append(f"查询性能较慢 ({query_time_ms:.1f} ms)")

        if not indexes:
            issues.append("缺少索引")

        if integrity_result != "ok":
            issues.append("完整性检查失败")

        # 检查是否有过多旧数据
        if conv_count > 10000:
            cursor.execute("""
                SELECT COUNT(*) FROM conversations
                WHERE timestamp < datetime('now', '-30 days')
            """)
            old_data_count = cursor.fetchone()[0]
            if old_data_count > 5000:
                issues.append(f"存在大量旧数据 ({old_data_count} 条超过 30 天)")

        if not issues:
            lines.append("✅ 数据库健康状况良好")
        else:
            lines.append(f"⚠️ 发现 {len(issues)} 个问题:")
            for issue in issues:
                lines.append(f"  - {issue}")

        # 建议
        if issues:
            lines.append("\n【优化建议】")
            if file_size_mb > 100 or (conv_count > 10000 and old_data_count > 5000):
                lines.append("  • 建议清理旧数据: check_database_health(cleanup_days=30)")
            if not indexes:
                lines.append("  • 建议重新初始化数据库以创建索引")
            if query_time_ms > 100:
                lines.append("  • 建议执行 VACUUM 优化数据库")

        conn.close()

    except sqlite3.Error as e:
        return f"❌ 数据库操作失败: {e}"
    except Exception as e:
        return f"❌ 检查失败: {e}"

    return "\n".join(lines)
