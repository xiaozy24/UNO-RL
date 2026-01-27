# UNO-RL: Reinforcement Learning Environment for UNO

An interactive UNO game environment supporting Human vs AI play, designed for Reinforcement Learning experiments. This project features a CLI-based interactive game loop where you can play against a Rule-based AI and a Deep Q-Learning (RL) Agent.

## 📖 Documentation (文档指南)

Before you start, we highly recommend reading the following guides:

*   **[📜 Game Rules (游戏规则)](uno_rule.md)**
    *   Detailed explanation of UNO rules, card effects, and the special "+4 Challenge" mechanics.
*   **[🎮 Controls & AI Logic (操作与AI逻辑)](control_introduction.md)**
    *   How to control the game via terminal.
    *   Introduction to the AI opponents: Alice, Charlie, and Bob.

## 🚀 Quick Start

To start a game in the terminal:

```bash
# Ensure you are in the project root
python3 main.py
```

## 🏗️ Architecture & Features

The project follows a modular design separating game logic from agent implementations:

*   **Interactive Terminal UI**: Color-coded card display, clear action logs, and menu-based input.
*   **Backend (`backend/`)**: Core game engine (Deck, Card, GameManager, Player). Handles state, turns, and rule enforcement.
*   **Agents**:
    - **HumanBack**: Direct control for human players via CLI.
    - **SimpleAI**: Heuristic-based bot (always plays, challenges randomly).
    - **RLPlayer**: DQN-based agent trained to optimize win rate.

## 🛠️ Development

### Training the Agent
To run the training loop:
```bash
python3 train.py
```

## Features Implemented (Backend)

- [x] Full 108 card deck generation.
- [x] Turn management (Clockwise/Counter-clockwise).
- [x] Legal move validation (Color match, Number match, Type match, Wild logic).
- [x] Action cards effects (Skip, Reverse, Draw Two, Wild, Wild Draw Four).
- [x] **"Challenge" System (质疑)** for +4 cards.

## Future Plans

- Implement Pygame Frontend.
- connect Backend events to Frontend UI.
- Implement sophisticated RL agents.
