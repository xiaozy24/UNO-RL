import os 
import typing
import logging
import traceback
import numpy as np
import torch 
from torch import multiprocessing as mp

from uno_dmc.env.env import UnoEnv, DmcEnv
from uno_dmc.utils.encoding import encode_action_onehot

# Buffers
Buffers = typing.Dict[str, typing.List[torch.Tensor]]

shandle = logging.StreamHandler()
shandle.setFormatter(
    logging.Formatter(
        '[%(levelname)s:%(process)d %(module)s:%(lineno)d %(asctime)s] '
        '%(message)s'))
log = logging.getLogger('uno-rl')
log.propagate = False
log.addHandler(shandle)
log.setLevel(logging.INFO)

def create_env(flags):
    return DmcEnv(flags.objective)

def get_batch(free_queue, full_queue, buffers, flags, lock):
    with lock:
        indices = [full_queue.get() for _ in range(flags.batch_size)]
    batch = {
        key: torch.stack([buffers[key][m] for m in indices], dim=1)
        for key in buffers
    }
    for m in indices:
        free_queue.put(m)
    return batch

def create_optimizers(flags, learner_model):
    optimizer = torch.optim.RMSprop(
        learner_model.parameters(),
        lr=flags.learning_rate,
        momentum=flags.momentum,
        eps=flags.epsilon,
        alpha=flags.alpha)
    # Return dict to match architecture if using positions, but we use shared
    return {'agent': optimizer}

def create_buffers(flags, device_iterator):
    T = flags.unroll_length
    positions = ['0', '1', '2', '3'] # Agent indices
    buffers = {}
    for device in device_iterator:
        buffers[device] = {}
        # Shared buffers for all positions? 
        # DouZero separates buffers per position.
        
        for position in positions:
            specs = dict(
                done=dict(size=(T,), dtype=torch.bool),
                episode_return=dict(size=(T,), dtype=torch.float32),
                target=dict(size=(T,), dtype=torch.float32),
                obs_x_no_action=dict(size=(T, 117), dtype=torch.int8),
                obs_action=dict(size=(T, 63), dtype=torch.int8),
                obs_z=dict(size=(T, 15, 63), dtype=torch.int8),
            )
            _buffers: Buffers = {key: [] for key in specs}
            for _ in range(flags.num_buffers):
                for key in _buffers:
                    if not device == "cpu":
                        _buffer = torch.empty(**specs[key]).to(torch.device('cuda:'+str(device))).share_memory_()
                    else:
                        _buffer = torch.empty(**specs[key]).to(torch.device('cpu')).share_memory_()
                    _buffers[key].append(_buffer)
            buffers[device][position] = _buffers
    return buffers

