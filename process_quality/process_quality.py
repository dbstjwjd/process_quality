import calendar
import ctypes
import ctypes.wintypes
import os
import time
import sys
from datetime import date
from pathlib import Path

import psutil
import xlwings as xw
import pyautogui
from pynput import keyboard as _kb

_key = _kb.Controller()

_user32 = ctypes.windll.user32
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

EXE_PATH = r"C:\Users\Public\Desktop\종합생산시스템.lnk"
USERNAME = "pjys0520"
PASSWORD = "1360"
WAIT_FOR_WINDOW = 5
IMG_DIR = Path(__file__).parent / "images"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

MENU_STEPS = [
    ("btn_quality",  "품질관리"),
    ("btn_status",   "공정품질현황"),
    ("btn_inquiry",  "공정품질조회"),
]


def _find_tims_pids() -> set[int]:
    pids = set()

    def _callback(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        if "ThunderRT6" in buf.value:
            pid = ctypes.wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(pid.value)
        return True

    _user32.EnumWindows(_WNDENUMPROC(_callback), 0)
    return pids


def kill_tims():
    pids = _find_tims_pids()
    if not pids:
        print("[*] 실행 중인 TIMS 없음")
        return

    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.kill()
            proc.wait(timeout=5)
            print(f"  [✓] TIMS 종료  PID={pid}  이름={proc_name}")
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass

    time.sleep(1.5)


def abort(reason: str = ""):
    print(f"[중단] {reason}" if reason else "[중단] 자동화를 중단합니다.")
    kill_tims()
    sys.exit(1)


def setup_esc_abort():
    def _on_press(key):
        if key == _kb.Key.esc:
            print("\n[긴급 중단] ESC 입력")
            kill_tims()
            os._exit(1)  # 백그라운드 스레드에서 전체 프로세스 종료 시 os._exit 필요

    listener = _kb.Listener(on_press=_on_press)
    listener.daemon = True
    listener.start()
    print("[*] ESC 키를 누르면 언제든지 중단됩니다.")


def click_image(image_name: str, confidence: float = 0.9, timeout: float = 10.0,
                region: tuple | None = None) -> bool:
    image_path = str(IMG_DIR / f"{image_name}.png")
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence, region=region)
            if location:
                pyautogui.click(location)
                print(f"  [✓] '{image_name}' 클릭  위치={location}")
                return True
        except pyautogui.ImageNotFoundException:
            pass
        time.sleep(0.5)

    print(f"  [✗] '{image_name}' 을(를) {timeout}초 내에 찾지 못했습니다.")
    return False


def login():
    kill_tims()

    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", EXE_PATH, None, None, 1)
    if ret <= 32:
        abort(f"프로그램 실행 실패 (코드: {ret})")

    print(f"[*] TIMS 실행 중... {WAIT_FOR_WINDOW}초 대기")
    time.sleep(WAIT_FOR_WINDOW)

    pyautogui.click(x=960, y=540)
    time.sleep(0.5)

    pyautogui.typewrite(USERNAME, interval=0.05)
    pyautogui.press("tab")
    pyautogui.typewrite(PASSWORD, interval=0.05)
    pyautogui.press("enter", presses=3)

    print("[*] 로그인 완료")
    time.sleep(5)


