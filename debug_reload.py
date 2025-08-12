#!/usr/bin/env python3
"""
Debug Reload Script for Launchpad95

This script helps debug why the reload isn't working by:
1. Testing MIDI connections
2. Sending debug signals
3. Checking log files
4. Providing specific troubleshooting steps
"""

import mido
import time
import os
import sys
from pathlib import Path

def check_ableton_logs():
    """Check Ableton Live log files for reload messages"""
    print("📋 Checking Ableton Live logs...")
    
    # Common log file locations
    possible_paths = [
        # macOS
        Path.home() / "Library/Preferences/Ableton",
        # Launchpad95 custom log
        Path.home() / "Documents/Ableton/User Library/Remote Scripts/log.txt",
        # Windows (if running on Windows)
        Path.home() / "AppData/Roaming/Ableton",
    ]
    
    log_files_found = []
    
    for base_path in possible_paths:
        if base_path.exists():
            if base_path.name == "log.txt":
                log_files_found.append(base_path)
            else:
                # Search for Live version folders
                for item in base_path.iterdir():
                    if item.is_dir() and "Live" in item.name:
                        log_file = item / "Log.txt"
                        if log_file.exists():
                            log_files_found.append(log_file)
    
    print(f"📁 Found {len(log_files_found)} log files:")
    for log_file in log_files_found:
        print(f"   • {log_file}")
    
    # Check recent entries for reload messages
    reload_messages = []
    for log_file in log_files_found:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-50:]  # Last 50 lines
                
            for i, line in enumerate(recent_lines):
                if any(keyword in line for keyword in ['🔄', 'Reload', 'reload', 'Launchpad95']):
                    reload_messages.append(f"{log_file.name}: {line.strip()}")
        except Exception as e:
            print(f"   ⚠️  Could not read {log_file}: {e}")
    
    if reload_messages:
        print(f"\n✅ Found {len(reload_messages)} reload-related messages:")
        for msg in reload_messages[-10:]:  # Show last 10
            print(f"   {msg}")
    else:
        print("\n❌ No reload messages found in logs")
        print("   This suggests the reload signal isn't reaching Ableton")
    
    return reload_messages

def test_midi_connection():
    """Test MIDI connection and send debug messages"""
    print("🎹 Testing MIDI connection...")
    
    try:
        # Get available ports
        output_ports = mido.get_output_names()
        print(f"📤 Available MIDI output ports:")
        for i, port in enumerate(output_ports):
            print(f"   {i}: {port}")
        
        # Find Launchpad ports
        launchpad_ports = [port for port in output_ports if 'launchpad' in port.lower()]
        
        if not launchpad_ports:
            print("\n❌ No Launchpad ports found!")
            print("💡 Make sure:")
            print("   1. Launchpad is connected")
            print("   2. Launchpad95 is selected in Ableton preferences")
            print("   3. Input/Output are set correctly in preferences")
            return False
        
        print(f"\n🎹 Found Launchpad ports: {launchpad_ports}")
        
        # Test with first Launchpad port
        port_name = launchpad_ports[0]
        print(f"\n🔌 Testing connection to: {port_name}")
        
        with mido.open_output(port_name) as outport:
            print("✅ Successfully opened MIDI port")
            
            # Send a simple note to test basic connection
            print("🎵 Sending test note...")
            note_on = mido.Message('note_on', channel=0, note=60, velocity=64)
            note_off = mido.Message('note_off', channel=0, note=60, velocity=0)
            
            outport.send(note_on)
            time.sleep(0.1)
            outport.send(note_off)
            print("✅ Test note sent")
            
            # Send our custom reload sysex
            print("🔄 Sending reload signal...")
            reload_msg = mido.Message('sysex', data=[0x00, 0x20, 0x29, 0x7F, 0x7F])
            outport.send(reload_msg)
            print("✅ Reload signal sent")
            
            # Send a few more variations to test
            print("🔄 Sending alternative reload signals...")
            
            # Try with different data
            alt_msg1 = mido.Message('sysex', data=[0x00, 0x20, 0x29, 0x7F, 0x7F, 0x7F])
            outport.send(alt_msg1)
            
            # Try control change that might trigger update
            cc_msg = mido.Message('control_change', channel=0, control=127, value=127)
            outport.send(cc_msg)
            
            print("✅ Alternative signals sent")
            
        return True
        
    except Exception as e:
        print(f"❌ MIDI test failed: {e}")
        return False

