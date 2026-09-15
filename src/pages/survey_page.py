from functools import partial
from typing import Any

from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pages.aqueduct_list_page import (
    AqueductListPage,
)
from pages.aqueduct_page import (
    AqueductPage,
)
from pages.inverted_siphon_list_page import (
    InvertedSiphonListPage,
)
from pages.inverted_siphon_page import (
    InvertedSiphonPage,
)
from pages.lined_channel_section_list_page import (
    LinedChannelSectionListPage,
)
from pages.lined_channel_section_page import (
    LinedChannelSectionPage,
)
from pages.sluice_gate_list_page import (
    SluiceGateListPage,
)
from pages.sluice_gate_page import (
    SluiceGatePage,
)
from pages.tunnel_list_page import (
    TunnelListPage,
)
from pages.tunnel_page import (
    TunnelPage,
)
from pages.culvert_list_page import (
    CulvertListPage,
)
from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)

# =============================================================
# 附表2工程现状调查页面注册
# =============================================================

ENGINEERING_SURVEY_FORMS: tuple[
    dict[str, Any],
    ...,
] = (
    {
        "form_code": "form_2_1",
        "button_text": ("附表2.1 " "防渗衬砌渠道渠段工程状况调查"),
        "list_page_class": (LinedChannelSectionListPage),
        "edit_page_factory": (LinedChannelSectionPage),
    },
    {
        "form_code": "form_2_2",
        "button_text": ("附表2.2 水闸工程状况调查"),
        "list_page_class": (SluiceGateListPage),
        "edit_page_factory": (SluiceGatePage),
    },
    {
        "form_code": "form_2_3",
        "button_text": ("附表2.3 " "渡槽（座槽）工程状况调查"),
        "list_page_class": (AqueductListPage),
        "edit_page_factory": (AqueductPage),
    },
    {
        "form_code": "form_2_4",
        "button_text": ("附表2.4 倒虹吸工程状况调查"),
        "list_page_class": (InvertedSiphonListPage),
        "edit_page_factory": (InvertedSiphonPage),
    },
    {
        "form_code": "form_2_5",
        "button_text": ("附表2.5 隧洞工程状况调查"),
        "list_page_class": (TunnelListPage),
        "edit_page_factory": (TunnelPage),
    },
    {
        "form_code": "form_2_6",
        "button_text": ("附表2.6 涵洞（暗涵）" "工程状况调查"),
        "list_page_class": CulvertListPage,
        "edit_page_factory": partial(
            GenericEngineeringSurveyPage,
            FORM_2_6,
        ),
    },
)


def prepare_engineering_new_page(
    edit_page,
):
    """
    进入工程调查新增页面。

    新通用框架：
        使用 initialize_new_record()
        初始化实际业务上下文。

    尚未迁移的旧页面：
        继续使用 prepare_new()。

    等全部附表迁移完成后，
    可以统一收敛为前一种接口。
    """

    initialize_new_record = getattr(
        edit_page,
        "initialize_new_record",
        None,
    )

    if callable(initialize_new_record):
        initialize_new_record()
        return

    edit_page.prepare_new()


