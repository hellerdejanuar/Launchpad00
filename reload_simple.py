#!/usr/bin/env python3
"""
Simple Launchpad95 Reload Helper

This script provides multiple ways to reload your Launchpad95 script faster 
than restarting Ableton Live completely.

Methods:
1. File watching with notifications
2. Instructions for Ableton Live Beta reload feature
3. Quick MIDI device toggle
"""

import os
import time
import sys
from pathlib import Path

def watch_files():
    """Watch for file changes and notify user"""
    print("👀 Watching Launchpad95 files for changes...")
    print("📝 When files change, you'll see instructions for reloading\n")
    
    script_dir = Path(__file__).parent
    python_files = list(script_dir.glob("*.py"))
    file_times = {f: f.stat().st_mtime for f in python_files if f.name != 'reload_simple.py'}
    
    print(f"📁 Watching {len(file_times)} Python files:")
    for f in file_times.keys():
        print(f"   • {f.name}")
    print()
    
    try:
        while True:
            time.sleep(1)
            
            for file_path in file_times.keys():
                try:
                    current_time = file_path.stat().st_mtime
                    if current_time > file_times[file_path]:
                        print(f"\n🔄 FILE CHANGED: {file_path.name}")
                        print("=" * 50)
                        show_reload_instructions()
                        file_times[file_path] = current_time
                        time.sleep(2)  # Avoid spam
                        break
                except OSError:
                    continue
                    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopped watching files")

def show_reload_instructions():
    """Show different reload methods"""
    print("🚀 RELOAD YOUR CHANGES using one of these methods:\n")
    
    print("📋 METHOD 1: Quick Toggle (Fastest)")
    print("   1. Go to Ableton Live Preferences → Link/Tempo/MIDI")
    print("   2. Set Control Surface to 'None'")
    print("   3. Set it back to 'Launchpad95'")
    print("   ⏱️  Takes ~10 seconds\n")
    
    print("🧪 METHOD 2: Ableton Live Beta (Instant)")
    print("   1. Download Ableton Live Beta")
    print("   2. Create options.txt with: -_ToolsMenuRemoteScripts")
    print("   3. Use Tools → Reload MIDI Remote Scripts")
    print("   ⏱️  Takes ~2 seconds\n")
    
    print("🔧 METHOD 3: MIDI Reload (If Modified)")
    print("   1. Run: python reload_script.py")
    print("   2. Script will send reload signal")
    print("   ⏱️  Takes ~3 seconds\n")
    
    print("💡 TIP: For fastest development, use Method 2 (Beta version)")
    print("=" * 50)

def create_options_file():
    """Help user create options.txt for beta reload feature"""
    print("🧪 Setting up Ableton Live Beta Reload Feature\n")
    
    # Detect OS and suggest path
    if sys.platform == "darwin":  # macOS
        paths = [
            "~/Music/Ableton/User Library/Preferences/",
            "/Applications/Ableton Live 12 Beta.app/Contents/App-Resources/",
            "/Applications/Ableton Live 11 Beta.app/Contents/App-Resources/"
        ]
        print("🍎 macOS detected. Try these locations for options.txt:")
    else:  # Windows
        paths = [
            "%USERPROFILE%/Documents/Ableton/User Library/Preferences/",
            "C:/ProgramData/Ableton/Live 12 Beta/",
            "C:/ProgramData/Ableton/Live 11 Beta/"
        ]
        print("🪟 Windows detected. Try these locations for options.txt:")
    
    for path in paths:
        print(f"   • {path}")
    
    print(f"\n📝 Create a file called 'options.txt' with this content:")
    print("   -_ToolsMenuRemoteScripts")
    
    print(f"\n🚀 Then restart Ableton Live Beta and look for:")
    print("   Tools → Reload MIDI Remote Scripts")

def show_main_menu():
    """Show main menu options"""
    print("🚀 Launchpad95 Development Helper")
    print("=" * 40)
    print("1. Watch files for changes")
    print("2. Show reload instructions")
    print("3. Setup Ableton Beta reload")
    print("4. Exit")
    print()
    
    while True:
        choice = input("Choose option (1-4): ").strip()
        
        if choice == "1":
            watch_files()
            break
        elif choice == "2":
            show_reload_instructions()
            break
        elif choice == "3":
            create_options_file()
            break
        elif choice == "4":
            print("👋 Happy coding!")
            break
        else:
            print("❌ Please enter 1, 2, 3, or 4")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--watch":
            watch_files()
        elif sys.argv[1] == "--instructions":
            show_reload_instructions()
        elif sys.argv[1] == "--setup-beta":
            create_options_file()
        else:
            print("Usage: python reload_simple.py [--watch|--instructions|--setup-beta]")
    else:
        show_main_menu()

if __name__ == "__main__":
    main() 