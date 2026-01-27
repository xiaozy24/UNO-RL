import torch
from torch import nn
import numpy as np

class UNOModel(nn.Module):
    """
    Simple Feed-Forward Network for UNO.
    Input: State Vector + Action Vector (concatenated or handled like DouZero)
    DouZero uses a Q-value approach where it scores state-action pairs.
    """
    def __init__(self, state_dim, hidden_dim=512):
        super().__init__()
        self.dense1 = nn.Linear(state_dim, hidden_dim)
        self.dense2 = nn.Linear(hidden_dim, hidden_dim)
        self.dense3 = nn.Linear(hidden_dim, hidden_dim)
        self.dense4 = nn.Linear(hidden_dim, 1) # Output Q-value for the given action state pair
        
    def forward(self, x):
        x = self.dense1(x)
        x = torch.relu(x)
        x = self.dense2(x)
        x = torch.relu(x)
        x = self.dense3(x)
        x = torch.relu(x)
        x = self.dense4(x)
        return x

class RLAgent:
    def __init__(self, model_path=None, device='cpu'):
        self.device = device
        # Dimensions need to be calculated based on state encoding
        # Let's assume a dimension for now, we will refine it in utils.
        # For simplicity, we'll assume a fixed size input.
        # In DouZero: Input = State Features (Hand, Public Info) + Action Features (One-hot action)
        
        # Approximate State features: 
        # - One-hot encoding of Own Hand (108 dims or simplified)
        # - One-hot encoding of Top Card (Color + Type/Value)
        # - Hand sizes of opponents (e.g. 3 opponents)
        # - Played cards history (maybe simplified)
        
        self.feature_dim = 200 # Placeholder
        self.model = UNOModel(self.feature_dim).to(self.device)
        
        if model_path:
            self.model.load_state_dict(torch.load(model_path, map_location=device))
        self.model.eval()

    def select_action(self, state_features, legal_actions_features, epsilon=0.0):
        """
        Selects the best action from legal actions.
        Args:
            state_features: Tensor representing global/player state.
            legal_actions_features: List of Tensors, each representing a legal action + state combined.
            epsilon: Exploration rate.
        """
        if not legal_actions_features:
            return None 
            
        # Epsilon-Greedy Exploration
        if np.random.rand() < epsilon:
            return np.random.randint(len(legal_actions_features))

        # We process all (state, action) pairs in a batch
        # legal_actions_features should be pre-formatted inputs for the network
        
        batch_input = torch.stack(legal_actions_features).to(self.device)
        
        with torch.no_grad():
            q_values = self.model(batch_input)
            
        best_action_idx = torch.argmax(q_values).item()
        return best_action_idx

    def save_model(self, path):
        torch.save(self.model.state_dict(), path)

    def load_model(self, path):
        self.model.load_state_dict(torch.load(path, map_location=self.device))
