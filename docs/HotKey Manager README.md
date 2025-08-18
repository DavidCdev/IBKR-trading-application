## Hotkey Manager

Application-level keyboard shortcuts for trading actions. Emits PyQt6 signals when a configured key combination is pressed and safely bridges into your async trading methods.

- Code: `utils/hotkey_manager.py`
- Class: `HotkeyManager(QObject)`

---

### Overview

`HotkeyManager` listens for key presses in your PyQt6 app and triggers trading actions via signals. It supports platform-aware modifiers:

- Windows/Linux: uses `Ctrl`
- macOS: uses `Cmd` (Qt Meta)

Important: This is application-level handling (not OS-global). Your app window must have focus, and you must forward key events to the manager (see Usage).

---

### Hotkeys

- Buy Put: `Ctrl+Alt+P` (macOS: `Cmd+Alt+P`)
- Buy Call: `Ctrl+Alt+C` (macOS: `Cmd+Alt+C`)
- Sell Position (chase): `Ctrl+Alt+X` (macOS: `Cmd+Alt+X`)
- Panic Button: `Ctrl+Alt+F` (macOS: `Cmd+Alt+F`)

Programmatic info:

```python
hotkeys.get_hotkey_info()
# => { 'buy_call': 'Ctrl+Alt+C' | 'Cmd+Alt+C', ... }
```

---

### Signals

Emitted when the corresponding hotkey is detected:

- `hotkey_buy_call()`
- `hotkey_buy_put()`
- `hotkey_sell_position()`
- `hotkey_panic_button()`

These are wired by default to call your `trading_manager` methods using asyncio (see Integration).

---

### Usage

Minimal integration with a `QMainWindow`:

```python
from PyQt6.QtWidgets import QApplication, QMainWindow
from utils.hotkey_manager import HotkeyManager

class MainWindow(QMainWindow):
    def __init__(self, trading_manager):
        super().__init__()
        self.trading_manager = trading_manager
        self.hotkeys = HotkeyManager(self.trading_manager)
        self.hotkeys.start()

    def keyPressEvent(self, event):
        # Forward to HotkeyManager first so it can accept() when matched
        self.hotkeys.keyPressEvent(event)
        if not event.isAccepted():
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.hotkeys.stop()
        super().closeEvent(event)

# ... create QApplication, TradingManager, and show MainWindow ...
```

Notes:

- The manager is a `QObject`; forwarding the window's `keyPressEvent` is required because `HotkeyManager` is not a widget.
- If you have nested widgets handling shortcuts, ensure your main window still receives unhandled key events (or forward from those widgets as well).

---

### Integration with `TradingManager`

`HotkeyManager` asynchronously invokes these coroutines on your `trading_manager`:

- `await trading_manager.place_buy_order("CALL")`
- `await trading_manager.place_buy_order("PUT")`
- `await trading_manager.place_sell_order(use_chase_logic=True)`
- `await trading_manager.panic_button()`

It detects the current asyncio loop:

- If a loop is running, it schedules the coroutine with `asyncio.create_task(...)`.
- If not, it runs the coroutine to completion with `loop.run_until_complete(...)`.

---

### Platform behavior

- Modifier key is chosen at runtime: `Ctrl` on Windows/Linux, `Cmd` on macOS.
- macOS uses Qt's Meta modifier (`Qt.KeyboardModifier.MetaModifier`).
- This does not register OS-global hotkeys; it only works when your app has focus.

---

### Extending hotkeys

To add or change shortcuts:

1. Update `keyPressEvent(...)` to check your new combination
2. Extend `_is_hotkey_combination(...)` if needed (supports `Ctrl`/`Alt`/`Cmd` + single letter)
3. Add a signal and a corresponding `_execute_*` handler

Example addition:

```python
elif self._is_hotkey_combination(key, modifiers, "Ctrl+Alt+N"):
    self.hotkey_new_action.emit()
    event.accept(); return
```

---

### Troubleshooting

- Hotkeys don’t fire: ensure your window has focus and that you forward `keyPressEvent` to `HotkeyManager` before calling `super()`.
- Another widget is capturing the keys: disable/override conflicting shortcuts or forward events from that widget.
- Nothing happens on trigger: confirm your `trading_manager` exposes the async methods listed above.
- Event loop errors: make sure only one asyncio event loop is active; let the manager schedule tasks when the loop is running.

---

### Dependencies

- Python 3.10+
- PyQt6

---

### License

Proprietary – internal use unless specified otherwise.

#