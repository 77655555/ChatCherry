# Gravity Hopper - Pygame Mobile 2D (Portrait 360x640)

Requirements:
- Python 3.10+
- Pygame 2.6+

Install deps:
```bash
pip install -r requirements.txt
```

Run game:
```bash
python -m gravity_hopper
```

Controls (mouse = touch):
- Tap (Left mouse press+release): jump; hold longer for higher jump
- While holding, small left/right swipe applies a lateral nudge mid-air
- Tap on game over screen to restart

Notes:
- Window size is locked to 360x640 portrait.
- Physics: gravity, terminal velocity, bounce with platform friction.
- Platform types: normal (green), moving (blue), fragile (orange). Some platforms have a yellow booster spring.
- Collectibles: crystals (+10), multiplier x2 for 10s, shields (prevents one fall).
- UI: score, best, height meters, multiplier indicator, parallax star background.
