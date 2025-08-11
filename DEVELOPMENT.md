# Launchpad95 Development Guide 🚀

This guide helps you develop and test changes to Launchpad95 much faster than restarting Ableton Live every time.

## Quick Start

1. **Make your code changes** to any `.py` file
2. **Choose a reload method** (see below)
3. **Test immediately** in Ableton Live!

## Reload Methods (Fastest to Slowest)

### 🥇 Method 1: Ableton Live Beta + Tools Menu (2 seconds)

**Best for: Active development**

This is the fastest and most reliable method:

1. **Get Ableton Live Beta**:
   - Sign up at [Ableton Beta Program](https://www.ableton.com/en/beta/)
   - Download Live 11 or 12 Beta

2. **Enable the hidden reload feature**:
   - Create an `options.txt` file in your Live Beta folder
   - Add this line: `-_ToolsMenuRemoteScripts`
   - Restart Live Beta

3. **Use the reload menu**:
   - In Live Beta: `Tools → Reload MIDI Remote Scripts`
   - Keyboard shortcut: `Cmd/Ctrl+Shift+Alt+R`

**Setup help**: Run `python reload_simple.py --setup-beta`

### 🥈 Method 2: MIDI Reload Signal (3 seconds)

**Best for: When you can't use Beta**

Uses a custom MIDI message to trigger reload:

```bash
# Install dependency
pip install mido python-rtmidi

# Send reload signal
python reload_script.py

# Watch files and auto-reload
python reload_script.py --watch
```

### 🥉 Method 3: Control Surface Toggle (10 seconds)

**Best for: No additional setup needed**

Manual toggle in Ableton preferences:

1. Go to `Preferences → Link/Tempo/MIDI`
2. Set Control Surface to `None`
3. Set it back to `Launchpad95`

## Development Workflow

### Option A: Automated with File Watching

```bash
# Terminal 1: Watch for changes
python reload_simple.py --watch

# Terminal 2: Edit your code
vim SkinMK1.py  # or your favorite editor

# When you save, you'll get reload instructions
```

### Option B: Manual Reload

```bash
# Edit your code
vim SkinMK1.py

# Reload when ready
python reload_script.py
# OR use Ableton Beta Tools menu
# OR toggle control surface in preferences
```

## Troubleshooting

### "No Launchpad MIDI ports found"
- Make sure your Launchpad is connected
- Check that Launchpad95 is selected in Ableton preferences
- Try `python -c "import mido; print(mido.get_output_names())"`

### "Reload signal sent but no change"
- Check Ableton's Log.txt for error messages
- Try toggling control surface in preferences instead
- Make sure you saved your Python file

### Python files not reloading
- Restart Ableton completely (some changes require full restart)
- Check for syntax errors in your Python files
- Verify the modified Launchpad.py includes reload handling

## Log Files

Check these locations for error messages:

**macOS**: `~/Library/Preferences/Ableton/Live X.X.X/Log.txt`
**Windows**: `%APPDATA%\Ableton\Live X.X.X\Preferences\Log.txt`

## What Each Script Does

- **`reload_script.py`**: Full-featured MIDI reload with file watching
- **`reload_simple.py`**: Helper script with instructions and file monitoring
- **Modified `Launchpad.py`**: Handles custom reload MIDI messages

## Tips for Fast Development

1. **Use Live Beta** with the Tools menu - it's by far the fastest
2. **Save frequently** and reload often rather than making big changes
3. **Test one change at a time** to isolate issues
4. **Use file watching** to get notified when files change
5. **Check logs** if something doesn't work as expected

## Advanced: Custom Reload Triggers

You can trigger reloads from your own scripts:

```python
import mido

# Send custom reload sysex
with mido.open_output('Launchpad') as port:
    msg = mido.Message('sysex', data=[0x00, 0x20, 0x29, 0x7F, 0x7F])
    port.send(msg)
```

---

**Happy coding!** 🎹✨

This development setup can reduce your iteration time from ~30 seconds (full restart) to ~2-3 seconds (reload), making Launchpad95 development much more enjoyable! 