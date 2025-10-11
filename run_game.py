#!/usr/bin/env python3
"""
Gravity Hopper Game Launcher
Simple launcher script with error handling and setup verification
"""

import sys
import os

def check_requirements():
    """Check if all requirements are met"""
    try:
        import pygame
        print(f"✓ Pygame {pygame.version.ver} is installed")
        return True
    except ImportError:
        print("❌ Pygame is not installed!")
        print("Please install it using: pip3 install pygame")
        return False

def main():
    """Main launcher function"""
    print("🚀 Gravity Hopper - Mobile 2D Game")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check if main game file exists
    if not os.path.exists("main.py"):
        print("❌ main.py not found!")
        print("Please make sure you're running this from the game directory.")
        sys.exit(1)
    
    print("✓ All requirements met")
    print("🎮 Starting Gravity Hopper...")
    print("\nControls:")
    print("- Click/Tap: Short jump")
    print("- Hold: Long jump (charge up)")
    print("- Swipe left/right: Air movement")
    print("- Arrow keys: Alternative movement")
    print("- Space: Jump")
    print("- P: Pause")
    print("- ESC/Close window: Quit")
    print("\nObjective: Jump as high as possible!")
    print("Collect crystals, avoid falling, use different platform types strategically.")
    print()
    
    try:
        # Import and run the game
        from main import main as game_main
        game_main()
    except KeyboardInterrupt:
        print("\n👋 Thanks for playing Gravity Hopper!")
    except Exception as e:
        print(f"\n❌ Game error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()