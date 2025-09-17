# -*- coding: utf-8 -*-

from .ConfigurableButtonElement import ConfigurableButtonElement
from .Log import log
from _Framework.ButtonElement import ButtonElement
from _Framework.InputControlElement import *
from threading import Timer

class ButtonPressHandler(ButtonElement):
    """
    A middleware class to handle different button gestures: press, release, hold, hold_release.
    """

    def __init__(self, 
                 mode_button, 
                 press_fn = None, 
                 release_fn = None, 
                 hold_fn = None, 
                 hold_release_fn = None, 
                 combo_press_fn = None,
                 combo_release_fn = None,
                 hold_time = 1.0,
                 combo_press_listeners=[], *a, **k):
        super(ButtonPressHandler, self).__init__(True, MIDI_NOTE_TYPE, 0, 0, *a, **k)
        self._mode_button = mode_button
        self._press_fn = press_fn if isinstance(press_fn, list) else [press_fn]       
        self._release_fn = release_fn if isinstance(release_fn, list) else [release_fn]
        self._hold_fn = hold_fn if isinstance(hold_fn, list) else [hold_fn]
        self._hold_release_fn = hold_release_fn if isinstance(hold_release_fn, list) else [hold_release_fn]
        self._combo_press_fn = combo_press_fn if isinstance(combo_press_fn, list) else [combo_press_fn]
        self._combo_release_fn = combo_release_fn if isinstance(combo_release_fn, list) else [combo_release_fn]

        if combo_press_listeners:
            self._combo_press_listeners = list(combo_press_listeners)

        self._hold_timer = None
        self._hold_time = hold_time
        self._is_held = False
        self._is_combo = False

        self._mode_button.add_value_listener(self._button_value_changed)
        if self._mode_button in self._combo_press_listeners:
            self._combo_press_listeners.remove(self._mode_button)
            
        for listener in self._combo_press_listeners:
            listener.add_value_listener(self._combo_press_value_changed)

    def _button_value_changed(self, value):
        log(f"BUTTON VALUE CHANGED: {str(value)} / IS_HELD:{str(self._is_held)} / IS_COMBO:{str(self._is_combo)} ")
        if value is 127:
            self._is_held = False  
            self._start_hold_timer()
            for func in self._press_fn: func()
        else:
            if self._is_combo: # Handle Combo Release
                for func in self._combo_release_fn: func()
                self._is_combo = False

            elif self._is_held: # Handle Hold Release
                log("HELD RELESE")
                for func in self._hold_release_fn: func()
                self._is_held = False   
            else: # Handle Button Release
                log(" RELESE")
                for func in self._release_fn: func()
                self._is_held = False                


            self._cancel_hold_timer()

    def _combo_press_value_changed(self, value):
        if value and self._mode_button.is_pressed():
            self._cancel_hold_timer()
            self._is_held = False
            self._is_combo = True


    def _start_hold_timer(self):
        log("Timer...")
        self._cancel_hold_timer()
        self._hold_timer = Timer(self._hold_time, self._hold)
        self._hold_timer.start()

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _hold(self):
        log("HOLD()")
        if self._mode_button.is_pressed():
            self._is_held = True
            if self._hold_fn:
                self._hold_fn()
            self._cancel_hold_timer()

    def disconnect(self):
        self._mode_button.remove_value_listener(self._button_value_changed)
        for listener in self._combo_press_listeners:
            listener.remove_value_listener(self._combo_press_value_changed)
        self._cancel_hold_timer()
        super(ButtonPressHandler, self).disconnect()
