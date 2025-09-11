import Live

from .LoopSelectorComponent import LoopSelectorComponent
from .NoteSelectorComponent import NoteSelectorComponent
from _Framework.CompoundComponent import CompoundComponent
from _Framework.ButtonElement import ButtonElement
from .ButtonPressHandler import ButtonPressHandler
from _Framework.Util import find_if
try:
    from itertools import imap
except ImportError:
    # Python 3...
    imap=map
from .NoteEditorComponent import NoteEditorComponent
from .TrackControllerComponent import TrackControllerComponent
from .Log import log
import time
from .ScaleComponent import ScaleComponent, MUSICAL_MODES, KEY_NAMES
try:
    from .Settings import Settings
except ImportError:
    from .Settings import *
# quantization button colours. this must remain of length 4.
QUANTIZATION_MAP = [1, 0.5, 0.25, 0.125]  # 1/4 1/8 1/16 1/32
QUANTIZATION_NAMES = ["1/4", "1/8", "1/16", "1/32"]

STEPSEQ_MODE_NORMAL = 1
STEPSEQ_MODE_MULTINOTE = 2
STEPSEQ_MODE_SCALE_EDIT = 10

LONG_BUTTON_PRESS = 1.0

#Scrolls the regions in Multinote Mode


class StepSequencerComponent(CompoundComponent):

    def __init__(self, matrix, side_buttons, top_buttons, control_surface):
        self._osd = None
        super(StepSequencerComponent, self).__init__()
        self._control_surface = control_surface
        self._number_of_lines_per_note = 1
        
        # Old-school blinking state management
        self._blinking_buttons = {}  # {button: {'state': bool, 'colors': [color1, color2], 'task': task}}
        self._blink_interval = 1  # quarter note (1 beat - 4 times faster tempo-synced blink)
        self.QUANTIZATION_COLOR_MAP = ["StepSequencer.Quantization.One", "StepSequencer.Quantization.Two", "StepSequencer.Quantization.Three", "StepSequencer.Quantization.Four"]
        self.QUANTIZATION_COLOR_MAP_LOW = ["StepSequencer.QuantizationLow.One", "StepSequencer.QuantizationLow.Two", "StepSequencer.QuantizationLow.Three", "StepSequencer.QuantizationLow.Four"]
        self._name = "drum step sequencer"
        # clip
        self._clip = None
        self._clip_slot = None
        self._note_cache = []
        self._playhead = 0
        self._new_clip_pages = 4
        # mode
        self._mode = -1
        self._mode_backup = self._mode
        # buttons
        self._height = matrix.height()
        self._width = matrix.width()
        self._matrix = matrix
        self._top_buttons = top_buttons
        self._side_buttons = side_buttons
        self._left_button = None
        self._right_button = None
        # scale
        # notes - reduced to 4 note lanes for new matrix layout
        self._root_note = 36
        self._chromatic_scale = []
        self._diatonic_scale = []

        # displayed Bank
        self._selected_subBank = "A"

        # Initialize loop selector state early (needed by quantization setup)
        self._loop_selector_active = False
        # Store original button assignments for proper disconnect/reconnect
        self._original_button_assignments = {}
        
        # Initialize velocity button listeners tracking
        self._velocity_button_listeners = {}
        self._velocity_listeners_added = False

        self._beat = 0
        # setup
        self._set_loop_selector()
        self._set_note_editor()
        self._set_note_selector()
        self._set_track_controller()
        self._set_scale_selector()
        self._set_quantization_function()
        self._set_mute_shift_function()
        self._set_lock_function()
        self._set_mode_function()
        self._scale_updated()
        # TODO: maybe clean this... this should be done on enable.
        # self.on_clip_slot_changed()

    def disconnect(self):
        # Clean up velocity listeners if they exist
        if hasattr(self, '_velocity_listeners_added') and self._velocity_listeners_added:
            self._remove_velocity_side_button_listeners()
            
        self._clip = None

        self._lock_button = None
        self._shift_button = None
        self._quantization_button = None
        self._top_buttons = None
        self._side_buttons = None
        self._matrix = None

        self._loop_selector = None
        self._loop_selector_button = None
        self._note_editor = None
        self._note_selector = None
        self._scale_selector = None
        self._track_controller = None

