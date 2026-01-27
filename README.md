# UNO-RL

A UNO game implementation in Python, inspired by "Pig Kingdom Legends" (Zhuguosha) architecture.

## Project Overview

This project implements the core logic of the UNO card game. It is designed with a separate backend structure to support future UI development (Pygame) and AI reinforcement learning experiments.

## Architecture

The project follows a modular design:

### Backend (`backend/`)
- **Card (`backend/card.py`)**: Defines the `Card` class with color, type, and value properties.
- **Deck (`backend/deck.py`)**: Manages the draw pile and discard pile, including shuffling and reshuffling.
- **Player (`backend/player.py`)**: Represents a player (Human or AI), holding hand cards and status (e.g., "UNO" call).
- **GameManager (`backend/game_manager.py`)**: The central controller that manages the game loop, turn logic, rule validation, and card effects.

### Config (`config/`)
- **Enums (`config/enums.py`)**: Defines `CardColor`, `CardType`, `PlayerType`, etc.
- **Settings (`config/settings.py`)**: Game constants and rules.

## Usage

To run a console-based simulation of the game:

```bash
export PYTHONPATH=$PYTHONPATH:/path/to/UNO-RL
python3 main.py
```

## Features Implemented (Backend)

- [x] Full 108 card deck generation.
- [x] Shuffling and dealing.
- [x] Draw pile and Discard pile management with auto-reshuffle.
- [x] Turn management (Clockwise/Counter-clockwise).
- [x] Legal move validation (Color match, Number match, Type match, Wild logic).
- [x] Action cards effects:
    - Skip
    - Reverse
    - Draw Two
    - Wild (Change Color)
    - Wild Draw Four
- [x] "UNO" shout status tracking.
- [x] Win condition detection.

## Future Plans

- Implement Pygame Frontend.
- connect Backend events to Frontend UI.
- Implement sophisticated RL agents.
