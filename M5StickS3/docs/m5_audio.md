# m5_audio

Speaker tone playback through the ES8311 codec + AW8737 amp.

```python
from m5.m5_audio import Speaker

speaker = Speaker(volume=70)  # 0-100
speaker.tone(440, 500)        # 440Hz for 500ms, blocking
speaker.set_volume(50)
speaker.deinit()              # stops I2S and powers the amp back off
```

**Construction can raise `OSError: [Errno 19] ENODEV`** — the codec's I2C
connection has been observed to be flaky on this repo's hardware (worked
fine after several unrelated power cycles, having been completely
unresponsive before that — see `m5_audio.py`'s docstring). Catch it if you
want your script to keep running without sound instead of crashing:

```python
try:
    speaker = Speaker(volume=60)
except OSError as e:
    print("no audio:", e)
    speaker = None
```

(`tilt_tone.py` does exactly this.)

Sample rate is fixed at 16000Hz stereo — that's specific to how this codec's
master clock is derived from the I2S bit clock on this board (MicroPython
can't drive a separate MCLK pin), not a tunable setting.

**Cross-peripheral gotcha**: turn the amp off (`speaker.deinit()`, or
`m5_power.power_off_speaker()` directly) before using
[m5_ir.md](m5_ir.md)'s `IRReceiver` in the same script — M5Stack's own docs
say the amp interferes with IR reception.