# SET FUNCTIONS
    def _set_mode_function(self): #Change the resolution of the sequencer
        self._mode_button = None
        # self.set_mode_button(self._side_buttons[5]) #SndB
        self._last_mode_button_press = time.time()
        self._number_of_lines_per_note = 1

    def _set_lock_function(self):
        self._is_locked = False
        self._lock_to_track = False
        self._last_lock_button_press = time.time()
        self._long_press = 0.5
        self._lock_button = None
        self.set_lock_button(self._side_buttons[1])  # Pan button - lock note editor to current clip
        self._selected_track = None
            
    def _set_mute_shift_function(self): #Allow to mute notes in the grid or all notes if selecting on Note Selector #FIX bad behavior
        self._mute_shift_button = None
        self._last_mute_shift_button_press = time.time()
        # self.set_mute_shift_button(self._side_buttons[7])#Arm
        self._is_mute_shifted = False

    def _set_quantization_function(self):
        self._quantization_index = 2
        self.set_quantization(QUANTIZATION_MAP[self._quantization_index])
        self._quantization_button = None
        self._last_quantize_button_press = time.time()
        # self.set_quantization_button(self._side_buttons[2])#SndA

    # Set loop selector using side buttons 1-4, activated by holding side button 6
    def _set_loop_selector(self):
        self._loop_selector = self.register_component(
            LoopSelectorComponent(self, [
                self._side_buttons[1], self._side_buttons[2], 
                self._side_buttons[3], self._side_buttons[4]
            ], self._control_surface)
        )
        # Loop selector starts disabled - only activated when holding side_button[6]
        self._loop_selector.set_enabled(False)
        # Configure blocksize for 4-button layout (each button represents more steps)
        self._loop_selector.set_blocksize(16)  # 16 steps per button for 4-button layout
        
        # Set up loop selector activation button (side_button[6])
        self._loop_selector_button = None
        self.set_loop_selector_button(self._side_buttons[6])
            
    #Allow to manipulate the LP grid and Live's Clip notes (add/del, velocity, mute, etc)
    #In charge of refreshing the notes LED matrix
    #Display page indicator for multinote mode    
    def _set_note_editor(self): 
        self._note_editor = self.register_component(NoteEditorComponent(self, self._matrix, self._control_surface))

        velocity_button_handler = ButtonPressHandler(
            self._side_buttons[5],
            press_fn=self._note_editor._enable_velocity_mode,
            release_fn=self._note_editor._disable_velocity_mode,
            hold_fn=None,
            hold_release_fn=None,
            combo_press_fn=None,
            combo_release_fn=self._note_editor._disable_velocity_mode,
            combo_press_listeners=self._side_buttons
        )

        self._note_editor.set_velocity_button(velocity_button_handler)

    #Set 4x4 lower left matrix section that allows note selection in Normal Mode
    def _set_note_selector(self):
        self._note_selector = self.register_component(
            NoteSelectorComponent(self, [],
                                  self._control_surface)
            )
        self._note_selector.set_subBank_selector(self._side_buttons[3])#SndB
        # self._note_selector.set_down_button(self._side_buttons[4])#Trk On

    def _set_track_controller(self):#Navigation buttons
        self._track_controller = self.register_component(TrackControllerComponent(self._control_surface, implicit_arm = False))
        self._track_controller.set_enabled(False)
        self._track_controller.set_prev_scene_button(self._top_buttons[0])
        self._track_controller.set_next_scene_button(self._top_buttons[1])
        self._track_controller.set_prev_track_button(self._top_buttons[2])
        self._track_controller.set_next_track_button(self._top_buttons[3])
        # Add play/stop functionality to first side button (was scale button): FLO
        self._track_controller.set_start_stop_button(self._side_buttons[0])
        # Set callback for creating clips when slot is empty
        self._track_controller.set_create_clip_callback(self.create_clip_for_selected_slot)

    def _set_scale_selector(self):
        self._scale_selector = self.register_component(ScaleComponent(self._control_surface))
        self._scale_selector.set_osd(self._osd)
        self._scale_selector.set_enabled(False)
        self._scale_selector.set_matrix(self._matrix)
        self._scale_selector._mode = "chromatic"
        self._scale_selector._drumrack = False
        self._scale_selector_button = None
        # Moved scale selector button from 0 to 4
        # self.set_scale_selector_button(self._side_buttons[4])
            
    def set_osd(self, osd):
        self._osd = osd
        self._scale_selector.set_osd(osd)

    def _update_OSD(self):
        if self._osd != None:
            if self._mode == STEPSEQ_MODE_MULTINOTE:
                self._osd.set_mode('Drum Step Sequencer (multinote)')
            else:
                self._osd.set_mode('Drum Step Sequencer')

            if self._clip != None:
                self._osd.attributes[0] = MUSICAL_MODES[self._scale_selector._modus * 2]
                self._osd.attribute_names[0] = "Scale"
                self._osd.attributes[1] = KEY_NAMES[self._scale_selector._key % 12]
                self._osd.attribute_names[1] = "Root Note"
                self._osd.attributes[2] = self._scale_selector._octave
                self._osd.attribute_names[2] = "Octave"
                self._osd.attributes[3] = QUANTIZATION_NAMES[self._quantization_index]
                self._osd.attribute_names[3] = "Quantisation"
                self._osd.attributes[4] = " "
                self._osd.attribute_names[4] = " "
                self._osd.attributes[5] = " "
                self._osd.attribute_names[5] = " "
                self._osd.attributes[6] = " "
                self._osd.attribute_names[6] = " "
                self._osd.attributes[7] = " "
                self._osd.attribute_names[7] = " "
            else:
                self._osd.attributes[0] = " "
                self._osd.attribute_names[0] = " "
                self._osd.attributes[1] = " "
                self._osd.attribute_names[1] = " "
                self._osd.attributes[2] = " "
                self._osd.attribute_names[2] = " "
                self._osd.attributes[3] = " "
                self._osd.attribute_names[3] = " "
                self._osd.attributes[4] = " "
                self._osd.attribute_names[4] = " "
                self._osd.attributes[5] = " "
                self._osd.attribute_names[5] = " "
                self._osd.attributes[6] = " "
                self._osd.attribute_names[6] = " "
                self._osd.attributes[7] = " "
                self._osd.attribute_names[7] = " "

            if self._selected_track != None:
                if self._lock_to_track and self._is_locked:
                    self._osd.info[0] = "track : " + self._selected_track.name + " (locked)"
                else:
                    self._osd.info[0] = "track : " + self._selected_track.name
            else:
                self._osd.info[0] = " "
            if self._clip != None:
                name = self._clip.name
                if name == "":
                    name = "(unamed clip)"
                if not self._lock_to_track and self._is_locked:
                    self._osd.info[1] = "clip : " + name + " (locked)"
                else:
                    self._osd.info[1] = "clip : " + name
            else:
                self._osd.info[1] = "no clip selected"
            self._osd.update()

    @property
    def _is_velocity_shifted(self):
        return self._note_editor._is_velocity_shifted

    def index_of(self, pad_list, pad):
        for i in range(0, len(pad_list)):
            if (pad_list[i] == pad):
                return i
        return(-1)

    def _remove_scale_listeners(self):
        try:
            self.song().remove_root_note_listener(self.handle_root_note_changed)
        except RuntimeError:
            pass
        try:
            self.song().remove_scale_name_listener(self.handle_scale_name_changed)
        except RuntimeError:
            pass
        
    
    def _register_scale_listeners(self):
        try:
            self.song().add_root_note_listener(self.handle_root_note_changed)
        except RuntimeError:
            pass
        try:
            self.song().add_scale_name_listener(self.handle_scale_name_changed)
        except RuntimeError:
            pass

    def handle_root_note_changed(self):
        self._scale_selector.set_key(self.song().root_note, False, True)
        self.update()


    def handle_scale_name_changed(self):
        self._scale_selector.set_modus(self._scale_selector._modus_names.index(self.song().scale_name), False, True)
        self.update()
        


# enabled
    def set_enabled(self, enabled):
        if enabled:
            if self._mode == STEPSEQ_MODE_SCALE_EDIT:
                self.set_mode(self._mode_backup)
            # clear note editor cache
            self._note_editor._force_update = True

            # todo: find a better way to init?
            if self._mode == -1:
                self._mode = STEPSEQ_MODE_MULTINOTE  # Default to multinote
                self._detect_scale_mode()

            # sync to selected pad
            self._update_drum_group_device()
            if(self._drum_group_device): #Select the note 
                self._note_selector.set_selected_note(self.index_of(self._drum_group_device.drum_pads,self._drum_group_device.view.selected_drum_pad)) #FIX set view again

            self._track_controller.set_enabled(enabled)    
            self._note_editor.set_enabled(enabled)
            # update clip notes as they might have changed while we were sleeping
            self.on_clip_slot_changed()
            # call super.set_enabled()
            CompoundComponent.set_enabled(self, enabled)
            if self._clip != None and self._is_locked:
                self._control_surface.show_message("stepseq : clip '"+str(self._clip.name)+"'")
            self._on_notes_changed()
            self._update_OSD()

        else:
            self._track_controller.set_enabled(enabled)
            self._loop_selector.set_enabled(enabled)
            self._note_selector.set_enabled(enabled)
            self._note_editor.set_enabled(enabled)
            CompoundComponent.set_enabled(self, enabled)
        if not enabled:
            self._remove_scale_listeners()
        else:
            self._register_scale_listeners()

    def set_mode(self, mode, number_of_lines_per_note=1):
        if self._mode != mode or number_of_lines_per_note != self._number_of_lines_per_note:
            self._number_of_lines_per_note = number_of_lines_per_note
            self._note_editor.set_multinote(mode == STEPSEQ_MODE_MULTINOTE, number_of_lines_per_note)
            if mode == STEPSEQ_MODE_NORMAL:
                if self._mode != mode:
                    # self._loop_selector._block = self._loop_selector._block * self._number_of_lines_per_note
                    self._note_editor.set_page(self._loop_selector._block)
                self.set_left_button(None)
                self.set_right_button(None)
                self._track_controller.set_prev_track_button(self._top_buttons[2])
                self._track_controller.set_next_track_button(self._top_buttons[3])
            else:
                if self._mode != mode:
                    # self._loop_selector._block = self._loop_selector._block / self._number_of_lines_per_note
                    self._note_editor.set_page(self._loop_selector._block)
                self._track_controller.set_prev_track_button(None)
                self._track_controller.set_next_track_button(None)
                self.set_left_button(self._top_buttons[2])
                self.set_right_button(self._top_buttons[3])
            self._mode = mode
            self._note_editor._force_update = True
            self.update()

    def set_page(self, block):
        self._note_editor.set_page(block)
        self._note_editor.update()
        
