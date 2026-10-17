from pathlib import Path

import av
import pytest
from PIL import Image


@pytest.fixture
def synthetic_video(tmp_path) -> Path:
    path = tmp_path / "artificial.mov"
    with av.open(str(path), mode="w", format="mov") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 160, 120, "yuv420p"
        for index in range(30):
            image = Image.new("RGB", (160, 120), (index * 7, 80, 60))
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path
