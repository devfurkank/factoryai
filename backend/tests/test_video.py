"""Video modülü testleri — Faz 5 (Gün 16-17: buffer, klip, HLS)."""
import asyncio
import os
import sys
import time

import cv2
import numpy as np
import pytest

from app.camera.schemas import CameraConfig, SourceType
from app.config import settings
from app.video.buffer import VideoBuffer, VideoBufferManager
from app.video.clips import estimate_fps, write_clip, _write_with_cv2
from app.video.hls import HLSStream, HLSStreamManager


def _frame(width=160, height=120, value=0):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = value
    return frame


def _jpeg(width=160, height=120, value=0):
    ok, buf = cv2.imencode(".jpg", _frame(width, height, value))
    assert ok
    return buf.tobytes()


# ── VideoBuffer (ring buffer) ─────────────────────────────────────────────────
class TestVideoBuffer:
    def test_add_and_range(self):
        buf = VideoBuffer("cam_t", capacity_seconds=5, nominal_fps=10)
        for i in range(20):
            buf.add_encoded(b"jpg%d" % i, 1000.0 + i * 0.1)
        # [1000.5, 1001.0] aralığı → 6 frame (0.5, 0.6, ..., 1.0)
        frames = buf.get_range(1000.5, 1001.0)
        assert len(frames) == 6
        assert frames[0][1] == pytest.approx(1000.5)
        assert frames[-1][1] == pytest.approx(1001.0)

    def test_ring_evicts_oldest(self):
        buf = VideoBuffer("cam_t", capacity_seconds=1, nominal_fps=10)  # maxlen=10
        for i in range(25):
            buf.add_encoded(b"x", 1000.0 + i)
        assert buf.frame_count == 10
        # En eski 15 frame atılmış olmalı
        assert buf.get_range(1000.0, 1014.0) == []

    def test_span_seconds(self):
        buf = VideoBuffer("cam_t", capacity_seconds=5, nominal_fps=10)
        assert buf.span_seconds == 0.0
        buf.add_encoded(b"a", 1000.0)
        buf.add_encoded(b"b", 1003.5)
        assert buf.span_seconds == pytest.approx(3.5)

    def test_default_capacity_covers_clip_window(self):
        buf = VideoBuffer("cam_t")
        expected = (
            settings.video_pre_buffer_seconds
            + settings.video_post_buffer_seconds
            + 5
        )
        assert buf.capacity_seconds == expected


class TestVideoBufferManager:
    def test_lazy_buffer_creation_and_sync_add(self):
        mgr = VideoBufferManager()
        mgr.add_frame_sync("cam_a", _frame(), 1000.0)
        mgr.add_frame_sync("cam_a", _frame(), 1000.5)
        mgr.add_frame_sync("cam_b", _frame(), 1000.0)
        assert len(mgr.get_frames("cam_a", 999.0, 1001.0)) == 2
        assert len(mgr.get_frames("cam_b", 999.0, 1001.0)) == 1

    def test_unknown_camera_returns_empty(self):
        mgr = VideoBufferManager()
        assert mgr.get_frames("yok", 0, 1e12) == []

    def test_stored_frames_are_valid_jpeg(self):
        mgr = VideoBufferManager()
        mgr.add_frame_sync("cam_a", _frame(value=128), 1000.0)
        jpeg, _ = mgr.get_frames("cam_a", 999.0, 1001.0)[0]
        decoded = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape == (120, 160, 3)

    @pytest.mark.asyncio
    async def test_async_add_frame(self):
        mgr = VideoBufferManager()
        await mgr.add_frame("cam_a", _frame(), 1000.0)
        assert len(mgr.get_frames("cam_a", 999.0, 1001.0)) == 1

    def test_stats(self):
        mgr = VideoBufferManager()
        mgr.add_frame_sync("cam_a", _frame(), time.time())
        stats = mgr.get_stats()
        assert stats["cam_a"]["frames"] == 1
        assert stats["cam_a"]["newest_age_seconds"] is not None


# ── FPS Tahmini ───────────────────────────────────────────────────────────────
class TestEstimateFps:
    def test_uniform_10fps(self):
        ts = [1000.0 + i * 0.1 for i in range(21)]
        assert estimate_fps(ts) == pytest.approx(10.0, abs=0.1)

    def test_single_frame_returns_min(self):
        assert estimate_fps([1000.0]) == 1.0
        assert estimate_fps([]) == 1.0

    def test_zero_span_returns_min(self):
        assert estimate_fps([1000.0, 1000.0]) == 1.0

    def test_clamped_to_max(self):
        ts = [1000.0 + i * 0.001 for i in range(100)]  # 1000fps
        assert estimate_fps(ts) == 30.0