# SCALE
    def _scale_updated(self):
        keys = [0, 0, 0, 0]  # Reduced to 4 note lanes
        key_is_root_note = [False, False, False, False]
        key_is_in_scale = [False, False, False, False]
        if self._note_selector.is_drumrack:
            for i in range(4):  # Only 4 note lanes now
                keys[i] = self._note_selector.selected_note + (3 - i)  # Reverse the note order
                key_is_root_note[i] = (keys[i] + 12 + 16) % 16 == 0
                key_is_in_scale[i] = (keys[i] + 12 + 16) % 4 == 0
        elif self._note_selector.is_diatonic:
            self._note_selector._scale_length = len(self._note_selector._scale)
            try:
                idx = self._note_selector._scale.index(self._note_selector._offset)
            except ValueError:
                idx = -1
            if(idx == -1):
                self._control_surface.log_message("not found : " + str(self._note_selector._offset) + " in " + str(self._note_selector._scale))
                for i in range(4):  # Only 4 note lanes now
                    keys[i] = self._note_selector._root_note + self._note_selector._offset + (3 - i)  # Reverse the note order
            else:
                for i in range(4):  # Only 4 note lanes now
                    scale_idx = ((3 - i) + idx) % self._note_selector._scale_length  # Reverse the note order
                    octave_offset = int(((3 - i) + idx) / self._note_selector._scale_length) * 12
                    keys[i] = self._note_selector._root_note + self._note_selector._scale[scale_idx] + octave_offset
                    key_is_root_note[i] = (keys[i] + 12) % 12 == self._note_selector._key
                    key_is_in_scale[i] = True
        else:
            for i in range(4):  # Only 4 note lanes now
                keys[i] = self._note_selector.selected_note + (3 - i)  # Reverse the note order
                key_is_root_note[i] = (keys[i] + 12) % 12 == self._note_selector._key
                key_is_in_scale[i] = (keys[i] - self._note_selector._key + 12) % 12 in self._note_selector._scale
                
        self._note_editor.set_key_indexes(keys)
        self._note_editor.set_key_index_is_in_scale(key_is_in_scale)
        self._note_editor.set_key_index_is_root_note(key_is_root_note)
        self._update_note_editor()
        self._update_note_selector()

# UPDATE
    def update(self):
        if self.is_enabled():
            self._update_track_controller()
            self._update_scale_selector()
            self._update_loop_selector()
            self._update_note_selector()
            self._update_buttons()
            self._update_note_editor()
            self._update_OSD()
            # show clip !
            if not self._is_locked and self._clip != None:
                if ((not self.application().view.is_view_visible('Detail')) or (not self.application().view.is_view_visible('Detail/Clip'))):
                    self.application().view.show_view('Detail')
                    self.application().view.show_view('Detail/Clip')

    def _update_track_controller(self):
        if self._track_controller != None:
            self._track_controller.set_enabled(True)

    def _update_scale_selector(self):
        self._scale_selector.set_enabled(self._mode == STEPSEQ_MODE_SCALE_EDIT)
        self._scale_selector.update()

    def _update_loop_selector(self):
        if self._loop_selector_active and self._mode == STEPSEQ_MODE_NORMAL:
            self._loop_selector.set_enabled(True)
            self._loop_selector.update()
        else:
            self._loop_selector.set_enabled(False)

    def _update_note_selector(self):
        self._note_selector._enable_offset_button = self._mode == STEPSEQ_MODE_NORMAL
        self._note_selector.set_enabled(self._mode != STEPSEQ_MODE_SCALE_EDIT)
        self._note_selector.update()

    def _update_note_editor(self):
        self._note_editor.set_multinote(self._mode == STEPSEQ_MODE_MULTINOTE, self._number_of_lines_per_note)
        if self._mode == STEPSEQ_MODE_NORMAL:
            self._note_editor.set_height(self._height)
        else:
            self._note_editor.set_height(self._height)
        self._note_editor.set_enabled(self._mode != STEPSEQ_MODE_SCALE_EDIT)
        self._note_editor.update()

    def _update_buttons(self):
        self._update_quantization_button()
        self._update_lock_button()
        self._update_mode_button()
        self._update_mute_shift_button()
        self._update_scale_selector_button()
        self._update_loop_selector_button()
        self._update_left_button()
        self._update_right_button()
        if self._track_controller != None:
            self._track_controller.update()


