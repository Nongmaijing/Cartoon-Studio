"""Persistent Chatterbox TTS worker (voice cloning).

Runs inside the isolated ``tools/chatterbox`` virtual environment. Reads
newline-delimited JSON commands from stdin and writes one JSON response per
line. Loading the model once keeps per-line latency low.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["original", "turbo"], default="original")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    import torch  # noqa: PLC0415
    import torchaudio as ta  # noqa: PLC0415

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if args.model == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS as Model  # noqa: PLC0415
    else:
        from chatterbox.tts import ChatterboxTTS as Model  # noqa: PLC0415

    model = Model.from_pretrained(device=device)
    print(
        json.dumps(
            {
                "ready": True,
                "model": args.model,
                "device": device,
                "sample_rate": getattr(model, "sr", 24000),
            }
        ),
        flush=True,
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": f"bad request: {exc}"}), flush=True)
            continue
        try:
            text = str(request.get("text") or "").strip()
            if not text:
                raise ValueError("empty text")
            out = str(request["out"])
            reference = request.get("reference") or None
            kwargs = {}
            if request.get("exaggeration") is not None:
                kwargs["exaggeration"] = float(request["exaggeration"])
            if request.get("cfg_weight") is not None:
                kwargs["cfg_weight"] = float(request["cfg_weight"])
            if reference:
                kwargs["audio_prompt_path"] = reference

            def generate():
                try:
                    return model.generate(text, **kwargs)
                except TypeError:
                    # Turbo does not accept the original model's tuning kwargs.
                    return (
                        model.generate(text, audio_prompt_path=reference)
                        if reference
                        else model.generate(text)
                    )

            try:
                wav = generate()
            except Exception as exc:  # noqa: BLE001
                message = str(exc).lower()
                if device == "cuda" and ("out of memory" in message or "cuda" in message):
                    print("CUDA failed; falling back to CPU", file=sys.stderr, flush=True)
                    del model
                    gc.collect()
                    torch.cuda.empty_cache()
                    device = "cpu"
                    model = Model.from_pretrained(device="cpu")
                    wav = generate()
                else:
                    raise

            ta.save(out, wav, model.sr)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "out": out,
                        "sample_rate": model.sr,
                        "device": device,
                        "seconds": float(wav.shape[-1]) / float(model.sr),
                    }
                ),
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
