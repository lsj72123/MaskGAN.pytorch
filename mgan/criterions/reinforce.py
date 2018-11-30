from torch import nn
import torch

# TODO(jerin): Need to fix this as per
# https://github.com/tensorflow/models/blob/master/research/maskgan/model_utils/model_losses.py

class REINFORCE(nn.Module):
    def __init__(self, gamma, clip_value):
        super().__init__()
        self.gamma = gamma
        self.clip_value = clip_value
        self.log_sigmoid = torch.nn.LogSigmoid()

    def forward(self, log_probs, logits, weight, baselines=None):
        # TODO(jerin): How do I assert that this implementation is solid?
        # Is the generator giving the correct rewards?
        EPS = 1e-7
        batch_size, seqlen, _ = logits.size()
        rewards = self.log_sigmoid(logits).squeeze(2)

        # print(rewards.size(), log_probs.size(), weight.size())
        # rewards = weight * rewards

        # The below is dumb. This doesn't actually lead to bad loss signal, but
        # pure fuckery.  
        # log_probs = weight * log_probs  

        cumulative_rewards = []
        for t in range(seqlen):
            cum_value = rewards.new_zeros(batch_size)
            for s in range(t, seqlen):
                exp = float(s-t)
                k = (self.gamma ** exp)
                cum_value +=  k * weight[:, s]  * rewards[:, s]
            cumulative_rewards.append(cum_value)

        cumulative_rewards = torch.stack(cumulative_rewards, dim=1)

        # Find and clamp advantages
        if baselines is not None:
            baselines = baselines.squeeze(2)
            advantages = cumulative_rewards - baselines
            advantages = advantages.clamp(-1*self.clip_value, self.clip_value)
        else:
            advantages = cumulative_rewards

        # b = 0
        # for t in range(seqlen):
        #     if weight[b, t] == 1:
        #         print("(", rewards[b, t].item(), cumulative_rewards[b, t].item(), log_probs[b, t].item(), ")", end=' ')
        # print('')

        #advantages = weight*(cumulative_rewards - baselines)

        # Multiply with logprobs
        generator_objective = (advantages * log_probs).sum(dim=0)
        return (generator_objective, cumulative_rewards)


