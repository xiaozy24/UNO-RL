import os
import threading
import time
import timeit
import pprint
from collections import deque
import numpy as np

import torch
from torch import multiprocessing as mp
from torch import nn

from uno_dmc.dmc.models import Model
from uno_dmc.dmc.utils import get_batch, log, create_env, create_buffers, create_optimizers, act

mean_episode_return_buf = {p:deque(maxlen=100) for p in ['0', '1', '2', '3']}

def compute_loss(logits, targets):
    loss = ((logits.squeeze(-1) - targets)**2).mean()
    return loss

def learn(position,
          actor_models,
          model,
          batch,
          optimizer,
          flags,
          lock):
    """Performs a learning (optimization) step."""
    if flags.training_device != "cpu":
        device = torch.device('cuda:'+str(flags.training_device))
    else:
        device = torch.device('cpu')
    
    obs_x_no_action = batch['obs_x_no_action'].to(device)
    obs_action = batch['obs_action'].to(device)
    obs_x = torch.cat((obs_x_no_action, obs_action), dim=2).float()
    obs_x = torch.flatten(obs_x, 0, 1)
    obs_z = torch.flatten(batch['obs_z'].to(device), 0, 1).float()
    target = torch.flatten(batch['target'].to(device), 0, 1)
    
    episode_returns = batch['episode_return'][batch['done']]
    if len(episode_returns) > 0:
        mean_episode_return_buf[position].append(torch.mean(episode_returns).to(device))
        
    with lock:
        learner_outputs = model(obs_z, obs_x, return_value=True)
        loss = compute_loss(learner_outputs['values'], target)
        
        ret_mean = 0
        if len(mean_episode_return_buf[position]) > 0:
             ret_mean = torch.mean(torch.stack([_r for _r in mean_episode_return_buf[position]])).item()
        
        stats = {
            'mean_episode_return_'+position: ret_mean,
            'loss_'+position: loss.item(),
        }
        
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), flags.max_grad_norm)
        optimizer.step()

        # Update actor models (shared model logic)
        # Since we use ONE shared model instance in Model wrapper possibly,
        # or we might have separate instances per device?
        # In my Model wrapper, I had one instance.
        # But in train(), we create `models = {}` for each device.
        # So we need to sync.
        for device_model in actor_models.values():
            device_model.get_model(position).load_state_dict(model.state_dict())
        return stats

def train(flags):  
    if flags.actor_device_cpu or flags.training_device != 'cpu':
        if not torch.cuda.is_available():
            pass # Just define CPU/GPU logic

    # Checkpoint path
    checkpointpath = os.path.expandvars(
        os.path.expanduser('%s/%s/%s' % (flags.savedir, flags.xpid, 'model.tar')))
    os.makedirs(os.path.dirname(checkpointpath), exist_ok=True)

    T = flags.unroll_length
    B = flags.batch_size

    if flags.actor_device_cpu:
        device_iterator = ['cpu']
    else:
        device_iterator = range(flags.num_actor_devices)

    # Initialize actor models
    actor_models = {}
    for device in device_iterator:
        model = Model(device=device)
        model.share_memory()
        model.eval()
        actor_models[device] = model

    # Initialize buffers
    buffers = create_buffers(flags, device_iterator)
   
    # Initialize queues
    actor_processes = []
    ctx = mp.get_context('spawn')
    free_queue = {}
    full_queue = {}
        
    for device in device_iterator:
        _free_queue = {p: ctx.SimpleQueue() for p in ['0', '1', '2', '3']}
        _full_queue = {p: ctx.SimpleQueue() for p in ['0', '1', '2', '3']}
        free_queue[device] = _free_queue
        full_queue[device] = _full_queue

    # Learner model for training
    learner_model = Model(device=flags.training_device).get_model() # Get the inner nn.Module

    # Create optimizers
    optimizers = create_optimizers(flags, learner_model)

    # Stat Keys
    stat_keys = []
    for p in ['0', '1', '2', '3']:
        stat_keys.append('mean_episode_return_'+p)
        stat_keys.append('loss_'+p)

    frames, stats = 0, {k: 0 for k in stat_keys}
    position_frames = {p:0 for p in ['0', '1', '2', '3']}

    # Starting actor processes
    for device in device_iterator:
        for i in range(flags.num_actors):
            actor = ctx.Process(
                target=act,
                args=(i, device, free_queue[device], full_queue[device], actor_models[device], buffers[device], flags))
            actor.start()
            actor_processes.append(actor)

    def batch_and_learn(i, device, position, local_lock, position_lock, lock=threading.Lock()):
        nonlocal frames, position_frames, stats
        while frames < flags.total_frames:
            batch = get_batch(free_queue[device][position], full_queue[device][position], buffers[device][position], flags, local_lock)
            # Use shared optimizer 'agent'
            _stats = learn(position, actor_models, learner_model, batch, 
                optimizers['agent'], flags, position_lock)

            with lock:
                for k in _stats:
                    stats[k] = _stats[k]
                frames += T * B
                position_frames[position] += T * B
                if frames % 1000 == 0:
                     log.info('Frames: %d, Stats: %s', frames, stats)

    for device in device_iterator:
        for m in range(flags.num_buffers):
            for p in ['0', '1', '2', '3']:
                free_queue[device][p].put(m)

    threads = []
    locks = {}
    for device in device_iterator:
        locks[device] = {p: threading.Lock() for p in ['0', '1', '2', '3']}
    position_locks = {p: threading.Lock() for p in ['0', '1', '2', '3']}

    for device in device_iterator:
        for i in range(flags.num_threads):
            for position in ['0', '1', '2', '3']:
                thread = threading.Thread(
                    target=batch_and_learn, name='batch-and-learn-%d' % i, args=(i,device,position,locks[device][position],position_locks[position]))
                thread.start()
                threads.append(thread)
    
    # Save Model Loop
    while frames < flags.total_frames:
         time.sleep(10)
         log.info('Saving checkpoint to %s', checkpointpath)
         torch.save({
             'model_state_dict': learner_model.state_dict(),
         }, checkpointpath)
