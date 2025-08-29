# Hotkey Protection Mechanism

## Overview

This implementation prevents duplicate hotkey submissions while orders are in the "pending submit" state. When a user presses a hotkey (e.g., Ctrl+Alt+P), the system tracks the submission state and blocks additional submissions until the order is confirmed or rejected.

## Problem Solved

**Before**: Users could press hotkeys multiple times during the 1-2 second delay between order submission and confirmation, causing duplicate orders to be sent to Trader Workstation (TWS).

**After**: While an order is being submitted, all hotkey submissions are blocked until the submission process completes.

## Implementation Details

### 1. Submission State Tracking

The `HotkeyManager` class now tracks submission state using:
- `_submission_in_progress`: Boolean flag indicating if an order is being submitted
- `_submission_lock`: Additional safety lock for extra protection

### 2. Coordination Between Components

- **HotkeyManager**: Manages the submission state and blocks duplicate hotkey triggers
- **TradingManager**: Notifies the hotkey manager when order submission starts and completes
- **Communication**: Bidirectional communication ensures accurate state tracking

### 3. State Flow

```
User presses hotkey → Check submission state → If blocked: show message
                                    ↓
                              If allowed: Lock submission state → Execute order
                                    ↓
                              Order completes → Unlock submission state → Allow new submissions
```

### 4. Key Methods

#### HotkeyManager
- `set_submission_state(in_progress: bool)`: Sets the submission lock state
- `is_submission_allowed() -> bool`: Checks if hotkey submissions are allowed
- `_safe_hotkey_trigger(signal)`: Safely triggers hotkey signals with state checking

#### TradingManager
- `set_hotkey_manager(hotkey_manager)`: Establishes communication link
- `_notify_hotkey_manager(submission_state: bool)`: Notifies about state changes

## Usage

### Setting Up the Connection

```python
# In your main application
hotkey_manager = HotkeyManager(trading_manager)
trading_manager.set_hotkey_manager(hotkey_manager)
```

### Automatic State Management

The system automatically manages submission states:
1. **Order Start**: `_notify_hotkey_manager(True)` - Locks submissions
2. **Order Complete**: `_notify_hotkey_manager(False)` - Unlocks submissions
3. **Error Handling**: Ensures unlock even if exceptions occur

## User Experience

### When Hotkey is Blocked

Users see a clear message:
> "Order submission in progress. Please wait for confirmation before placing another order."

### Visual Feedback

- **Blocked State**: Warning dialog appears explaining why the hotkey is blocked
- **Active State**: Normal hotkey behavior when no submission is in progress

## Testing

Run the test script to verify the protection mechanism:

```bash
python test_hotkey_protection.py
```

This demonstrates:
- Single hotkey presses work normally
- Rapid hotkey presses are blocked during submission
- State properly resets after order completion
- Different hotkey types are all protected

## Benefits

1. **Prevents Duplicate Orders**: Eliminates the risk of multiple orders from rapid hotkey presses
2. **Clear User Feedback**: Users understand why their hotkey was blocked
3. **Automatic Recovery**: System automatically returns to normal state after order completion
4. **Robust Error Handling**: Protection works even if exceptions occur during order processing
5. **Non-Intrusive**: Only blocks during actual submission, doesn't interfere with normal trading

## Technical Notes

- **Thread Safety**: Uses proper locking mechanisms for state management
- **Async Support**: Works with both synchronous and asynchronous order execution
- **Platform Independent**: Protection works on Windows, macOS, and Linux
- **Error Recovery**: Ensures submission state is always properly reset

## Future Enhancements

Potential improvements could include:
- Configurable timeout periods for submission states
- Visual indicators in the UI showing submission status
- Logging of blocked hotkey attempts for debugging
- User preferences for blocking behavior
