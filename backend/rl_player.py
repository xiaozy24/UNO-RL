import torch
import numpy as np
from collections import deque
from backend.player import Player
from config.enums import PlayerType, CardColor, CardType
from uno_dmc.dmc.models import Model
from uno_dmc.utils.encoding import *

class RLPlayer(Player):
    def __init__(self, player_id: int, name: str, model_path=None, device='cpu'):
        super().__init__(player_id, name, PlayerType.AI)
        self.model_wrapper = Model(device=0 if torch.cuda.is_available() and device!='cpu' else 'cpu')
        if model_path:
            # Load model
            checkpoint = torch.load(model_path, map_location=self.model_wrapper.device_str)
            self.model_wrapper.get_model().load_state_dict(checkpoint['model_state_dict'])
        
        self.model_wrapper.eval()
        self.history = deque(maxlen=15)
        
    def update_history(self, card: Card):
        if card:
            self.history.append(card)

    def choose_action(self, gm):
        # 1. Construct Obs
        obs = self._build_obs(gm, decision_mode="play")
        
        # 2. Forward
        action_id = self._forward(obs)
        
        # 3. Decode
        card, color, special = act_id_to_card_action(action_id)
        
        if special == "DRAW":
            return {'action_type': 'draw'}
            
        return {'action_type': 'play', 'card': card, 'color': color}

    def challenge_decision(self, gm, previous_color):
        obs = self._build_obs(gm, decision_mode="challenge")
        action_id = self._forward(obs)
        _, _, special = act_id_to_card_action(action_id)
        return special == "CHALLENGE_YES"

    def play_drawn_decision(self, gm, drawn_card):
        # We need to temporarily hold the drawn card effectively
        # In this context, the card is in hand?
        obs = self._build_obs(gm, decision_mode="play_drawn", drawn_card=drawn_card)
        action_id = self._forward(obs)
        card, color, special = act_id_to_card_action(action_id)
        
        if special == "DRAW" or special == "PASS": # Pass
             return False, None
        return True, color # Play

    def _forward(self, obs):
        legal_actions = obs['legal_actions']
        num_legal = len(legal_actions)
        
        # 1. Prepare X Batch
        # x_no_action: (FeatureDim,)
        x_no_action = obs['x_no_action']
        x_repeated = np.repeat(x_no_action[np.newaxis, :], num_legal, axis=0) # (Num, 117)
        
        # Action OneHot: (Num, 63)
        act_batch = np.zeros((num_legal, 63), dtype=np.int8)
        for i, aid in enumerate(legal_actions):
            act_batch[i, aid] = 1
            
        x_input = np.hstack((x_repeated, act_batch)) # (Num, 180)
        
        # 2. Prepare Z Batch
        # obs['z_batch'] is (15, 63). We need (Num, 15, 63)
        z_template = obs['z_batch']
        z_repeated = np.repeat(z_template[np.newaxis, :, :], num_legal, axis=0)
        
        # 3. To Tensor
        x_torch = torch.from_numpy(x_input).float().to(self.model_wrapper.device_str)
        z_torch = torch.from_numpy(z_repeated).float().to(self.model_wrapper.device_str)
        
        # 4. Forward
        # Model returns dict(values=...) if return_value=True
        res = self.model_wrapper.forward(None, z_torch, x_torch, return_value=True)
        values = res['values'].cpu().detach().numpy().flatten()
        
        # Debug
        # print(f"Action Values: {values}")
        # print(f"Legal: {legal_actions}")
        # print(f"Best: {legal_actions[np.argmax(values)]}")
        
        # 5. Pick Best


        best_idx = np.argmax(values)
        return legal_actions[best_idx]


    def _build_obs(self, gm, decision_mode, drawn_card=None):
        player = self
        agent_idx = player.player_id - 1 # Assuming IDs 1-4
        
        # Legal Mask
        legal_mask = np.zeros(63, dtype=np.int8)
        top_card = gm.deck.peek_discard_pile() # Should peek gm deck
        
        if decision_mode == "play":
            legal_mask[60] = 1 # Allow Draw
            for c in player.hand:
                if gm.check_legal_play(c, top_card):
                    if c.color == CardColor.WILD:
                         base = 52 if c.card_type == CardType.WILD else 56
                         legal_mask[base:base+4] = 1
                    else:
                        legal_mask[card_action_to_act_id(c)] = 1
                        
        elif decision_mode == "challenge":
            legal_mask[61] = 1
            legal_mask[62] = 1
            
        elif decision_mode == "play_drawn":
            legal_mask[60] = 1 # Pass
            if drawn_card:
                if drawn_card.color == CardColor.WILD:
                     base = 52 if drawn_card.card_type == CardType.WILD else 56
                     legal_mask[base:base+4] = 1
                else:
                    legal_mask[card_action_to_act_id(drawn_card)] = 1
                    
        # State Features
        my_hand = encode_hand(player.hand)
        
        opp_sizes = []
        # Need to access gm.players
        # Assuming gm.players is ordered list.
        # Find self index
        my_index = -1
        for i, p in enumerate(gm.players):
             if p.player_id == player.player_id:
                 my_index = i
                 break
        
        for i in range(1, 4):
            if len(gm.players) > 1:
                opp_idx = (my_index + i) % len(gm.players)
                opp_sizes.append(len(gm.players[opp_idx].hand))
            else:
                opp_sizes.append(0)
        opp_sizes = np.array(opp_sizes, dtype=np.int8)
        # Pad if < 3 opps
        while len(opp_sizes) < 3:
            opp_sizes = np.concatenate([opp_sizes, [0]])
            
        top_enc = encode_onehot(top_card)
        
        color_enc = np.zeros(4, dtype=np.int8)
        if gm.current_color:
             c_idx = {CardColor.RED:0, CardColor.YELLOW:1, CardColor.GREEN:2, CardColor.BLUE:3}.get(gm.current_color, 0)
             color_enc[c_idx] = 1
             
        flags = np.array([1 if decision_mode == "challenge" else 0, 1 if decision_mode == "play_drawn" else 0], dtype=np.int8)
        
        x_no_action = np.concatenate([my_hand, top_enc, color_enc, opp_sizes, flags])
        
        # History
        # We need self.history or gm history.
        # Ideally gm tracks it or we track it.
        # RLPlayer has self.history.
        z_array = np.zeros((15, 63), dtype=np.int8)
        idx = 0
        for card in list(self.history)[-15:]:
             act_id = card_action_to_act_id(card, CardColor.RED)
             if 0 <= act_id < 63:
                 z_array[idx][act_id] = 1
             idx += 1
             
        # Reshape Z for output? Env returns flattened Z.
        # Here we return structured Z because we use it directly in _forward with Repeat.
        # Env flattened it for Buffer storage.
        
        return {
            'x_no_action': x_no_action,
            'x_batch': None, # Built in forward
            'z_batch': z_array,
            'legal_actions': np.where(legal_mask)[0].tolist()
        }

