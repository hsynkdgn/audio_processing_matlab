"""Generate the committed synthetic WAV fixtures under tests/fixtures/.

Fixtures are NEVER edited by hand (CLAUDE.md rule); re-run this script and
commit the outputs if they must change. Generation is fully deterministic
(seeded RNG) so re-runs produce byte-identical files.

Usage:
    python scripts/make_fixtures.py
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SEED = 20260705


def _write(name: str, data: np.ndarray, samplerate: int) -> None:
    """Peak-normalize to 0.9 and write mono 16-bit PCM WAV."""
    peak = np.max(np.abs(data))
    if peak > 0:
        data = 0.9 * data / peak
    path = FIXTURES_DIR / name
    sf.write(str(path), data.astype(np.float64), samplerate, subtype="PCM_16")
    info = sf.info(str(path))
    print(f"wrote {path.name}: {info.frames} frames @ {info.samplerate} Hz, {info.subtype}")


def tone_440hz_48k() -> None:
    """Pure 440 Hz sine, 1.0 s @ 48 kHz."""
    sr = 48_000
    t = np.arange(int(1.0 * sr)) / sr
    _write("tone_440hz_48k.wav", np.sin(2 * np.pi * 440.0 * t), sr)


def mix_100_400_1000hz_44k1() -> None:
    """Equal-amplitude 100 + 400 + 1000 Hz mixture, 1.5 s @ 44.1 kHz."""
    sr = 44_100
    t = np.arange(int(1.5 * sr)) / sr
    x = sum(np.sin(2 * np.pi * f * t) for f in (100.0, 400.0, 1000.0))
    _write("mix_100_400_1000hz_44k1.wav", x, sr)


def noise_250hz_48k() -> None:
    """2.0 s white noise with an embedded 250 Hz tone @ 48 kHz (seeded)."""
    sr = 48_000
    rng = np.random.default_rng(SEED)
    t = np.arange(int(2.0 * sr)) / sr
    x = rng.standard_normal(t.size) * 0.3 + np.sin(2 * np.pi * 250.0 * t)
    _write("noise_250hz_48k.wav", x, sr)


def stereo_tone_440hz_48k() -> None:
    """Stereo 440 Hz tone, L/R at different amplitudes (0.8/0.4), 1.0 s @ 48 kHz.

    Exercises the channel-averaging downmix end-to-end: a GoPro-shaped
    stereo AAC source should extract to a mono WAV whose amplitude sits
    between the two channels' amplitudes.
    """
    sr = 48_000
    t = np.arange(int(1.0 * sr)) / sr
    left = 0.8 * np.sin(2 * np.pi * 440.0 * t)
    right = 0.4 * np.sin(2 * np.pi * 440.0 * t)
    stereo = np.column_stack([left, right]).astype(np.float64)
    wav_path = FIXTURES_DIR / "stereo_tone_440hz_48k.wav"
    sf.write(str(wav_path), stereo, sr, subtype="PCM_16")
    info = sf.info(str(wav_path))
    print(
        f"wrote {wav_path.name}: {info.frames} frames @ {info.samplerate} Hz, "
        f"{info.channels}ch, {info.subtype}"
    )
    _encode(
        wav_path, FIXTURES_DIR / "stereo_tone_440hz_48k.mp4", ["-acodec", "aac", "-b:a", "128k"]
    )


def _encode(source_wav: Path, target: Path, codec_args: list[str]) -> bool:
    """Encode a WAV fixture into a compressed container via bundled ffmpeg.

    Returns True on success, False if the encoder is unavailable in the
    static ffmpeg build (the fixture is then skipped, not an error).
    """
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-y",
        "-i",
        str(source_wav),
        *codec_args,
        str(target),
    ]
    result = subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 or not target.is_file():
        print(
            f"SKIPPED {target.name}: encoder unavailable or failed "
            f"({result.stderr.strip().splitlines()[-1] if result.stderr else '?'})"
        )
        return False
    print(f"wrote {target.name}: {target.stat().st_size} bytes")
    return True


def compressed_fixtures() -> None:
    """1 s 440 Hz tone as MP4 (AAC) and MP3 — real extraction test inputs."""
    source = FIXTURES_DIR / "tone_440hz_48k.wav"
    _encode(source, FIXTURES_DIR / "tone_440hz_48k.mp4", ["-acodec", "aac", "-b:a", "128k"])
    _encode(source, FIXTURES_DIR / "tone_440hz_48k.mp3", ["-acodec", "libmp3lame", "-b:a", "128k"])


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    tone_440hz_48k()
    mix_100_400_1000hz_44k1()
    noise_250hz_48k()
    stereo_tone_440hz_48k()
    compressed_fixtures()


if __name__ == "__main__":
    main()
