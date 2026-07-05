"""Media handling: probing, audio extraction/cutting via ffmpeg, WAV I/O.

The ffmpeg binary is always resolved through imageio-ffmpeg (bundled with
the application); the system PATH is never consulted. All subprocess
calls follow the cross-platform rules in
.claude/skills/ffmpeg-media/SKILL.md: shell=False, list arguments,
explicit UTF-8 decoding, no shell redirection.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

from heli_noise.core.exceptions import InvalidTimeRangeError, MediaDecodeError

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")
_AUDIO_STREAM_RE = re.compile(r"Audio:.*?(\d+)\s*Hz.*?(mono|stereo|\d+ channels)")


@dataclass(frozen=True)
class MediaInfo:
    """Audio properties of a media file.

    Attributes:
        duration: Total duration in seconds.
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
    """

    duration: float
    sample_rate: int
    channels: int


def _ffmpeg_exe() -> str:
    """Return the absolute path of the bundled ffmpeg binary."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command with the project's cross-platform subprocess rules.

    Args:
        cmd: Full command as a list of strings (never a joined string).

    Returns:
        The completed process; the caller inspects ``returncode``.
    """
    creationflags = 0
    if sys.platform == "win32":  # no console window flash on Windows
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=creationflags,
    )


def _parse_channels(text: str) -> int:
    """Convert an ffmpeg channel description to a channel count."""
    if text == "mono":
        return 1
    if text == "stereo":
        return 2
    return int(text.split()[0])


def probe_media(path: Path) -> MediaInfo:
    """Read duration, sample rate, and channel count from a media file.

    Runs ``ffmpeg -i`` (which exits non-zero without an output file) and
    parses the stream information it prints on stderr. There is no
    bundled ffprobe, so this is the sanctioned probing method.

    Args:
        path: Media file (MP4/MP3/WAV/...) to inspect.

    Returns:
        The probed :class:`MediaInfo`.

    Raises:
        MediaDecodeError: If the file does not exist, has no audio
            stream, or its duration cannot be determined.
    """
    if not path.is_file():
        raise MediaDecodeError(f"File not found: {path}")

    result = _run([_ffmpeg_exe(), "-hide_banner", "-i", str(path)])
    stderr = result.stderr

    duration_match = _DURATION_RE.search(stderr)
    if duration_match is None:
        raise MediaDecodeError(
            f"Could not determine duration of {path.name} (ffmpeg output: {stderr[-500:]!r})"
        )
    hours, minutes, seconds, fraction = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + float(f"0.{fraction}")

    audio_match = _AUDIO_STREAM_RE.search(stderr)
    if audio_match is None:
        raise MediaDecodeError(f"No audio stream found in {path.name}")
    sample_rate = int(audio_match.group(1))
    channels = _parse_channels(audio_match.group(2))

    return MediaInfo(duration=duration, sample_rate=sample_rate, channels=channels)


def extract_audio(
    input_path: Path,
    start_s: float,
    stop_s: float,
    output_path: Path,
) -> Path:
    """Extract a time interval of the audio track into a mono 16-bit WAV.

    Uses input seeking (``-ss`` before ``-i``) for speed on large GoPro
    MP4s, with an explicit ``-t`` duration bound (unambiguous across
    ffmpeg versions). The original sample rate is preserved; multichannel
    audio is downmixed to mono by ffmpeg.

    Args:
        input_path: Source media file (MP4/MP3/WAV/...).
        start_s: Interval start in seconds (>= 0).
        stop_s: Interval stop in seconds (> start, <= duration).
        output_path: Destination WAV path; parent directories are created.

    Returns:
        ``output_path`` on success.

    Raises:
        MediaDecodeError: If probing or decoding fails.
        InvalidTimeRangeError: If the interval is not within the media.
    """
    info = probe_media(input_path)
    if start_s < 0:
        raise InvalidTimeRangeError(f"Start time must be >= 0, got {start_s}")
    if stop_s <= start_s:
        raise InvalidTimeRangeError(
            f"Stop time ({stop_s}) must be greater than start time ({start_s})"
        )
    if stop_s > info.duration + 0.05:  # small tolerance for container rounding
        raise InvalidTimeRangeError(
            f"Stop time ({stop_s}s) is past the end of the media ({info.duration:.3f}s)"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-y",
        "-ss",
        f"{start_s:.6f}",
        "-i",
        str(input_path),
        "-t",
        f"{stop_s - start_s:.6f}",
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(info.sample_rate),
        "-ac",
        "1",
        str(output_path),
    ]
    result = _run(cmd)
    if result.returncode != 0 or not output_path.is_file():
        raise MediaDecodeError(
            f"ffmpeg failed to extract audio from {input_path.name}: {result.stderr[-2000:]}"
        )
    return output_path


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file as a mono float64 signal in [-1, 1].

    Stereo/multichannel input is downmixed to mono by channel averaging
    (project rule).

    Args:
        path: WAV file to read.

    Returns:
        Tuple of (mono float64 samples, sample rate in Hz).

    Raises:
        MediaDecodeError: If the file cannot be read as audio.
    """
    try:
        data, sample_rate = sf.read(str(path), dtype="float64", always_2d=True)
    except (sf.LibsndfileError, RuntimeError) as exc:
        raise MediaDecodeError(f"Could not read WAV file {path}: {exc}") from exc
    mono = data.mean(axis=1)
    return mono, int(sample_rate)


def save_wav(path: Path, data: np.ndarray, sample_rate: int) -> None:
    """Write a mono float signal as a 16-bit PCM WAV.

    Values are clipped to [-1, 1] before writing (clipping prevention is
    normalization's job upstream; the clip here is a safety net).

    Args:
        path: Destination WAV path; parent directories are created.
        data: 1-D float samples in [-1, 1].
        sample_rate: Sample rate in Hz.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(np.asarray(data, dtype=np.float64), -1.0, 1.0)
    sf.write(str(path), clipped, sample_rate, subtype="PCM_16")