# ── Klip Yazımı ───────────────────────────────────────────────────────────────
class TestWriteClip:
    def _frames(self, count=10, fps=8.0):
        return [(_jpeg(value=i * 10), 1000.0 + i / fps) for i in range(count)]

    def test_too_few_frames_returns_none(self, tmp_path):
        assert write_clip("ev_x", [], out_dir=str(tmp_path)) is None
        assert write_clip("ev_x", self._frames(1), out_dir=str(tmp_path)) is None

    def test_write_clip_produces_playable_mp4(self, tmp_path):
        """FFmpeg varsa onunla, yoksa cv2 fallback ile MP4 üretilmeli."""
        path = write_clip("ev_clip", self._frames(12), out_dir=str(tmp_path))
        assert path is not None
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0
        # Üretilen dosya OpenCV ile tekrar açılıp okunabilmeli
        cap = cv2.VideoCapture(path)
        assert cap.isOpened()
        ret, frame = cap.read()
        cap.release()
        assert ret and frame is not None

    def test_cv2_fallback_directly(self, tmp_path):
        path = str(tmp_path / "fallback.mp4")
        ok = _write_with_cv2(self._frames(8), fps=8.0, path=path)
        assert ok
        assert os.path.getsize(path) > 0

    def test_ffmpeg_missing_falls_back_to_cv2(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "ffmpeg_binary", "ffmpeg-yok-boyle-binary")
        path = write_clip("ev_fb", self._frames(8), out_dir=str(tmp_path))
        assert path is not None
        assert os.path.isfile(path)

    def test_corrupt_jpeg_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "ffmpeg_binary", "ffmpeg-yok-boyle-binary")
        frames = [(b"bozuk", 1000.0), (b"bozuk2", 1000.1)]
        assert write_clip("ev_bad", frames, out_dir=str(tmp_path)) is None


# ── HLS Manager ───────────────────────────────────────────────────────────────
class TestHLSManager:
    def _rtsp_config(self, cam_id="cam_rtsp_t"):
        return CameraConfig(
            id=cam_id,
            name="Test RTSP",
            source_type=SourceType.rtsp,
            source_url="rtsp://example.local/stream",
        )

    def test_build_command_contains_hls_essentials(self, tmp_path):
        mgr = HLSStreamManager()
        stream = HLSStream(
            camera_id="cam_t",
            source_url="rtsp://example.local/s1",
            playlist_path=str(tmp_path / "cam_t" / "stream.m3u8"),
        )
        cmd = mgr._build_command(stream)
        assert settings.ffmpeg_binary == cmd[0]
        assert "rtsp://example.local/s1" in cmd
        # Roadmap §5.7: TCP transport + libx264 + zerolatency + HLS
        for flag in ("-rtsp_transport", "libx264", "zerolatency", "hls"):
            assert any(flag in str(part) for part in cmd)
        # Bozuk timestamp'li IP kameralara karşı (canlıda bulunan stall nedeni):
        # wallclock giriş damgası + sabit çıkış FPS'i olmadan encoder kare
        # kopyalama patlamasına giriyor ve hiç segment yazamıyordu
        assert "-use_wallclock_as_timestamps" in cmd
        r_idx = cmd.index("-r")
        assert cmd[r_idx + 1] == str(settings.hls_fps)
        assert cmd[-1] == stream.playlist_path

    def test_stream_status_before_spawn(self, tmp_path):
        stream = HLSStream(
            camera_id="cam_t",
            source_url="rtsp://x",
            playlist_path=str(tmp_path / "stream.m3u8"),
        )
        assert not stream.is_running
        assert not stream.playlist_exists
        assert not stream.is_healthy

    def test_manager_status_unknown_camera(self):
        mgr = HLSStreamManager()
        assert mgr.get_status("bilinmeyen") is None
        assert mgr.get_all_statuses() == []

    @pytest.mark.asyncio
    async def test_disabled_by_config(self, monkeypatch):
        monkeypatch.setattr(settings, "hls_enabled", False)

        class FakeCamManager:
            def list_cameras(self):  # çağrılmamalı bile
                return []

        mgr = HLSStreamManager()
        await mgr.start(FakeCamManager())
        assert mgr._streams == {}
        assert mgr._monitor_task is None

    @pytest.mark.asyncio
    async def test_webcam_cameras_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "hls_enabled", True)
        monkeypatch.setattr(settings, "streams_dir", str(tmp_path))

        webcam = CameraConfig(
            id="cam_web", name="Webcam", source_type=SourceType.webcam
        )

        class FakeCamManager:
            def list_cameras(self):
                return [webcam]

        mgr = HLSStreamManager()
        # FFmpeg var mı bilinmez — kontrolü bypass et
        mgr._ffmpeg_available = True
        await mgr.start(FakeCamManager())
        try:
            assert "cam_web" not in mgr._streams
        finally:
            await mgr.stop_all()

    @pytest.mark.asyncio
    async def test_add_camera_ignored_when_not_running(self):
        mgr = HLSStreamManager()
        await mgr.add_camera(self._rtsp_config())
        assert mgr._streams == {}

    @pytest.mark.asyncio
    async def test_restart_unknown_camera_returns_false(self):
        mgr = HLSStreamManager()
        assert (await mgr.restart("yok")) is False


