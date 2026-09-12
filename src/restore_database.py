"""
引大灌区调查数据采集系统
数据库备份恢复维护工具。

重要：
执行恢复前必须完全关闭主程序。
"""

from services.database_backup import (
    get_database_backups,
    restore_database_backup,
    validate_database_file,
)


def main():
    backups = get_database_backups()

    if not backups:
        print("当前没有可用的数据库备份。")
        return

    print()
    print("=" * 60)
    print("引大灌区调查数据采集系统" " - 数据库恢复工具")
    print("=" * 60)
    print()

    print("注意：执行恢复前必须已经" "完全关闭主程序。")
    print()

    print("现有备份：")
    print()

    for index, backup_path in enumerate(
        backups,
        start=1,
    ):
        size_mb = backup_path.stat().st_size / 1024 / 1024

        print(f"[{index}] " f"{backup_path.name}" f"  ({size_mb:.2f} MB)")

    print()
    choice_text = input("请输入要恢复的备份序号" "（直接回车取消）：").strip()

    if not choice_text:
        print("已取消。")
        return

    try:
        choice = int(choice_text)
    except ValueError:
        print("输入无效，已取消。")
        return

    if choice < 1 or choice > len(backups):
        print("备份序号不存在，已取消。")
        return

    selected_backup = backups[choice - 1]

    print()
    print("准备恢复：")
    print(selected_backup)
    print()

    try:
        validate_database_file(selected_backup)
    except Exception as error:
        print("备份检查失败：" f"{error}")
        return

    confirm = input("请输入 RESTORE " "确认执行恢复：").strip()

    if confirm != "RESTORE":
        print("未收到正确确认文本，" "已取消恢复。")
        return

    try:
        result = restore_database_backup(selected_backup)

    except Exception as error:
        print()
        print("数据库恢复失败：" f"{error}")
        return

    print()
    print("=" * 60)
    print("数据库恢复成功。")
    print()

    print("恢复来源：" f"{result['restored_from']}")

    safety_backup = result["safety_backup"]

    if safety_backup is not None:
        print("恢复前安全备份：" f"{safety_backup}")

    print()
    print("现在可以重新启动主程序" "检查数据。")
    print("=" * 60)


if __name__ == "__main__":
    main()
