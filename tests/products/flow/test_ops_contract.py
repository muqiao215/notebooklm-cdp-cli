import asyncio

from notebooklm_cdp_cli.products.flow.ops import FlowPage


class FlowFailureTransport:
    async def evaluate(self, script: str):
        return {"result": {"value": {"type": "video", "src": "https://example.com/video.mp4"}}}


def test_flow_wait_for_video_returns_download_failed_not_timeout(monkeypatch, tmp_path):
    page = FlowPage.__new__(FlowPage)
    page.transport = FlowFailureTransport()

    async def fake_sleep(_: float):
        return None

    async def fake_download(url: str, output_dir: str):
        assert url == "https://example.com/video.mp4"
        assert output_dir == str(tmp_path)
        return None

    time_values = iter([0.0, 0.1, 10.0])

    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.ops.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.ops.time.time", lambda: next(time_values))
    monkeypatch.setattr(page, "_download_video", fake_download)

    result = asyncio.run(page._wait_for_video(str(tmp_path), timeout=1000))

    assert result.path is None
    assert result.error_code == "download_failed"
    assert result.error_message == "Failed to download generated video"
    assert result.evidence == {
        "source_type": "video",
        "video_url": "https://example.com/video.mp4",
    }
