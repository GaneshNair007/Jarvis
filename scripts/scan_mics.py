"""Probes default sample rates and records at each device's native rate."""

import sounddevice as sd
import numpy as np

for dev_id in [0, 1, 4, 5]:
    info = sd.query_devices(dev_id)
    default_rate = int(info["default_samplerate"])
    print(f"dev {dev_id}: {info['name'][:45]:45} default_rate={default_rate}")
    for rate in sorted({default_rate, 44100, 48000}):
        try:
            rec = sd.rec(
                int(1.5 * rate),
                samplerate=rate,
                channels=1,
                dtype="int16",
                device=dev_id,
            )
            sd.wait()
            audio = rec.flatten()
            energy = float(np.mean(np.abs(audio.astype(np.float32))))
            marker = " <== LIVE" if energy >= 100 else ""
            print(f"    rate={rate:6d} energy={energy:8.1f}{marker}")
        except Exception as exc:
            print(f"    rate={rate:6d} ERROR {exc}")