def check_launchpad_modifications():
    """Check if Launchpad.py has been modified correctly"""
    print("🔧 Checking Launchpad.py modifications...")
    
    script_dir = Path(__file__).parent
    launchpad_file = script_dir / "Launchpad.py"
    
    if not launchpad_file.exists():
        print("❌ Launchpad.py not found!")
        return False
    
    try:
        with open(launchpad_file, 'r') as f:
            content = f.read()
        
        # Check for our reload modifications
        checks = [
            ("Custom reload sysex message", "Custom reload sysex message" in content),
            ("Reload signal log", "🔄 Reload signal received" in content),
            ("Success log", "✅ Launchpad95 reload completed" in content),
            ("Error handling", "❌ Error during reload" in content),
            ("Handle sysex method", "def handle_sysex" in content),
        ]
        
        all_good = True
        for check_name, check_result in checks:
            status = "✅" if check_result else "❌"
            print(f"   {status} {check_name}")
            if not check_result:
                all_good = False
        
        if all_good:
            print("✅ Launchpad.py modifications look correct")
        else:
            print("❌ Launchpad.py is missing some reload modifications")
            
        return all_good
        
    except Exception as e:
        print(f"❌ Could not check Launchpad.py: {e}")
        return False

def provide_specific_solutions(midi_ok, logs_found, modifications_ok):
    """Provide specific solutions based on test results"""
    print("\n" + "="*50)
    print("🎯 SPECIFIC SOLUTIONS")
    print("="*50)
    
    if not midi_ok:
        print("\n🔧 MIDI Connection Issues:")
        print("1. Check Ableton Live Preferences → Link/Tempo/MIDI")
        print("2. Make sure Launchpad95 is selected as Control Surface")
        print("3. Set Input to 'Launchpad' and Output to 'Launchpad'")
        print("4. For Launchpad X/Mini MK3: use 'LPX MIDI' not 'DAW'")
        print("5. Restart Ableton Live after changing settings")
        
    elif not modifications_ok:
        print("\n🔧 Missing Reload Code:")
        print("1. The Launchpad.py file is missing reload modifications")
        print("2. Make sure you applied the handle_sysex changes")
        print("3. Try re-applying the Launchpad.py modifications")
        
    elif not logs_found:
        print("\n🔧 Signal Not Reaching Ableton:")
        print("1. Try the 'Control Surface Toggle' method instead:")
        print("   • Go to Preferences → Link/Tempo/MIDI")
        print("   • Set Control Surface to 'None'")
        print("   • Set it back to 'Launchpad95'")
        print("2. Or use Ableton Live Beta with Tools → Reload MIDI Remote Scripts")
        print("3. Make sure you saved your Python changes first")
        
    else:
        print("\n🔧 Reload Signal Working But Changes Not Updating:")
        print("1. Some changes require full Ableton restart:")
        print("   • Import statements")
        print("   • Class definitions")
        print("   • Module structure changes")
        print("2. For color changes, try:")
        print("   • Toggle between different modes on your Launchpad")
        print("   • Press buttons to force LED updates")
        print("3. Check for Python syntax errors in your changes")

def main():
    print("🔍 Launchpad95 Reload Debugger")
    print("="*40)
    print("This will help figure out why reload isn't working\n")
    
    # Run all tests
    midi_ok = test_midi_connection()
    print()
    
    modifications_ok = check_launchpad_modifications()
    print()
    
    logs_found = check_ableton_logs()
    print()
    
    # Wait a moment for logs to update
    print("⏳ Waiting 3 seconds for logs to update...")
    time.sleep(3)
    
    # Check logs again
    print("\n🔄 Checking logs again...")
    recent_logs = check_ableton_logs()
    
    # Provide solutions
    provide_specific_solutions(midi_ok, bool(recent_logs), modifications_ok)
    
    print(f"\n{'='*50}")
    if midi_ok and modifications_ok:
        print("✅ Technical setup looks good!")
        if recent_logs:
            print("✅ Reload signals are being received!")
            print("💡 If changes still aren't updating, try the solutions above.")
        else:
            print("⚠️  Reload signals might not be reaching Ableton")
            print("💡 Try the Control Surface toggle method instead.")
    else:
        print("❌ Found issues that need to be fixed first")
        print("💡 Follow the specific solutions above")

if __name__ == "__main__":
    main() 