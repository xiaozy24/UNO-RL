import numpy as np
import torch
from torch import nn

class UnoLstmModel(nn.Module):
    def __init__(self):
        super().__init__()
        # History: 15 steps of 63 dim actions
        self.lstm = nn.LSTM(63, 128, batch_first=True)
        
        # input: LSTM(128) + X_No_Action(117) + Candidate_Action(63)
        self.dense1 = nn.Linear(128 + 117 + 63, 512)
        self.dense2 = nn.Linear(512, 512)
        self.dense3 = nn.Linear(512, 512)
        self.dense4 = nn.Linear(512, 512)
        self.dense5 = nn.Linear(512, 512)
        # Value Output: 1 score per action
        self.dense6 = nn.Linear(512, 1)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.constant_(m.weight, 0)
                nn.init.constant_(m.bias, 0)
        # LSTM
        for name, param in self.lstm.named_parameters():
             nn.init.constant_(param, 0)


    def forward(self, z, x, return_value=False, flags=None):

        # z: [Batch, Sequence=15, Feature=63]
        # x: [Batch, Features(117+63)]
        
        lstm_out, (h_n, _) = self.lstm(z)
        lstm_out = lstm_out[:,-1,:] # Last hidden state
        
        x = torch.cat([lstm_out, x], dim=-1)
        x = self.dense1(x)
        x = torch.relu(x)
        x = self.dense2(x)
        x = torch.relu(x)
        x = self.dense3(x)
        x = torch.relu(x)
        x = self.dense4(x)
        x = torch.relu(x)
        x = self.dense5(x)
        x = torch.relu(x)
        x = self.dense6(x)
        
        if return_value:
            return dict(values=x)
        else:
            # Epsilon Greedy handled here or in act?
            if flags is not None and flags.exp_epsilon > 0 and np.random.rand() < flags.exp_epsilon:
                action = torch.randint(x.shape[0], (1,))[0]
            else:
                action = torch.argmax(x, dim=0)[0]
            return dict(action=action)

class Model:
    """
    Wrapper for UNO Model.
    For Symmetric Self-Play, we treat all positions same.
    But to support the DouZero infrastructure (which often keys by position),
    we can map any position string to the same underlying model or separate ones.
    
    Given the request "Strictly reference DouZero methods", DouZero trains 3 separate agents.
    But UNO is symmetric.
    I will instantiate ONE network and share it for all agents if possible,
    OR instantiate identical networks.
    Let's instantiate ONE network shared logic.
    """
    def __init__(self, device=0):
        self.device = device
        if not device == "cpu":
            self.device_str = 'cuda:' + str(device)
        else:
            self.device_str = 'cpu'
            
        self.model = UnoLstmModel().to(torch.device(self.device_str))

    def forward(self, position, z, x, return_value=False, flags=None):
        return self.model.forward(z, x, return_value, flags)


    def share_memory(self):
        self.model.share_memory()

    def eval(self):
        self.model.eval()

    def parameters(self, position=None):
        return self.model.parameters()

    def get_model(self, position=None):
        return self.model
    
    def get_models(self):
        return {'agent': self.model}