def _get_tims_hwnd() -> int:
    found = [0]

    def _callback(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "ThunderRT6MDIForm":
            found[0] = hwnd
            return False
        return True

    _user32.EnumWindows(_WNDENUMPROC(_callback), 0)
    if not found[0]:
        abort("TIMS 메인 창을 찾을 수 없습니다.")
    return found[0]


# 공정품질조회 MDI 자식 창 내 필드 위치 (TIMS 메인 창 기준 오프셋)
# 실제 위치와 다르면 아래 두 값을 조정
_FIELD_OFFSET_Y = 169   # MDI 클라이언트 시작(+43) + 조회창 검색행(+119)
_MONTH_OFFSET_X = 165
_DAY_OFFSET_X   = 230


def set_inquiry_dates():
    today = date.today()
    prev_month = today.month - 1 or 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]
    work_month = f"{prev_year}-{prev_month:02d}"

    hwnd = _get_tims_hwnd()
    rect = ctypes.wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    wx, wy = rect.left, rect.top

    def _clear_and_type(x, y, value):
        _user32.SetForegroundWindow(hwnd)
        pyautogui.click(x, y)
        _key.press(_kb.Key.home);  _key.release(_kb.Key.home)
        _key.press(_kb.Key.shift)
        _key.press(_kb.Key.end);   _key.release(_kb.Key.end)
        _key.release(_kb.Key.shift)
        _key.press(_kb.Key.delete); _key.release(_kb.Key.delete)
        _key.type(value)

    _clear_and_type(wx + _MONTH_OFFSET_X, wy + _FIELD_OFFSET_Y, work_month)
    _clear_and_type(wx + _DAY_OFFSET_X,   wy + _FIELD_OFFSET_Y, str(last_day))

    print(f"[*] 조회 기간: {work_month}-01 ~ {work_month}-{last_day:02d}")


def navigate_to_inquiry():
    print("[*] 메뉴 탐색 시작")
    for image_name, label in MENU_STEPS:
        print(f"  -> {label} 클릭 중...")
        if not click_image(image_name, confidence=0.95, timeout=10.0):
            abort(f"'{label}' 단계에서 이미지를 찾지 못했습니다.")
        time.sleep(1.0)
    print("[*] 공정품질조회 화면 진입 완료")


def wait_for_excel(timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for app in xw.apps:
                for book in app.books:
                    if "공정품질" in book.name:
                        print(f"  [✓] 엑셀 열림: {book.name}")
                        return book
        except Exception:
            pass
        time.sleep(1.0)
    abort(f"공정품질 엑셀이 {timeout}초 내에 열리지 않았습니다.")


def extract_quality_data(wb, last_day: int) -> dict:
    ws = wb.sheets[0]

    # 총수량 / 불량수 행 찾기 (B열 텍스트 기준)
    total_row = defect_row = None
    for row in range(1, 20):
        val = str(ws.cells(row, 2).value or "")
        if "총수량" in val:
            total_row = row
        elif "불량수" in val:
            defect_row = row
        if total_row and defect_row:
            break

    if not total_row or not defect_row:
        abort("엑셀에서 총수량/불량수 행을 찾지 못했습니다.")

    # 2행에서 일자(1~last_day) 열 위치 찾기
    day_to_col = {}
    for col in range(1, 60):
        val = ws.cells(2, col).value
        if isinstance(val, (int, float)) and 1 <= int(val) <= 31:
            day_to_col[int(val)] = col

    result = {}
    for day in range(1, last_day + 1):
        col = day_to_col.get(day)
        if not col:
            continue
        total = ws.cells(total_row, col).value or 0
        defect = ws.cells(defect_row, col).value or 0
        if total == 0 and defect == 0:
            continue  # 비작업일 제외
        result[day] = {
            "총수량/2": total / 2,
            "불량수":   defect,
        }

    print(f"[*] 데이터 추출 완료: 작업일 {len(result)}일")
    return result


if __name__ == "__main__":
    setup_esc_abort()
    login()
    navigate_to_inquiry()
    set_inquiry_dates()
    if not click_image("btn_dataInquiry", timeout=10.0):
        abort("조회 버튼을 찾지 못했습니다.")
    time.sleep(3)
    if not click_image("btn_excel", timeout=10.0):
        abort("엑셀 버튼을 찾지 못했습니다.")

    wb = wait_for_excel(timeout=30.0)

    today = date.today()
    prev_month = today.month - 1 or 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]

    data = extract_quality_data(wb, last_day)
    for day, vals in data.items():
        print(f"  {day:2d}일  총수량/2={vals['총수량/2']}  불량수={vals['불량수']}")
