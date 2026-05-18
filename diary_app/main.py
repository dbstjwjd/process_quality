import sys
from pathlib import Path
from datetime import date
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                              QHBoxLayout, QVBoxLayout, QStackedWidget,
                              QPushButton, QLabel)
from PyQt6.QtGui import QAction, QFontDatabase, QFont
from PyQt6.QtCore import Qt
from db import init_db
from ui.themes import THEMES, DEFAULT_THEME, get_stylesheet
from ui.calender import CalendarWidget
from ui.diary import DiaryDialog
from ui.todo import TodoWidget
import json

CONFIG_PATH = Path(__file__).parent / "config.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📅 내 다이어리")
        self.setMinimumSize(900, 650)
        self._load_config()
        self.current_theme_key = DEFAULT_THEME

        init_db()
        self._build_menubar()
        self._build_ui()
        self._apply_theme(self.current_theme_key)


    def _load_config(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            self.current_theme_key = config.get("theme", DEFAULT_THEME)
            family = config.get("font_family", "Pretendard")
            size = config.get("font_size", 13)
            self.app_font = QFont(family, size)
        else:
            self.current_theme_key = DEFAULT_THEME
            self.app_font = QFont("Pretendard", 13)

    def _save_config(self):
        config = {
            "theme": self.current_theme_key,
            "font_family": self.app_font.family(),
            "font_size": self.app_font.pointSize(),
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _open_font_dialog(self):
        from PyQt6.QtWidgets import QFontDialog
        current_font = self.app_font
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            self.app_font = font
            QApplication.instance().setFont(font)
            self._save_config()
            self._apply_theme(self.current_theme_key)

    def _build_menubar(self):
        menubar = self.menuBar()

        # 설정 메뉴
        settings_menu = menubar.addMenu("설정")
        theme_menu = settings_menu.addMenu("🎨 테마")
        font_action = QAction("🔤 폰트 설정", self)
        font_action.triggered.connect(self._open_font_dialog)
        settings_menu.addAction(font_action)
        for key, theme in THEMES.items():
            action = QAction(theme["name"], self)
            action.setCheckable(True)
            action.setChecked(key == self.current_theme_key)
            action.triggered.connect(lambda checked, k=key: self._apply_theme(k))
            theme_menu.addAction(action)
        self._theme_menu = theme_menu

        # TODO 버튼 (메뉴바에 추가)
        self.todo_action = QAction("✅ TODO", self)
        self.todo_action.triggered.connect(self._toggle_view)
        menubar.addAction(self.todo_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # QStackedWidget으로 화면 전환
        self.stack = QStackedWidget()

        # 0번 - 메인 (달력 + 안내문구)
        self.main_page = self._build_main_page()

        # 1번 - TODO 페이지
        self.todo_page = self._build_todo_page()

        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.todo_page)

        main_layout.addWidget(self.stack)

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 달력
        self.calendar = CalendarWidget(THEMES[self.current_theme_key])
        self.calendar.date_clicked.connect(self._update_memo_panel)
        self.calendar.date_double_clicked.connect(self._open_diary)

        # 오른쪽 탭
        self.right_tab = QTabWi dget()
        self.right_tab.setFont(QFont("Pretendard", 11))

        # 메모 탭
        memo_widget = QWidget()
        memo_layout = QVBoxLayout(memo_widget)
        memo_layout.setContentsMargins(12, 12, 12, 12)
        self.memo_date_label = QLabel()
        self.memo_date_label.setFont(QFont("Pretendard", 13, QFont.Weight.Bold))
        self.memo_content_label = QLabel()
        self.memo_content_label.setFont(QFont("Pretendard", 11))
        self.memo_content_label.setWordWrap(True)
        self.memo_content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        memo_layout.addWidget(self.memo_date_label)
        memo_layout.addWidget(self.memo_content_label)
        memo_layout.addStretch()

        # 통계/D-day 탭
        self.status_widget = StatusWidget(THEMES[self.current_theme_key])

        self.right_tab.addTab(memo_widget, "📝 메모")
        self.right_tab.addTab(self.status_widget, "📊 통계")

        layout.addWidget(self.calendar, 3)
        layout.addWidget(self.right_tab, 2)

        self._update_memo_panel(date.today())
        return page

    def _build_todo_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 뒤로가기 버튼
        back_layout = QHBoxLayout()
        back_btn = QPushButton("← 달력으로 돌아가기")
        back_btn.setFixedWidth(160)
        back_btn.clicked.connect(self._toggle_view)
        back_layout.addWidget(back_btn)
        back_layout.addStretch()

        # TODO 위젯
        self.todo_widget = TodoWidget(THEMES[self.current_theme_key])

        layout.addLayout(back_layout)
        layout.addWidget(self.todo_widget)
        return page

    def _update_memo_panel(self, selected_date: date):
        from db import get_memo
        t = THEMES[self.current_theme_key]
        self.memo_date_label.setText(
            selected_date.strftime("%Y년 %m월 %d일")
        )
        content = get_memo(str(selected_date))
        if content:
            self.memo_content_label.setText(content)
            self.memo_content_label.setStyleSheet(f"color: {t['text']};")
        else:
            self.memo_content_label.setText("메모가 없어요.\n날짜를 클릭해서 작성해보세요!")
            self.memo_content_label.setStyleSheet(f"color: {t['text_sub']};")

    def _toggle_view(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self.todo_action.setText("📅 달력")
        else:
            self.stack.setCurrentIndex(0)
            self.todo_action.setText("✅ TODO")

    def _open_diary(self, selected_date: date):
        dialog = DiaryDialog(selected_date, THEMES[self.current_theme_key], self)
        if dialog.exec():
            self.calendar.refresh()
            self._update_memo_panel(selected_date)

    def _apply_theme(self, key: str):
        self.current_theme_key = key
        theme = THEMES[key]
        self.setStyleSheet(get_stylesheet(theme))
        self._save_config()

        # 각 위젯 테마 업데이트
        if hasattr(self, 'calendar'):
            self.calendar.update_theme(theme)
        if hasattr(self, 'todo_widget'):
            self.todo_widget.update_theme(theme)
        if hasattr(self, 'status_widget'):
            self.status_widget.update_theme(theme)

        # 메뉴 체크 상태 업데이트
        for action in self._theme_menu.actions():
            action.setChecked(action.text() == theme["name"])


if __name__ == "__main__":
    app = QApplication(sys.argv)

    font_path = Path(__file__).parent / "assets" / "fonts"
    QFontDatabase.addApplicationFont(str(font_path / "Pretendard-Regular.otf"))
    QFontDatabase.addApplicationFont(str(font_path / "Pretendard-Bold.otf"))
    app.setFont(QFont("Pretendard", 10))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())