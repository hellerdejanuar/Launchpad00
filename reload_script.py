#!/usr/bin/env python3
"""
Launchpad95 Reload Script

This script allows you to reload the Launchpad95 control surface script 
without restarting Ableton Live, making development much faster.

Usage:
1. Make your changes to the Launchpad95 Python files
2. Run this script: python reload_script.py
3. The changes should be reflected immediately in Ableton

Requirements:
- Python 3.x
- Ableton Live should be running with Launchpad95 loaded

Note: This works by sending a MIDI message that triggers the refresh_state method.
"""

import time
import mido
import sys
import os

def find_launchpad_ports():
    """Find available Launchpad MIDI ports"""
    input_ports = mido.get_input_names()
    output_ports = mido.get_output_names()
    
    launchpad_inputs = [port for port in input_ports if 'launchpad' in port.lower()]
    launchpad_outputs = [port for port in output_ports if 'launchpad' in port.lower()]
    
    return launchpad_inputs, launchpad_outputs

def send_reload_message():
    """Send a special MIDI message to trigger reload"""
    try:
        launchpad_inputs, launchpad_outputs = find_launchpad_ports()
        
        if not launchpad_outputs:
            print("❌ No Launchpad MIDI output ports found!")
            print("Available output ports:", mido.get_output_names())
            return False
        
        # Use the first available Launchpad output port
        port_name = launchpad_outputs[0]
        print(f"🎹 Using MIDI port: {port_name}")
        
        with mido.open_output(port_name) as outport:
            # Send a sysex message that will trigger the Launchpad to refresh
            # This is a custom sysex that can be caught by our modified script
            sysex_msg = mido.Message('sysex', data=[0x00, 0x20, 0x29, 0x7F, 0x7F])  # Custom reload command
            outport.send(sysex_msg)
            
            # Also send a control change that might trigger update
            cc_msg = mido.Message('control_change', channel=0, control=127, value=127)
            outport.send(cc_msg)
            
            print("✅ Reload signal sent to Launchpad95!")
            return True
            
    except Exception as e:
        print(f"❌ Error sending reload message: {e}")
        return False

def watch_file_changes():
    """Watch for file changes and auto-reload"""
    print("👀 Watching for file changes... Press Ctrl+C to stop")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_files = []
    file_times = {}
    
    # Get all Python files in the directory
    for file in os.listdir(script_dir):
        if file.endswith('.py') and file != 'reload_script.py':
            full_path = os.path.join(script_dir, file)
            python_files.append(full_path)
            file_times[full_path] = os.path.getmtime(full_path)
    
    print(f"📁 Watching {len(python_files)} Python files for changes...")
    
    try:
        while True:
            time.sleep(1)  # Check every second
            
            for file_path in python_files:
                try:
                    current_time = os.path.getmtime(file_path)
                    if current_time > file_times[file_path]:
                        file_name = os.path.basename(file_path)
                        print(f"🔄 File changed: {file_name}")
                        file_times[file_path] = current_time
                        
                        # Wait a moment for file to be fully written
                        time.sleep(0.5)
                        
                        if send_reload_message():
                            print(f"✅ Reloaded Launchpad95 due to changes in {file_name}")
                        else:
                            print(f"❌ Failed to reload after changes in {file_name}")
                        
                        time.sleep(2)  # Avoid rapid successive reloads
                        break
                except OSError:
                    # File might have been deleted/moved
                    continue
                    
    except KeyboardInterrupt:
        print("\n🛑 Stopped watching for file changes")

def main():
    print("🚀 Launchpad95 Reload Script")
    print("=" * 40)
    
    # Check if mido is installed
    try:
        import mido
    except ImportError:
        print("❌ mido library not found!")
        print("📦 Install it with: pip install mido")
        print("   or: pip install python-rtmidi")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--watch':
        watch_file_changes()
    else:
        print("🔄 Sending reload signal...")
        if send_reload_message():
            print("✅ Done! Your changes should be reflected in Ableton now.")
            print("\n💡 Tip: Use 'python reload_script.py --watch' to auto-reload on file changes")
        else:
            print("❌ Reload failed. Make sure:")
            print("   1. Ableton Live is running")
            print("   2. Launchpad95 is selected as control surface")
            print("   3. Your Launchpad is connected")

if __name__ == "__main__":
    main() 