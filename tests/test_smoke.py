"""Infrastructure smoke tests (no application logic).

Verifies that the package imports, the committed fixtures exist, and the
headless-Qt test configuration is in effect.
"""

import os
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_package_imports() -> None:
    import heli_noise

    assert heli_noise.__version__


def test_headless_qt_platform_is_set() -> None:
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_fixture_wavs_exist_and_are_valid() -> None:
    import soundfile as sf

    expected = {
        "tone_440hz_48k.wav": (48_000, 48_000),
        "mix_100_400_1000hz_44k1.wav": (44_100, 66_150),
        "noise_250hz_48k.wav": (48_000, 96_000),
    }
    for name, (samplerate, frames) in expected.items():
        path = FIXTURES / name
        assert path.is_file(), f"missing fixture: {name}"
        info = sf.info(str(path))
        assert info.samplerate == samplerate
        assert info.frames == frames
        assert info.channels == 1
        assert info.subtype == "PCM_16"
