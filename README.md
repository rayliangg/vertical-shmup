# 🪸 vertical shmup

**A SpongeBob-inspired vertical shmup** — play as **Patrick Star**, dodge jellyfish and debris, shoot back, and grab power-ups in **Jellyfish Fields**.

https://github.com/user-attachments/assets/d097b8b8-cb58-4512-a758-4d0506c7be58

## Quick facts

- **Stack:** Python 3.10+, [Pygame](https://www.pygame.org/)
- **Genre:** 2D vertical scrolling shooter
- **Gameplay:** Keyboard move + shoot; varied jellyfish patterns, treasures, music

## Project layout

| File | Role |
|------|------|
| `main.py` | Game loop, window |
| `player.py` | Patrick: move, shoot, collisions |
| `bullet.py` | Bullets |
| `aerolite.py` | Falling hazards / obstacles |
| `treasure.py` | Pickups & power-ups |
| `config.py` | Screen size, speeds, colors, etc. |

## Run

```bash
pip install pygame
python main.py
