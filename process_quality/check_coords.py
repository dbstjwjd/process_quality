"""
마우스를 필드 위에 올려두면 좌표와 TIMS 기준 오프셋을 출력합니다.
Ctrl+C로 종료
"""
import ctypes
import ctypes.wintypes
import time
import pyautogui

_user32 = ctypes.windll.user32
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def get_tims_topleft():
    found = [0]

    def _cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "ThunderRT6MDIForm":
            found[0] = hwnd
            return False
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    if not found[0]:
        return None
    r = ctypes.wintypes.RECT()
    _user32.GetWindowRect(found[0], ctypes.byref(r))
    return r.left, r.top


print("TIMS 공정품질조회 창을 열고, 마우스를 각 필드 위에 올려두세요.")
print("Ctrl+C 로 종료\n")

prev = None
while True:
    try:
        pos = pyautogui.position()
        tims = get_tims_topleft()

        if tims:
            ox = pos.x - tims[0]
            oy = pos.y - tims[1]
            info = f"화면 ({pos.x:4d}, {pos.y:4d})  |  TIMS 오프셋 X={ox:4d}  Y={oy:4d}"
        else:
            info = f"화면 ({pos.x:4d}, {pos.y:4d})  |  TIMS 창 없음"

        if info != prev:
            print(info)
            prev = info

        time.sleep(0.3)
    except KeyboardInterrupt:
        break