# CLIP CALLBACKS
    def on_track_list_changed(self):
        self.on_selected_track_changed()

    def on_scene_list_changed(self):
        self.on_selected_scene_changed()

    def on_selected_scene_changed(self):
        self.on_clip_slot_changed()
        self.update()

    def on_selected_track_changed(self):
        if not self._is_locked or self._clip == None:
            self._detect_scale_mode()
            self.on_clip_slot_changed()
            self.update()

    def _on_loop_changed(self):
        if self.is_enabled() and self._clip != None:
            self._loop_selector._get_clip_loop()

    def on_clip_slot_has_clip_changed(self):
        # the clip was deleted. unlock.
        if not self._clip_slot.has_clip:
            self._is_locked = False
        self.on_clip_slot_changed()
        self.update()

    def on_clip_slot_changed(self, scheduled=False):
        # get old reference to clipslot
        clip_slot = self._clip_slot

        # update track if not track locked
        if not self._is_locked or self._selected_track == None:
            self._selected_track = self.song().view.selected_track

        # update scene
        if self._selected_track != None:
            idx = -1
            if self._lock_to_track and self._is_locked:
                # track locked mode

                # schedule a refresh as scene fire happens after scene selection
                # so that we can catch the clip scheduled for playing
                if not scheduled:
                    self._control_surface.schedule_message(5, self.on_clip_slot_changed, (True))

                # locate with clip pending fire
                for i in range(len(self.song().scenes)):
                    if self._selected_track.clip_slots[i].has_clip and self._selected_track.clip_slots[i].clip.is_triggered:
                        idx = i
                # no tirggered clip, locate with playing clip
                if idx == -1:
                    for i in range(len(self.song().scenes)):
                        if self._selected_track.clip_slots[i].has_clip and self._selected_track.clip_slots[i].clip.is_playing:
                            idx = i
                # fallback: use scene selection
                if idx == -1:
                    try:
                        idx = list(self.song().scenes).index(self.song().view.selected_scene)
                    except ValueError: 
                        idx = -1

            # unlocked mode
            if not self._is_locked:
                try:
                    idx = list(self.song().scenes).index(self.song().view.selected_scene)
                except ValueError:
                    idx = -1
            if(idx != -1 and idx < len(list(self._selected_track.clip_slots))):
                clip_slot = self._selected_track.clip_slots[idx]

        # update clip slot
        if clip_slot != self._clip_slot or self._clip_slot == None:
            if clip_slot != None and clip_slot.has_clip_has_listener(self.on_clip_slot_has_clip_changed):
                clip_slot.remove_has_clip_listener(self.on_clip_slot_has_clip_changed)
            self._clip_slot = clip_slot
            if self._clip_slot != None:
                if self._clip_slot.has_clip_has_listener(self.on_clip_slot_has_clip_changed):
                    self._clip_slot.remove_has_clip_listener(self.on_clip_slot_has_clip_changed)
                self._clip_slot.add_has_clip_listener(self.on_clip_slot_has_clip_changed)

        if self._clip_slot != None and self._clip_slot.has_clip and self._clip_slot.clip != None and self._clip_slot.clip.is_midi_clip:
            if self._clip == None or self._clip != self._clip_slot.clip:
                # unlink
                if self._clip != None and self._clip.is_midi_clip:
                    if self._clip.notes_has_listener(self._on_notes_changed):
                        self._clip.remove_notes_listener(self._on_notes_changed)
                    if self._clip.playing_status_has_listener(self._on_playing_status_changed):
                        self._clip.remove_playing_status_listener(self._on_playing_status_changed)
                    if self._clip.playing_position_has_listener(self._on_playing_position_changed):
                        self._clip.remove_playing_position_listener(self._on_playing_position_changed)
                    if self._clip.loop_start_has_listener(self._on_loop_changed):
                        self._clip.remove_loop_start_listener(self._on_loop_changed)
                    if self._clip.loop_end_has_listener(self._on_loop_changed):
                        self._clip.remove_loop_end_listener(self._on_loop_changed)
              

                # link new clip
                self._clip_slot.clip.add_notes_listener(self._on_notes_changed)
                self._clip_slot.clip.add_playing_status_listener(self._on_playing_status_changed)
                self._clip_slot.clip.add_playing_position_listener(self._on_playing_position_changed)
                self._clip_slot.clip.add_loop_start_listener(self._on_loop_changed)
                self._clip_slot.clip.add_loop_end_listener(self._on_loop_changed)
                
                # publish
                self._clip = self._clip_slot.clip
                        
                # update
                #if scheduled:
                self._clip_changed()
                #else:
                #self._control_surface.schedule_message(1, self._clip_changed)
            else:
                # same clip...
                pass
                
        else:
            # unlink
            if self._clip != None:
                if self._clip.notes_has_listener(self._on_notes_changed):
                    self._clip.remove_notes_listener(self._on_notes_changed)
                if self._clip.playing_status_has_listener(self._on_playing_status_changed):
                    self._clip.remove_playing_status_listener(self._on_playing_status_changed)
                if self._clip.playing_position_has_listener(self._on_playing_position_changed):
                    self._clip.remove_playing_position_listener(self._on_playing_position_changed)
                if self._clip.loop_start_has_listener(self._on_loop_changed):
                    self._clip.remove_loop_start_listener(self._on_loop_changed)
                if self._clip.loop_end_has_listener(self._on_loop_changed):
                    self._clip.remove_loop_end_listener(self._on_loop_changed)

            # publish
            self._clip = None
            self._clip_changed()

    def _clip_changed(self):  # triggered by _on_clip_slot_changed() or manually on enable.
        self._note_editor.set_clip(self._clip)
        self._note_selector.set_clip(self._clip)
        self._loop_selector.set_clip(self._clip)
        self._note_editor.set_playhead(None)
        self._note_selector.set_playhead(None)
        self._loop_selector.set_playhead(None)
        # reload notes
        self._on_notes_changed()
            
    def _on_notes_changed(self):  # trigger by callback on clip or via _clip_changed.
        if self.is_enabled():
            # get notes
            if self._clip == None:
                note_cache = []
            else:
                self._clip.select_all_notes()
                note_cache = self._clip.get_selected_notes()
                self._clip.deselect_all_notes()

            # update if needed
            if note_cache != self._note_cache:
                self._note_cache = note_cache
                self._note_editor.set_note_cache(self._note_cache)
                self._note_selector.set_note_cache(self._note_cache)
                self._loop_selector.set_note_cache(self._note_cache)
                self._note_editor.update()

# PLAY POSITION
    def _on_playing_status_changed(self):  # playing status changed listener
        if self.is_enabled():
            self._on_playing_position_changed()
            # Update loop selector button when playing status changes
            self._update_loop_selector_button()

    def _on_playing_position_changed(self):  # playing position changed listener
        if self.is_enabled():
            if self._clip != None and self._clip.is_playing and self.song().is_playing:
                self._playhead = self._clip.playing_position
            else:
                self._playhead = None
            self._loop_selector.set_playhead(self._playhead, Settings.STEPSEQ__AUTO_SCROLL)
            self._note_selector.set_playhead(self._playhead)
            self._note_editor.set_playhead(self._playhead)
            self.updateQuantizationButton()

# DRUM_GROUP_DEVICE
    def _update_drum_group_device(self):
        if self.song().view.selected_track != None:
            track = self.song().view.selected_track
            if(track.devices != None and len(track.devices) > 0):
                #device = track.devices[0]
                device = self.find_drum_group_device(track)
                if(device!= None and device.can_have_drum_pads and device.has_drum_pads):#Is drumrack and it have pads
                    self._drum_group_device = device
                else:
                    self._drum_group_device = None
            else:
                self._drum_group_device = None
        else:
            self._drum_group_device = None

    def _detect_scale_mode(self):
        if not self._is_locked:
            self._update_drum_group_device()
            self._scale_selector.set_drumrack(self._drum_group_device != None)
    
    def find_drum_group_device(self, track):
        device = find_if(lambda d: d.type == Live.Device.DeviceType.instrument, track.devices)#find track's Instrument device
        if device:
            if device.can_have_drum_pads:#device is a drum rack??
                return device
            elif device.can_have_chains:#device is a rack??
                return find_if(bool, imap(self.find_drum_group_device, device.chains))#recursive->returns the first drum rack item of the chain
        else:
            return None
            
# SCALE Selector Button
    def _update_scale_selector_button(self):
        if self.is_enabled():
            if (self._scale_selector_button != None):
                if self._clip != None:
                    self._scale_selector_button.set_on_off_values("StepSequencer.Scale")
                else:
                    self._scale_selector_button.set_on_off_values("DefaultButton.Disabled","DefaultButton.Disabled")
                if self._mode == STEPSEQ_MODE_SCALE_EDIT:
                    self._scale_selector_button.turn_on()
                    self._osd.set_mode('Scale')
                else:
                    self._scale_selector_button.turn_off()

    def set_scale_selector_button(self, button): #remove old scale button listener and adds new one 
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._scale_selector_button != button):
            if (self._scale_selector_button != None):
                self._scale_selector_button.remove_value_listener(self._scale_selector_button_value)
            self._scale_selector_button = button
            if (self._scale_selector_button != None):
                assert isinstance(button, ButtonElement)
                self._scale_selector_button.add_value_listener(self._scale_selector_button_value)

    def _scale_selector_button_value(self, value):
        assert (value in range(128))
        if self.is_enabled():

            if value > 0:
                self._mode_backup = self._mode
                if self._scale_selector != None and self._note_selector != None:
                    self._scale_selector.set_octave(int(self._note_selector._root_note / 12))
                    self._scale_selector.set_key(self._note_selector._key)
                    self.set_mode(STEPSEQ_MODE_SCALE_EDIT)
            else:
                if self._scale_selector != None and self._note_selector != None:
                    self._note_selector.set_scale(self._scale_selector.notes, self._scale_selector._key)
                    self._note_selector.set_selected_note(self._scale_selector._octave * 12 + self._scale_selector._key)
                    self._scale_updated()
                self.set_mode(self._mode_backup)


