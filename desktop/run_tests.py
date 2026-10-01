"""
引大灌区调查数据采集系统
自动化回归测试启动器。

功能：
1. 编译检查 src / tests
2. 运行全部 unittest
3. 同时输出到终端和日志文件
4. 返回正确的进程退出码
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = PROJECT_ROOT / "src"
TEST_DIR = PROJECT_ROOT / "tests"

LOG_DIR = PROJECT_ROOT / "test_logs"


def run_command(
    command: list[str],
    log_file,
) -> int:
    """
    执行命令，并同时输出到：
    - 当前终端
    - 日志文件
    """

    command_text = " ".join(command)

    header = "\n" + "=" * 72 + "\n" + f"> {command_text}" + "\n" + "=" * 72 + "\n"

    print(header, end="")
    log_file.write(header)
    log_file.flush()

    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert process.stdout is not None

    for line in process.stdout:
        print(
            line,
            end="",
        )

        log_file.write(line)

        log_file.flush()

    return process.wait()


def main() -> int:
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_path = LOG_DIR / f"test_{timestamp}.log"

    start_time = datetime.now()

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log_file:
        title = (
            "=" * 72
            + "\n"
            + "引大灌区调查数据采集系统 - 自动化回归测试\n"
            + f"开始时间：{start_time:%Y-%m-%d %H:%M:%S}\n"
            + f"Python：{sys.executable}\n"
            + f"项目目录：{PROJECT_ROOT}\n"
            + f"日志文件：{log_path}\n"
            + "=" * 72
            + "\n"
        )

        print(title)
        log_file.write(title)
        log_file.flush()

        # =========================
        # 1. Python 编译检查
        # =========================

        compile_result = run_command(
            [
                sys.executable,
                "-m",
                "compileall",
                str(SRC_DIR),
                str(TEST_DIR),
            ],
            log_file,
        )

        if compile_result != 0:
            status = "FAILED - 编译检查失败"
            exit_code = compile_result

        else:
            # =========================
            # 2. 全部自动化测试
            # =========================

            test_result = run_command(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(TEST_DIR),
                    "-p",
                    "test_*.py",
                    "-v",
                ],
                log_file,
            )

            if test_result == 0:
                status = "PASSED"
                exit_code = 0
            else:
                status = "FAILED - 自动化测试失败"
                exit_code = test_result

        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()

        summary = (
            "\n"
            + "=" * 72
            + "\n"
            + "测试结束\n"
            + f"状态：{status}\n"
            + f"结束时间：{end_time:%Y-%m-%d %H:%M:%S}\n"
            + f"耗时：{duration:.2f} 秒\n"
            + f"日志：{log_path}\n"
            + "=" * 72
            + "\n"
        )

        print(summary)

        log_file.write(summary)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
