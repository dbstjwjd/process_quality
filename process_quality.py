import calendar
import ctypes
import ctypes.wintypes
import os
import re
import time
import sys
from datetime import date
from pathlib import Path

import psutil
import xlwings as xw
import pyautogui
from pynput import keyboard as _kb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import numpy as np
from scipy import stats
from matplotlib.patches import FancyBboxPatch

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

_key = _kb.Controller()

_user32 = ctypes.windll.user32
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

EXE_PATH = r"C:\Users\Public\Desktop\종합생산시스템.lnk"
USERNAME = "pjys0520"
PASSWORD = "1360"
WAIT_FOR_WINDOW = 5
IMG_DIR    = Path(__file__).parent / "images"
CHARTS_DIR = Path(__file__).parent / "charts"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

MENU_STEPS = [
    ("btn_quality",  "품질관리"),
    ("btn_status",   "공정품질현황"),
    ("btn_inquiry",  "공정품질조회"),
]

CAMERA_EXCEL_PATH = r"C:\Users\jungsunghun\Desktop\CAMERA공정능력분석26년.xlsx"
DNVR_EXCEL_PATH   = r"C:\Users\jungsunghun\Desktop\DNVR공정능력분석26년.xlsx"
STAMP_IMAGE_PATH  = str(IMG_DIR / "stamp.png")
_CM_TO_PT   = 28.3465
STAMP_W_PT  = 5.86 * _CM_TO_PT   # 5.86 cm
STAMP_H_PT  = 2.66 * _CM_TO_PT   # 2.66 cm

EDIT_DELAY = 0.25  # 셀 편집 후 대기 시간(초) — 시각적으로 확인 가능한 속도


def _jump(sheet, row: int, col: int, delay: float = EDIT_DELAY):
    """해당 셀로 Excel 창을 스크롤하고 선택 상태로 표시."""
    try:
        sheet.activate()
        sheet.cells(row, col).api.Activate()
    except Exception:
        pass
    if delay > 0:
        time.sleep(delay)


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


_EXCEL_KEYWORDS = ["공정품질", "quality", "ipc"]

def wait_for_excel(timeout: float = 60.0):
    deadline = time.time() + timeout
    last_names: set[str] = set()

    while time.time() < deadline:
        try:
            current_names: set[str] = set()
            for app in xw.apps:
                for book in app.books:
                    current_names.add(book.name)
                    if any(kw in book.name.lower() for kw in _EXCEL_KEYWORDS):
                        print(f"  [✓] 엑셀 열림: {book.name}")
                        return book

            # 새로 열린 파일명 출력 (디버그)
            new_names = current_names - last_names
            if new_names:
                print(f"  [엑셀 감지] 현재 열린 파일: {', '.join(current_names)}")
            last_names = current_names
        except Exception:
            pass
        time.sleep(1.0)

    abort(f"엑셀이 {timeout}초 내에 열리지 않았습니다. "
          f"(찾은 파일: {', '.join(last_names) or '없음'})")


def extract_quality_data(wb, last_day: int) -> dict:
    ws = wb.sheets[0]

    # B열에서 행 레이블 탐색 (1~25행)
    # 생산수 > 총수량 순으로 우선순위 적용 (샘플 사이즈 = 생산수 ÷ 2)
    prod_row = defect_row = None
    for row in range(1, 25):
        val = str(ws.cells(row, 2).value or "")
        if "생산수" in val and prod_row is None:
            prod_row = row
        elif "총수량" in val and prod_row is None:
            prod_row = row
        if "불량수" in val and defect_row is None:
            defect_row = row

    if not prod_row or not defect_row:
        # 찾지 못한 경우 B열 전체 레이블 출력 후 중단
        print("[!] 발견된 B열 레이블:")
        for row in range(1, 25):
            v = ws.cells(row, 2).value
            if v:
                print(f"    row {row:2d}: {v}")
        abort("엑셀에서 생산수(총수량)/불량수 행을 찾지 못했습니다.")

    # 2행에서 일자(1~last_day) 열 위치 찾기
    day_to_col = {}
    for col in range(1, 70):
        val = ws.cells(2, col).value
        if isinstance(val, (int, float)) and 1 <= int(val) <= 31:
            day_to_col[int(val)] = col

    print(f"[*] 생산수 행={prod_row}, 불량수 행={defect_row}, 일자 열 수={len(day_to_col)}")

    result = {}
    for day in range(1, last_day + 1):
        col = day_to_col.get(day)
        if not col:
            continue
        prod   = ws.cells(prod_row,   col).value or 0
        defect = ws.cells(defect_row, col).value or 0
        if prod == 0 and defect == 0:
            continue  # 비작업일 제외
        result[day] = {
            "총수량/2": int(prod / 2 + 0.5),
            "불량수":   defect,
        }

    # 첫 번째 작업일 값 출력으로 검증
    if result:
        first = sorted(result)[0]
        print(f"[*] 샘플 확인 ({first}일): 생산수={result[first]['총수량/2']*2:.0f}, "
              f"샘플사이즈={result[first]['총수량/2']:.1f}, "
              f"불량수={result[first]['불량수']}, "
              f"불량률={result[first]['불량수']/result[first]['총수량/2']*100:.2f}%")

    print(f"[*] 데이터 추출 완료: 작업일 {len(result)}일")
    return result