# MUTE SHIFT Button
    def set_mute_shift_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._mute_shift_button != button):
            if (self._mute_shift_button != None):
                self._mute_shift_button.remove_value_listener(self._mute_shift_button_value)
            self._mute_shift_button = button
            if (self._mute_shift_button != None):
                assert isinstance(button, ButtonElement)
                self._mute_shift_button.add_value_listener(self._mute_shift_button_value, identify_sender=True)

    def _update_mute_shift_button(self):
        if self.is_enabled() and self._mute_shift_button != None:
            if self._clip != None and self._clip.is_midi_clip:
                self._mute_shift_button.set_on_off_values("StepSequencer.Mute")
                if self._is_mute_shifted:
                    self._mute_shift_button.turn_on()
                else:
                    self._mute_shift_button.turn_off()
            else:
                self._mute_shift_button.set_light("DefaultButton.Disabled")
    
    def _mute_shift_button_value(self, value, sender):
        assert (self._mute_shift_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            now = time.time()
            if ((value is not 0) or (not sender.is_momentary())):
                self._is_mute_shifted = not self._is_mute_shifted
            else:
                if now - self._last_mute_shift_button_press> 0.25:
                    self._is_mute_shifted = not self._is_mute_shifted
                self._last_mute_shift_button_press = now
                
            self._note_editor._is_mute_shifted = self._is_mute_shifted
            self._update_mute_shift_button()
            
# MODE
    def _update_mode_button(self):
        if self.is_enabled():
            if (self._mode_button != None):
                if self._clip != None:
                    self._mode_button.set_on_off_values("StepSequencer.Mode")
                    if self._mode == STEPSEQ_MODE_MULTINOTE:
                        self._mode_button.turn_on()
                        self._osd.update()
                    else:
                        self._mode_button.turn_off()
                        self._osd.update()
                else:
                    self._mode_button.set_light("DefaultButton.Disabled")

    def set_mode_button(self, button):#remove old mode button listener and adds new one 
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._mode_button != button):
            if (self._mode_button != None):
                self._mode_button.remove_value_listener(self._mode_button_value)
            self._mode_button = button
            if (self._mode_button != None):
                assert isinstance(button, ButtonElement)
                self._mode_button.add_value_listener(self._mode_button_value, identify_sender=True)

    def _mode_button_value(self, value, sender):
        assert (self._mode_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            if ((value is not 0) or (not sender.is_momentary())):
                self._last_mode_button_press = time.time()
            else:
                if self._mode == STEPSEQ_MODE_MULTINOTE and time.time() - self._last_mode_button_press > 0.25:
                    if(self._number_of_lines_per_note == 1):
                        number_of_lines_per_note = 2
                    else:
                        number_of_lines_per_note = 1
                    self.set_mode(STEPSEQ_MODE_MULTINOTE, number_of_lines_per_note)

                elif self._mode != STEPSEQ_MODE_MULTINOTE:
                    self.set_mode(STEPSEQ_MODE_MULTINOTE, self._number_of_lines_per_note)

                else:
                    self.set_mode(STEPSEQ_MODE_NORMAL, self._number_of_lines_per_note)
                self._scale_updated()

# QUANTIZE
    def _update_quantization_button(self):
        if self.is_enabled() and self._quantization_button != None:
            if self._clip != None:
                self._quantization_button.set_light(self.QUANTIZATION_COLOR_MAP[self._quantization_index])
            else:
                self._quantization_button.set_light("DefaultButton.Disabled")

    # Refresh button and its listener OK
    def set_quantization_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._quantization_button != button):
            if (self._quantization_button != None):
                self._quantization_button.remove_value_listener(self._quantization_button_value)
            self._quantization_button = button
            if (self._quantization_button != None):
                self._quantization_button.add_value_listener(self._quantization_button_value, identify_sender=True)

    # Handle button holded and quantization resolution selection OK    
    def _quantization_button_value(self, value, sender):
        assert (self._quantization_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            now = time.time()
            if ((value is not 0) or (not sender.is_momentary())):
                self._last_quantize_button_press = now
            else:
                if now - self._last_quantize_button_press > 0.5:
                    self._control_surface.show_message("Step Sequencer: duplicate clip")
                    self.duplicate_clip()
                else:
                    if(self._mode == STEPSEQ_MODE_SCALE_EDIT):
                        self._quantization_index = (self._quantization_index - 1+len(QUANTIZATION_MAP)) % len(QUANTIZATION_MAP)
                    else:
                        self._quantization_index = (self._quantization_index + 1) % len(QUANTIZATION_MAP)
                    self.set_quantization(QUANTIZATION_MAP[self._quantization_index])
                    self._control_surface.show_message("QUANTIZATION : "+QUANTIZATION_NAMES[self._quantization_index])
                    
                    self._update_quantization_button()


    def updateQuantizationButton(self):
        if self.is_enabled() and self._quantization_button != None and self._playhead != None:
            if(self._beat == int(self._playhead)):
                self._quantization_button.set_light(self.QUANTIZATION_COLOR_MAP_LOW[self._quantization_index])
            else:
                self._beat = int(self._playhead)
                self._update_quantization_button()

    def set_quantization(self, quantization):
        self._quantization = quantization
        if self._note_editor != None:
            self._note_editor.set_quantization(self._quantization)
        if self._loop_selector != None:
            self._update_loop_selector()
        if self._note_selector != None:
            self._update_note_selector()
        if self._note_editor != None:
            self._update_note_editor()

# LOOP SELECTOR BUTTON
    def set_loop_selector_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (button != self._loop_selector_button):
            if (self._loop_selector_button != None):
                self._loop_selector_button.remove_value_listener(self._loop_selector_button_value)
            self._loop_selector_button = button
            if (self._loop_selector_button != None):
                self._loop_selector_button.add_value_listener(self._loop_selector_button_value, identify_sender=True)

    def _loop_selector_button_value(self, value, sender):
        assert (self._loop_selector_button != None)
        assert (value in range(128))
        if self.is_enabled():
            if value != 0:  # Button pressed - toggle the state
                self._loop_selector_active = not self._loop_selector_active
                if self._loop_selector_active:
                    self._disconnect_side_button_functionality()
                    self._loop_selector.set_enabled(True)
                    self._loop_selector.update()  # Force update when enabling
                else:
                    self._loop_selector.set_enabled(False)
                    # Comprehensive refresh with corrections
                    self._comprehensive_refresh_on_exit()
                self._update_loop_selector_button()

    def _update_loop_selector_button(self):
        if self.is_enabled() and self._loop_selector_button != None:
            if self._clip != None:
                # Check if Live is playing to determine behavior
                if hasattr(self._control_surface, 'song') and self._control_surface.song():
                    is_playing = self._control_surface.song().is_playing
                else:
                    is_playing = False
                
                if is_playing:
                    if self._loop_selector_active:
                        # Live playing + loop selector active: blink between green_half and off
                        self.make_button_blink_oldschool(
                            self._loop_selector_button, 
                            "StepSequencer.NoteEditor.Velocity0",  # GREEN_HALF (bright)
                            "DefaultButton.Disabled"  # OFF (dark)
                        )
                    else:
                        # Live playing + loop selector not active: green_third
                        self.stop_button_blink_oldschool(self._loop_selector_button, "DefaultButton.Off")
                else:
                    # Live not playing: always green_half (whether active or not)
                    self.stop_button_blink_oldschool(self._loop_selector_button, "StepSequencer.NoteEditor.Velocity0")
            else:
                self._loop_selector_button.set_light("DefaultButton.Disabled")

    def _disconnect_side_button_functionality(self):
        """Disconnect side button functionality when entering loop selector mode (except start/stop)"""
        # Store current assignments and disconnect components from side buttons
        self._original_button_assignments.clear()
        
        # Keep track controller start/stop button (side_button[0]) active in loop selector mode
        # No need to disconnect it - it should remain available
        
        # Disconnect note selector from side_button[3] (subBank selector) 
        if self._note_selector and hasattr(self._note_selector, '_subBank_selector'):
            if self._note_selector._subBank_selector:
                self._original_button_assignments['note_subbank'] = self._note_selector._subBank_selector
                self._note_selector.set_subBank_selector(None)
        
        # Disconnect note editor from side_button[5] (velocity button)
        if self._note_editor and hasattr(self._note_editor, '_velocity_button'):
            if self._note_editor._velocity_button:
                self._original_button_assignments['note_velocity'] = self._note_editor._velocity_button
                self._note_editor.set_velocity_button(None)
        
        # Disconnect lock button from side_button[1] 
        if hasattr(self, '_lock_button') and self._lock_button:
            self._original_button_assignments['lock_button'] = self._lock_button
            self.set_lock_button(None)
                
        # Visually disable non-loop buttons
        if self._side_buttons:
            for i, button in enumerate(self._side_buttons):
                # Skip loop selector buttons (1-4), activation button (6), and start/stop button (0)
                if button and i not in [0, 1, 2, 3, 4, 6]:
                    button.set_light("DefaultButton.Disabled")

    def _disconnect_side_button_functionality_for_velocity(self):
        """Disconnect side button functionality when entering velocity mode (except velocity button itself)"""
        # Use the generic function, ignoring only the velocity button (index 5)
        self._disengage_side_buttons(buttons_to_ignore=[5])
        # Set velocity colors on side buttons 0-4 (Velocity4 to Velocity0 in reverse order)
        self._update_velocity_side_button_colors()
        # Add velocity selection listeners to side buttons 0-4
        self._setup_velocity_side_button_listeners()
        self._velocity_listeners_added = True

    def _reconnect_side_button_functionality_for_velocity(self):
        """Reconnect side button functionality when exiting velocity mode"""
        # Immediately remove velocity selection listeners first
        self._remove_velocity_side_button_listeners()
        # Clear velocity colors immediately
        self._clear_velocity_side_button_colors()
        # Then restore normal functionality
        self._engage_side_buttons()

    def _reconnect_side_button_functionality(self):
        """Reconnect side button functionality when exiting loop selector mode"""
        # Restore NoteEditor MAIN button assignments
        # start/stop button (side_button[0]) was never disconnected, so no need to reconnect
            
        if 'note_subbank' in self._original_button_assignments:
            self._note_selector.set_subBank_selector(self._original_button_assignments['note_subbank'])
            
        if 'note_velocity' in self._original_button_assignments:
            self._note_editor.set_velocity_button(self._original_button_assignments['note_velocity'])
            
        if 'lock_button' in self._original_button_assignments:
            self.set_lock_button(self._original_button_assignments['lock_button'])
        
        # Clear stored assignments
        self._original_button_assignments.clear()
        
        # Re-enable all side buttons first and clear any disabled lights
        if self._side_buttons:
            for i, button in enumerate(self._side_buttons):
                if button and i != 6:  # Skip loop selector activation button
                    button.set_enabled(True)
                    # Clear any disabled state lights
                    button.clear_send_cache()
        
        # Clear all side button displays
        self._clear_side_buttons()
        
        # Force comprehensive update of all components to restore their button states
        self._update_buttons()
        self._update_note_selector()
        self._update_note_editor()
        
        # Explicitly update velocity button 
        if self._note_editor and hasattr(self._note_editor, '_update_velocity_button'):
            self._note_editor._update_velocity_button()
            
        # Update lock button
        self._update_lock_button()
            
        if self._track_controller:
            self._track_controller.update()
        # Force a complete update cycle
        self.update()

    def _clear_side_buttons(self):
        """Clear the visual display of all side buttons - reusable function"""
        # Clear all side buttons by turning them off and resetting their state
        if self._side_buttons:
            for i, button in enumerate(self._side_buttons):
                if button:
                    # Set to default disabled state to clear any colors/states
                    button.set_light("DefaultButton.Disabled")
                    button.turn_off()
                    # Clear any cached states
                    button.clear_send_cache()

    def _disengage_side_buttons(self, buttons_to_ignore=None):
        """
        Disconnect and visually disable side buttons except for specified buttons to ignore
        
        Args:
            buttons_to_ignore (list): List of button indices to keep active/ignore (e.g., [5] for velocity mode)
        """
        if buttons_to_ignore is None:
            buttons_to_ignore = []
            
        # Store current assignments and disconnect components from side buttons
        if not hasattr(self, '_temp_button_assignments'):
            self._temp_button_assignments = {}
        self._temp_button_assignments.clear()
        
        # Define button mappings: index -> (component, attribute_name, setter_method, assignment_key)
        button_mappings = {
            0: (self._track_controller, '_start_stop_button', 'set_start_stop_button', 'start_stop_button'),
            1: (self, '_lock_button', 'set_lock_button', 'lock_button'),
            2: (None, None, None, 'quantization_button'),  # Usually unassigned (was quantization)
            3: (self._note_selector, '_subBank_selector', 'set_subBank_selector', 'note_subbank'),
            4: (None, None, None, 'scale_selector_button'),  # Usually unassigned (was scale selector)
            5: (self._note_editor, '_velocity_button', 'set_velocity_button', 'note_velocity'),
            6: (self, '_loop_selector_button', 'set_loop_selector_button', 'loop_selector_button'),
            7: (None, None, None, 'mute_shift_button'),  # Usually unassigned (was mute shift)
        }
        
        # Loop through and disconnect buttons that are not ignored
        for button_index, (component, attribute, setter, key) in button_mappings.items():
            if button_index not in buttons_to_ignore:
                if component and hasattr(component, attribute):
                    button_obj = getattr(component, attribute)
                    if button_obj:
                        self._temp_button_assignments[key] = button_obj
                        getattr(component, setter)(None)
                
        # Visually disable all buttons except those in buttons_to_ignore
        if self._side_buttons:
            for i, button in enumerate(self._side_buttons):
                if button and i not in buttons_to_ignore:
                    button.set_light("DefaultButton.Disabled")

    def _engage_side_buttons(self):
        """
        Reconnect side button functionality that was previously disengaged
        """
        if not hasattr(self, '_temp_button_assignments'):
            return
            
        # Define restoration mappings: assignment_key -> (component, setter_method)
        restore_mappings = {
            'start_stop_button': (self._track_controller, 'set_start_stop_button'),
            'lock_button': (self, 'set_lock_button'),
            'quantization_button': (None, None),  # Usually unassigned
            'note_subbank': (self._note_selector, 'set_subBank_selector'),
            'scale_selector_button': (None, None),  # Usually unassigned
            'note_velocity': (self._note_editor, 'set_velocity_button'),
            'loop_selector_button': (self, 'set_loop_selector_button'),
            'mute_shift_button': (None, None),  # Usually unassigned
        }
        
        # Loop through and restore button assignments
        for key, (component, setter) in restore_mappings.items():
            if key in self._temp_button_assignments and component:
                getattr(component, setter)(self._temp_button_assignments[key])
            
        # Clear the assignments
        self._temp_button_assignments.clear()
        
        # Force comprehensive refresh
        self._update_buttons()

    def _update_velocity_side_button_colors(self):
        """Set velocity colors on side buttons 0-4 when in velocity mode"""
        if self._side_buttons:
            # Velocity colors in reverse order: button 0=Velocity4, button 1=Velocity3, ..., button 4=Velocity0
            velocity_colors = [
                "StepSequencer.NoteEditor.Velocity4",  # side_button[0]
                "StepSequencer.NoteEditor.Velocity3",  # side_button[1]
                "StepSequencer.NoteEditor.Velocity2",  # side_button[2]
                "StepSequencer.NoteEditor.Velocity1",  # side_button[3]
                "StepSequencer.NoteEditor.Velocity0"   # side_button[4]
            ]
            
            for i in range(5):  # buttons 0-4
                if i < len(self._side_buttons) and self._side_buttons[i]:
                    self._side_buttons[i].set_light(velocity_colors[i])

    def _clear_velocity_side_button_colors(self):
        """Clear velocity colors from side buttons 0-4 when exiting velocity mode"""
        if self._side_buttons:
            for i in range(5):  # buttons 0-4
                if i < len(self._side_buttons) and self._side_buttons[i]:
                    # Clear to disabled state to prepare for normal functionality restoration
                    self._side_buttons[i].set_light("DefaultButton.Disabled")
                    # Also clear any cached button state
                    self._side_buttons[i].clear_send_cache()

    def _setup_velocity_side_button_listeners(self):
        """Add velocity selection listeners to side buttons 0-4"""
        if not hasattr(self, '_velocity_button_listeners'):
            self._velocity_button_listeners = {}
            
        if self._side_buttons:
            for i in range(5):  # buttons 0-4
                if i < len(self._side_buttons) and self._side_buttons[i]:
                    # Create a proper listener function for each button
                    velocity_index = 4 - i  # button 0=velocity4, button 4=velocity0
                    
                    def create_velocity_listener(vel_idx):
                        return lambda value, sender: self._velocity_side_button_value(value, sender, vel_idx)
                    
                    listener = create_velocity_listener(velocity_index)
                    self._velocity_button_listeners[i] = listener
                    
                    # Add velocity selection listener
                    self._side_buttons[i].add_value_listener(listener, identify_sender=True)

    def _remove_velocity_side_button_listeners(self):
        """Remove velocity selection listeners from side buttons 0-4"""
        if hasattr(self, '_velocity_button_listeners') and self._velocity_button_listeners:
            if self._side_buttons:
                for i in range(5):  # buttons 0-4
                    if (i < len(self._side_buttons) and self._side_buttons[i] and 
                        i in self._velocity_button_listeners):
                        try:
                            # Remove the specific listener
                            self._side_buttons[i].remove_value_listener(self._velocity_button_listeners[i])
                        except (ValueError, RuntimeError):
                            # Listener might already be removed, ignore
                            pass
                        del self._velocity_button_listeners[i]
            # Clear the dictionary completely
            self._velocity_button_listeners.clear()
        
        # Reset the flag regardless
        self._velocity_listeners_added = False

    def _velocity_side_button_value(self, value, sender, velocity_index):
        """Handle velocity selection from side buttons 0-4"""
        if value != 0 and self.is_enabled() and self._note_editor and self._note_editor._velocity_mode_active:
            # Set the velocity index (0-4 maps to velocity levels)
            self._note_editor._velocity_index = velocity_index
            self._note_editor._velocity = self._note_editor.velocity_map[velocity_index]
            # Update the main velocity button to show the new selection
            self._note_editor._update_velocity_button()
            # Optionally show a message
            velocity_names = ["Low", "Med-Low", "Medium", "Med-High", "High"]
            if velocity_index < len(velocity_names):
                self._control_surface.show_message(f"Velocity: {velocity_names[velocity_index]}")

    def _clear_top_buttons(self):
        """Clear the visual display of all top buttons - reusable function"""
        # Clear all top buttons by turning them off and resetting their state
        if self._top_buttons:
            for i, button in enumerate(self._top_buttons):
                if button:
                    # Set to default disabled state to clear any colors/states
                    button.set_light("DefaultButton.Disabled")
                    button.turn_off()
                    # Clear any cached states
                    button.clear_send_cache()

    def _clear_matrix_buttons(self):
        """Clear the visual display of all matrix buttons - reusable function"""
        # Clear all matrix buttons by turning them off and resetting their state
        if self._matrix:
            for x in range(self._matrix.width()):
                for y in range(self._matrix.height()):
                    button = self._matrix.get_button(x, y)
                    if button:
                        # Set to default disabled state to clear any colors/states
                        button.set_light("DefaultButton.Disabled")
                        button.turn_off()
                        # Clear any cached states
                        button.clear_send_cache()

    def _clear_all_buttons(self):
        """Clear the visual display of ALL buttons (side, top, matrix) - master clearing function"""
        self._clear_side_buttons()
        self._clear_top_buttons()
        self._clear_matrix_buttons()
    
    def _comprehensive_refresh_on_exit(self):
        """Comprehensive refresh when exiting loop selector mode with corrections"""
        
        # Step 1: Clear ALL side buttons and force cache clearing
        self._clear_side_buttons()
        
        # Step 2: Force clear button caches to prevent stale state issues
        if self._side_buttons:
            for button in self._side_buttons:
                if button and hasattr(button, 'clear_send_cache'):
                    button.clear_send_cache()
        
        # Step 3: Reconnect functionality FIRST (timing correction)
        self._reconnect_side_button_functionality()
        
        # Step 4: Force component updates with explicit cache clearing
        # This ensures components actually update their buttons
        if self._note_selector:
            self._note_selector.set_enabled(False)  # Force state change
            self._note_selector.set_enabled(True)   # to trigger updates
            self._note_selector.update()
            
        if self._note_editor:
            self._note_editor.set_enabled(False)  # Force state change
            self._note_editor.set_enabled(True)   # to trigger updates  
            self._note_editor.update()
            
        if self._track_controller:
            self._track_controller.update()
        
        # Step 5: Update all buttons (after components are properly reconnected)
        self._update_buttons()
        
        # Step 6: Explicitly handle unassigned buttons (comprehensive approach needs this)
        self._disable_unassigned_side_buttons()
    
    def _disable_unassigned_side_buttons(self):
        """Disable side buttons that have no function assigned in main mode"""
        if self._side_buttons:
            for i, button in enumerate(self._side_buttons):
                if button:
                    # Check which buttons should be disabled based on current assignments
                    should_disable = False
                    
                    # side_button[0] = start/stop (always assigned)
                    # side_button[1] = lock button (assigned if _lock_button is set)
                    # side_button[2] = usually unassigned in step sequencer main mode
                    # side_button[3] = subBank selector (assigned to note selector)
                    # side_button[4] = usually unassigned in step sequencer main mode  
                    # side_button[5] = velocity button (assigned to note editor)
                    # side_button[6] = loop selector activation button (always assigned)
                    # side_button[7] = usually unassigned in step sequencer main mode
                    
                    if i == 2 or i == 4 or i == 7:  # Commonly unassigned buttons
                        should_disable = True
                    
                    if should_disable:
                        button.set_light("DefaultButton.Disabled")

    def make_button_blink_oldschool(self, button, bright_color="StepSequencer.NoteEditor.Velocity0", dim_color="DefaultButton.On"):
        """Old-school blinking: manually toggle between two colors using timed callbacks"""
        if not button:
            return
            
        # Stop any existing blink for this button
        self.stop_button_blink_oldschool(button)
        
        # Set up blinking state
        self._blinking_buttons[button] = {
            'state': False,  # False = dim, True = bright
            'colors': [dim_color, bright_color],
            'task': None
        }
        
        # Force immediate start of the blink cycle with current interval
        self._start_blink_cycle(button)
    
    def _start_blink_cycle(self, button):
        """Start or continue the blink cycle for a button"""
        if button not in self._blinking_buttons:
            return
            
        # Sync with Live's beat position instead of arbitrary timing
        try:
            if hasattr(self._control_surface, 'song') and self._control_surface.song():
                current_beat = self._control_surface.song().get_current_beats_song_time().beats
                # Determine if we should be bright or dim based on beat position
                beat_cycle = int(current_beat) % (self._blink_interval * 2)  # Full on/off cycle
                should_be_bright = beat_cycle < self._blink_interval
            else:
                # Fallback: toggle state
                blink_data = self._blinking_buttons[button]
                should_be_bright = not blink_data['state']
        except:
            # Fallback: toggle state  
            blink_data = self._blinking_buttons[button]
            should_be_bright = not blink_data['state']
        
        # Update state and set color
        blink_data = self._blinking_buttons[button]
        blink_data['state'] = should_be_bright
        color = blink_data['colors'][1 if should_be_bright else 0]
        button.set_light(color)
        
        # Schedule next check (check more frequently for responsiveness)
        if hasattr(self._control_surface, 'schedule_message'):
            self._control_surface.schedule_message(
                1,  # Check every beat for beat sync
                lambda: self._start_blink_cycle(button)
            )
            
    def _calculate_tempo_sync_interval(self):
        """Calculate the actual interval based on Live's current tempo"""
        try:
            if hasattr(self._control_surface, 'song') and self._control_surface.song():
                current_tempo = self._control_surface.song().tempo
                # Convert beats to schedule_message units
                # Assuming schedule_message uses some kind of ticks
                # 1 beat at 120 BPM = 500ms, so we scale accordingly
                beat_duration_ms = (60.0 / current_tempo) * 1000  # milliseconds per beat
                total_interval_ms = beat_duration_ms * self._blink_interval
                # Convert to schedule_message units (appears to be ~100ms per unit based on usage)
                return int(total_interval_ms / 100)
            else:
                # Fallback to fixed interval if tempo not available
                return self._blink_interval * 5
        except:
            # Fallback
            return self._blink_interval * 5
    
    def stop_button_blink_oldschool(self, button, final_color="DefaultButton.On"):
        """Stop old-school blinking and set final color"""
        if button in self._blinking_buttons:
            # Clean up blinking state
            del self._blinking_buttons[button]
        
        # Set final color
        if button:
            button.set_light(final_color)

    def _stop_all_blinking(self):
        """Stop all old-school blinking buttons"""
        for button in list(self._blinking_buttons.keys()):
            self.stop_button_blink_oldschool(button, "DefaultButton.Disabled")

# LOCK Button
    def _update_lock_button(self):
        if self.is_enabled():
            if self._lock_button != None:
                if self._clip != None:
                    if self._lock_to_track:
                        self._lock_button.set_on_off_values("StepSequencer.Lock.ToTrack")
                    else:
                        self._lock_button.set_on_off_values("StepSequencer.Lock.ToClip")
                    if self._is_locked:
                        self._lock_button.turn_on()
                    else:
                        self._lock_button.turn_off()
                else:
                    self._lock_button.set_light("DefaultButton.Disable")

    def set_lock_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (button != self._lock_button):
            if (self._lock_button != None):
                self._lock_button.remove_value_listener(self._lock_value)
            self._lock_button = button
            if (self._lock_button != None):
                assert isinstance(button, ButtonElement)                
                self._lock_button.add_value_listener(self._lock_value, identify_sender=True)

    def _lock_value(self, value, sender):
        assert (self._lock_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            now = time.time() 
            if ((value != 0) or (not self._lock_button.is_momentary())):
                self._last_lock_button_press = now
            else:
                if now - self._last_lock_button_press > self._long_press:
                    self._lock_to_track = (not self._lock_to_track)
                    if not self._is_locked:
                        self._control_surface.show_message("stepseq : locked to clip '"+str(self._clip.name)+"'")
                        self._is_locked = True
                    self._update_lock_button()
                else:
                    self._is_locked = (not self._is_locked)
                    if self._is_locked:
                        self._control_surface.show_message("stepseq : locked to clip '"+str(self._clip.name)+"'")
                    self._update_lock_button()
                    self._update_OSD()

# RIGHT Button
    def _update_right_button(self):
        if self.is_enabled():
            if self._right_button != None:
                if self._clip != None:
                    self._right_button.set_on_off_values("DefaultButton")
                    if self._loop_selector.can_scroll(1):
                        self._right_button.turn_on()
                    else:
                        self._right_button.turn_off()
                else:
                    self._right_button.set_light("DefaultButton.Disabled")

    def set_right_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (button != self._right_button):
            if (self._right_button != None):
                self._right_button.remove_value_listener(self._right_value)
            self._right_button = button
            if (self._right_button != None):
                self._right_button.add_value_listener(self._right_value, identify_sender=True)

    def _right_value(self, value, sender):
        assert (self._right_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            if ((value is not 0) or (not sender.is_momentary())):
                self._loop_selector.scroll(1)
                self._note_editor.request_display_page()
                self.update()

# LEFT Button
    def _update_left_button(self):
        if self.is_enabled():
            if self._left_button != None:
                if self._clip != None:
                    self._left_button.set_on_off_values("DefaultButton")
                    if self._loop_selector.can_scroll(-1):
                        self._left_button.turn_on()
                    else:
                        self._left_button.turn_off()
                else:
                    self._left_button.set_light("DefaultButton.Disabled")

    def set_left_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (button != self._left_button):
            if (self._left_button != None):
                self._left_button.remove_value_listener(self._left_value)
            self._left_button = button
            if (self._left_button != None):
                self._left_button.add_value_listener(self._left_value, identify_sender=True)

    def _left_value(self, value, sender):
        assert (self._right_button != None)
        assert (value in range(128))
        if self.is_enabled() and self._clip != None:
            if ((value is not 0) or (not sender.is_momentary())):
                self._loop_selector.scroll(-1)
                self._note_editor.request_display_page()
                self.update()

# UTILS
    def create_clip(self):
        if self.song().view.highlighted_clip_slot != None:
            clip_slot = self.song().view.highlighted_clip_slot
            if not clip_slot.has_clip:
                if self._mode == STEPSEQ_MODE_NORMAL:
                    clip_slot.create_clip(QUANTIZATION_MAP[self._quantization_index] * 8 * 4)
                else:
                    clip_slot.create_clip(QUANTIZATION_MAP[self._quantization_index] * 8)
                self._detect_scale_mode()
                clip_slot.fire()
                self.on_clip_slot_changed()
                self.update()

    def create_clip_for_selected_slot(self):
        """Create a clip in the currently selected track and scene"""
        if self.song().view.selected_track != None and self.song().view.selected_scene != None:
            track = self.song().view.selected_track
            scene = self.song().view.selected_scene
            try:
                scene_index = list(self.song().scenes).index(scene)
                clip_slot = track.clip_slots[scene_index]
                if not clip_slot.has_clip:
                    # Create 1 bar (4 beats) clip by default
                    clip_slot.create_clip(4.0)
                    self._detect_scale_mode()
                    clip_slot.fire()
                    self.on_clip_slot_changed()
                    self.update()
            except (ValueError, IndexError):
                # Fallback if scene/track not found
                pass

    def duplicate_clip(self):
        if self._clip_slot and self._clip_slot.has_clip:
            try:
                if not self._is_locked or self._lock_to_track:
                    track = self._clip_slot.canonical_parent
                    newIdx = track.duplicate_clip_slot(list(track.clip_slots).index(self._clip_slot))
                    self.song().view.selected_scene = self.song().scenes[newIdx]
                    #if track.clip_slots[newIdx] != None:
                        #track.clip_slots[newIdx].fire()
                    self.on_clip_slot_changed()
                    self.update()
            except Live.Base.LimitationError:
                pass
            except RuntimeError:
                pass