class SurveyPage(QWidget):
    """
    调查录入模块。

    当前按业务性质划分为两个调查域：

    1. 工程现状调查
       - 附表2系列；
       - 基于 EngineeringAsset /
         SurveyRecord / InspectionResult；
       - 当前已接入附表2.1～2.6。

    2. 灌区综合与水土资源调查
       - 附表1系列；
       - 当前仅建立业务域入口；
       - 后续独立设计数据模型和录入方式。

    附表2具体页面通过注册表接入，
    避免每增加一张表就在本类中
    重复增加一整套导航方法。
    """

    def __init__(self):
        super().__init__()

        self.engineering_pages = {}

        self.init_ui()

    # =========================================================
    # UI
    # =========================================================

    def init_ui(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.stack = QStackedWidget()

        # =====================================================
        # 两级业务导航页面
        # =====================================================

        self.home_page = self.create_home_page()

        self.engineering_home_page = self.create_engineering_home_page()

        self.comprehensive_home_page = self.create_comprehensive_home_page()

        self.stack.addWidget(self.home_page)

        self.stack.addWidget(self.engineering_home_page)

        self.stack.addWidget(self.comprehensive_home_page)

        # =====================================================
        # 注册附表2工程调查页面
        # =====================================================

        self._register_engineering_pages()

        layout.addWidget(self.stack)

    # =========================================================
    # 调查录入首页
    # =========================================================

    def create_home_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        title = QLabel("调查录入")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel("请选择需要开展的调查业务类型。")

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        layout.addWidget(description)

        # =====================================================
        # 工程现状调查
        # =====================================================

        engineering_button = QPushButton("工程现状调查（附表2系列）")

        engineering_button.setMinimumHeight(52)

        engineering_button.clicked.connect(self.open_engineering_home)

        layout.addWidget(engineering_button)

        engineering_description = QLabel(
            "工程设施现状、工程状况评价及" "工程调查记录管理。"
        )

        engineering_description.setWordWrap(True)

        engineering_description.setStyleSheet("color: #7a8793;")

        layout.addWidget(engineering_description)

        # =====================================================
        # 灌区综合与水土资源调查
        # =====================================================

        comprehensive_button = QPushButton("灌区综合与水土资源调查" "（附表1系列）")

        comprehensive_button.setMinimumHeight(52)

        comprehensive_button.clicked.connect(self.open_comprehensive_home)

        layout.addWidget(comprehensive_button)

        comprehensive_description = QLabel(
            "灌区基本情况、自然条件、" "水土资源、农业生产、管理运行" "等综合调查。"
        )

        comprehensive_description.setWordWrap(True)

        comprehensive_description.setStyleSheet("color: #7a8793;")

        layout.addWidget(comprehensive_description)

        layout.addStretch()

        return page

    # =========================================================
    # 工程现状调查首页
    # =========================================================

    def create_engineering_home_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        back_button = QPushButton("返回调查分类")

        back_button.clicked.connect(self.open_home)

        layout.addWidget(back_button)

        title = QLabel("工程现状调查")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel("附表2系列工程设施现状调查与评价。")

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        layout.addWidget(description)

        # =====================================================
        # 根据注册表生成工程调查入口
        # =====================================================

        for definition in ENGINEERING_SURVEY_FORMS:
            button = QPushButton(definition["button_text"])

            button.setMinimumHeight(46)

            button.clicked.connect(
                partial(
                    self.open_engineering_list,
                    definition["form_code"],
                )
            )

            layout.addWidget(button)

        placeholder = QLabel("附表2.7～2.14将在后续" "逐步接入。")

        placeholder.setStyleSheet("color: #7a8793;")

        layout.addWidget(placeholder)

        layout.addStretch()

        return page

    # =========================================================
    # 灌区综合与水土资源调查首页
    # =========================================================

    def create_comprehensive_home_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        back_button = QPushButton("返回调查分类")

        back_button.clicked.connect(self.open_home)

        layout.addWidget(back_button)

        title = QLabel("灌区综合与水土资源调查")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel("本业务域用于附表1系列综合调查。")

        description.setWordWrap(True)

        layout.addWidget(description)

        placeholder = QLabel(
            "业务域入口已经建立。\n\n"
            "附表1系列的数据模型、"
            "矩阵录入和统计方式将在"
            "附表2工程现状调查完成后"
            "单独设计和开发。"
        )

        placeholder.setWordWrap(True)

        placeholder.setStyleSheet("color: #7a8793;")

        layout.addWidget(placeholder)

        layout.addStretch()

        return page

    # =========================================================
    # 附表2页面注册
    # =========================================================

    def _register_engineering_pages(self):
        for definition in ENGINEERING_SURVEY_FORMS:
            form_code = definition["form_code"]

            list_page = definition["list_page_class"]()

            edit_page = definition["edit_page_factory"]()

            self.engineering_pages[form_code] = {
                "list_page": list_page,
                "edit_page": edit_page,
            }

            self.stack.addWidget(list_page)

            self.stack.addWidget(edit_page)

            # ---------------------------------------------
            # 列表页信号
            # ---------------------------------------------

            list_page.new_requested.connect(
                partial(
                    self.open_engineering_new,
                    form_code,
                )
            )

            list_page.back_requested.connect(self.open_engineering_home)

            list_page.edit_requested.connect(
                partial(
                    self.open_engineering_edit,
                    form_code,
                )
            )

            # ---------------------------------------------
            # 编辑页信号
            # ---------------------------------------------

            edit_page.back_requested.connect(
                partial(
                    self.open_engineering_list,
                    form_code,
                )
            )

            edit_page.survey_saved.connect(
                partial(
                    self.engineering_saved,
                    form_code,
                )
            )

    # =========================================================
    # 离开模块检查
    # =========================================================

    def can_leave_page(self):
        current_widget = self.stack.currentWidget()

        for pages in self.engineering_pages.values():
            edit_page = pages["edit_page"]

            if current_widget is edit_page:
                return edit_page.confirm_leave_changes()

        return True

    # =========================================================
    # 一级业务域导航
    # =========================================================

    def open_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def open_engineering_home(self):
        self.stack.setCurrentWidget(self.engineering_home_page)

    def open_comprehensive_home(self):
        self.stack.setCurrentWidget(self.comprehensive_home_page)

    # =========================================================
    # 工程调查统一导航
    # =========================================================

    def open_engineering_list(
        self,
        form_code,
    ):
        pages = self.engineering_pages[form_code]

        list_page = pages["list_page"]

        list_page.load_data()

        self.stack.setCurrentWidget(list_page)

    def open_engineering_new(
        self,
        form_code,
    ):
        pages = self.engineering_pages[form_code]

        edit_page = pages["edit_page"]

        prepare_engineering_new_page(edit_page)

        self.stack.setCurrentWidget(edit_page)

    def open_engineering_edit(
        self,
        form_code,
        survey_record_id,
    ):
        pages = self.engineering_pages[form_code]

        edit_page = pages["edit_page"]

        try:
            edit_page.load_record(survey_record_id)

            self.stack.setCurrentWidget(edit_page)

        except Exception as error:
            QMessageBox.warning(
                self,
                "打开失败",
                str(error),
            )

    def engineering_saved(
        self,
        form_code,
    ):
        pages = self.engineering_pages[form_code]

        pages["list_page"].load_data()
