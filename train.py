import os
import torch
import torch.optim as optim
import time
from backend.game_manager import GameManager
from backend.rl_player import RLPlayer
from backend.utils.logger import game_logger
from config.enums import CardColor, CardType

# Training Configuration
BATCH_SIZE = 32 # Episodes per batch
LEARNING_RATE = 1e-4
EPOCHS = 100
SAVE_INTERVAL = 10
# Get absolute path to the directory containing this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "uno_rl_model.pth")

def run_episode(game_manager):
    """
    Runs a single game episode.
    Returns: A list of (player, feature_vector) tuples for every move made.
    """
    game_manager.start_game()
    episode_data = [] # List of (player_id, feature_tensor)
    
    turn_limit = 200 # Avoid infinite games
    turn = 0
    
    while not game_manager.game_over and turn < turn_limit:
        current_player = game_manager.get_current_player()
        
        # We only care about collecting data from RLPlayers
        if isinstance(current_player, RLPlayer):
            # Shout UNO automatically
            if current_player.get_hand_size() == 2:
                current_player.say_uno()
            
            action = current_player.choose_action(game_manager)
            
            if action['action_type'] == 'play':
                # Store the feature vector of the chosen action
                if 'feature' in action:
                    episode_data.append((current_player.player_id, action['feature']))
                
                game_manager.play_card(current_player, action['card'], action.get('color'))
            else:
                # 'draw' action also effectively transitions state, but for simplicty 
                # we only train on 'play' decisions (Q-value of playing a card vs another).
                # DouZero trains on all actions. For now, training on 'play' selection is easiest.
                game_manager.draw_card_action(current_player)
        else:
            # Fallback for non-RL players (simulated random/simple AI)
            # Not creating data for them
            pass # Implement simple logic or reuse draw/play
            
            # Simple AI logic copy-paste just to make game proceed
            top_card = game_manager.deck.peek_discard_pile()
            playable = None
            for card in current_player.hand:
                if game_manager.check_legal_play(card, top_card):
                    playable = card
                    break
            if playable:
                wc = CardColor.RED if playable.color == CardColor.WILD else None
                game_manager.play_card(current_player, playable, wc)
            else:
                game_manager.draw_card_action(current_player)

        turn += 1
        
    winner_id = game_manager.winner.player_id if game_manager.winner else None
    return episode_data, winner_id

def train():
    # 1. Initialize Global Model & Optimizer
    # We create a dummy agent just to access the model structure
    global_agent = RLPlayer(0, "Global", None).agent
    global_agent.model.train() # Set to train mode
    
    optimizer = optim.Adam(global_agent.model.parameters(), lr=LEARNING_RATE)
    
    print(f"Starting training for {EPOCHS} epochs...")
    
    for epoch in range(1, EPOCHS + 1):
        epoch_start_time = time.time()
        
        total_loss = 0
        batch_data_features = []
        batch_data_targets = []
        
        wins = {1: 0, 2: 0, 3: 0, None: 0} # Player IDs are 1, 2, 3
        
        # 2. Collect Batch Data
        for _ in range(BATCH_SIZE):
            # Create fresh players/game for each episode
            # All agents share the same model (weights) for experience collection? 
            # Or use global model. DouZero copies weights.
            # Here we just point to the same model file or object. 
            # Since threads aren't involved, we can just share the state_dict or same object.
            # But RLPlayer instantiates its own RLAgent.
            # Let's manually inject the global model into players for speed.
            
            p1 = RLPlayer(1, "Agent1", epsilon=0.1)
            p2 = RLPlayer(2, "Agent2", epsilon=0.1)
            p3 = RLPlayer(3, "Agent3", epsilon=0.1)
            
            # Share the training model
            p1.agent.model = global_agent.model
            p2.agent.model = global_agent.model
            p3.agent.model = global_agent.model
            
            gm = GameManager([p1, p2, p3])
            
            # Run
            transitions, winner_id = run_episode(gm)
            wins[winner_id] += 1
            
            # Compute Rewards
            # Monte Carlo: Reward = +1 if won, -1 if lost
            for pid, feature in transitions:
                reward = 1.0 if pid == winner_id else -1.0
                
                batch_data_features.append(feature)
                batch_data_targets.append(reward)
        
        # 3. Update Model
        if batch_data_features:
            features = torch.stack(batch_data_features)
            targets = torch.tensor(batch_data_targets, dtype=torch.float32).unsqueeze(1)
            
            # Forward pass
            predictions = global_agent.model(features)
            
            # MSE Loss
            loss = ((predictions - targets) ** 2).mean()
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss = loss.item()
        
        # 4. Log & Save
        print(f"Epoch {epoch}/{EPOCHS} | Loss: {total_loss:.4f} | Wins: {wins} | Time: {time.time()-epoch_start_time:.2f}s")
        
        if epoch % SAVE_INTERVAL == 0:
            torch.save(global_agent.model.state_dict(), MODEL_PATH)
            print(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()
