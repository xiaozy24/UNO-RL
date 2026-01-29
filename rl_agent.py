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
        # Use raw logits (Q-values), no Sigmoid
        card_vals = outputs["card"].squeeze(0).numpy()
        
        candidates = {} 
        for c in legal_cards:
            idx = get_card_index(c)
            if idx not in candidates: candidates[idx] = []
            candidates[idx].append(c)
            
        valid_indices = list(candidates.keys())
        scores = card_vals[valid_indices] # These can be negative now
        
        if len(scores) == 0: return None 
        
        if self.is_train:
            # 50% Greedy, 50% Softmax Sampling
            if random.random() < 0.5:
                # Greedy
                max_score = np.max(scores)
                best_indices = [valid_indices[i] for i, s in enumerate(scores) if s == max_score]
                chosen_type_idx = random.choice(best_indices)
            else:
                # Softmax Sampling
                # Subtract max for numerical stability
                exp_scores = np.exp(scores - np.max(scores))
                probs = exp_scores / np.sum(exp_scores)
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
        # Use raw logits
        color_vals = outputs["color"].squeeze(0).numpy()
        
        scores = color_vals
        
        if self.is_train:
            # 50% Greedy, 50% Softmax Sampling
            if random.random() < 0.5:
                # Greedy
                max_score = np.max(scores)
                best_indices = [i for i, s in enumerate(scores) if s == max_score]
                chosen_idx = random.choice(best_indices)
            else:
                # Softmax Sampling
                exp_scores = np.exp(scores - np.max(scores))
                probs = exp_scores / np.sum(exp_scores)
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
        # Use raw logits
        chal_vals = outputs["challenge"].squeeze(0).numpy()
        
        scores = chal_vals
        if self.is_train:
            # 50% Greedy, 50% Softmax Sampling
            if random.random() < 0.5:
                # Greedy
                max_score = np.max(scores)
                best_indices = [i for i, s in enumerate(scores) if s == max_score]
                choice = random.choice(best_indices)
            else:
                # Softmax Sampling
                exp_scores = np.exp(scores - np.max(scores))
                probs = exp_scores / np.sum(exp_scores)
                choice = np.random.choice([0, 1], p=probs)
        else:
            max_score = np.max(scores)
            best_indices = [i for i, s in enumerate(scores) if s == max_score]
            choice = random.choice(best_indices)
            
        # Store challenge attempt
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "challenge",
                 "action": int(choice),
                 "challenge_success": None # Will be filled by caller if possible, or we need redesign
             })

        return choice == 1

    def should_challenge_probabilistic(self, player, game_manager, thresholds=None):
        """
        Special method for challenge training.
        Training: Sample based on probability (Softmax).
        Testing: Argmax (Challenge if prob >= 0.5).
        """
        outputs, state_tensor = self._get_vals(player, game_manager)
        chal_vals = outputs["challenge"].squeeze(0).numpy()
        
        # Calculate probabilities via Softmax
        exp_scores = np.exp(chal_vals - np.max(chal_vals))
        probs = exp_scores / np.sum(exp_scores) # [Prob(No), Prob(Yes)]
        
        prob_challenge = probs[1]
        
        if self.is_train:
            # Sample based on probability
            choice = np.random.choice([0, 1], p=probs)
        else:
            # Deterministic: >= 0.5
            choice = 1 if prob_challenge >= 0.5 else 0
            
        if self.is_train:
             self.history.append({
                 "state": state_tensor,
                 "head": "challenge",
                 "action": int(choice),
                 "challenge_success": None # Will be filled by caller
             })
             
        return choice == 1, prob_challenge

    def should_play_drawn(self, player, game_manager, card):
        outputs, state_tensor = self._get_vals(player, game_manager)
        # Use raw logits
        pd_vals = outputs["play_drawn"].squeeze(0).numpy()
        
        scores = pd_vals
        if self.is_train:
             # 50% Greedy, 50% Softmax Sampling
            if random.random() < 0.5:
                # Greedy
                max_score = np.max(scores)
                best_indices = [i for i, s in enumerate(scores) if s == max_score]
                choice = random.choice(best_indices)
            else:
                # Softmax Sampling
                exp_scores = np.exp(scores - np.max(scores))
                probs = exp_scores / np.sum(exp_scores)
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
