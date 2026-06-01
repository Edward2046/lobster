import os
import plistlib
import platform
import subprocess
from pathlib import Path

from smolagents import tool


def _is_cron_job_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if stripped.startswith("@"):
        return len(stripped.split()) >= 2
    return len(stripped.split()) >= 6


def _read_user_crontab() -> tuple[int, list[str], str | None]:
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        return 0, [], "当前系统未安装 crontab 命令。"
    except Exception as e:
        return 0, [], f"读取 crontab 失败：{e}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "no crontab for" in stderr.lower():
            return 0, [], None
        return 0, [], f"读取 crontab 失败：{stderr or '未知错误'}"

    entries = [line.strip() for line in result.stdout.splitlines() if _is_cron_job_line(line)]
    return len(entries), entries, None


def _read_macos_launchd_tasks() -> tuple[int, list[str]]:
    launchd_dirs = [
        Path("/System/Library/LaunchAgents"),
        Path("/System/Library/LaunchDaemons"),
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
        Path("~/Library/LaunchAgents").expanduser(),
    ]

    tasks: list[str] = []
    for directory in launchd_dirs:
        if not directory.exists():
            continue

        for plist_path in directory.glob("*.plist"):
            try:
                with plist_path.open("rb") as fh:
                    data = plistlib.load(fh)
            except Exception:
                continue

            if "StartInterval" not in data and "StartCalendarInterval" not in data:
                continue

            label = str(data.get("Label") or plist_path.stem)
            schedule_parts: list[str] = []
            if "StartInterval" in data:
                schedule_parts.append(f"StartInterval={data['StartInterval']}")
            if "StartCalendarInterval" in data:
                schedule_parts.append("StartCalendarInterval")

            tasks.append(f"{label} [{', '.join(schedule_parts)}]")

    return len(tasks), tasks


@tool
def get_scheduled_task_count(max_items: int = 10) -> str:
    """Get how many scheduled tasks are configured on the current machine.

    On macOS, this counts:
      - the current user's crontab entries
      - launchd plist jobs with StartInterval or StartCalendarInterval

    On Linux and other Unix-like systems, this currently counts the current
    user's crontab entries only.

    Args:
        max_items: Maximum number of example task entries to include. Defaults to 10.
    """
    max_items = max(0, min(max_items, 20))

    cron_count, cron_entries, cron_error = _read_user_crontab()
    if cron_error:
        return cron_error

    system_name = platform.system()
    lines = [f"当前机器检测到 {cron_count} 个 crontab 定时任务。"]
    examples: list[str] = []

    if cron_entries:
        examples.extend(f"crontab: {entry}" for entry in cron_entries)

    total_count = cron_count
    if system_name == "Darwin":
        launchd_count, launchd_tasks = _read_macos_launchd_tasks()
        total_count += launchd_count
        lines = [f"当前机器检测到约 {total_count} 个定时任务。"]
        lines.append(f"- crontab: {cron_count} 个")
        lines.append(f"- launchd: {launchd_count} 个（基于 LaunchAgents/LaunchDaemons 中带定时配置的 plist）")
        if launchd_tasks:
            examples.extend(f"launchd: {task}" for task in launchd_tasks)

    if not examples:
        lines.append("未发现可读取的定时任务配置。")
        return "\n".join(lines)

    if max_items > 0:
        lines.append("示例任务：")
        for item in examples[:max_items]:
            lines.append(f"- {item}")

    return "\n".join(lines)
