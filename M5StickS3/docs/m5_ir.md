# m5_ir

Raw infrared transmit/receive on the built-in IR LED (GPIO46) and receiver
(GPIO42), 38kHz carrier. This is **not** a protocol decoder — it's the
building block that `rcx_ir.py`, `power_functions.py`, and
`universal_remote.py` (all at the `M5StickS3/` project root, not in `m5/`)
are built on.

```python
from m5.m5_ir import IRTransmitter, IRReceiver

tx = IRTransmitter()  # or carrier_hz=40000 for Sony SIRC, 36000 for RC5
tx.send([9000, 4500, 563, 1687, 563])  # alternating on/off durations, µs

rx = IRReceiver()
durations = rx.read(timeout_ms=2000)  # [] if nothing arrived in time
```

- `IRTransmitter.send(durations_us)` — durations alternate on/off,
  **starting with on**. Each duration must be under ~32768µs (the RMT's
  per-symbol limit at this resolution) — split a longer gap into multiple
  calls if you need one.
- `IRReceiver.read(timeout_ms, ...)` — busy-polls (not interrupt-driven), so
  it's simple and accurate enough for well-spaced pulses like LEGO PF or RCX's
  2400-baud framing, but will jitter more than an IRQ-based capture on faster
  protocols like NEC if you're hand-rolling something new.
- Remember the amp/IR interference gotcha noted in
  [m5_audio.md](m5_audio.md) if your script also plays sound.

If you're adding a new IR-based device, start here rather than the compiled
`esp32.RMT` API directly — see `rcx_ir.py` or `power_functions.py` for the
shape a new protocol module built on this typically takes.
