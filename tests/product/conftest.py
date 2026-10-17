from pathlib import Path

import av
import pytest
from PIL import Image


@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("synthetic-media") / "synthetic.mov"
    image = Image.new("RGB", (160, 120), (90, 110, 80))
    with av.open(str(path), mode="w", format="mov") as container:
        stream = container.add_stream("mpeg4", rate=12)
        stream.width = 160
        stream.height = 120
        stream.pix_fmt = "yuv420p"
        for _ in range(36):
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path
