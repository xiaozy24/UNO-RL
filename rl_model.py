import torch
import torch.nn as nn
from rl_utils import STATE_DIM

class UNOAgent(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(STATE_DIM, 512)
        self.fc2 = nn.Linear(512, 512)
        self.fc3 = nn.Linear(512, 256)
        self.fc4 = nn.Linear(256, 128)
        
        # Heads
        # We output "Win Rate" logits.
        # Ideally, we want these to be interpreted as non-negative or log-probs.
        # But for Q-learning / Policy Gradient, logits are fine.
        
        self.card_head = nn.Linear(128, 54) # Value for each card type
        self.challenge_head = nn.Linear(128, 2) # [No, Yes] values
        self.play_drawn_head = nn.Linear(128, 2) # [No, Yes] values
        self.color_head = nn.Linear(128, 4) # [R, B, G, Y] values

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        x = torch.relu(self.fc4(x))
        
        return {
            "card": self.card_head(x),
            "challenge": self.challenge_head(x),
            "play_drawn": self.play_drawn_head(x),
            "color": self.color_head(x)
        }
