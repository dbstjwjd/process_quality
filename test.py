from pynput import mouse, keyboard

def find_coordinates():
    print("클릭한 위치 좌표를 출력합니다. ESC로 종료.")

    def on_click(x, y, button, pressed):
        if pressed:
            print(f"X: {x}, Y: {y}")

    def on_press(key):
        if key == keyboard.Key.esc:
            print("종료!")
            mouse_listener.stop()
            return False

    mouse_listener = mouse.Listener(on_click=on_click)
    mouse_listener.start()

    with keyboard.Listener(on_press=on_press) as kb_listener:
        kb_listener.join()

find_coordinates()