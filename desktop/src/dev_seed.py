"""
开发环境测试数据初始化工具。

这是项目唯一的开发测试数据初始化入口。

使用：
    python src/dev_seed.py

注意：
- 本文件只用于开发测试；
- 正式程序 main.py 不调用本文件；
- 正式业务数据库不会自动创建测试项目和测试批次。
"""

from database import (
    create_demo_data,
    create_initial_forms,
    init_database,
    show_database_info,
)


def main():
    print("正在初始化开发测试数据...")
    print()

    init_database()
    create_initial_forms()
    create_demo_data()

    print("开发测试数据初始化完成。")
    print()

    show_database_info()


if __name__ == "__main__":
    main()
