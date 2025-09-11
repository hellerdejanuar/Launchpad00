from _Framework.ControlSurfaceComponent import ControlSurfaceComponent
from _Framework.ButtonElement import ButtonElement
import time
from .Log import log
class NoteEditorComponent(ControlSurfaceComponent):

	def __init__(self, stepsequencer = None, matrix = None, control_surface = None):
		ControlSurfaceComponent.__init__(self)
		self.set_enabled(False)
		self._stepsequencer = stepsequencer
		self._control_surface = control_surface
		self._clip = None
		self._note_cache = None
		self._playhead = None

		# playback step indicator - enabled by default for 4-button tall cursor
		self.display_metronome = True
		self.metronome_color = "StepSequencer.NoteEditor.Metronome"
		
		# playback page indicator
		self._current_page = -1
		# Normal Color map.
		self.lanes_color_map = "StepSequencer.NoteEditor.LanesColorMap"
		# Velocity color map. this must remain of length 3. WHY???
		self.velocity_map = [20, 50, 80, 105, 127]
		self.velocity_color_map = [	"StepSequencer.NoteEditor.Velocity0", "StepSequencer.NoteEditor.Velocity1", "StepSequencer.NoteEditor.Velocity2", "StepSequencer.NoteEditor.Velocity3", "StepSequencer.NoteEditor.Velocity4"]
		
		# other colors
		self.muted_note_color = "StepSequencer.NoteEditor.Muted"
		self.playing_note_color = "StepSequencer.NoteEditor.Playing"

		#hold button for 500 ms
		self.long_button_press = 0.500

		# buttons
		self._matrix = None
		self._mute_shift_button = None
		self._velocity_button = None
		self._velocity_shift_button = None

		# displayed page
		self._page = 0
		self._display_page = False
		self._display_page_time = time.time()

		# notes
		self._key_indexes = [36, 37, 38, 39, 40, 41, 42, 43]
		self._key_index_is_in_scale = [True, False, True, True, False, True, False, True]
		self._key_index_is_root_note = [True, False, False, False, False, False, False, False]
		self._number_of_lines_per_note = 1

		# Matrix layout: 4x16 displayed as two 4x8 sub-matrices (initialized later)
		self._virtual_width = 16
		self._physical_width = 8
		self._physical_height = 8
		self._virtual_height = 4

		# clip
		self._force_update = True

		# quantization
		self._quantization = 16

		# velocity
		self._velocity_index = 3
		self._velocity = self.velocity_map[self._velocity_index]
		self._is_velocity_shifted = False
		self._velocity_notes_pressed = 0
		self._velocity_last_press = time.time()

		# modes
		self._is_mute_shifted = False
		self._is_mutlinote = False
		self._velocity_mode_active = False
			
		if (self.is_multinote):
			log("is_multinote")	
		else:
			log("not is_multinote")
			
		# matrix
		if matrix != None:
			self.set_matrix(matrix)

	def disconnect(self):
		self._matrix = None
		self._velocity_button = None
		self._clip = None
			

	@property
	def is_multinote(self):
		return self._is_mutlinote

	def set_multinote(self, is_mutlinote, number_of_lines_per_note):
		self._is_mutlinote = is_mutlinote
		self._number_of_lines_per_note = number_of_lines_per_note

	@property
	def quantization(self):
		return self._quantization

	def set_quantization(self, quantization):
		self._quantization = quantization

	def set_scale(self, scale):
		self._scale = scale

	def set_diatonic(self, diatonic):
		self._diatonic = diatonic

	@property
	def key_indexes(self):
		return self._key_indexes

	def set_key_indexes(self, key_indexes):
		self._key_indexes = key_indexes

	def set_key_index_is_in_scale(self, key_index_is_in_scale):
		self._key_index_is_in_scale = key_index_is_in_scale

	def set_key_index_is_root_note(self, key_index_is_root_note):
		self._key_index_is_root_note = key_index_is_root_note

	@property
	def height(self):
		return self._virtual_height

	def set_height(self, height):
		self._height = height
		self._virtual_height = 4  # Always use 4 for the new layout

	@property
	def width(self):
		return self._virtual_width  # Return logical width (16 steps)

	@property
	def number_of_lines_per_note(self):
		if self.is_multinote:
			return self._number_of_lines_per_note
		else:
			return self.height

	def set_page(self, page):
		if self.is_multinote:
			self._page = page
		else:
			self._page = int(page / 4)  # 4 lines per note (32 steps seq)

	def set_clip(self, clip):
		self._clip = clip

	def set_note_cache(self, note_cache):
		self._note_cache = note_cache

	def set_playhead(self, playhead): # Playing cursor
		self._playhead = playhead
		self._update_matrix()

	def update_notes(self): # Deprecated ???
		if self._clip != None:
			self._clip.select_all_notes()
			note_cache = self._clip.get_selected_notes()
			self._clip.deselect_all_notes()
			if self._clip_notes != note_cache:
				self._clip_notes = note_cache
		self._update_matrix()

	def update(self, force=False):
		if self.is_enabled():
			if force:
				self._force_update = True
			self._update_velocity_button()
			self._update_matrix()

	# Display the third amber column to show the current page in multinote mode OK
	def _display_selected_page(self): # OK
		# Display page marker on both sub-matrices
		logical_x = self._page % self.width
		if logical_x < self.width:
			physical_x, physical_y_top = self._logical_to_physical_coords(logical_x, 0)
			physical_x, physical_y_bottom = self._logical_to_physical_coords(logical_x, 3)
			for y in range(self._physical_height):
				# Only mark the column corresponding to the page
				if logical_x == physical_x or logical_x == physical_x + 8:
					self._grid_back_buffer[physical_x][y] = "StepSequencer.NoteEditor.PageMarker"
		
	# Displays 3 buttons for the root of the scale and 1 for the in scale notes 	
	def _display_note_markers(self, selected_subBank="B"):
		# (out of scale notes buttons are dark) OK

		# for i in range(0, int(self.height / self.number_of_lines_per_note)):
		# # 	NoteBackground = f"NoteBackground_{selected_subBank}{i % 4}"
		# 	# selected_subBank_background = f"{selected_subBank}{i % 4}"
		# 	for j in range(0, self.width):
		# 		self._grid_back_buffer[j][i] = f"StepSequencer.NoteEditor.NoteBackground_{selected_subBank}"
		pass
