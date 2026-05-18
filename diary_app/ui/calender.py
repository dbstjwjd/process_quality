import calendar
from datetime import date, datetime
from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout,
                              QHBoxLayout, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from db import get_memos_for_month


class CalendarWidget(QWidget):
    date_clicked = pyqtSignal(date)  # 싱글클릭 - 메모 패널
    date_double_clicked = pyqtSignal(date)  # 더블클릭 - 팝업

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.today = date.today()
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.memo_dates = {}  # {date: content}

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 상단 네비게이션
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("⬅")
        self.next_btn = QPushButton("➡")
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setFont(QFont("Pretendard", 14, QFont.Weight.Bold))

        self.prev_btn.setFixedSize(32, 32)
        self.next_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self._prev_month)
        self.next_btn.clicked.connect(self._next_month)

        nav.addWidget(self.prev_btn)
        nav.addWidget(self.month_label)
        nav.addWidget(self.next_btn)

        # 요일 헤더
        self.grid = QGridLayout()
        self.grid.setSpacing(4)
        days = ["월", "화", "수", "목", "금", "토", "일"]
        for i, d in enumerate(days):
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Pretendard", 9))
            color = self.theme["primary"] if i < 5 else "#ff6b6b"
            lbl.setStyleSheet(f"color: {color};")
            self.grid.addWidget(lbl, 0, i)

        self.main_layout.addLayout(nav)
        self.main_layout.addLayout(self.grid)

    def refresh(self):
        # 기존 날짜 버튼 제거 (헤더 제외)
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            if item and self.grid.getItemPosition(i)[0] > 0:
                w = item.widget()
                if w:
                    w.deleteLater()

        self.month_label.setText(f"{self.current_year}년 {self.current_month}월")

        # DB에서 이번 달 메모 가져오기
        self.memo_dates = get_memos_for_month(self.current_year, self.current_month)

        cal = calendar.monthcalendar(self.current_year, self.current_month)
        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                if day == 0:
                    self.grid.addWidget(QLabel(""), row + 1, col)
                    continue

                d = date(self.current_year, self.current_month, day)
                btn = self._make_day_button(d, col)
                self.grid.addWidget(btn, row + 1, col)

    def _make_day_button(self, d: date, col: int) -> QPushButton:
        # 미리보기 제거 - 날짜 숫자만 표시
        btn = QPushButton(str(d.day))
        btn.setFixedHeight(80)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setFont(QFont("Pretendard", 11))

        t = self.theme
        is_today = (d == date.today())
        is_weekend = col >= 5

        if is_today:
            bg = t["primary"]
            color = "#ffffff"
        elif is_weekend:
            bg = t["surface2"]
            color = "#ff6b8a"
        else:
            bg = t["surface"]
            color = t["text"]

        # 메모 있는 날짜는 점으로 표시
        has_memo = str(d) in self.memo_dates
        border_color = t["primary"] if has_memo else t["border"]

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: 2px solid {border_color};
                border-radius: 8px;
                text-align: center;
            }}
            QPushButton:hover {{
                border: 2px solid {t['primary']};
                background-color: {t['surface2']};
            }}
        """)

        btn.clicked.connect(lambda: self.date_clicked.emit(d))

        btn.mouseDoubleClickEvent = lambda event, d_=d: self.date_double_clicked.emit(d_)

        return btn

    def _prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.refresh()

    def _next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.refresh()

    def update_theme(self, theme: dict):
        self.theme = theme
        self.refresh()