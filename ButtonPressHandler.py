from .ConfigurableButtonElement import ConfigurableButtonElement
from threading import Timer
from .Log import log

class ButtonPressHandler:
    """
    A ButtonElement-compatible wrapper that adds press/hold/release/combo behavior.
    Delegates button functionality to an underlying ConfigurableButtonElement while
    adding gesture detection like press, hold, release and combos.
    """

    def __init__(self, mode_button: ConfigurableButtonElement,
                 press_fn=None, release_fn=None, hold_fn=None, hold_release_fn=None,
                 combo_press_fn=None, combo_release_fn=None,
                 hold_time=1.0, combo_press_listeners=None):
        
        # Store the wrapped button
        self._mode_button = mode_button

        self._mode_button = mode_button
        self._press_fn = press_fn if isinstance(press_fn, list) else [press_fn] if press_fn else []
        self._release_fn = release_fn if isinstance(release_fn, list) else [release_fn] if release_fn else []
        self._hold_fn = hold_fn if isinstance(hold_fn, list) else [hold_fn] if hold_fn else []
        self._hold_release_fn = hold_release_fn if isinstance(hold_release_fn, list) else [hold_release_fn] if hold_release_fn else []
        self._combo_press_fn = combo_press_fn if isinstance(combo_press_fn, list) else [combo_press_fn] if combo_press_fn else []
        self._combo_release_fn = combo_release_fn if isinstance(combo_release_fn, list) else [combo_release_fn] if combo_release_fn else []

        self._combo_press_listeners = list(combo_press_listeners) if combo_press_listeners else []
        if self._mode_button in self._combo_press_listeners:
            self._combo_press_listeners.remove(self._mode_button)

        self._hold_timer = None
        self._hold_time = hold_time
        self._is_held = False
        self._is_combo = False
        self._enabled = True

        # Register listeners
        self._mode_button.add_value_listener(self._button_value_changed)
        for listener in self._combo_press_listeners:
            listener.add_value_listener(self._combo_press_value_changed)

        # Register listeners
        self._mode_button.add_value_listener(self._button_value_changed)
        for listener in self._combo_press_listeners:
            listener.add_value_listener(self._combo_press_value_changed)

    # --- Explicitly forward API methods/properties so no recursion ---
    def is_momentary(self): return self._mode_button.is_momentary()
    def message_type(self): return self._mode_button.message_type()
    def message_channel(self): return self._mode_button.message_channel()
    def message_identifier(self): return self._mode_button.message_identifier()
    def is_pressed(self): return self._mode_button.is_pressed()

    # Delegate basic button functionality directly to wrapped button
    def send_value(self, *a, **k): return self._mode_button.send_value(*a, **k)
    def set_light(self, *a, **k): return self._mode_button.set_light(*a, **k)
    def turn_on(self): return self._mode_button.turn_on()
    def turn_off(self): return self._mode_button.turn_off()
    
    # Delegate value listener management to wrapped button
    def add_value_listener(self, callback, identify_sender=False):
        self._mode_button.add_value_listener(callback, identify_sender)
        
    def remove_value_listener(self, callback):
        self._mode_button.remove_value_listener(callback)
        
    def set_channel(self, channel):
        self._mode_button.set_channel(channel)
        
    def set_enabled(self, enabled):
        self._mode_button.set_enabled(enabled)
        
    def use_default_message(self):
        self._mode_button.use_default_message()
        
    def clear_send_cache(self):
        self._mode_button.clear_send_cache()

    def disable(self):
        """Disable the handler without removing listeners"""
        self._enabled = False

    def enable(self):
        """Enable the handler"""
        self._enabled = True

    # --- Gesture logic (unchanged from your version) ---
    def _button_value_changed(self, value):
        log(f"BUTTON VALUE CHANGED: {value} / IS_HELD:{self._is_held} / IS_COMBO:{self._is_combo}")
        if not self._enabled:
            return
        if value == 127:
            self._is_held = False
            self._start_hold_timer()
            for func in self._press_fn: func()
        else:
            if self._is_combo:
                for func in self._combo_release_fn: func()
                self._is_combo = False
            elif self._is_held:
                for func in self._hold_release_fn: func()
                self._is_held = False
            else:
                for func in self._release_fn: func()
                self._is_held = False
            self._cancel_hold_timer()

    def _combo_press_value_changed(self, value):
        if value and self._mode_button.is_pressed():
            self._cancel_hold_timer()
            self._is_held = False
            self._is_combo = True
            for func in self._combo_press_fn: func()

    def _start_hold_timer(self):
        self._cancel_hold_timer()
        self._hold_timer = Timer(self._hold_time, self._hold)
        self._hold_timer.start()

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _hold(self):
        if self._mode_button.is_pressed():
            self._is_held = True
            for func in self._hold_fn: func()
            self._cancel_hold_timer()

    def disconnect(self):
        self._mode_button.remove_value_listener(self._button_value_changed)
        for listener in self._combo_press_listeners:
            listener.remove_value_listener(self._combo_press_value_changed)
        self._cancel_hold_timer()
