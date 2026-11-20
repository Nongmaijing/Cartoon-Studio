# Village-Life / Ambient Episode Format

A relaxing, music-led format rather than a plotted episode. The reference in
`examples/` is a 3:04 montage of hand-painted domestic moments — cooking, a
garden, a cat, tea, rain — with **music only, no dialogue**, and short 3–5 s
shots. It is copyrighted film footage; the format is what we reproduce, with
original art.

## Format recipe

| Element | Setting |
|---|---|
| Length | 60–180 s |
| Structure | 8–16 vignettes, 6–8 s each |
| Aspect / frame rate | 1280×720 or 1920×1080, 24 fps |
| Camera | Slow push/pull or pan, 2–5 % |
| Transitions | Cuts inside the piece; fades only at the opening/closing |
| Dialogue | None |
| Subtitles | None |
| Audio | Ambient score + birds/wind/rain; **−16 LUFS** |
| Colour | Rich gouache, warm wood, lush greens, soft daylight |

## Prompt bank

Use close-ups and details, not full scenes. Hands, food, textiles, pots, rain,
cats and village paths carry this format.

- hands kneading dough on a floured wooden table, steam from a kettle
- hands slicing tomatoes and basil, blue ceramic bowl
- basket of tomatoes, basil and marigolds on a veranda
- grey cat sleeping on a sunlit veranda, laundry in the breeze
- copper pot simmering on a wood stove, hanging herbs
- narrow village path, wildflowers, bicycles against a stone wall
- white sheets drying between wooden houses, village roofs
- rain on a cottage window, warm lamp and a cup of tea

Append:

```
ghibli-inspired hand-painted 2D animation, painterly gouache, rich saturated
colors, soft morning light, detailed background, cinematic still
```

Negative: photo, 3D, CGI, text, watermark, deformed, extra limbs, extra fingers.

Hands are the risk. Keep them mid-frame, partially cropped, or replace them with
props if the fingers fail; regenerate only that vignette.

## Audio

`audio_synth.py` now generates original beds locally:

| Bed | Character |
|---|---|
| `synthesize_ambient_music` | Slow Cmaj7/Am7/Fmaj7/G pads, no melody |
| `synthesize_ambience("birds")` | Soft wind bed + distant chirps |
| `synthesize_ambience("wind")` | Low filtered noise with slow swells |
| `synthesize_ambience("rain")` | Rain bed + droplets |
| `synthesize_ambience("stream")` | Filtered water + bubbles |
| `synthesize_ambience("fire")` | Low bed + crackles |

Mix at roughly music 0.30, birds 0.34, wind 0.18. The episode export now applies
`loudnorm=I=-16:TP=-1.5:LRA=11` to every final mix, so the delivered file is
web-ready regardless of source levels.

## Build the proof

```powershell
backend\.venv\Scripts\python.exe scripts\build_village_life_episode.py --dry-run
backend\.venv\Scripts\python.exe scripts\build_village_life_episode.py
```

The builder creates eight 1280×720 plates, an ambient score, birds and wind,
eight scenes, and a 64 s episode with no subtitles. Re-running reuses the
project and scenes and adds a new export rather than overwriting.

Proof: project `b1ff88aadcf3`, episode `bb64f8ca279c`, 64.0 s, 1280×720,
H.264/AAC, **−15.7 LUFS**.

## Limits

- This is a mood piece, not a story. If you want narrative, add a soft narrator
  (Chatterbox) or short dialogue lines.
- Procedural ambience is serviceable but not a substitute for a recorded or
  licensed sound library. Replacing the beds with CC0 recordings is the next
  quality step.
- Character-led lifestyle scenes need the character LoRA and cutout pipeline;
  the proof uses hands/props only.
