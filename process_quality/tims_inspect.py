"""
TIMS(종합생산시스템) UI 요소 탐색 스크립트
VB6 앱이므로 win32 + uia 두 백엔드 모두 시도
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pywinauto import Desktop, Application
from pywinauto.findwindows import ElementNotFoundError


TIMS_KEYWORDS = ["TIMS", "tims", "생산", "IDIS", "종합", "로그인", "로그온", "Logon"]


def find_tims_windows():
    desktop = Desktop(backend="win32")
    all_windows = desktop.windows()

    print("=== 현재 열린 창 목록 ===")
    candidates = []
    for w in all_windows:
        try:
            title = w.window_text()
            class_name = w.class_name()
            print(f"  제목: {repr(title):<55}  클래스: {class_name}")
            if any(k in title for k in TIMS_KEYWORDS):
                candidates.append((w.handle, title, class_name))
        except Exception:
            pass
    print()
    return candidates


def dump_controls_win32(handle, indent=0, max_depth=8):
    """win32 백엔드로 컨트롤 트리 출력"""
    from pywinauto import Application
    try:
        app = Application(backend="win32").connect(handle=handle)
        dlg = app.window(handle=handle)
    except Exception as e:
        print(f"  연결 실패: {e}")
        return

    def _dump(ctrl, depth):
        if depth > max_depth:
            return
        prefix = "  " * depth
        try:
            ctype = ctrl.friendly_class_name()
            name = ctrl.window_text()
            ctrl_id = ctrl.control_id()
            rect = ctrl.rectangle()
            marker = " <-- [클릭 가능]" if "Button" in ctype or "Static" == ctype else ""
            print(f"{prefix}[{ctype}] 이름={repr(name):<30} ID={ctrl_id}  rect={rect}{marker}")
        except Exception as ex:
            print(f"{prefix}(읽기 실패: {ex})")
            return
        try:
            for child in ctrl.children():
                _dump(child, depth + 1)
        except Exception:
            pass

    print(f"\n--- win32 컨트롤 트리 ---")
    _dump(dlg, 0)


def list_buttons_win32(handle):
    """win32 백엔드로 버튼 목록만 출력"""
    from pywinauto import Application
    try:
        app = Application(backend="win32").connect(handle=handle)
        dlg = app.window(handle=handle)
    except Exception as e:
        print(f"  연결 실패: {e}")
        return

    print("\n=== 버튼 목록 (win32) ===")

    def _collect_buttons(ctrl, results):
        try:
            ctype = ctrl.friendly_class_name()
            if "Button" in ctype:
                name = ctrl.window_text()
                enabled = ctrl.is_enabled()
                visible = ctrl.is_visible()
                ctrl_id = ctrl.control_id()
                rect = ctrl.rectangle()
                results.append((name, enabled, visible, ctrl_id, rect))
        except Exception:
            pass
        try:
            for child in ctrl.children():
                _collect_buttons(child, results)
        except Exception:
            pass

    buttons = []
    _collect_buttons(dlg, buttons)

    if not buttons:
        print("  버튼 없음 (내부 창을 열면 더 나타날 수 있습니다)")
    for name, enabled, visible, ctrl_id, rect in buttons:
        print(f"  버튼명={repr(name):<30} 활성={enabled}  보임={visible}  ID={ctrl_id}  위치={rect}")


def demo_click_by_name(handle, button_name):
    """버튼 이름으로 클릭 가능 여부 확인 (클릭하지 않음)"""
    from pywinauto import Application
    print(f"\n=== '{button_name}' 버튼 탐색 ===")
    try:
        app = Application(backend="win32").connect(handle=handle)
        dlg = app.window(handle=handle)
        btn = dlg.child_window(title=button_name, class_name="ThunderRT6CommandButton")
        if btn.exists():
            print(f"  찾음: 활성={btn.is_enabled()}, 위치={btn.rectangle()}")
            print(f"  -> btn.click_input() 으로 클릭 가능")
        else:
            print(f"  '{button_name}' 버튼 없음")
    except Exception as e:
        print(f"  오류: {e}")


def main():
    candidates = find_tims_windows()

    if not candidates:
        print("[!] TIMS 관련 창을 찾지 못했습니다. 프로그램을 먼저 실행하세요.")
        sys.exit(1)

    for handle, title, class_name in candidates:
        print(f"\n{'='*65}")
        print(f"[창] {repr(title)}")
        print(f"     클래스: {class_name}  핸들: {handle}")
        print(f"{'='*65}")

        dump_controls_win32(handle, max_depth=8)
        list_buttons_win32(handle)

        # 원하는 버튼 이름으로 클릭 가능 여부 확인 예시
        # demo_click_by_name(handle, "조회")
        # demo_click_by_name(handle, "닫기")
        # demo_click_by_name(handle, "확인")


if __name__ == "__main__":
    main()
