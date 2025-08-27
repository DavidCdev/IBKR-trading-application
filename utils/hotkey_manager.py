import platform
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QMessageBox
from .logger import get_logger

logger = get_logger("HOTKEY_MANAGER")


class HotkeyManager(QObject):
    """
    Global Hotkey Manager for trading commands
    """
    
    # Signals for hotkey events
    hotkey_buy_call = pyqtSignal()
    hotkey_buy_put = pyqtSignal()
    hotkey_sell_position = pyqtSignal()
    hotkey_panic_button = pyqtSignal()
    
    def __init__(self, trading_manager, parent_window=None):
        super().__init__()
        self.trading_manager = trading_manager
        self.parent_window = parent_window
        self.is_active = False
        self._hotkey_shortcuts = {}
        self._global_listener = None
        
        # Platform-specific hotkey handling
        self.system = platform.system().lower()
        if self.system == "darwin":  # macOS
            self.modifier_key = "Cmd"
        else:  # Windows/Linux
            self.modifier_key = "Ctrl"
        
        logger.info(f"Hotkey Manager initialized for {self.system} with modifier key: {self.modifier_key}")
    
    def start(self):
        """Start hotkey monitoring"""
        try:
            self._setup_hotkeys()
            self.is_active = True
            logger.info("Hotkey Manager started")
        except Exception as e:
            logger.error(f"Error starting Hotkey Manager: {e}")
    
    def stop(self):
        """Stop hotkey monitoring"""
        try:
            self._cleanup_hotkeys()
            self.is_active = False
            logger.info("Hotkey Manager stopped")
        except Exception as e:
            logger.error(f"Error stopping Hotkey Manager: {e}")
    
    def _setup_hotkeys(self):
        """Setup global hotkeys"""
        try:
            # Connect signals to trading manager methods
            self.hotkey_buy_call.connect(self._execute_buy_call)
            self.hotkey_buy_put.connect(self._execute_buy_put)
            self.hotkey_sell_position.connect(self._execute_sell_position)
            self.hotkey_panic_button.connect(self._execute_panic_button)
            
            # Setup platform-specific hotkey registration
            if self.system == "darwin":
                self._setup_macos_hotkeys()
            else:
                self._setup_windows_linux_hotkeys()
                
        except Exception as e:
            logger.error(f"Error setting up hotkeys: {e}")
    
    def _setup_macos_hotkeys(self):
        """Setup system-wide hotkeys for macOS using Command key"""
        try:
            # Use pynput's global hotkeys (requires Accessibility permission)
            try:
                from pynput import keyboard
            except Exception as import_error:
                logger.error(f"pynput is required for global hotkeys on macOS: {import_error}")
                return

            hotkeys = {
                '<cmd>+<alt>+p': lambda: self.hotkey_buy_put.emit(),
                '<cmd>+<alt>+c': lambda: self.hotkey_buy_call.emit(),
                '<cmd>+<alt>+x': lambda: self.hotkey_sell_position.emit(),
                '<cmd>+<alt>+f': lambda: self.hotkey_panic_button.emit(),
            }

            # Stop any existing listener first
            if self._global_listener is not None:
                try:
                    self._global_listener.stop()
                except Exception:
                    pass

            self._global_listener = keyboard.GlobalHotKeys(hotkeys)
            self._global_listener.start()

            logger.info("macOS global hotkey setup completed (system-wide)")
            
        except Exception as e:
            logger.error(f"Error setting up macOS hotkeys: {e}")
    
    def _setup_windows_linux_hotkeys(self):
        """Setup system-wide hotkeys for Windows/Linux using Ctrl key"""
        try:
            # Use pynput's global hotkeys
            try:
                from pynput import keyboard
            except Exception as import_error:
                logger.error(f"pynput is required for global hotkeys on Windows/Linux: {import_error}")
                return

            hotkeys = {
                '<ctrl>+<alt>+p': lambda: self.hotkey_buy_put.emit(),
                '<ctrl>+<alt>+c': lambda: self.hotkey_buy_call.emit(),
                '<ctrl>+<alt>+x': lambda: self.hotkey_sell_position.emit(),
                '<ctrl>+<alt>+f': lambda: self.hotkey_panic_button.emit(),
            }

            # Stop any existing listener first
            if self._global_listener is not None:
                try:
                    self._global_listener.stop()
                except Exception:
                    pass

            self._global_listener = keyboard.GlobalHotKeys(hotkeys)
            self._global_listener.start()

            logger.info("Windows/Linux global hotkey setup completed (system-wide)")
            
        except Exception as e:
            logger.error(f"Error setting up Windows/Linux hotkeys: {e}")
    
    def _cleanup_hotkeys(self):
        """Cleanup hotkey registrations"""
        try:
            # Disconnect signals
            self.hotkey_buy_call.disconnect()
            self.hotkey_buy_put.disconnect()
            self.hotkey_sell_position.disconnect()
            self.hotkey_panic_button.disconnect()
            
            # Stop global listener if running
            if self._global_listener is not None:
                try:
                    self._global_listener.stop()
                except Exception as stop_error:
                    logger.warning(f"Error stopping global hotkey listener: {stop_error}")
                finally:
                    self._global_listener = None
            
            logger.info("Hotkey cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up hotkeys: {e}")
    
    def _execute_buy_call(self):
        """Execute buy call order"""
        try:
            logger.info("Hotkey: BUY CALL triggered")
            if self.trading_manager:
                import asyncio
                # Run in event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    async def _run():
                        ok = await self.trading_manager.place_buy_order("CALL")
                        self._show_action_result(ok)
                    asyncio.create_task(_run())
                else:
                    # If loop is not running, run it and then show
                    ok = loop.run_until_complete(self.trading_manager.place_buy_order("CALL"))
                    self._show_action_result(ok)
        except Exception as e:
            logger.error(f"Error executing buy call hotkey: {e}")
    
    def _execute_buy_put(self):
        """Execute buy put order"""
        try:
            logger.info("Hotkey: BUY PUT triggered")
            if self.trading_manager:
                import asyncio
                # Run in event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    async def _run():
                        ok = await self.trading_manager.place_buy_order("PUT")
                        self._show_action_result(ok)
                    asyncio.create_task(_run())
                else:
                    ok = loop.run_until_complete(self.trading_manager.place_buy_order("PUT"))
                    self._show_action_result(ok)
        except Exception as e:
            logger.error(f"Error executing buy put hotkey: {e}")
    
    def _execute_sell_position(self):
        """Execute sell position order with chase logic"""
        try:
            logger.info("Hotkey: SELL POSITION triggered")
            if self.trading_manager:
                import asyncio
                # Run in event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    async def _run():
                        ok = await self.trading_manager.place_sell_order(use_chase_logic=True)
                        self._show_action_result(ok)
                    asyncio.create_task(_run())
                else:
                    ok = loop.run_until_complete(self.trading_manager.place_sell_order(use_chase_logic=True))
                    self._show_action_result(ok)
        except Exception as e:
            logger.error(f"Error executing sell position hotkey: {e}")
    
    def _execute_panic_button(self):
        """Execute panic button"""
        try:
            logger.warning("Hotkey: PANIC BUTTON triggered")
            if self.trading_manager:
                import asyncio
                # Run in event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    async def _run():
                        ok = await self.trading_manager.panic_button()
                        self._show_action_result(ok)
                    asyncio.create_task(_run())
                else:
                    ok = loop.run_until_complete(self.trading_manager.panic_button())
                    self._show_action_result(ok)
        except Exception as e:
            logger.error(f"Error executing panic button hotkey: {e}")

    def _show_action_result(self, success: bool):
        """Show a message box with the last action result from trading manager"""
        try:
            message = ""
            try:
                if hasattr(self.trading_manager, 'get_last_action_message'):
                    message = self.trading_manager.get_last_action_message() or ""
            except Exception:
                message = ""
            parent = self.parent_window if self.parent_window is not None else None
            msg_box = QMessageBox(parent)
            if success:
                msg_box.setWindowTitle("Trade Result")
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setText(message or "Action completed successfully.")
            else:
                # If we failed due to active contract rule, message will already explain
                msg_box.setWindowTitle("Trade Failed")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setText(message or "Action failed. See logs for details.")

            # Force the notification to stay on top of all applications
            try:
                msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass

            # Show the dialog (modal, to keep behavior consistent, but top-most)
            msg_box.exec()
        except Exception as e:
            logger.error(f"Error showing action result: {e}")
    
    def keyPressEvent(self, event):
        """Handle key press events for hotkey detection"""
        try:
            # Get the key combination
            key = event.key()
            modifiers = event.modifiers()
            
            # Check for hotkey combinations
            if self._is_hotkey_combination(key, modifiers, "Ctrl+Alt+P"):
                self.hotkey_buy_put.emit()
                event.accept()
                return
            elif self._is_hotkey_combination(key, modifiers, "Ctrl+Alt+C"):
                self.hotkey_buy_call.emit()
                event.accept()
                return
            elif self._is_hotkey_combination(key, modifiers, "Ctrl+Alt+X"):
                self.hotkey_sell_position.emit()
                event.accept()
                return
            elif self._is_hotkey_combination(key, modifiers, "Ctrl+Alt+F"):
                self.hotkey_panic_button.emit()
                event.accept()
                return
            
            # Handle macOS Command key equivalents
            if self.system == "darwin":
                if self._is_hotkey_combination(key, modifiers, "Cmd+Alt+P"):
                    self.hotkey_buy_put.emit()
                    event.accept()
                    return
                elif self._is_hotkey_combination(key, modifiers, "Cmd+Alt+C"):
                    self.hotkey_buy_call.emit()
                    event.accept()
                    return
                elif self._is_hotkey_combination(key, modifiers, "Cmd+Alt+X"):
                    self.hotkey_sell_position.emit()
                    event.accept()
                    return
                elif self._is_hotkey_combination(key, modifiers, "Cmd+Alt+F"):
                    self.hotkey_panic_button.emit()
                    event.accept()
                    return
            
            # Let other key events pass through
            event.ignore()
            
        except Exception as e:
            logger.error(f"Error in keyPressEvent: {e}")
            event.ignore()
    
    @staticmethod
    def _is_hotkey_combination(key, modifiers, hotkey_string):
        """Check if the key combination matches the hotkey string"""
        try:
            # Parse the hotkey string (e.g., "Ctrl+Alt+P")
            parts = hotkey_string.split("+")
            
            # Check modifiers
            if "Ctrl" in parts and not (modifiers & Qt.KeyboardModifier.ControlModifier):
                return False
            if "Alt" in parts and not (modifiers & Qt.KeyboardModifier.AltModifier):
                return False
            if "Cmd" in parts and not (modifiers & Qt.KeyboardModifier.MetaModifier):
                return False
            
            # Check the key
            key_char = parts[-1].upper()
            if key_char == "P" and key == Qt.Key.Key_P:
                return True
            elif key_char == "C" and key == Qt.Key.Key_C:
                return True
            elif key_char == "X" and key == Qt.Key.Key_X:
                return True
            elif key_char == "F" and key == Qt.Key.Key_F:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking hotkey combination: {e}")
            return False
