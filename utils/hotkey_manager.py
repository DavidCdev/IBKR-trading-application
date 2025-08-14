import sys
import platform
from typing import Callable, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QKeySequence
from .smart_logger import get_logger

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
    
    def __init__(self, trading_manager):
        super().__init__()
        self.trading_manager = trading_manager
        self.is_active = False
        self._hotkey_shortcuts = {}
        
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
        """Setup hotkeys for macOS using Command key"""
        try:
            # Note: For macOS, we'll use Qt's native key handling
            # The actual global hotkey registration would require additional libraries
            # For now, we'll implement a basic version that works within the application
            
            logger.info("macOS hotkey setup completed (application-level)")
            
        except Exception as e:
            logger.error(f"Error setting up macOS hotkeys: {e}")
    
    def _setup_windows_linux_hotkeys(self):
        """Setup hotkeys for Windows/Linux using Ctrl key"""
        try:
            # Note: For Windows/Linux, we'll use Qt's native key handling
            # The actual global hotkey registration would require additional libraries
            # For now, we'll implement a basic version that works within the application
            
            logger.info("Windows/Linux hotkey setup completed (application-level)")
            
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
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.trading_manager.place_buy_order("CALL"))
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(self.trading_manager.place_buy_order("CALL"))
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
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.trading_manager.place_buy_order("PUT"))
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(self.trading_manager.place_buy_order("PUT"))
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
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.trading_manager.place_sell_order(use_chase_logic=True))
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(self.trading_manager.place_sell_order(use_chase_logic=True))
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
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.trading_manager.panic_button())
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(self.trading_manager.panic_button())
        except Exception as e:
            logger.error(f"Error executing panic button hotkey: {e}")
    
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
    
    def _is_hotkey_combination(self, key, modifiers, hotkey_string):
        """Check if the key combination matches the hotkey string"""
        try:
            # Parse the hotkey string (e.g., "Ctrl+Alt+P")
            parts = hotkey_string.split("+")
            
            # Check modifiers
            if "Ctrl" in parts and not (modifiers & 0x04000000):  # Qt.ControlModifier
                return False
            if "Alt" in parts and not (modifiers & 0x08000000):  # Qt.AltModifier
                return False
            if "Cmd" in parts and not (modifiers & 0x10000000):  # Qt.MetaModifier
                return False
            
            # Check the key
            key_char = parts[-1].upper()
            if key_char == "P" and key == 0x50:  # Qt.Key_P
                return True
            elif key_char == "C" and key == 0x43:  # Qt.Key_C
                return True
            elif key_char == "X" and key == 0x58:  # Qt.Key_X
                return True
            elif key_char == "F" and key == 0x46:  # Qt.Key_F
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking hotkey combination: {e}")
            return False
    
    def get_hotkey_info(self) -> Dict[str, str]:
        """Get information about configured hotkeys"""
        return {
            "buy_call": f"{self.modifier_key}+Alt+C",
            "buy_put": f"{self.modifier_key}+Alt+P", 
            "sell_position": f"{self.modifier_key}+Alt+X",
            "panic_button": f"{self.modifier_key}+Alt+F"
        }
