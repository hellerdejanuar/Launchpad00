# -*- coding: utf-8 -*-

from _Framework.ButtonElement import ButtonElement
from _Framework.InputControlElement import *
from threading import Timer

class ButtonPressHandler(ButtonElement):
    """
    A middleware class to handle different button gestures: press, release, hold, hold_release.
    """

    def __init__(self, mode_button, press_fn, release_fn, hold_fn, hold_release_fn, force_hold_listeners=None, *a, **k):
        super(ButtonPressHandler, self).__init__(True, MIDI_NOTE_TYPE, 0, 0, *a, **k)
        self.mode_button = mode_button
        self.press_fn = press_fn
        self.release_fn = release_fn
        self.hold_fn = hold_fn
        self.hold_release_fn = hold_release_fn
        self.force_hold_listeners = force_hold_listeners or []

        self._hold_timer = None
        self._is_held = False

        self.mode_button.add_value_listener(self._button_value_changed)
        for listener in self.force_hold_listeners:
            listener.add_value_listener(self._force_hold_value_changed)

    def _button_value_changed(self, value):
        if value:
            self._start_hold_timer()
            if self.press_fn:
                self.press_fn()
        else:
            if self._is_held:
                if self.hold_release_fn:
                    self.hold_release_fn()
                self._is_held = False
            else:
                if self.release_fn:
                    self.release_fn()
            self._cancel_hold_timer()

    def _force_hold_value_changed(self, value):
        if value and self.mode_button.is_pressed():
            self._hold()

    def _start_hold_timer(self):
        self._cancel_hold_timer()
        self._hold_timer = Timer(0.7, self._hold)
        self._hold_timer.start()

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _hold(self):
        if self.mode_button.is_pressed():
            self._is_held = True
            if self.hold_fn:
                self.hold_fn()
            self._cancel_hold_timer()

    def disconnect(self):
        self.mode_button.remove_value_listener(self._button_value_changed)
        for listener in self.force_hold_listeners:
            listener.remove_value_listener(self._force_hold_value_changed)
        self._cancel_hold_timer()
        super(ButtonPressHandler, self).disconnect()
