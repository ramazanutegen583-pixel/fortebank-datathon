from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from vision.optimization import LinearPatchProjection


@pytest.mark.parametrize("shape", [(2, 2, 2), (2, 4, 4)])
def test_patch_projection_matches_convolution(shape):
    torch.manual_seed(17)
    conv = torch.nn.Conv3d(3, 16, kernel_size=shape, stride=shape, bias=True)
    patches = torch.randn(7, 3, *shape)
    expected = conv(patches).reshape(7, 16)
    adapted = LinearPatchProjection(SimpleNamespace(proj=conv))
    actual = adapted(patches.flatten(1))
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


def test_overlapping_patch_layout_is_rejected():
    conv = torch.nn.Conv3d(3, 16, kernel_size=2, stride=1)
    with pytest.raises(ValueError):
        LinearPatchProjection(SimpleNamespace(proj=conv))
