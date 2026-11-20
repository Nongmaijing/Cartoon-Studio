# Character Turnaround: View Control

## The problem

A character was generated front-on, approved as canonical, then asked for a side
view. The side jobs came back front-facing. The saved prompts show why:

- The approved canonical triggered `sdxl_ipadapter_identity`.
- The `IPAdapterAdvanced` node ran at **weight 0.9** with a front reference.
- Identity conditioning is not view control. At 0.9 it reproduced the front
  pose and ignored "true side profile" in the prompt.
- The character had no `appearance` or `clothing` fields, so the prompt had
  almost nothing to rebuild the design from.
- The style field said "ghibli style" while the global preset appended "Western
  preschool", and the negative prompt contained "anime, manga".

## What changed

1. **Turnaround views use a generated OpenPose skeleton.**
   `pose_service.py` draws an 18-keypoint skeleton for front, three-quarter,
   side or back. The app stores it as a project asset and feeds it to ControlNet.

2. **Identity is combined with pose control.**
   `sdxl_controlnet_ipadapter` runs IP-Adapter (identity) and
   ControlNet OpenPose (view) in one graph. The canonical image keeps the
   character; the skeleton enforces the camera angle.

3. **IP-Adapter weight follows the view.**
   Front 0.8, three-quarter 0.55, side 0.35, back 0.25. The further the view is
   from the canonical, the more the prompt and skeleton must lead.

4. **Style is no longer contradictory.**
   A character's `style` field replaces the global preset instead of stacking on
   top of it. A short colour cue is placed inside the first 77 CLIP tokens, and
   the full art direction follows at the tail.

5. **Negative prompts are style-safe.**
   "anime, manga, semi-realistic illustration" were removed; "monochrome,
   greyscale, line art, sketch" were added.

6. **Turnarounds render at 768×1152.**
   The `sdxl_turnaround` preset keeps combined ControlNet + IP-Adapter inside
   the 6 GB budget.

## How to use it

1. Fill in `appearance` and `clothing` before generating views. This is the
   single biggest consistency lever. Example:

   ```text
   appearance: short dark blue hair in twin pigtails, brown eyes, round face,
               light skin, small build, age 10
   clothing:   white t-shirt with a blue smiley print, blue running shorts,
               white socks, red sneakers
   style:      ghibli-inspired painterly 2D animation
   ```

2. Generate the front view. Approve it and set it as canonical.

3. Generate `side profile`, `three-quarter` and `back view`. Each one runs
   through `sdxl_controlnet_ipadapter`.

4. Review each view. Keep the best; regenerate with a different seed only if the
   view or identity is wrong.

5. Approve the selected views as references. They become the visual bible for
   scenes, cutouts and future shots.

## Measured

| Step | Result |
|---|---|
| Side view, combined graph | 40 s, 768×1152, peak 5723 MB |
| Back view, combined graph | 49 s, 768×1152, peak 5990 MB |
| Tests | 158 passed |

The back view is the tightest job. If another GPU application is running, free
VRAM first (`POST /api/v1/resources/free`) or render at 704×1056.

## Limits

- A single front reference cannot guarantee an exact outfit on the back. Fill
  `clothing` and regenerate; do not expect pixel identity from one image.
- The back skeleton encodes body orientation, not hairstyle. Hair length and
  style on the back view depend on the prompt and the canonical.
- For a series, train a per-character LoRA once the turnaround is approved.
  That locks the face and wardrobe far better than prompt text.
