"""Equivalent patch projection avoiding slow small-output Conv3D kernels."""

import torch.nn.functional as functional
from torch import nn


class LinearPatchProjection(nn.Module):
    """Express a nonoverlapping, single-output patch convolution as a GEMM."""

    def __init__(self, patch_embed: nn.Module):
        super().__init__()
        self.proj = patch_embed.proj
        if (self.proj.groups != 1 or self.proj.kernel_size != self.proj.stride
                or any(self.proj.padding) or any(dilation != 1 for dilation in self.proj.dilation)):
            raise ValueError("Unsupported patch convolution layout.")

    def forward(self, hidden_states):
        weight = self.proj.weight
        flattened = weight.reshape(weight.shape[0], -1)
        patches = hidden_states.reshape(-1, flattened.shape[1]).to(dtype=weight.dtype)
        return functional.linear(patches, flattened, self.proj.bias)