def act(i, device, free_queue, full_queue, model, buffers, flags):
    positions = ['0', '1', '2', '3']
    try:
        T = flags.unroll_length
        log.info('Device %s Actor %i started.', str(device), i)

        env = DmcEnv(flags.objective)
        
        done_buf = {p: [] for p in positions}
        episode_return_buf = {p: [] for p in positions}
        target_buf = {p: [] for p in positions}
        obs_x_no_action_buf = {p: [] for p in positions}
        obs_action_buf = {p: [] for p in positions}
        obs_z_buf = {p: [] for p in positions}
        size = {p: 0 for p in positions}

        position, obs, env_output = env.initial()

        while True:
            while True:
                obs_x_no_action_buf[position].append(obs['x_no_action'])
                obs_z_buf[position].append(obs['z'])
                
                # Model Forward
                # Expand X_no_action to batch with legal actions
                x_no_action = obs['x_no_action'] # (117,)
                legal_actions = obs['legal_actions']
                
                # Construct Batch manually
                # Batch Size = len(legal_actions)
                # X Batch = concat(repeat(x_no_action), one_hot(actions))
                num_legal = len(legal_actions)
                
                x_no_action_repeated = np.repeat(x_no_action[np.newaxis, :], num_legal, axis=0)
                
                action_batch = np.zeros((num_legal, 63), dtype=np.int8)
                for j, act_id in enumerate(legal_actions):
                    action_batch[j, act_id] = 1
                
                x_batch = np.hstack((x_no_action_repeated, action_batch)) # (Num, 180)
                
                # Reshape Z

                z_reshaped = obs['z'].reshape(15, 63)
                z_batch = np.repeat(z_reshaped[np.newaxis, :, :], num_legal, axis=0)
                
                # Convert to Tensor
                x_torch = torch.from_numpy(x_batch).float().to(model.device)
                z_torch = torch.from_numpy(z_batch).float().to(model.device)
                
                with torch.no_grad():
                     agent_output = model.forward(position, z_torch, x_torch, flags=flags)
                
                _action_idx = int(agent_output['action'].cpu().detach().numpy())
                action_id = legal_actions[_action_idx]
                
                # Store Action Feature (One Hot)
                action_onehot = encode_action_onehot(action_id)
                obs_action_buf[position].append(torch.from_numpy(action_onehot))
                
                size[position] += 1
                
                # Step
                position, obs, reward, done, _ = env.step(action_id)
                
                if done:
                    # Episode Finish.
                    # Reward is usually final return.
                    # In Env, reward contains result.
                    # Propagate rewards?
                    # Since we only get final reward, we can fill buffers.
                    # Assume Zero Sum, reward is 1 or -1.
                    # We need to fill for ALL players?
                    # The env loop runs for one game.
                    # We should probably clear buffers and fill carefully?
                    # Logic: We have buffers accumulating frame by frame.
                    # We need to assign `episode_return` to all frames of that episode.
                    
                    # Wait, simplified: Just use current buffer accumulation.
                    # We need to know the return for each player.
                    # Env.step returns done. And we can query who won.
                    winner_id = env.env.game.winner.player_id if env.env.game.winner else -1
                    
                    for p in positions:
                        # p is '0', '1'...
                        p_id = int(p)
                        ret = 1.0 if p_id == winner_id else -1.0
                        
                        current_len = size[p]
                        filled_len = len(target_buf[p])
                        diff = current_len - filled_len
                        
                        if diff > 0:
                             done_buf[p].extend([False for _ in range(diff-1)])
                             done_buf[p].append(True)
                             episode_return_buf[p].extend([0.0 for _ in range(diff-1)])
                             episode_return_buf[p].append(ret)
                             target_buf[p].extend([ret for _ in range(diff)])
                    
                    # Reset
                    position, obs, _ = env.initial()
                    break

            for p in positions:
                while size[p] > T: 
                    index = free_queue[p].get()
                    if index is None:
                        break
                    for t in range(T):
                        buffers[p]['done'][index][t, ...] = done_buf[p][t]
                        buffers[p]['episode_return'][index][t, ...] = episode_return_buf[p][t]
                        buffers[p]['target'][index][t, ...] = target_buf[p][t]
                        buffers[p]['obs_x_no_action'][index][t, ...] = torch.from_numpy(obs_x_no_action_buf[p][t])
                        buffers[p]['obs_action'][index][t, ...] = obs_action_buf[p][t]
                        
                        # Z needs reshape logic or storage logic?
                        # Z buffer is (T, 15, 63). Buffer append was flat? 
                        # In loop: obs_z_buf append(obs['z']). obs['z'] is flat.
                        z_item = obs_z_buf[p][t].reshape(15, 63)
                        buffers[p]['obs_z'][index][t, ...] = torch.from_numpy(z_item)
                        
                    full_queue[p].put(index)
                    done_buf[p] = done_buf[p][T:]
                    episode_return_buf[p] = episode_return_buf[p][T:]
                    target_buf[p] = target_buf[p][T:]
                    obs_x_no_action_buf[p] = obs_x_no_action_buf[p][T:]
                    obs_action_buf[p] = obs_action_buf[p][T:]
                    obs_z_buf[p] = obs_z_buf[p][T:]
                    size[p] -= T

    except KeyboardInterrupt:
        pass  
    except Exception as e:
        log.error('Exception in worker process %i', i)
        traceback.print_exc()
        raise e
