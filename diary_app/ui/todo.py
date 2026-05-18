from datetime import date, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QLineEdit,
                              QScrollArea, QCheckBox, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from db import get_todos_for_week, add_todo, toggle_todo, delete_todo


class TodoWidget(QWidget):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.today = date.today()
        self.week_start = self._get_week_start(self.today)
        self.selected_date = self.today

        self._build_ui()
        self.refresh()

    def _get_week_start(self, d: date) -> date:
        # 월요일 기준
        return d - timedelta(days=d.weekday())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 주간 네비게이션
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_label.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
        self.prev_btn.setFixedSize(32, 32)
        self.next_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self._prev_week)
        self.next_btn.clicked.connect(self._next_week)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.week_label)
        nav.addWidget(self.next_btn)

        # 주간 달력 (7칸)
        self.week_frame = QHBoxLayout()
        self.week_frame.setSpacing(4)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)

        # 선택된 날짜 표시
        self.selected_label = QLabel()
        self.selected_label.setFont(QFont("Pretendard", 11, QFont.Weight.Bold))

        # 할일 입력
        input_layout = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("할일 입력 후 Enter")
        self.input.setFont(QFont("Pretendard", 10))
        self.input.returnPressed.connect(self._add_todo)
        self.add_btn = QPushButton("추가")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self._add_todo)
        input_layout.addWidget(self.input)
        input_layout.addWidget(self.add_btn)

        # 할일 목록 스크롤
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.todo_container = QWidget()
        self.todo_layout = QVBoxLayout(self.todo_container)
        self.todo_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.todo_layout.setSpacing(6)
        self.scroll.setWidget(self.todo_container)

        layout.addLayout(nav)
        layout.addLayout(self.week_frame)
        layout.addWidget(line)
        layout.addWidget(self.selected_label)
        layout.addLayout(input_layout)
        layout.addWidget(self.scroll)

    def refresh(self):
        self._render_week()
        self._render_todos()

    def _render_week(self):
        # 기존 버튼 제거
        while self.week_frame.count():
            item = self.week_frame.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        end = self.week_start + timedelta(days=6)
        self.week_label.setText(
            f"{self.week_start.strftime('%Y.%m.%d')} - {end.strftime('%m.%d')}"
        )

        days = ["월", "화", "수", "목", "금", "토", "일"]
        for i in range(7):
            d = self.week_start + timedelta(days=i)
            day_name = days[i]
            btn = QPushButton(f"{day_name}\n{d.day}")
            btn.setFixedHeight(56)
            btn.setFont(QFont("Pretendard", 9))

            t = self.theme
            is_today = (d == date.today())
            is_selected = (d == self.selected_date)
            is_weekend = i >= 5

            if is_selected:
                bg = t["primary"]
                color = t["bg"]
            elif is_today:
                bg = t["surface2"]
                color = t["primary"]
            elif is_weekend:
                bg = t["surface"]
                color = "#ff6b6b"
            else:
                bg = t["surface"]
                color = t["text"]

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color};
                    border: 1px solid {t['border']};
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    border: 1px solid {t['primary']};
                }}
            """)
            btn.clicked.connect(lambda _, date_=d: self._select_date(date_))
            self.week_frame.addWidget(btn)

    def _render_todos(self):
        # 기존 항목 제거
        while self.todo_layout.count():
            item = self.todo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.selected_label.setText(
            f"📅 {self.selected_date.strftime('%Y년 %m월 %d일')} 할일"
        )

        todos = get_todos_for_week(str(self.selected_date))
        t = self.theme

        if not todos:
            empty = QLabel("할일이 없어요 😊")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {t['text_sub']}; padding: 20px;")
            self.todo_layout.addWidget(empty)
            return

        for todo in todos:
            todo_id, title, is_done = todo[0], todo[1], todo[3]
            row = QHBoxLayout()

            # 체크박스
            check = QCheckBox(title)
            check.setChecked(bool(is_done))
            check.setFont(QFont("Pretendard", 10))
            if is_done:
                check.setStyleSheet(f"""
                    QCheckBox {{ color: {t['done_text']};
                                 text-decoration: line-through; }}
                    QCheckBox::indicator:checked {{ background: {t['primary']};
                                                    border-radius: 3px; }}
                """)
            else:
                check.setStyleSheet(f"color: {t['text']};")
            check.stateChanged.connect(lambda state, tid=todo_id: self._toggle(tid))

            # 삭제 버튼
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {t['text_sub']};
                    border: none;
                    font-size: 11px;
                }}
                QPushButton:hover {{ color: #ff6b6b; }}
            """)
            del_btn.clicked.connect(lambda _, tid=todo_id: self._delete(tid))

            row.addWidget(check)
            row.addStretch()
            row.addWidget(del_btn)

            container = QWidget()
            container.setLayout(row)
            container.setStyleSheet(f"""
                QWidget {{
                    background-color: {t['surface']};
                    border: 1px solid {t['border']};
                    border-radius: 6px;
                    padding: 4px;
                }}
            """)
            self.todo_layout.addWidget(container)

    def _select_date(self, d: date):
        self.selected_date = d
        self.refresh()

    def _add_todo(self):
        title = self.input.text().strip()
        if title:
            add_todo(title, str(self.selected_date))
            self.input.clear()
            self._render_todos()

    def _toggle(self, todo_id: int):
        toggle_todo(todo_id)
        self._render_todos()

    def _delete(self, todo_id: int):
        delete_todo(todo_id)
        self._render_todos()

    def _prev_week(self):
        self.week_start -= timedelta(weeks=1)
        self.selected_date = self.week_start
        self.refresh()

    def _next_week(self):
        self.week_start += timedelta(weeks=1)
        self.selected_date = self.week_start
        self.refresh()

    def update_theme(self, theme: dict):
        self.theme = theme
        self.refresh()