#*********************MATRIX*********************
	
	#Add listener and initialize note buffers OK
	def set_matrix(self, matrix): 
		if (matrix != self._matrix):
			if (self._matrix != None):
				self._matrix.remove_value_listener(self._matrix_value)
			self._matrix = matrix
			if (self._matrix != None):
				self._matrix.add_value_listener(self._matrix_value)
				self._width = self._matrix.width()
				self._height = self._matrix.height()
				# Set up the new layout properties
				self._physical_width = self._width  # 8
				self._physical_height = self._height  # 8
				# Grid buffers remain 8x8 for the physical matrix
				self._grid_buffer = [[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]
				self._grid_back_buffer = [[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]

	def _logical_to_physical_coords(self, logical_x, logical_y):
		"""Convert logical 4x16 coordinates to physical 8x8 coordinates"""
		# Clamp values to safe ranges
		logical_x = max(0, min(logical_x, 15))  # 0-15
		logical_y = max(0, min(logical_y, 3))   # 0-3 for 4 note lanes
		
		# logical_x: 0-15 (16 steps), logical_y: 0-3 (4 note lanes)
		# Upper 4x8: steps 0-7, y=0-3 -> physical x=0-7, y=0-3
		# Lower 4x8: steps 8-15, y=0-3 -> physical x=0-7, y=4-7
		if logical_x < 8:
			# Upper sub-matrix (steps 0-7)
			physical_x = logical_x
			physical_y = logical_y
		else:
			# Lower sub-matrix (steps 8-15)
			physical_x = logical_x - 8
			physical_y = logical_y + 4
		return physical_x, physical_y

	def _physical_to_logical_coords(self, physical_x, physical_y):
		"""Convert physical 8x8 coordinates to logical 4x16 coordinates"""
		# Clamp values to safe ranges
		physical_x = max(0, min(physical_x, 7))  # 0-7
		physical_y = max(0, min(physical_y, 7))  # 0-7
		
		# physical_x: 0-7, physical_y: 0-7
		if physical_y < 4:
			# Upper sub-matrix
			logical_x = physical_x
			logical_y = physical_y
		else:
			# Lower sub-matrix
			logical_x = physical_x + 8
			logical_y = physical_y - 4
		return logical_x, logical_y



	# Updates the LP LEDs OK
	def _update_matrix(self):  
		if self.is_enabled() and self._matrix!=None:
			

			# clear back buffer. BACKGROUND COLOR <--
			for x in range(self._physical_width):
				for y in range(self._physical_height):
					self._grid_back_buffer[x][y] = "DefaultButton.Disabled"

			# update back buffer
			if self._clip != None and self._note_cache != None:

				# playback position (using logical coordinates)
				if self._playhead != None:
					play_position = self._playhead  # position in beats (integer = number of beats, decimal subdivisions)
					play_page = int(play_position / self.quantization / self.width / self.number_of_lines_per_note)
					play_row = int(play_position / self.quantization / self.width) % self.number_of_lines_per_note
					play_logical_x_position = int(play_position / self.quantization) % self.width
					play_logical_y_position = int(play_position / self.quantization / self.width) % self._virtual_height
					# Convert to physical coordinates for display
					play_physical_x, play_physical_y = self._logical_to_physical_coords(play_logical_x_position, play_logical_y_position)
				else:
					play_position = -1
					play_page = -1
					play_row = -1
					play_logical_x_position = -1
					play_logical_y_position = -1
					play_physical_x = -1
					play_physical_y = -1
				# Note: metronome cursor will be applied after all notes are processed for highest priority
 
				# Display the selected page
				if(self._display_page):
					self._display_selected_page()
					if self._display_page_time + 0.25 < time.time():
						self._display_page = False
						


				# Display the notes in the 1st left column 
				if self.is_multinote:
					# self._display_note_markers()
					# Display the current played page
					if(self._current_page !=play_page):
						self._current_page=play_page
						self._display_current_page()


				# display clip notes
				for note in self._note_cache:
					note_position = note[1] # decimal value of a beat (1=beat, same as playhead)
					note_key = note[0]  # key: 0-127 MIDI note #
					note_velocity = note[3] # velocity: 0-127 value #
					note_muted = note[4]#Boolean
					note_page = int(note_position / self.quantization / self.width / self.number_of_lines_per_note)
					note_logical_x_position = int(note_position / self.quantization) % self.width
					
					# Find which note lane this belongs to
					try:
						note_idx = self.key_indexes.index(note_key)
					except ValueError:
						note_idx = -1
					
					if note_idx != -1:
						# Calculate logical Y position (note lane: 0-3)
						note_logical_y_position = note_idx
						
						# Convert to physical coordinates
						note_physical_x, note_physical_y = self._logical_to_physical_coords(note_logical_x_position, note_logical_y_position)
					else:
						# Note not in our key range, skip it
						note_logical_x_position = -1
						note_logical_y_position = -1
						note_physical_x = -1
						note_physical_y = -1
				
					#Set note color
					if (note_physical_x >= 0 and note_physical_y >= 0):
						if self._velocity_mode_active == True: # velocity mode active
							# compute Velocity colors
							velocity_color = self.velocity_color_map[0]
							for index in range(len(self.velocity_map)):
								if note_velocity >= self.velocity_map[index]:
									velocity_color = self.velocity_color_map[index]
							# highligh playing notes in <playing_note_color>. even if they are from other pages.
							# BUT don't override metronome cursor
							if  not note_muted \
									and note_page == play_page \
							    and play_logical_x_position == note_logical_x_position  \
									and play_logical_y_position == note_logical_y_position  \
									and self.song().is_playing  \
									and self._clip.is_playing \
									and self._grid_back_buffer[note_physical_x][note_physical_y] != self.metronome_color:
								self._grid_back_buffer[note_physical_x][note_physical_y] = self.playing_note_color
							elif note_page == self._page:  # if note is in current page, then update grid
								# do not erase current note highlight or metronome cursor
								if (self._grid_back_buffer[note_physical_x][note_physical_y] != self.playing_note_color and 
									self._grid_back_buffer[note_physical_x][note_physical_y] != self.metronome_color):
									if note_muted:
										self._grid_back_buffer[note_physical_x][note_physical_y] = self.muted_note_color
									else:
										self._grid_back_buffer[note_physical_x][note_physical_y] = velocity_color

						elif self._velocity_mode_active == False: # velocity mode inactive
							lane = note_logical_y_position % 4
							lane_color = self.lanes_color_map+f".{self._stepsequencer._selected_subBank}{lane}"
							# highligh playing notes in <playing_note_color>. even if they are from other pages.
							# BUT don't override metronome cursor
							if  not note_muted \
									and note_page == play_page \
									and play_logical_x_position == note_logical_x_position  \
									and play_logical_y_position == note_logical_y_position  \
									and self.song().is_playing  \
									and self._clip.is_playing \
									and self._grid_back_buffer[note_physical_x][note_physical_y] != self.metronome_color:
								self._grid_back_buffer[note_physical_x][note_physical_y] = self.playing_note_color

							elif note_page == self._page:  # if note is in current page, then update grid
								# do not erase current note highlight or metronome cursor
								if (self._grid_back_buffer[note_physical_x][note_physical_y] != self.playing_note_color and 
									self._grid_back_buffer[note_physical_x][note_physical_y] != self.metronome_color):
									if note_muted:
										self._grid_back_buffer[note_physical_x][note_physical_y] = self.muted_note_color
									else:
										self._grid_back_buffer[note_physical_x][note_physical_y] = lane_color


				#Display the column to show the page for half a second
				if self._display_page:
					if time.time() - self._display_page_time > 0.5:
						self._display_page = False
					self._display_selected_page()

				# Apply metronome cursor LAST to ensure highest priority - 4 buttons tall cursor
				if(self.display_metronome):
					# Show cursor when playing OR when there's a valid playhead position
					if play_logical_x_position >= 0 and (
						(self._clip.is_playing and self.song().is_playing) or 
						(self._playhead is not None)
					):
						# Display cursor on all 4 note lanes for the current step
						for lane in range(4):  # 4 note lanes
							cursor_physical_x, cursor_physical_y = self._logical_to_physical_coords(play_logical_x_position, lane)
							if cursor_physical_x >= 0 and cursor_physical_y >= 0:
								self._grid_back_buffer[cursor_physical_x][cursor_physical_y] = "StepSequencer.NoteEditor.Metronome"

			# caching : compare back buffer to buffer and update grid. this should minimize midi traffic quite a bit.
			for x in range(self._physical_width):
				for y in range(self._physical_height):
					if self._grid_back_buffer[x][y] != self._grid_buffer[x][y] or self._force_update:
						self._grid_buffer[x][y] = self._grid_back_buffer[x][y]
						self._matrix.get_button(x, y).set_light(self._grid_buffer[x][y])
			self._force_update = False

	def request_display_page(self): # Reset page column display timer
		self._display_page = True
		self._display_page_time = time.time()			
	
	

	# matrix buttons listener OK
	def _matrix_value(self, value, x, y, is_momentary): 
		if self.is_enabled() and y < self._physical_height: #Height value can be 8 (MULTINOTE/SCALE_EDIT) or 4 (STEPSEQ_MODE_NORMAL)
			if ((value != 0) or (not is_momentary)): #if NOTE_ON or button is toggle
				self._stepsequencer._was_velocity_shifted = False # Some previous state logic INVESTIGATE
				# Convert physical coordinates to logical coordinates
				logical_x, logical_y = self._physical_to_logical_coords(x, y)
				self._matrix_value_message([value, logical_x, logical_y, is_momentary])

	#Add/Delete/Mute notes in the cache for PL light management and in the Live's Clip OK
	def _matrix_value_message(self, values):  # (value=127/0, x=idx, y=idx, is_momentary=True) 
		value = values[0]
		x = values[1]  # logical x (0-15)
		y = values[2]  # logical y (0-3)
		is_momentary = values[3]
		"""(pitch, time, duration, velocity, mute state)"""
		assert (self._matrix != None)
		assert (value in range(128))
		assert (x in range(self.width))  # logical width (16)
		assert (y in range(self._virtual_height))  # logical height (4)
		assert isinstance(is_momentary, type(False))

		if self.is_enabled() and self._clip == None:
			self._stepsequencer.create_clip()

		elif self.is_enabled() and self._clip != None:
			if value != 0 or not is_momentary: #if NOTE_ON or button is toggle
				if(self._is_velocity_shifted):
					self._velocity_notes_pressed = self._velocity_notes_pressed + 1 #Just changing some note velocity

				# note data - now using logical coordinates
				# Time calculation: position in the sequence
				time = self.quantization * (self._page * self.width + x)
				# Pitch: directly from the y coordinate (note lane)
				pitch = self._key_indexes[y]
				velocity = self._velocity #setted by velocity button
				duration = self.quantization #setted by quantization button in StepSequencerComponent

				# TODO: use new better way for editing clip

				self._clip.select_all_notes()
				note_cache = self._clip.get_selected_notes()
				if self._note_cache != note_cache:
					self._note_cache = note_cache

				note_cache = list(self._note_cache)
				for note in note_cache:
					if pitch == note[0] and time == note[1]:
						if self._is_velocity_shifted:
							# update velocity of the note
							new_velocity_index = 0
							for index in range(len(self.velocity_map)):
								if note[3] >= self.velocity_map[index]:
									new_velocity_index = (index + 1) % len(self.velocity_map)
							note_cache.append([note[0], note[1], note[2], self.velocity_map[new_velocity_index], note[4]])  # (pitch, time, duration, velocity, mute state)
						elif not self._is_mute_shifted:
							note_cache.remove(note)
						else:
							# mute / un mute note.
							note_cache.append([note[0], note[1], note[2], note[3], not note[4]])  # (pitch, time, duration, velocity, mute state)
						break
				else:
					note_cache.append([pitch, time, duration, velocity, self._is_mute_shifted]) # (pitch, time, duration, velocity, mute state)
				self._clip.select_all_notes()
				self._clip.replace_selected_notes(tuple(note_cache))

				note_cache = self._clip.get_selected_notes()
				if self._note_cache != note_cache:
					self._note_cache = note_cache

#*********************VELOCITY/BTN_SHIFT*********************

	# Updates the velocity button light OK			
	def _update_velocity_button(self): 
		if self.is_enabled() and self._velocity_button != None:
			if self._clip != None:
				# Always show current velocity color, don't use special "VelocityShifted" state
				self._velocity_button.set_light("StepSequencer.NoteEditor.Velocity"+str(self._velocity_index))
			else:
				self._velocity_button.set_light("DefaultButton.Disabled")

	# Refresh button and its listener OK
	def set_velocity_button(self, button): 
		assert (isinstance(button, (ButtonElement, type(None))))
		if (button != self._velocity_button):
			if (self._velocity_button != None):
				self._velocity_button.remove_value_listener(self._velocity_value)
			self._velocity_button = button
			if (self._velocity_button != None):
				self._velocity_button.add_value_listener(self._velocity_value, identify_sender=True)

			
	# Handle button shifted and velocity selection OK			
	def _velocity_value(self, value, sender): 
		pass

	def _enable_velocity_mode(self):
		self._velocity_notes_pressed = 0
		self._is_velocity_shifted = True
		self._velocity_mode_active = True
		#While velocity is pressed, can play sounds using notes region-- Maybe a clash with velocity mode
		self._stepsequencer._track_controller._implicit_arm = True #Arm the track to force play MIDI notes
		self._stepsequencer._track_controller._do_implicit_arm(True)
		self._velocity_last_press = time.time()
		self._update_velocity_button()
		self._update_matrix()
		self._stepsequencer._note_selector.update()
		self._stepsequencer._disconnect_side_button_functionality_for_velocity()

	def _disable_velocity_mode(self):
		if self._velocity_notes_pressed == 0 and time.time() - self._velocity_last_press < self.long_button_press:
			# cycle thru velocities
			self._velocity_index = (len(self.velocity_map) + self._velocity_index + 1) % len(self.velocity_map)
			self._velocity = self.velocity_map[self._velocity_index]
		self._stepsequencer._track_controller._implicit_arm = False
		if self._is_velocity_shifted:
			self._stepsequencer._track_controller._do_implicit_arm(False)
		self._is_velocity_shifted = False
		self._velocity_mode_active = False
		self._update_velocity_button()
		self._update_matrix()
		self._stepsequencer._note_selector.update()
		self._stepsequencer._reconnect_side_button_functionality_for_velocity()

#*********************MUTE/BTN_SHIFT*********************

	# Mute all entries for a given MIDI note OK
	def mute_lane(self, pitch_to_mute):
		if self.is_enabled() and self._clip != None:
			self._clip.select_all_notes()
			note_cache = self._clip.get_selected_notes()
			if self._note_cache != note_cache:
				self._note_cache = note_cache
			note_cache = list(self._note_cache)
			notes_changed = 0
			for note in self._note_cache:
				if note[0] == pitch_to_mute:
					notes_changed = notes_changed + 1
					note_to_mute = note
					note_cache.remove(note)
					note_cache.append([note_to_mute[0], note_to_mute[1], note_to_mute[2], note_to_mute[3], not note_to_mute[4]])
			if notes_changed > 0:
				self._clip.select_all_notes()
				self._clip.replace_selected_notes(tuple(note_cache))
				note_cache = self._clip.get_selected_notes()
			self.update()

	# Display the third red column to show the current page in multinote mode each time that the metronome goes to new pageOK
	def _display_current_page(self): # OK
		# Display current page marker on both sub-matrices
		logical_x = self._current_page % self.width
		if logical_x < self.width:
			physical_x, _ = self._logical_to_physical_coords(logical_x, 0)
			for y in range(self._physical_height):
				# Only mark the column corresponding to the current page
				if logical_x == physical_x or logical_x == physical_x + 8:
					if(self._page==self._current_page):
						self._grid_back_buffer[physical_x][y] = "StepSequencer.NoteEditor.CurrentPageMarkerPlay"
					else:
						self._grid_back_buffer[physical_x][y] = "StepSequencer.NoteEditor.CurrentPageMarker"