def generate_p_chart(data: dict, year: int, month: int, product_name: str = "DNVR",
                     output_path: str = None, x_labels: list = None, title: str = None):
    days = sorted(data.keys())
    if not days:
        print("[!] 데이터가 없어 그래프를 생성할 수 없습니다.")
        return

    # ── 통계 계산 ─────────────────────────────────────────────────────
    n_arr = np.array([data[d]["총수량/2"] for d in days], dtype=float)
    d_arr = np.array([data[d]["불량수"]   for d in days], dtype=float)
    k = len(days)

    p_bar   = d_arr.sum() / n_arr.sum()
    pct_bar = p_bar * 100
    p_i     = d_arr / n_arr
    pct_i   = p_i * 100

    se_i    = np.sqrt(p_bar * (1 - p_bar) / n_arr)
    ucl_i   = (p_bar + 3 * se_i) * 100
    lcl_i   = np.maximum((p_bar - 3 * se_i) * 100, 0.0)
    ucl_avg = ucl_i.mean()
    lcl_avg = lcl_i.mean()

    cum_pct     = np.cumsum(d_arr) / np.cumsum(n_arr) * 100
    sample_nums = np.arange(1, k + 1)

    z95       = stats.norm.ppf(0.975)
    se_tot    = np.sqrt(p_bar * (1 - p_bar) / n_arr.sum())
    lower_pct = max((p_bar - z95 * se_tot) * 100, 0.0)
    upper_pct = (p_bar + z95 * se_tot) * 100
    ppm_def   = p_bar * 1_000_000
    ppm_lower = max((p_bar - z95 * se_tot) * 1_000_000, 0.0)
    ppm_upper = (p_bar + z95 * se_tot) * 1_000_000

    _clamp          = lambda v: max(min(v, 1 - 1e-9), 1e-9)
    process_z       = stats.norm.ppf(1 - _clamp(p_bar))
    process_z_lower = stats.norm.ppf(1 - _clamp(p_bar + z95 * se_tot))
    process_z_upper = stats.norm.ppf(1 - _clamp(max(p_bar - z95 * se_tot, 1e-9)))

    # ── 색상 팔레트 ───────────────────────────────────────────────────
    BLUE    = '#2563EB'
    BLUE_D  = '#1E3A8A'
    BLUE_LT = '#DBEAFE'
    RED     = '#DC2626'
    GREEN   = '#16A34A'
    PURPLE  = '#7C3AED'
    GRAY    = '#6B7280'
    BLACK   = '#111827'
    CARD_BD = '#E5E7EB'

    # ── 피겨 & 레이아웃 ───────────────────────────────────────────────
    fig = plt.figure(figsize=(24, 10), facecolor='#ffffff')
    fig.suptitle(
        title if title else f"{year}년 {month:02d}월  {product_name}  공정능력현황",
        fontsize=20, fontweight='bold', color=BLACK, y=0.99,
    )

    outer  = gridspec.GridSpec(2, 1, figure=fig,
                               left=0.05, right=0.98, top=0.93, bottom=0.10,
                               hspace=0.60)
    bot_gs = gridspec.GridSpecFromSubplotSpec(
        1, 4, subplot_spec=outer[1],
        wspace=0.35, width_ratios=[4, 2.5, 3, 3],
    )

    ax_p    = fig.add_subplot(outer[0])
    ax_cum  = fig.add_subplot(bot_gs[0, 0])
    ax_stat = fig.add_subplot(bot_gs[0, 1])
    ax_rate = fig.add_subplot(bot_gs[0, 2])
    ax_hist = fig.add_subplot(bot_gs[0, 3])

    # ── 공통 스타일 ───────────────────────────────────────────────────
    def _style(ax, title=''):
        ax.set_facecolor('#ffffff')
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_color(CARD_BD)
            sp.set_linewidth(0.8)
        ax.tick_params(labelsize=13, colors=GRAY, length=4, pad=5)
        if title:
            ax.set_title(title, fontsize=18, fontweight='bold',
                         color=BLACK, loc='left', pad=10)

    for ax in (ax_p, ax_cum, ax_rate, ax_hist):
        _style(ax)

    x_step        = 5 if k > 21 else 1
    x_ticks       = sample_nums[::x_step]
    tick_labels   = ([x_labels[i - 1] for i in x_ticks] if x_labels else None)

    # ── P Chart ───────────────────────────────────────────────────────
    _style(ax_p, 'P Chart')

    ooc = (pct_i > ucl_i) | ((lcl_i > 0) & (pct_i < lcl_i))

    ax_p.fill_between(sample_nums, lcl_i, ucl_i,
                      alpha=0.10, color=BLUE, step='mid')
    ax_p.step(sample_nums, ucl_i, color=RED,   linewidth=1.2, where='mid')
    ax_p.step(sample_nums, lcl_i, color=RED,   linewidth=1.2, where='mid')
    ax_p.axhline(pct_bar,          color=GREEN, linewidth=1.8)
    ax_p.plot(sample_nums, pct_i,  color=BLUE,  linewidth=2.2, zorder=3)
    ax_p.scatter(sample_nums[~ooc], pct_i[~ooc],
                 color=BLUE_D, s=60, zorder=4, edgecolors='white', linewidths=1.5)
    if ooc.any():
        ax_p.scatter(sample_nums[ooc], pct_i[ooc],
                     color=RED, s=75, zorder=5, marker='s',
                     edgecolors='white', linewidths=1.5)

    ax_p.set_xlim(0.3, k + 0.7)
    ax_p.set_xticks(x_ticks)
    if tick_labels:
        ax_p.set_xticklabels(tick_labels)
    ax_p.set_xlabel('Sample',      fontsize=14, fontweight='bold', color=GRAY, labelpad=6)
    ax_p.set_ylabel('% Defective', fontsize=14, fontweight='bold', color=GRAY, labelpad=6)
    ax_p.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:.3f}%'))
    ax_p.text(
        0.0, -0.16,
        f'UCL = {ucl_avg:.5f}      P̅ = {pct_bar:.5f}      LCL = {lcl_avg:.5f}',
        transform=ax_p.transAxes, fontsize=12, color=GRAY, va='top',
    )

    # ── Cumulative % Defective ────────────────────────────────────────
    _style(ax_cum, 'Cumulative\n% Defective')
    ax_cum.fill_between(sample_nums, pct_bar, cum_pct, alpha=0.12, color=PURPLE)
    ax_cum.axhline(pct_bar, color=GREEN,  linewidth=1.8)
    ax_cum.plot(sample_nums, cum_pct, color=PURPLE, linewidth=2.0, zorder=3)
    ax_cum.scatter(sample_nums, cum_pct, color=RED, s=45, zorder=4,
                   edgecolors='white', linewidths=1.5)
    ax_cum.set_xlim(0.3, k + 0.7)
    ax_cum.set_xticks(x_ticks)
    if tick_labels:
        ax_cum.set_xticklabels(tick_labels)
    ax_cum.set_xlabel('Sample',      fontsize=14, fontweight='bold', color=GRAY, labelpad=6)
    ax_cum.set_ylabel('% Defective', fontsize=14, fontweight='bold', color=GRAY, labelpad=6)

    # ── Summary Stats 카드 ────────────────────────────────────────────
    ax_stat.axis('off')
    ax_stat.add_patch(FancyBboxPatch(
        (0.0, 0.0), 1.0, 1.0,
        boxstyle='round,pad=0.03',
        linewidth=1.0, edgecolor=CARD_BD, facecolor='#F9FAFB',
        transform=ax_stat.transAxes, clip_on=False,
    ))

    def _row(y, label, value, lc=GRAY, vc=BLACK):
        ax_stat.text(0.07, y, label, transform=ax_stat.transAxes,
                     fontsize=13, va='top', color=lc, fontweight='bold')
        ax_stat.text(0.96, y, value, transform=ax_stat.transAxes,
                     fontsize=13, va='top', ha='right', color=vc)

    def _sep(y):
        ax_stat.plot([0.05, 0.95], [y, y], transform=ax_stat.transAxes,
                     color=CARD_BD, linewidth=0.8, clip_on=False)

    ax_stat.text(0.5, 0.97, 'Summary Stats', transform=ax_stat.transAxes,
                 fontsize=15, fontweight='bold', va='top', ha='center', color=BLACK)
    ax_stat.text(0.5, 0.90, '95% Confidence', transform=ax_stat.transAxes,
                 fontsize=12, va='top', ha='center', color=GRAY)
    _sep(0.855)

    entries = [
        (0.82, '% Defective', f'{pct_bar:.3f}%',          BLUE,   BLACK),
        (0.75, 'Lower CI',    f'{lower_pct:.3f}%',         GRAY,   BLACK),
        (0.68, 'Upper CI',    f'{upper_pct:.3f}%',         GRAY,   BLACK),
        (0.61, None, None, None, None),
        (0.57, 'PPM Def',     f'{ppm_def:,.0f}',           PURPLE, BLACK),
        (0.50, 'Lower CI',    f'{ppm_lower:,.0f}',         GRAY,   BLACK),
        (0.43, 'Upper CI',    f'{ppm_upper:,.0f}',         GRAY,   BLACK),
        (0.36, None, None, None, None),
        (0.32, 'Process Z',   f'{process_z:.4f}',          GREEN,  BLACK),
        (0.25, 'Lower CI',    f'{process_z_lower:.4f}',    GRAY,   BLACK),
        (0.18, 'Upper CI',    f'{process_z_upper:.4f}',    GRAY,   BLACK),
    ]
    for y, label, value, lc, vc in entries:
        if label is None:
            _sep(y + 0.02)
        else:
            _row(y, label, value, lc, vc)

    # ── Rate of Defectives ────────────────────────────────────────────
    _style(ax_rate, 'Rate of\nDefectives')
    y_mg = (pct_i.max() - pct_i.min()) * 0.35 or 0.1
    ax_rate.set_ylim(max(pct_i.min() - y_mg, 0), pct_i.max() + y_mg)
    ax_rate.axhline(pct_bar,   color=GREEN, linewidth=1.8)
    ax_rate.axhline(upper_pct, color=RED,   linewidth=1.0, linestyle='--', alpha=0.75)
    ax_rate.axhline(lower_pct, color=RED,   linewidth=1.0, linestyle='--', alpha=0.75)
    ax_rate.scatter(n_arr, pct_i, color=BLUE_D, s=65, zorder=4,
                    edgecolors='white', linewidths=1.5)
    ax_rate.set_xlabel('Sample Size', fontsize=14, fontweight='bold', color=GRAY, labelpad=6)
    ax_rate.set_ylabel('% Defective', fontsize=14, fontweight='bold', color=GRAY, labelpad=6)

    # ── Histogram ─────────────────────────────────────────────────────
    _style(ax_hist, 'Distribution')
    n_bins = max(5, min(10, k // 3))
    counts, _, bars = ax_hist.hist(pct_i, bins=n_bins,
                                   color=BLUE_LT, edgecolor='white', linewidth=1.0)
    bars[int(np.argmax(counts))].set_facecolor(BLUE)
    ax_hist.axvline(pct_bar, color=GREEN, linewidth=1.8, zorder=5)
    ax_hist.set_xlabel('% Defective', fontsize=14, fontweight='bold', color=GRAY, labelpad=6)
    ax_hist.set_ylabel('Frequency',   fontsize=14, fontweight='bold', color=GRAY, labelpad=6)

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#ffffff')
        print(f"[*] 그래프 저장: {output_path}")
    else:
        plt.show()
    plt.close()


def _ppk_grade(ppk: float) -> int:
    if ppk >= 1.67:  return 0
    if ppk >= 1.33:  return 1
    if ppk >= 1.00:  return 2
    if ppk >= 0.67:  return 3
    return 4


def _calc_process_stats(data: dict) -> tuple[float, float, int]:
    """(sigma_level, ppk, grade) 반환. sigma_level = process_z + 1.5, ppk = sigma_level / 3."""
    n_arr = np.array([data[d]["총수량/2"] for d in sorted(data)], dtype=float)
    d_arr = np.array([data[d]["불량수"]   for d in sorted(data)], dtype=float)
    p_bar = d_arr.sum() / n_arr.sum()
    _clamp = lambda v: max(min(v, 1 - 1e-9), 1e-9)
    process_z   = stats.norm.ppf(1 - _clamp(p_bar))
    sigma_level = process_z + 1.5
    ppk         = sigma_level / 3
    return sigma_level, ppk, _ppk_grade(ppk)


def _rgb(r, g, b) -> int:
    return r + g * 256 + b * 65536


def _write_data_table(sheet, data: dict):
    days = sorted(data.keys())
    if not days:
        return

    TABLE_ROW    = 20
    DATE_ROW     = TABLE_ROW + 4          # row 24: 날짜 셀
    n            = len(days)
    new_last_col = n + 2                  # 레이블(1) + 작업일(n) + 합계(1)

    # 기존 표 마지막 열 탐색 (B열부터 빈 셀 나올 때까지)
    old_last_col = 2
    while sheet.cells(TABLE_ROW, old_last_col).value is not None:
        old_last_col += 1
    old_last_col -= 1

    # 날짜 값 미리 읽기 (열 조정 전)
    date_val = sheet.cells(DATE_ROW, old_last_col).value

    # ── 열 수 조정 ────────────────────────────────────────────────────
    if old_last_col > new_last_col:
        # 초과 열 삭제 (전체 열 삭제, 왼쪽으로 당김)
        sheet.range(
            sheet.cells(1, new_last_col + 1),
            sheet.cells(1, old_last_col),
        ).api.EntireColumn.Delete()
        print(f"[*] {old_last_col - new_last_col}열 삭제")

    elif new_last_col > old_last_col:
        # 부족한 열 삽입 (old 합계 열 앞에 삽입 → 합계·날짜가 오른쪽으로 밀림)
        cols_to_add = new_last_col - old_last_col
        sheet.range(
            sheet.cells(1, old_last_col),
            sheet.cells(1, old_last_col + cols_to_add - 1),
        ).api.EntireColumn.Insert()
        print(f"[*] {cols_to_add}열 삽입")
        # 삽입 후 날짜는 이미 new_last_col 위치로 밀렸으므로 재읽기
        date_val = sheet.cells(DATE_ROW, new_last_col).value

    # ── 데이터 계산 ───────────────────────────────────────────────────
    prod_vals   = [int(data[d]["총수량/2"]) for d in days]
    defect_vals = [int(data[d]["불량수"])   for d in days]
    rate_vals   = [data[d]["불량수"] / data[d]["총수량/2"] if data[d]["총수량/2"] > 0 else 0
                   for d in days]
    total_prod   = sum(prod_vals)
    total_defect = sum(defect_vals)
    total_rate   = total_defect / total_prod if total_prod > 0 else 0

    # ── 값 쓰기 ───────────────────────────────────────────────────────
    for c_i in range(n):
        sheet.cells(TABLE_ROW,     2 + c_i).value = c_i + 1   # 구분
        sheet.cells(TABLE_ROW + 1, 2 + c_i).value = prod_vals[c_i]
        sheet.cells(TABLE_ROW + 2, 2 + c_i).value = defect_vals[c_i]
        rc = sheet.cells(TABLE_ROW + 3, 2 + c_i)
        rc.value = rate_vals[c_i]
        rc.api.NumberFormat = "0.0%"
        _jump(sheet, TABLE_ROW + 1, 2 + c_i)

    sheet.cells(TABLE_ROW,     new_last_col).value = "합계"
    sheet.cells(TABLE_ROW + 1, new_last_col).value = total_prod
    sheet.cells(TABLE_ROW + 2, new_last_col).value = total_defect
    tc = sheet.cells(TABLE_ROW + 3, new_last_col)
    tc.value = total_rate
    tc.api.NumberFormat = "0.0%"
    _jump(sheet, TABLE_ROW + 1, new_last_col)

    # 합계 열 너비 7.75 고정
    sheet.cells(TABLE_ROW, new_last_col).api.EntireColumn.ColumnWidth = 7.75

    # 날짜를 합계 열 바로 아래(row 24)에 배치, 오른쪽 정렬
    if date_val is not None:
        date_cell = sheet.cells(DATE_ROW, new_last_col)
        date_cell.value = date_val
        date_cell.api.HorizontalAlignment = -4152  # xlRight

    print(f"[*] 데이터 테이블 업데이트 완료: A{TABLE_ROW} ({n}일 + 합계)")


def _safe_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _read_monthly_sheet_daily_data(sheet) -> list:
    """월별 시트 테이블(row20~)에서 일별 (생산수, 불량수) 리스트 반환."""
    TABLE_ROW = 20
    result = []
    for col in range(2, 100):
        구분_val = sheet.cells(TABLE_ROW, col).value
        if 구분_val is None or str(구분_val).strip() == "합계":
            break
        prod   = _safe_int(sheet.cells(TABLE_ROW + 1, col).value)
        defect = _safe_int(sheet.cells(TABLE_ROW + 2, col).value)
        if prod > 0:
            result.append((prod, defect))
    return result


def _read_accum_all_daily_data(wb, year: int, current_month: int) -> dict:
    """1월~current_month 월별 시트에서 일별 데이터를 이어 붙여 반환. generate_p_chart 형식."""
    year_short = str(year)[2:]
    result = {}
    idx = 1
    for m in range(1, current_month + 1):
        candidates = [f"{year_short}년{m}월", f"{year_short}년 {m}월"]
        sheet = next(
            (wb.sheets[n] for n in candidates if n in [s.name for s in wb.sheets]),
            None,
        )
        if sheet is None:
            print(f"[!] '{candidates[0]}' 시트 없음 — 건너뜀")
            continue
        daily = _read_monthly_sheet_daily_data(sheet)
        for prod, defect in daily:
            result[idx] = {"총수량/2": prod, "불량수": defect}
            idx += 1
        print(f"[*] {m}월 일별 {len(daily)}일 읽기 완료")
    return result


def _insert_sheet_images(sheet, chart_path: str, data: dict):
    """차트(A2~row19/합계열)와 작성검토승인 스탬프(합계 직전 4열, row19 하단)를 삽입."""
    n        = len(data)
    last_col = n + 2  # label(1) + days(n) + 합계(1)

    # 기존 이미지 전체 삭제
    shapes = sheet.api.Shapes
    for i in range(shapes.Count, 0, -1):
        shapes.Item(i).Delete()

    # ── 차트 이미지: A2 ~ (row19, last_col열) 꽉 채우기 ──────────────
    if chart_path and Path(chart_path).exists():
        left   = sheet.cells(2, 1).left
        top    = sheet.cells(2, 1).top
        right  = sheet.cells(19, last_col).left + sheet.cells(19, last_col).width
        bottom = sheet.cells(19, last_col).top  + sheet.cells(19, last_col).height
        sheet.api.Shapes.AddPicture(
            Filename=str(chart_path),
            LinkToFile=False, SaveWithDocument=True,
            Left=left, Top=top, Width=right - left, Height=bottom - top,
        )
        _jump(sheet, 2, 1, delay=0.5)
        print(f"[*] 차트 이미지 삽입: A2 ~ (row19, col{last_col})")
    elif chart_path:
        print(f"[!] 차트 파일 없음: {chart_path}")

    # ── 작성/검토/승인 스탬프: 합계 열 우측 끝에 고정 크기로 배치 ─────
    if STAMP_IMAGE_PATH and Path(STAMP_IMAGE_PATH).exists():
        s_right = sheet.cells(1, last_col).left + sheet.cells(1, last_col).width
        s_top   = sheet.cells(1, 1).top
        sheet.api.Shapes.AddPicture(
            Filename=str(STAMP_IMAGE_PATH),
            LinkToFile=False, SaveWithDocument=True,
            Left=s_right - STAMP_W_PT, Top=s_top,
            Width=STAMP_W_PT, Height=STAMP_H_PT,
        )
        print(f"[*] 스탬프 삽입: col{last_col} 우측 끝 / row1 기준  {STAMP_W_PT:.0f}×{STAMP_H_PT:.0f}pt")


def _update_accum_sheet(wb, data: dict, year: int, month: int, accum_data: dict = None):
    year_short = str(year)[2:]
    accum_candidates = [f"{year_short}년 누적", f"{year_short}년누적", "누적"]
    sheet_names = [s.name for s in wb.sheets]

    accum = next((wb.sheets[n] for n in accum_candidates if n in sheet_names), None)
    if accum is None:
        print("[!] 누적 시트를 찾지 못했습니다.")
        return

    # 월별 합계 계산
    prod_total   = sum(int(data[d]["총수량/2"]) for d in data)
    defect_total = sum(int(data[d]["불량수"])   for d in data)
    rate         = defect_total / prod_total if prod_total > 0 else 0
    sigma, ppk, grade = _calc_process_stats(data)

    month_label = f"{month}월"
    accum_label = f"{year_short}년 누계"

    HEADER_ROW = 22  # 표 헤더 행 고정

    # 22행 전체 스캔하여 월 컬럼, 누계 컬럼, 레이블 컬럼 위치 확인
    month_col = accum_col = label_col = None
    for c in range(1, 50):
        v = str(accum.cells(HEADER_ROW, c).value or "").strip()
        if v == month_label and month_col is None:
            month_col = c
        if accum_label in v and accum_col is None:
            accum_col = c
        if v in ("구분", "항목") and label_col is None:
            label_col = c

    if month_col is None:
        print(f"[!] '{month_label}' 열을 찾지 못했습니다. (22행 스캔)")
        # 디버그: 22행 내용 출력
        for c in range(1, 20):
            v = accum.cells(HEADER_ROW, c).value
            if v:
                print(f"    22행 col {c}: {v!r}")
        return

    # 레이블 열에서 행 위치 탐색, 못 찾으면 순서대로 고정 배치
    ORDER = ["생산수", "불량수", "불량율", "시그마", "Ppk", "등급"]
    row_map = {}
    if label_col is not None:
        keywords = {"생산수": "생산수", "불량수": "불량수", "불량율": "불량율",
                    "시그마": "시그마", "Ppk": "Ppk", "등급": "등급"}
        for r in range(HEADER_ROW + 1, HEADER_ROW + 15):
            v = str(accum.cells(r, label_col).value or "")
            for key, lbl in keywords.items():
                if lbl in v and key not in row_map:
                    row_map[key] = r

    # 레이블 매칭이 안 된 항목은 순서(HEADER_ROW+1부터) 기준으로 채움
    for i, key in enumerate(ORDER):
        if key not in row_map:
            row_map[key] = HEADER_ROW + 1 + i

    def _put(row_key, col, value):
        if row_key in row_map and col:
            accum.cells(row_map[row_key], col).value = value

    # 월 열 채우기
    for row_key, col, value in [
        ("생산수", month_col, prod_total),
        ("불량수",  month_col, defect_total),
        ("불량율",  month_col, rate),
        ("시그마",  month_col, round(sigma, 2)),
        ("Ppk",    month_col, round(ppk,   2)),
        ("등급",   month_col, grade),
    ]:
        _put(row_key, col, value)
        if row_key in row_map and col:
            _jump(accum, row_map[row_key], col)

    # 누계 열 갱신 — 월별 시트에서 읽어온 일별 원본 데이터를 합산 (항상 처음부터 재계산)
    if accum_col:
        if accum_data:
            new_prod   = sum(int(v["총수량/2"]) for v in accum_data.values())
            new_defect = sum(int(v["불량수"])   for v in accum_data.values())
        else:
            new_prod   = prod_total
            new_defect = defect_total
        new_rate = new_defect / new_prod if new_prod > 0 else 0

        _clamp = lambda v: max(min(v, 1 - 1e-9), 1e-9)
        pz_cum    = stats.norm.ppf(1 - _clamp(new_rate))
        sigma_cum = pz_cum + 1.5
        ppk_cum   = sigma_cum / 3

        for row_key, value in [
            ("생산수", new_prod),
            ("불량수",  new_defect),
            ("불량율",  new_rate),
            ("시그마",  round(sigma_cum, 2)),
            ("Ppk",    round(ppk_cum,   2)),
            ("등급",   _ppk_grade(ppk_cum)),
        ]:
            _put(row_key, accum_col, value)
            if row_key in row_map:
                _jump(accum, row_map[row_key], accum_col)

        # A1 영역 시그마수준/Ppk/월범위 텍스트 갱신 (누계 기준값으로)
        grade_cum = _ppk_grade(ppk_cum)
        for r in range(1, 6):
            for c in range(1, 30):
                val = accum.cells(r, c).value
                if not isinstance(val, str):
                    continue
                new_val = re.sub(r'시그마수준\s+[\d.]+σ',
                                 f'시그마수준 {sigma_cum:.1f}σ', val)
                new_val = re.sub(r'Ppk\s+[\d.]+-\d+등급',
                                 f'Ppk {ppk_cum:.2f}-{grade_cum}등급', new_val)
                new_val = re.sub(r'\[1월\s*~\s*\d+월\]',
                                 f'[1월 ~ {month}월]', new_val)
                if new_val != val:
                    accum.cells(r, c).value = new_val
        print(f"[*] 누적 시트 A1 영역 갱신: [1월 ~ {month}월]  시그마수준 {sigma_cum:.1f}σ  Ppk {ppk_cum:.2f}-{grade_cum}등급")

    print(f"[*] 누적 시트 '{month_label}' 업데이트 완료  (누계열={'있음' if accum_col else '없음'})")


def update_excel_report(year: int, month: int, excel_path: str, data: dict = None,
                        chart_path: str = None, product_name: str = ""):
    if not excel_path:
        print("[!] 엑셀 경로 미설정 — 건너뜁니다.")
        return

    ref_month      = month - 1 if month > 1 else 12
    ref_year       = year if month > 1 else year - 1
    year_short     = str(year)[2:]
    ref_year_short = str(ref_year)[2:]

    # 시트 이름 후보 (공백 있는/없는 버전 모두 허용)
    ref_candidates   = [f"{ref_year_short}년{ref_month}월", f"{ref_year_short}년 {ref_month}월"]
    accum_candidates = [f"{year_short}년 누적", f"{year_short}년누적", "누적"]
    new_sheet_name   = f"{year_short}년{month}월"

    app = xw.App(visible=True)
    app.api.WindowState = -4137  # xlMaximized
    try:
        wb = app.books.open(excel_path)
        sheet_names = [s.name for s in wb.sheets]
        print(f"[*] 시트 목록: {sheet_names}")

        ref_sheet = next(
            (wb.sheets[n] for n in ref_candidates if n in sheet_names), None
        )
        if ref_sheet is None:
            abort(f"참조 시트를 찾지 못했습니다. 후보: {ref_candidates} / 현재: {sheet_names}")

        accum_sheet = next(
            (wb.sheets[n] for n in accum_candidates if n in sheet_names), None
        )
        if accum_sheet is None:
            abort(f"누적 시트를 찾지 못했습니다. 현재: {sheet_names}")

        # 동일 이름 시트가 이미 있으면 삭제
        if new_sheet_name in sheet_names:
            wb.sheets[new_sheet_name].delete()
            sheet_names = [s.name for s in wb.sheets]
            print(f"[*] 기존 '{new_sheet_name}' 시트 삭제")

        # 참조 시트를 누적 시트 바로 앞에 복사
        ref_sheet.api.Copy(Before=accum_sheet.api)

        # 복사 직후 새로 생긴 시트 이름 확인
        names_after = [s.name for s in wb.sheets]
        added = set(names_after) - set(sheet_names)
        new_sheet = wb.sheets[added.pop() if added else f"{ref_sheet.name} (2)"]
        new_sheet.name = new_sheet_name
        print(f"[*] '{new_sheet_name}' 시트 생성 완료")

        if data:
            _write_data_table(new_sheet, data)
            _insert_sheet_images(new_sheet, chart_path, data)

        # 텍스트 셀에서 월 표기 및 시그마/Ppk 값 갱신
        sigma_z = ppk = grade = None
        if data:
            sigma_z, ppk, grade = _calc_process_stats(data)

        rng  = new_sheet.used_range
        vals = rng.value
        if vals is not None:
            if not isinstance(vals[0], list):
                vals = [vals]
            sr, sc = rng.row, rng.column
            old_text = f"{ref_month}월"
            new_text = f"{month}월"
            for r_i, row in enumerate(vals):
                for c_i, val in enumerate(row):
                    if not isinstance(val, str):
                        continue
                    new_val = val.replace(old_text, new_text)
                    if sigma_z is not None and "시그마수준" in new_val:
                        new_val = re.sub(r'시그마수준\s+[\d.]+σ',
                                         f'시그마수준 {sigma_z:.1f}σ', new_val)
                        new_val = re.sub(r'Ppk\s+[\d.]+-\d+등급',
                                         f'Ppk {ppk:.2f}-{grade}등급', new_val)
                    if new_val != val:
                        new_sheet.cells(sr + r_i, sc + c_i).value = new_val
                        _jump(new_sheet, sr + r_i, sc + c_i, delay=0.1)

        if sigma_z is not None:
            print(f"[*] 시그마수준={sigma_z:.1f}σ  Ppk={ppk:.2f}  {grade}등급")

        if data:
            year_short       = str(year)[2:]
            accum_candidates = [f"{year_short}년 누적", f"{year_short}년누적", "누적"]
            accum_sh = next(
                (wb.sheets[n] for n in accum_candidates if n in [s.name for s in wb.sheets]),
                None,
            )
            accum_data = _read_accum_all_daily_data(wb, year, month) if accum_sh else None
            _update_accum_sheet(wb, data, year, month, accum_data)

            if accum_sh and accum_data:
                accum_name  = f"{product_name}_accum" if product_name else f"p_chart_accum_{year}_{month:02d}"
                accum_chart = str(CHARTS_DIR / f"{accum_name}.png")
                generate_p_chart(
                    accum_data, year, month,
                    product_name or "제품",
                    accum_chart,
                    title=f"{year}년 {product_name}  공정능력현황 [누적 1~{month}월]",
                )

                # 누적 시트 A6:P21에 차트 삽입
                shapes = accum_sh.api.Shapes
                for i in range(shapes.Count, 0, -1):
                    shapes.Item(i).Delete()
                left   = accum_sh.range("A6").left
                top    = accum_sh.range("A6").top
                right  = accum_sh.range("P21").left + accum_sh.range("P21").width
                bottom = accum_sh.range("P21").top  + accum_sh.range("P21").height
                accum_sh.api.Shapes.AddPicture(
                    Filename=accum_chart,
                    LinkToFile=False, SaveWithDocument=True,
                    Left=left, Top=top, Width=right - left, Height=bottom - top,
                )
                print("[*] 누적 차트 삽입: A6:P21")

                # 누적 시트 스탬프 삽입 (P열 우측 끝, 고정 크기)
                if STAMP_IMAGE_PATH and Path(STAMP_IMAGE_PATH).exists():
                    s_right = accum_sh.range("P1").left + accum_sh.range("P1").width
                    s_top   = accum_sh.range("A1").top
                    accum_sh.api.Shapes.AddPicture(
                        Filename=str(STAMP_IMAGE_PATH),
                        LinkToFile=False, SaveWithDocument=True,
                        Left=s_right - STAMP_W_PT, Top=s_top,
                        Width=STAMP_W_PT, Height=STAMP_H_PT,
                    )
                    print(f"[*] 누적 시트 스탬프 삽입: P1 우측 끝  {STAMP_W_PT:.0f}×{STAMP_H_PT:.0f}pt")

        wb.save()
        wb.close()
        print(f"[*] 엑셀 저장 완료: {excel_path}")
    finally:
        try:
            app.quit()
        except Exception:
            pass


def _run_inquiry_and_chart(prev_year: int, prev_month: int, last_day: int,
                            product_name: str, chart_path: str) -> dict:
    if not click_image("btn_dataInquiry", timeout=10.0):
        abort("조회 버튼을 찾지 못했습니다.")
    time.sleep(3)
    if not click_image("btn_excel", timeout=10.0):
        abort("엑셀 버튼을 찾지 못했습니다.")

    wb = wait_for_excel(timeout=30.0)
    data = extract_quality_data(wb, last_day)
    for day, vals in data.items():
        print(f"  {day:2d}일  총수량/2={vals['총수량/2']}  불량수={vals['불량수']}")

    generate_p_chart(data, prev_year, prev_month, product_name, chart_path)
    wb.close()
    print(f"[*] {product_name} 완료")
    return data


if __name__ == "__main__":
    setup_esc_abort()
    login()
    navigate_to_inquiry()
    set_inquiry_dates()

    today = date.today()
    prev_month = today.month - 1 or 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]

    CHARTS_DIR.mkdir(exist_ok=True)
    dnvr_chart   = str(CHARTS_DIR / "DNVR_chart.png")
    camera_chart = str(CHARTS_DIR / "IPC_chart.png")

    # ── DNVR ─────────────────────────────────────────────────────────
    print("[*] DNVR 조회 시작")
    dnvr_data = _run_inquiry_and_chart(
        prev_year, prev_month, last_day,
        product_name="DNVR",
        chart_path=dnvr_chart,
    )
    update_excel_report(prev_year, prev_month, DNVR_EXCEL_PATH, data=dnvr_data, chart_path=dnvr_chart, product_name="DNVR")

    # ── Camera / IPC ─────────────────────────────────────────────────
    print("[*] Camera 항목 선택 중")
    if not click_image("btn_camera", timeout=10.0):
        abort("Camera 선택 버튼을 찾지 못했습니다.")
    time.sleep(1.0)

    set_inquiry_dates()
    camera_data = _run_inquiry_and_chart(
        prev_year, prev_month, last_day,
        product_name="IPC",
        chart_path=camera_chart,
    )
    update_excel_report(prev_year, prev_month, CAMERA_EXCEL_PATH, data=camera_data, chart_path=camera_chart, product_name="IPC")
