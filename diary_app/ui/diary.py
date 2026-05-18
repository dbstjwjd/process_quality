from datetime import date
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QTextEdit, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_memo, save_memo, delete_memo


class DiaryDialog(QDialog):
    def __init__(self, selected_date: date, theme: dict, parent=None):
        super().__init__(parent)
        self.selected_date = selected_date
        self.theme = theme
        self.setWindowTitle(f"📝 {selected_date.strftime('%Y년 %m월 %d일')}")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._build_ui()
        self._load_memo()
        self._apply_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 날짜 라벨
        self.date_label = QLabel(self.selected_date.strftime("%Y년 %m월 %d일 (%a)"))
        self.date_label.setFont(QFont("Pretendard", 13, QFont.Weight.Bold))
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 메모 입력창
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("오늘의 메모를 입력하세요...")
        self.text_edit.setFont(QFont("Pretendard", 10))

        # 버튼
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("저장")
        self.delete_btn = QPushButton("삭제")
        self.cancel_btn = QPushButton("취소")
        self.delete_btn.setProperty("class", "secondary")
        self.cancel_btn.setProperty("class", "secondary")

        self.save_btn.clicked.connect(self._save)
        self.delete_btn.clicked.connect(self._delete)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)

        layout.addWidget(self.date_label)
        layout.addWidget(self.text_edit)
        layout.addLayout(btn_layout)

    def _load_memo(self):
        content = get_memo(str(self.selected_date))
        if content:
            self.text_edit.setText(content)

    def _save(self):
        content = self.text_edit.toPlainText().strip()
        if content:
            save_memo(str(self.selected_date), content)
        else:
            delete_memo(str(self.selected_date))
        self.accept()

    def _delete(self):
        delete_memo(str(self.selected_date))
        self.accept()

    def _apply_theme(self):
        t = self.theme
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t['bg']};
            }}
            QLabel {{
                color: {t['text']};
            }}
            QTextEdit {{
                background-color: {t['surface']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 8px;
            }}
            QTextEdit:focus {{
                border: 1px solid {t['primary']};
            }}
            QPushButton {{
                background-color: {t['primary']};
                color: {t['bg']};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t['primary_hover']};
            }}
            QPushButton[class="secondary"] {{
                background-color: {t['surface2']};
                color: {t['text']};
            }}
            QPushButton[class="secondary"]:hover {{
                background-color: {t['border']};
            }}
        """)