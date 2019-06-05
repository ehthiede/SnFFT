import sys
sys.path.append('../')
import math
from young_tableau import FerrersDiagram
import torch
import torch.nn as nn
import torch.nn.functional as F

class IrrepDQN(nn.Module):
    def __init__(self, partitions):
        super(IrrepDQN, self).__init__()
        n_in = 0
        for p in partitions:
            f = FerrersDiagram(p)
            n_in += (len(f.tableaux) * len(f.tableaux))

        self.tile_size = sum(partitions[0])
        self.w = nn.Linear(n_in, 1)
        self.n_in = n_in
        self.n_out = 1
        self.init_weights()

    # Mostly for debugging
    def forward_grid(self, grid, env):
        irr = env.cat_irreps(grid)
        th_irrep = torch.from_numpy(irr).float().unsqueeze(0)
        return self.forward(th_irrep)

    def forward(self, x):
        '''
        Assumption is that x has already been raveled/concattenated so x is of dim: batch x n_in
        '''
        return self.w.forward(x)

    def init_weights(self):
        self.w.weight.data.normal_(0, 1. / math.sqrt(self.n_in + self.n_out))
        if self.tile_size == 2:
            self.w.bias[0] = -3.0
        elif self.tile_size == 3:
            self.w.bias[0] = -21.97

    def get_action(self, env, grid_state, e, all_nbrs=None, x=None, y=None):
        '''
        env: TileIrrepEnv
        state: not actually used! b/c we need to get the neighbors of the current state!
               Well, we _could_ have the state be the grid state!
        e: int
        '''
        if all_nbrs is None:
            all_nbrs = env.all_nbrs(grid_state, x, y) # these are irreps

        invalid_moves = [m for m in env.MOVES if m not in env.valid_moves(x, y)]
        vals = self.forward(torch.from_numpy(all_nbrs).float())
        # TODO: this is pretty hacky
        for m in invalid_moves:
            vals[m] = -float('inf')
        return torch.argmax(vals).item()

class IrrepDQNMLP(nn.Module):
    def __init__(self, partition, n_hid, n_out):
        super(IrrepDQNMLP, self).__init__()
        ferrer = FerrersDiagram(partition)
        size = len(ferrer.tableaux) * len(ferrer.tableaux)
        self.net = MLP(size, n_hid, n_out)

    def forward(self, x):
        '''
        x: an irrep
        '''
        return self.net(x)

    def get_action(self, env, grid_state, e, all_nbrs=None, x=None, y=None):
        '''
        env: TileIrrepEnv
        state: not actually used! b/c we need to get the neighbors of the current state!
               Well, we _could_ have the state be the grid state!
        e: int
        '''
        if all_nbrs is None:
            all_nbrs = env.all_nbrs(grid_state, x, y) # these are irreps

        invalid_moves = [m for m in env.MOVES if m not in env.valid_moves(x, y)]
        vals = self.forward(torch.from_numpy(all_nbrs).float())
        # TODO: this is pretty hacky
        for m in invalid_moves:
            vals[m] = -float('inf')
        return torch.argmax(vals).item()

    def forward_grid(self, grid, env):
        irr = env.cat_irreps(grid)
        th_irrep = torch.from_numpy(irr).float().unsqueeze(0)
        return self.forward(th_irrep)

class MLP(nn.Module):
    def __init__(self, n_in, n_hid, n_out):
        super(MLP, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, n_hid),
            nn.ReLU(),
            nn.Linear(n_hid, n_hid),
            nn.ReLU(),
            nn.Linear(n_hid, n_out)
        )

    def forward(self, x):
        return self.net.forward(x)

class TileBaselineQ(nn.Module):
    def __init__(self, n_in, n_hid, n_out):
        super(TileBaselineQ, self).__init__()
        self.net = MLP(n_in, n_hid, n_out)

    def get_action(self, state):
        '''
        state: 1 x n_in tensor
        Returns int of the argmax
        '''
        state = torch.from_numpy(state).float().unsqueeze(0)
        vals = self.forward(state)
        return vals.argmax(dim=1).item()

    def update_simple(self, targ_net, env, batch, opt, discount, ep):
        rewards = torch.from_numpy(batch['reward'])
        actions = torch.from_numpy(batch['action']).long()
        dones = torch.from_numpy(batch['done'])
        states = torch.from_numpy(batch['onehot_state'])
        next_states = torch.from_numpy(batch['next_onehot_state'])

        pred_vals = self.forward(states)
        vals = torch.gather(pred_vals, 1, actions)

        targ_max = targ_net.forward(next_states).max(dim=1)[0]
        targ_vals = (rewards + discount * (1 - dones) * targ_max.unsqueeze(-1)).detach()

        opt.zero_grad()
        loss = F.mse_loss(vals, targ_vals)
        loss.backward()
        opt.step()
        return loss.item()


    def update(self, targ_net, env, batch, opt, discount, ep):
        '''
        targ_net: TileBaselineQ
        env: TileEnv
        batch: dictionary
        opt: torch optimizer
        discount: float
        ep: int, episode number

        Computes the loss and takes a gradient step.
        '''
        rewards = torch.from_numpy(batch.reward)
        actions = torch.from_numpy(batch.action).long()
        dones = torch.from_numpy(batch.done)
        states = torch.from_numpy(batch.state)
        next_states = torch.from_numpy(batch.next_state)

        pred_vals = self.forward(states)
        vals = torch.gather(pred_vals, 1, actions)

        targ_max = targ_net.forward(next_states).max(dim=1)[0]
        targ_vals = (rewards + discount * (1 - dones) * targ_max.unsqueeze(-1)).detach()

        opt.zero_grad()
        loss = F.mse_loss(vals, targ_vals)
        loss.backward()
        opt.step()
        return loss.item()

    def forward(self, x):
        return self.net.forward(x)

class TileBaselineV(nn.Module):
    def __init__(self, n_in, n_hid):
        super(TileBaselineV, self).__init__()
        self.net = MLP(n_in, n_hid, 1)

    def get_action(self, env, grid_state, e, all_nbrs=None, x=None, y=None):
        # get neighbors
        if all_nbrs is None:
            all_nbrs = env.all_nbrs(grid_state, x, y) # these are irreps

        invalid_moves = [m for m in env.MOVES if m not in env.valid_moves(x, y)]
        vals = self.forward(torch.from_numpy(all_nbrs).float())
        # TODO: this is pretty hacky
        for m in invalid_moves:
            vals[m] = -float('inf')
        return torch.argmax(vals).item()

    def update(self, targ_net, env, batch, opt, discount, ep):
        rewards = torch.from_numpy(batch['reward'])
        dones = torch.from_numpy(batch['done'])
        states = torch.from_numpy(batch['irrep_state'])
        next_states = torch.from_numpy(batch['next_irrep_state'])
        dists = torch.from_numpy(batch['scramble_dist']).float()
        pred_vals = pol_net.forward(next_states)
        targ_vals = (rewards + discount * (1 - dones) * targ_net.forward(next_states))

        opt.zero_grad()
        #errors = (1 / (dists + 1.)) * (pred_vals - targ_vals.detach()).pow(2)
        #errors = (pred_vals - targ_vals.detach()).pow(2)
        #loss = errors.sum() / len(targ_vals)
        loss = F.mse_loss(pred_vals, targ_vals.detach())
        loss.backward()
        opt.step()
        return loss.item()



def test():
    partitions = [(8, 1)]
    net = IrrepDQN(partitions)
    net.forward(torch.rand(100, 64))

if __name__ == '__main__':
    test()