# ── FFmpeg Süreç Yönetimi (subprocess.Popen) ──────────────────────────────────
class TestHLSSpawn:
    """Regresyon: Windows'ta `uvicorn --reload` event loop'u SelectorEventLoop'a
    zorlar ve asyncio.create_subprocess_exec orada NotImplementedError fırlatır
    (boş str() mesajlı — canlıda `hls.stream.spawn_failed error=` olarak
    görüldü). Bu yüzden HLS süreçleri subprocess.Popen ile başlatılır ve her
    event loop tipinde çalışmalıdır."""

    def _stream(self, tmp_path):
        return HLSStream(
            camera_id="cam_t",
            source_url="rtsp://x",
            playlist_path=str(tmp_path / "stream.m3u8"),
        )

    def test_spawn_and_terminate_on_selector_event_loop(self, tmp_path, monkeypatch):
        mgr = HLSStreamManager()
        stream = self._stream(tmp_path)
        # FFmpeg yerine uzun süre uyuyan bir Python süreci kullan
        fake_cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
        monkeypatch.setattr(mgr, "_build_command", lambda s: fake_cmd)

        old_policy = asyncio.get_event_loop_policy()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            async def scenario():
                await mgr._spawn(stream)
                assert stream.is_running, f"spawn başarısız: {stream.last_error}"
                assert stream.last_error is None
                await mgr._terminate(stream)
                assert not stream.is_running

            asyncio.run(scenario())
        finally:
            asyncio.set_event_loop_policy(old_policy)

    @pytest.mark.asyncio
    async def test_spawn_missing_binary_records_exception_type(
        self, tmp_path, monkeypatch
    ):
        """Boş mesajlı istisnalar log'da kaybolmamalı — repr() tip adını korur."""
        monkeypatch.setattr(settings, "ffmpeg_binary", "boyle-bir-binary-yok-xyz")
        mgr = HLSStreamManager()
        stream = self._stream(tmp_path)
        await mgr._spawn(stream)
        assert not stream.is_running
        assert stream.last_error and "Error" in stream.last_error

    def test_read_log_tail(self, tmp_path):
        stream = self._stream(tmp_path)
        with open(stream.log_path, "wb") as f:
            f.write(b"x" * 1000 + b"\nson hata satiri")
        tail = stream.read_log_tail(max_bytes=100)
        assert tail.endswith("son hata satiri")
        assert len(tail) <= 100

    def test_read_log_tail_missing_file(self, tmp_path):
        stream = self._stream(tmp_path)
        assert stream.read_log_tail() == ""


# ── sync_camera (çalışma anında kamera ekleme/güncelleme — code review) ──────
class TestHLSSyncCamera:
    def _mgr(self, monkeypatch):
        mgr = HLSStreamManager()
        mgr._running = True
        mgr._ffmpeg_available = True
        spawned = []

        async def fake_spawn(stream):
            spawned.append(stream.camera_id)

        monkeypatch.setattr(mgr, "_spawn", fake_spawn)
        return mgr, spawned

    def _rtsp(self, url="rtsp://example.local/s1", active=True):
        return CameraConfig(
            id="cam_x", name="X", source_type=SourceType.rtsp,
            source_url=url, is_active=active,
        )

    @pytest.mark.asyncio
    async def test_noop_when_not_running(self, monkeypatch):
        mgr, spawned = self._mgr(monkeypatch)
        mgr._running = False
        await mgr.sync_camera(self._rtsp())
        assert spawned == [] and mgr._streams == {}

    @pytest.mark.asyncio
    async def test_new_rtsp_camera_gets_stream(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "streams_dir", str(tmp_path))
        mgr, spawned = self._mgr(monkeypatch)
        await mgr.sync_camera(self._rtsp())
        assert spawned == ["cam_x"]
        assert "cam_x" in mgr._streams

    @pytest.mark.asyncio
    async def test_deactivated_camera_stream_removed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "streams_dir", str(tmp_path))
        mgr, spawned = self._mgr(monkeypatch)
        await mgr.sync_camera(self._rtsp())
        await mgr.sync_camera(self._rtsp(active=False))
        assert "cam_x" not in mgr._streams

    @pytest.mark.asyncio
    async def test_url_change_respawns(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "streams_dir", str(tmp_path))
        mgr, spawned = self._mgr(monkeypatch)
        await mgr.sync_camera(self._rtsp("rtsp://a/1"))
        await mgr.sync_camera(self._rtsp("rtsp://b/2"))
        assert spawned == ["cam_x", "cam_x"]
        assert mgr._streams["cam_x"].source_url == "rtsp://b/2"

    @pytest.mark.asyncio
    async def test_webcam_camera_ignored(self, monkeypatch):
        mgr, spawned = self._mgr(monkeypatch)
        webcam = CameraConfig(id="cam_w", name="W", source_type=SourceType.webcam)
        await mgr.sync_camera(webcam)
        assert spawned == [] and mgr._streams == {}
