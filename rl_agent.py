import torch
import numpy as np
import random
from config.enums import CardColor
from rl_utils import encode_state, get_card_index, COLOR_ORDER
from rl_model import UNOAgent

class RLAgentHandler:
    def __init__(self, model_path=None):
        self.model = UNOAgent()
        if model_path:
            self.model.load_state_dict(torch.load(model_path))
        self.model.eval()
        self.is_train = False
        self.history = []
        
    def clear_history(self):
        self.history = []

    def _get_vals(self, player, game_manager):
        state_vec = encode_state(player, game_manager)
        state_tensor = torch.tensor(state_vec, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            outputs = self.model(state_tensor)
        return outputs, state_tensor

    def select_card(self, player, game_manager, legal_cards):
        outputs, state_tensor = self._get_vals(player, game_manager)
        card_vals = torch.sigmoid(outputs["card"]).squeeze(0).numpy()
        
        candidates = {} 
        for c in legal_cards:
            idx = get_card_index(c)
            if idx not in candidates: candidates[idx] = []
            candidates[idx].append(c)
            
        valid_indices = list(candidates.keys())
        scores = card_vals[valid_indices]
        
        if len(scores) == 0: return None 
        
        if self.is_train:
            total = np.sum(scores)
            if total < 1e-9: probs = np.ones_like(scores) / len(scores)
            else: probs = scores / total
            chosen_type_idx = np.random.choice(valid_indices, p=probs)
        else:
            max_score = np.max(scores)
            best_indices = [valid_indices[i] for i, s in enumerate(scores) if s == max_score]
            chosen_type_idx = random.choice(best_indices)
        
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "card",
                 "action": int(chosen_type_idx)
             })

        return candidates[chosen_type_idx][0]

    def select_color(self, player, game_manager):
        outputs, state_tensor = self._get_vals(player, game_manager)
        color_vals = torch.sigmoid(outputs["color"]).squeeze(0).numpy()
        
        scores = color_vals
        
        if self.is_train:
            total = np.sum(scores)
            if total < 1e-9: probs = np.ones(4) / 4
            else: probs = scores / total
            chosen_idx = np.random.choice(4, p=probs)
        else:
            max_score = np.max(scores)
            best_indices = [i for i, s in enumerate(scores) if s == max_score]
            chosen_idx = random.choice(best_indices)
            
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "color",
                 "action": int(chosen_idx)
             })

        return COLOR_ORDER[chosen_idx]

    def should_challenge(self, player, game_manager):
        outputs, state_tensor = self._get_vals(player, game_manager)
        chal_vals = torch.sigmoid(outputs["challenge"]).squeeze(0).numpy()
        
        scores = chal_vals
        if self.is_train:
            total = np.sum(scores)
            if total < 1e-9: probs = np.array([0.5, 0.5])
            else: probs = scores / total
            choice = np.random.choice([0, 1], p=probs)
        else:
            max_score = np.max(scores)
            best_indices = [i for i, s in enumerate(scores) if s == max_score]
            choice = random.choice(best_indices)
            
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "challenge",
                 "action": int(choice)
             })

        return choice == 1

    def should_play_drawn(self, player, game_manager, card):
        outputs, state_tensor = self._get_vals(player, game_manager)
        pd_vals = torch.sigmoid(outputs["play_drawn"]).squeeze(0).numpy()
        
        scores = pd_vals
        if self.is_train:
            total = np.sum(scores)
            if total < 1e-9: probs = np.array([0.5, 0.5])
            else: probs = scores / total
            choice = np.random.choice([0, 1], p=probs)
        else:
            max_score = np.max(scores)
            best_indices = [i for i, s in enumerate(scores) if s == max_score]
            choice = random.choice(best_indices)
            
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "play_drawn",
                 "action": int(choice)
             })

        return choice == 1
