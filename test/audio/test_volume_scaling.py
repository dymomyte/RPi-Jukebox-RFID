import sys
from unittest.mock import MagicMock

import pytest

import jukebox.plugs as plugin

sys.modules.setdefault('jukebox.publishing', MagicMock())


def dummy_decorator(function):
    return function


plugin.initialize = dummy_decorator
plugin.finalize = dummy_decorator
plugin.atexit = dummy_decorator
plugin.tag = dummy_decorator

import components.volume as volume  # noqa: E402

SINK = 'usb'


@pytest.mark.parametrize(
    ('user_volume', 'floor', 'limit', 'sink_volume'),
    [
        (100, 0, 100, 100),
        (50, 0, 50, 25),
        (1, 9, 50, 9.41),
        (50, 9, 50, 29.5),
        (100, 9, 50, 50),
    ],
)
def test_user_volume_scales_into_floor_and_limit(user_volume, floor, limit, sink_volume):
    assert volume.to_sink_volume(user_volume, floor, limit) == pytest.approx(sink_volume)


@pytest.mark.parametrize('user_volume', range(1, 101))
@pytest.mark.parametrize(('floor', 'limit'), [(0, 100), (0, 50), (9, 50), (20, 100)])
def test_sink_volume_scales_back_to_user_volume(user_volume, floor, limit):
    sink_volume = volume.to_sink_volume(user_volume, floor, limit)
    assert volume.from_sink_volume(sink_volume, floor, limit) == user_volume


@pytest.mark.parametrize('sink_volume', [0, 5, 9])
def test_sink_volume_at_or_below_floor_is_zero(sink_volume):
    assert volume.from_sink_volume(sink_volume, 9, 50) == 0


@pytest.mark.parametrize(('floor', 'expected'), [(0, 0), (9, 9), (-1, 0), (50, 0), (60, 0)])
def test_volume_floor_must_lie_below_limit(floor, expected):
    assert volume.valid_volume_floor('primary', floor, 50) == expected


def test_audio_sink_floor_defaults_to_zero():
    assert volume.AudioSinkClass('Speakers', SINK, 50).volume_floor == 0


@pytest.fixture
def control(monkeypatch):
    monkeypatch.setattr(volume, 'audio_monitor', MagicMock(), raising=False)
    monkeypatch.setattr(volume.cfg, 'setndefault', MagicMock(return_value=100))
    sink_control = volume.VolumeControl([volume.AudioSinkClass('Speakers', SINK, 50, 9)])
    monkeypatch.setattr(sink_control, '_publish_volume', MagicMock())
    return sink_control


def test_set_volume_applies_floor(control):
    pulse_inst = MagicMock()

    control._set_volume(pulse_inst, 1, SINK)

    pulse_inst.mute.assert_called_once_with(pulse_inst.get_sink_by_name.return_value, mute=False)
    pulse_inst.volume_set_all_chans.assert_called_once_with(pulse_inst.get_sink_by_name.return_value, pytest.approx(0.0941))


def test_set_volume_zero_still_mutes(control):
    pulse_inst = MagicMock()

    control._set_volume(pulse_inst, 0, SINK)

    pulse_inst.mute.assert_called_once_with(pulse_inst.get_sink_by_name.return_value, mute=True)
    pulse_inst.volume_set_all_chans.assert_called_once_with(pulse_inst.get_sink_by_name.return_value, 0)


def test_get_volume_reverses_floor(control):
    pulse_inst = MagicMock()
    pulse_inst.get_sink_by_name.return_value.mute = 0
    pulse_inst.volume_get_all_chans.return_value = 0.295

    assert control._get_volume_and_mute(pulse_inst, SINK) == (50, 0)
