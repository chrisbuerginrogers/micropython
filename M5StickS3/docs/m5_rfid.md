# m5_rfid

M5Stack RFID2 Unit — a WS1850S (MFRC522 work-alike) 13.56MHz ISO/IEC 14443-A
reader, I2C `0x28` on the Grove bus. Reads tag UIDs and, for MIFARE Classic,
authenticated data blocks.

```python
from m5.m5_rfid import RFID

rfid = RFID()

uid = rfid.read_uid()      # bytes (4, 7 or 10 long), or None if no tag
if uid:
    print(uid.hex(), rfid.card_type())
    rfid.halt()            # let the tag be tapped again as a new read
```

## Reading tags

| Call | Does |
|---|---|
| `read_uid()` | Wake + select one tag; returns its UID as `bytes`, or `None` |
| `is_card_present()` | Cheap "is anything in the field" poll |
| `card_type()` | Type of the last-selected tag, decoded from its SAK byte |
| `halt()` | Put the tag to sleep and close any crypto session |

After a successful `read_uid()`, `rfid.uid` / `rfid.uid_size` / `rfid.sak` hold
the raw values.

**Call `halt()` when you're done with a tag.** Otherwise it keeps answering and
you can't tell "still sitting there" from "tapped again". A halted tag ignores
REQA but still answers WUPA, which `read_uid()` sends as a fallback — so it
comes straight back when you poll again.

## MIFARE Classic blocks

```python
from m5.m5_rfid import RFID, DEFAULT_KEY, ReadError

rfid = RFID()
if rfid.read_uid():
    try:
        data = rfid.read_block(4, DEFAULT_KEY)   # 16 bytes, or None
    except ReadError:
        data = None   # read didn't complete - worth trying again
    rfid.halt()
```

`read_block()` authenticates the sector first, so it works standalone after a
`read_uid()`. `DEFAULT_KEY` is `FF FF FF FF FF FF`, the factory key on a blank
tag. Pass `use_key_b=True` for key B. Sector 0 block 0 is manufacturer data and
every 4th block (3, 7, 11, …) is a sector trailer holding the keys themselves —
key A always reads back as zeros there. The crypto session stays open until
`halt()`, so further blocks in the same sector are readable without
re-authenticating.

## Ultralight / NTAG pages

Ultralight and NTAG tags (SAK `0x00`) have no MIFARE authentication, so
`read_block()` always returns `None` for them. Use `read_pages()` instead — same
underlying read command, no auth:

```python
data = rfid.read_pages(4)    # 16 bytes = pages 4,5,6,7
```

Check `rfid.sak == 0x00` and pick one rather than trying both: a *failed*
authentication drops the tag out of its ACTIVE state, so a `read_pages()` after
a failed `read_block()` fails too, even on a tag that would otherwise read.

## Failed reads: `None` vs `ReadError`

`read_block()` and `read_pages()` separate the two very different ways a read
fails, so callers don't have to guess whether retrying is worth it:

| Outcome | Means | Do |
|---|---|---|
| returns bytes | Read succeeded | — |
| returns `None` | Tag is still in the field and **permanently** can't serve this request — wrong key, or wrong tag type for the command | Don't retry; it'll fail the same way |
| raises `ReadError` | The read **didn't complete** — CRC mismatch, short answer, or the tag moved mid-transaction | Retry |

Both methods already retry transient failures internally (`retries=3`,
`retry_ms=60` by default), re-selecting the tag between attempts — a failed
transaction leaves it deselected, so a bare retry would fail identically. They
only raise once those attempts are used up.

The distinction is decided by whether the tag is still in the field after the
last attempt: still there means it refused on its own terms, gone means the read
was interrupted. Without this split, an occasional empty read on a perfectly good
card is indistinguishable from "wrong card", and callers end up telling the user
their working card is bad.

## Range

If tags only read while touching the unit, raise the receiver gain:

```python
from m5.m5_rfid import RFID, GAIN_48DB

rfid = RFID()
rfid.set_antenna_gain(GAIN_48DB)   # reset default is GAIN_33DB
```

`antenna_off()` drops the RF field between polls, which is worth doing on
battery.

## Cold start

`power_on_grove_5v()` only *starts* the Grove 5V boost rail coming up, so the
reader can still be unpowered when the first register write goes out — which
surfaces as an intermittent `OSError: [Errno 110] ETIMEDOUT` from `RFID()` that
reads like flaky hardware rather than a race. The constructor waits
`BOOST_SETTLE_MS` (100ms) and then retries, `attempts=6` times `retry_ms=500`
apart, before raising an `OSError` naming the address and elapsed time. Tune via
`RFID(attempts=..., retry_ms=...)`.

## Not implemented

Block/page writes, the UID-changeable-card backdoor, and the sector-dump
pretty-printer from the upstream driver. See [`../m5/CLAUDE.md`](../m5/CLAUDE.md)
for the port's provenance and the upstream bugs fixed along the way.

`rfid_reader.py` at the project root is the example script that uses this
module.
