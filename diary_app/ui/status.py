from datetime import date, datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QLineEdit,
                              QProgressBar, QFrame, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from db import get_todo_stats, get_ddays, add_dday, delete_dday


class StatusWidget(QWidget):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 완료율 섹션
        stats_label = QLabel("📊 이번 달 할일 완료율")
        stats_label.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")

        self.stats_detail = QLabel()
        self.stats_detail.setFont(QFont("Pretendard", 10))

        # 주간 완료율
        self.week_label = QLabel()
        self.week_label.setFont(QFont("Pretendard", 10))

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)

        # D-day 섹션
        dday_label = QLabel("📅 D-day")
        dday_label.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))

        # D-day 입력
        input_layout = QHBoxLayout()
        self.dday_name = QLineEdit()
        self.dday_name.setPlaceholderText("이름 (예: 생일)")
        self.dday_date = QLineEdit()
        self.dday_date.setPlaceholderText("날짜 (YYYY-MM-DD)")
        add_btn = QPushButton("추가")
        add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._add_dday)
        input_layout.addWidget(self.dday_name)
        input_layout.addWidget(self.dday_date)
        input_layout.addWidget(add_btn)

        # D-day 목록
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.dday_container = QWidget()
        self.dday_layout = QVBoxLayout(self.dday_container)
        self.dday_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dday_layout.setSpacing(6)
        self.scroll.setWidget(self.dday_container)

        layout.addWidget(stats_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.stats_detail)
        layout.addWidget(self.week_label)
        layout.addWidget(line)
        layout.addWidget(dday_label)
        layout.addLayout(input_layout)
        layout.addWidget(self.scroll)

    def refresh(self):
        self._render_stats()
        self._render_ddays()

    def _render_stats(self):
        t = self.theme
        today = date.today()

        # 이번 달 통계
        total, done = get_todo_stats(today.year, today.month)
        pct = int(done / total * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {t['surface2']};
                border-radius: 10px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {t['primary']};
                border-radius: 10px;
            }}
        """)
        self.stats_detail.setText(
            f"이번 달: 총 {total}개 중 {done}개 완료"
        )
        self.stats_detail.setStyleSheet(f"color: {t['text_sub']};")

        # 이번 주 통계
        from datetime import timedelta
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        wtotal, wdone = get_todo_stats_range(str(week_start), str(week_end))
        wpct = int(wdone / wtotal * 100) if wtotal > 0 else 0
        self.week_label.setText(
            f"이번 주: 총 {wtotal}개 중 {wdone}개 완료 ({wpct}%)"
        )
        self.week_label.setStyleSheet(f"color: {t['text_sub']};")

    def _render_ddays(self):
        while self.dday_layout.count():
            item = self.dday_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = self.theme
        ddays = get_ddays()
        today = date.today()

        if not ddays:
            empty = QLabel("D-day를 추가해보세요!")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {t['text_sub']}; padding: 12px;")
            self.dday_layout.addWidget(empty)
            return

        for dday in ddays:
            did, name, target_str = dday[0], dday[1], dday[2]
            target = datetime.strptime(target_str, "%Y-%m-%d").date()
            delta = (target - today).days

            if delta > 0:
                d_text = f"D-{delta}"
                color = t["primary"]
            elif delta == 0:
                d_text = "D-Day! 🎉"
                color = "#ff6b8a"
            else:
                d_text = f"D+{abs(delta)}"
                color = t["text_sub"]

            row = QHBoxLayout()
            name_lbl = QLabel(f"  {name}")
            name_lbl.setFont(QFont("Pretendard", 11))
            date_lbl = QLabel(target_str)
            date_lbl.setFont(QFont("Pretendard", 10))
            date_lbl.setStyleSheet(f"color: {t['text_sub']};")
            d_lbl = QLabel(d_text)
            d_lbl.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
            d_lbl.setStyleSheet(f"color: {color};")
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {t['text_sub']};
                    border: none;
                }}
                QPushButton:hover {{ color: #ff6b8a; }}
            """)
            del_btn.clicked.connect(lambda _, i=did: self._delete_dday(i))

            row.addWidget(name_lbl)
            row.addWidget(date_lbl)
            row.addStretch()
            row.addWidget(d_lbl)
            row.addWidget(del_btn)

            container = QWidget()
            container.setLayout(row)
            container.setStyleSheet(f"""
                QWidget {{
                    background-color: {t['surface']};
                    border: 1px solid {t['border']};
                    border-radius: 8px;
                    padding: 4px;
                }}
            """)
            self.dday_layout.addWidget(container)

    def _add_dday(self):
        name = self.dday_name.text().strip()
        d = self.dday_date.text().strip()
        if name and d:
            try:
                datetime.strptime(d, "%Y-%m-%d")
                add_dday(name, d)
                self.dday_name.clear()
                self.dday_date.clear()
                self._render_ddays()
            except ValueError:
                self.dday_date.setPlaceholderText("형식 오류! YYYY-MM-DD")

    def _delete_dday(self, did: int):
        delete_dday(did)
        self._render_ddays()

    def update_theme(self, theme: dict):
        self.theme = theme
        self.refresh()