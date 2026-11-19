"""Pilot Test 01 — "Bramble and the Last Lantern".

A ~6 minute original short, produced entirely through the Cartoon Studio API.

Stages (run in order):
    python scripts/pilot_test_01.py setup
    python scripts/pilot_test_01.py art
    python scripts/pilot_test_01.py backgrounds
    python scripts/pilot_test_01.py keyframes
    python scripts/pilot_test_01.py voices
    python scripts/pilot_test_01.py music
    python scripts/pilot_test_01.py timeline
    python scripts/pilot_test_01.py export
    python scripts/pilot_test_01.py status
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"
PROJECT_NAME = "Pilot Test 01"
EPISODE_NAME = "Bramble and the Last Lantern"

KEYFRAME_EXTRA = (
    "wide cinematic storybook scene, the location clearly visible, character inside the environment, "
    "head and feet fully in frame, not a character sheet"
)
KEYFRAME_NEGATIVE = (
    "character sheet, reference sheet, multiple views, plain background, studio backdrop, "
    "cropped head, cropped body, duplicate character, text, watermark, extra limbs, deformed"
)

# --------------------------------------------------------------------------- cast

CHARACTERS = [
    {
        "key": "bramble",
        "name": "Bramble",
        "description": (
            "Bramble is a small girl, eight years old, brave in her head and nervous in her tummy. "
            "She talks to herself when she is scared and narrates her own courage. She is kind before she is brave."
        ),
        "style": "rounded preschool cartoon shapes, warm russet palette",
        "clothing": "mustard-yellow knitted scarf, olive canvas satchel with a candle stub, small brown boots",
        "appearance": (
            "small girl with curly ash-grey hair, round dark eyes, freckles, cream shirt, "
            "two tiny hedgehogs that follow her everywhere"
        ),
        "voice": {"engine": "kokoro", "voice": "af_sky", "rate": 1, "pitch": 32, "volume": 100},
        "seed": 4101,
    },
    {
        "key": "tock",
        "name": "Tock",
        "description": (
            "Tock is a palm-sized clockwork mouse who counts everything: steps, raindrops, scary moments. "
            "He is anxious, precise and fiercely loyal, and winds himself up when he is nervous."
        ),
        "style": "brass and rivets, tiny mechanical details",
        "clothing": "a bottle-cap hat and a tiny brass key in his back",
        "appearance": "brass clockwork mouse, riveted seams, one droopy ear, glowing amber eyes, small wheel feet",
        "voice": {"engine": "kokoro", "voice": "am_puck", "rate": 2, "pitch": 38, "volume": 100},
        "seed": 4102,
    },
    {
        "key": "moss",
        "name": "Grandmother Moss",
        "description": (
            "Grandmother Moss is an ancient tortoise who speaks in short proverbs and moves like the weather. "
            "She is warm, unhurried and knows more than she says."
        ),
        "style": "storybook elder, mossy textures, soft green palette",
        "clothing": "twig spectacles and a shawl of soft green moss",
        "appearance": "enormous ancient tortoise, moss-covered shell with tiny mushrooms, wrinkled kind face, gentle eyes",
        "voice": {"engine": "kokoro", "voice": "bf_emma", "rate": -3, "pitch": -6, "volume": 100},
        "seed": 4103,
    },
    {
        "key": "grumble",
        "name": "The Grumble",
        "description": (
            "The Grumble is a small storm cloud, grumpy and lonely. It stopped the wind so nobody could leave it. "
            "It speaks in low rumbles and rains a little when embarrassed."
        ),
        "style": "soft rounded storm cloud, violet-grey palette, gentle lightning",
        "clothing": "",
        "appearance": "fist-sized grey-violet storm cloud, soft rounded edges, tiny lightning freckles, droopy rain, two sleepy eyes",
        "voice": {"engine": "kokoro", "voice": "am_onyx", "rate": -2, "pitch": -20, "volume": 85},
        "seed": 4104,
    },
]

# --------------------------------------------------------------------- locations

BACKGROUNDS = [
    {
        "key": "village",
        "name": "Bellhollow Village at Dusk",
        "description": (
            "crooked cottages with tiny bells on every roof, warm glowing windows, lavender and peach sunset sky, "
            "a windmill silhouette on the hill, quiet cobblestone lane"
        ),
    },
    {
        "key": "meadow",
        "name": "The Firefly Meadow",
        "description": (
            "tall silver grass, drifting fireflies, a low dry-stone wall, wildflowers, huge rising moon, "
            "cool blue evening light"
        ),
    },
    {
        "key": "bridge",
        "name": "The Rope Bridge",
        "description": (
            "swaying rope bridge with wooden planks over a dry creek bed, mist between ferns, grey-blue twilight, "
            "distant hills"
        ),
    },
    {
        "key": "wood",
        "name": "The Whispering Wood",
        "description": (
            "dark blue pine forest, winding dirt path, clusters of glowing teal mushrooms, soft fog, "
            "moonbeams through branches"
        ),
    },
    {
        "key": "mill",
        "name": "The Old Windmill Top",
        "description": (
            "wooden platform at the top of an old windmill, huge still canvas sails, wooden gears, open night sky, "
            "full moon, tiny village lights far below"
        ),
    },
]

# ------------------------------------------------------------------------- shots
# dialogue: (character_key, text, emotion)

SHOTS = [
    # Act 1 — Bellhollow
    dict(id="s01", bg="village", cast=[], name="Bellhollow at dusk", duration=8, motion="pan_right",
         description="A crooked little village on a hillside at sunset, every roof carrying a tiny brass bell.",
         action="Bells sway gently in a warm evening breeze.", camera="wide establishing shot"),
    dict(id="s02", bg="village", cast=[], name="Bells above the rooftops", duration=5, motion="zoom_in",
         description="A single brass bell above a blue cottage door, polished and glowing in sunset light.",
         action="The bell swings and catches the last of the sun.", camera="close-up"),
    dict(id="s03", bg="village", cast=["bramble"], name="Bramble at her window", duration=10, motion="zoom_in",
         description="A small girl with curly ash-grey hair leans on her windowsill, chin in her hands, watching the windy grass. Two tiny hedgehogs sit beside her.",
         action="Bramble sighs and her scarf lifts in the breeze.", camera="medium close-up, warm window light",
         dialogue=[("bramble", "Every bell in Bellhollow has a job. Mine just... hasn't started yet.", "sad")]),
    dict(id="s04", bg="village", cast=[], name="The wind stops", duration=7, motion="none",
         description="The village lane, perfectly still. Grass frozen mid-bend, a leaf hanging in the air.",
         action="Everything stops. A single leaf drifts straight down.", camera="static wide shot"),
    dict(id="s05", bg="village", cast=["bramble", "moss"], name="The empty square", duration=11, motion="pan_left",
         description="Neighbours gather in the square looking up at silent bells. A huge mossy tortoise stands among them.",
         action="Bramble looks up at the quiet roofs; Grandmother Moss rests a paw on her shoulder.",
         camera="wide group shot",
         dialogue=[("moss", "The wind has gone to bed, little one. And it took the bells' voices with it.", "calm")]),
    dict(id="s06", bg="village", cast=["bramble"], name="Bramble and the dark corner", duration=9, motion="zoom_in",
         description="A cozy kitchen with one lantern on the table and a deep dark corner beside the stove.",
         action="Bramble stares at the dark corner and hugs her scarf.", camera="medium shot, lantern light",
         dialogue=[("bramble", "I'm not scared of the dark. I'm just... not friends with it yet.", "scared")]),
    dict(id="s07", bg="village", cast=["bramble", "moss"], name="The last lantern", duration=11, motion="none",
         description="Grandmother Moss holds out a small brass lantern to Bramble at the cottage door.",
         action="Moss presses the lantern into Bramble's paws and closes them around the handle.",
         camera="two-shot, warm doorway light",
         dialogue=[("moss", "Then go make friends. The mill needs a light, and the wind needs a reason.", "calm")]),
    dict(id="s08", bg="village", cast=["bramble"], name="The door closes", duration=9, motion="pan_right",
         description="Bramble steps into the lane with the lantern, the cottage door closing softly behind her.",
         action="She squares her shoulders and starts walking toward the hill.", camera="wide shot from behind",
         dialogue=[("bramble", "One hill. One lantern. One very brave hedgehog. Probably.", "excited")]),

    # Act 2 — Meadow
    dict(id="s09", bg="meadow", cast=[], name="The firefly meadow", duration=8, motion="pan_left",
         description="A wide moonlit meadow full of drifting fireflies and silver grass.",
         action="Fireflies rise slowly like tiny lanterns.", camera="wide establishing shot"),
    dict(id="s10", bg="meadow", cast=["bramble"], name="Bramble crosses the meadow", duration=10, motion="none",
         description="Bramble walks through tall grass with her lantern held high, fireflies gathering around it.",
         action="She lifts the lantern and the fireflies swirl closer.", camera="medium tracking shot",
         dialogue=[("bramble", "Okay, dark. You're very big. But I brought a light, so.", "neutral")]),
    dict(id="s11", bg="meadow", cast=["bramble"], name="Something in the grass", duration=7, motion="zoom_in",
         description="Bramble freezes, lantern trembling, as the grass beside her rustles.",
         action="Her eyes go wide and she holds her breath.", camera="close-up on Bramble"),
    dict(id="s12", bg="meadow", cast=["bramble", "tock"], name="Tock tumbles out", duration=11, motion="none",
         description="A tiny brass clockwork mouse tumbles out of the grass and lands at Bramble's boots.",
         action="Tock scrambles upright, dusts his bottle-cap hat and counts on his wheel feet.",
         camera="low angle two-shot",
         dialogue=[("tock", "Ninety-nine steps. Ninety-nine! I lost one, and now I'm late, and the moon is— oh. Hello.", "surprised")]),
    dict(id="s13", bg="meadow", cast=["bramble", "tock"], name="Two travellers", duration=10, motion="none",
         description="Bramble kneels down to Tock's height, lantern between them, fireflies overhead.",
         action="They introduce themselves; Tock offers a tiny brass paw.", camera="medium two-shot",
         dialogue=[("bramble", "I'm Bramble. I'm carrying the last light up the hill.", "neutral"),
                   ("tock", "Tock. I count things. I can count your steps. I'm very good at it.", "happy")]),
    dict(id="s14", bg="meadow", cast=["tock"], name="Tock winds his key", duration=6, motion="zoom_in",
         description="Close-up of Tock winding the little brass key in his back, eyes bright.",
         action="He winds it three times and ticks with satisfaction.", camera="macro close-up"),
    dict(id="s15", bg="meadow", cast=["bramble", "tock"], name="Into the long grass", duration=9, motion="pan_right",
         description="Bramble and Tock walk on together, a girl and a small mouse, fireflies parting ahead.",
         action="Tock counts under his breath as they go.", camera="wide tracking shot",
         dialogue=[("tock", "Ninety-eight... ninety-seven... you walk very loudly.", "neutral")]),

    # Act 2 — Bridge
    dict(id="s16", bg="bridge", cast=[], name="The rope bridge", duration=7, motion="pan_right",
         description="A swaying rope bridge over a dry creek bed, planks worn smooth, mist curling below.",
         action="The bridge creaks gently in the still air.", camera="wide establishing shot"),
    dict(id="s17", bg="bridge", cast=["bramble", "tock"], name="Over the dry creek", duration=10, motion="none",
         description="Bramble steps onto the bridge; Tock clings to her scarf and peers down.",
         action="The planks shift under them and Tock squeezes his eyes shut.", camera="medium two-shot",
         dialogue=[("tock", "I don't like heights. I like counting them from the ground.", "scared")]),
    dict(id="s18", bg="bridge", cast=["bramble"], name="The creaking plank", duration=8, motion="zoom_out",
         description="A worn plank bends under Bramble's boot; the lantern swings and throws long shadows.",
         action="She steadies the lantern with both paws and keeps walking.", camera="low angle, dramatic lantern light",
         dialogue=[("bramble", "Don't look down. Look at the light. The light is on our side.", "calm")]),
    dict(id="s19", bg="bridge", cast=["bramble", "tock"], name="Across the bridge", duration=8, motion="none",
         description="Safe on the far bank, Tock exhales and pats his own chest.",
         action="Bramble sets him down and he counts on his wheels.", camera="medium two-shot",
         dialogue=[("tock", "Ninety-six. I counted the scary bits. There were forty.", "happy")]),
    dict(id="s20", bg="bridge", cast=[], name="The mist closes in", duration=6, motion="pan_left",
         description="The bridge disappears into mist behind them; the far path narrows into dark trees.",
         action="Mist rolls across the empty planks.", camera="wide shot from the far bank"),

    # Act 2 — Wood
    dict(id="s21", bg="wood", cast=[], name="The whispering wood", duration=8, motion="zoom_in",
         description="A dark blue pine wood with a winding path and clusters of glowing teal mushrooms.",
         action="Mushroom light pulses softly, like breathing.", camera="wide establishing shot"),
    dict(id="s22", bg="wood", cast=["bramble", "tock"], name="Small in the dark", duration=10, motion="none",
         description="Bramble and Tock look tiny on the path, lantern a small warm dot in the blue dark.",
         action="Bramble holds the lantern higher and the shadows lean away.", camera="wide shot, characters small",
         dialogue=[("bramble", "Grandmother Moss says the wood only whispers if you listen too hard.", "neutral")]),
    dict(id="s23", bg="wood", cast=[], name="The mushrooms go out", duration=7, motion="pan_left",
         description="A row of glowing mushrooms dims one by one as something passes.",
         action="The teal lights fade into darkness.", camera="slow pan along the path"),
    dict(id="s24", bg="wood", cast=["bramble", "tock", "grumble"], name="The Grumble appears", duration=10, motion="none",
         description="A small grey-violet storm cloud drifts out between the trees, raining slightly.",
         action="The cloud swells, trying to look frightening, and rumbles.", camera="low angle, cloud looming",
         dialogue=[("grumble", "Go away. This is my dark. I was here first.", "angry")]),
    dict(id="s25", bg="wood", cast=["bramble", "tock", "grumble"], name="Bramble lifts the lantern", duration=11, motion="none",
         description="Bramble steps forward and raises the lantern toward the little storm cloud.",
         action="Tock hides behind her scarf; Bramble's hand shakes but she does not step back.",
         camera="medium shot, lantern glow on the cloud",
         dialogue=[("bramble", "You're not very scary. You're just... grumpy.", "surprised")]),
    dict(id="s26", bg="wood", cast=["grumble"], name="The Grumble rains on itself", duration=9, motion="zoom_in",
         description="Close on the little cloud, drooping, a tiny private rain shower falling from it.",
         action="It sighs and a small lightning freckle fizzles out.", camera="close-up",
         dialogue=[("grumble", "Everyone runs from me. Even the wind. So I stopped it. Now nobody leaves.", "sad")]),
    dict(id="s27", bg="wood", cast=["bramble", "grumble"], name="Bramble sits down", duration=11, motion="none",
         description="Bramble sits on a tree root beside the hovering cloud, lantern between them.",
         action="She pats the root and the cloud settles down next to her.", camera="medium two-shot, warm and cool light",
         dialogue=[("bramble", "I was scared of the dark too. Then I brought a light. The dark turned out to be mostly empty... and a little bit lonely.", "calm")]),
    dict(id="s28", bg="wood", cast=["bramble", "tock", "grumble"], name="A small kindness", duration=9, motion="none",
         description="Tock peeks out, counts on his wheels, and offers the cloud a tiny brass paw.",
         action="The cloud hesitates, then rains one polite drop.", camera="medium group shot",
         dialogue=[("tock", "I counted your grumbles. There were three. That's not very scary at all.", "happy")]),

    # Act 3 — Windmill
    dict(id="s29", bg="mill", cast=[], name="The old windmill", duration=8, motion="pan_right",
         description="The windmill on the hilltop, its great sails perfectly still against the moon.",
         action="Not a breath of wind moves the canvas.", camera="wide low angle"),
    dict(id="s30", bg="mill", cast=["bramble", "tock"], name="The last steps", duration=8, motion="none",
         description="At the top of the wooden stairs, Bramble and Tock catch their breath.",
         action="Tock taps each step as he climbs and counts aloud.", camera="medium two-shot",
         dialogue=[("tock", "Three steps. Three! That's a very good number.", "excited")]),
    dict(id="s31", bg="mill", cast=["bramble"], name="The top of the hill", duration=9, motion="zoom_in",
         description="Bramble stands at the windmill platform rail, the sleeping village tiny and dark below.",
         action="She leans on the rail and listens to the silence.", camera="wide shot from behind, moonlit",
         dialogue=[("bramble", "It's so quiet you can hear everyone sleeping.", "calm")]),
    dict(id="s32", bg="mill", cast=["bramble"], name="Too small a lantern", duration=8, motion="none",
         description="Bramble holds her little lantern up against the great iron lamp hook, which is twice her size.",
         action="She stretches, then droops, then thinks.", camera="medium shot, scale contrast",
         dialogue=[("bramble", "The lamp hook is bigger than my whole lantern.", "sad")]),
    dict(id="s33", bg="mill", cast=["bramble", "grumble"], name="The Grumble drifts up", duration=10, motion="none",
         description="The little storm cloud floats up over the rail and hovers beside Bramble, shy.",
         action="It clears its throat with a tiny roll of thunder.", camera="two-shot, moon behind",
         dialogue=[("grumble", "I could... blow. A little. If you wanted.", "neutral")]),
    dict(id="s34", bg="mill", cast=["bramble", "grumble"], name="The wind returns", duration=12, motion="zoom_out",
         description="Bramble lifts the lantern and the cloud breathes out; the great sails begin to turn.",
         action="Wind ripples across the platform, lifting her scarf and scattering dust and fireflies.",
         camera="wide shot, sails moving",
         dialogue=[("bramble", "You don't have to be a storm. You can just be the wind's friend.", "happy")]),
    dict(id="s35", bg="mill", cast=[], name="The sails turn", duration=8, motion="pan_left",
         description="The huge canvas sails sweep across the moon, gears turning, dust glittering in the light.",
         action="The mill wakes up, creaking and turning.", camera="low angle on the sails"),
    dict(id="s36", bg="mill", cast=[], name="Light spills over the village", duration=8, motion="zoom_out",
         description="Warm lantern light floods out from the windmill and spills down the hill toward the village.",
         action="The beam sweeps over rooftops and the first bell trembles.", camera="high wide shot"),

    # Act 4 — Return
    dict(id="s37", bg="village", cast=[], name="The bells ring again", duration=9, motion="pan_right",
         description="Bellhollow at night, windows lighting up one by one as every bell begins to ring.",
         action="Bells swing, warm light spreads, curtains fly open.", camera="wide establishing shot"),
    dict(id="s38", bg="village", cast=["bramble", "tock", "grumble"], name="Walking home", duration=10, motion="none",
         description="Bramble walks down the lane with Tock on her shoulder and the little cloud drifting above.",
         action="The cloud blows a gentle breeze that turns the village weather-vane.", camera="wide tracking shot",
         dialogue=[("tock", "Ninety-nine steps home. I found the one I lost.", "happy")]),
    dict(id="s39", bg="village", cast=["bramble", "moss", "grumble"], name="Grandmother Moss at the door", duration=10, motion="none",
         description="Grandmother Moss waits in her doorway, spectacles catching the lantern light.",
         action="She looks at the cloud, then at Bramble, and smiles slowly.", camera="medium three-shot",
         dialogue=[("moss", "You brought back more than the wind, little one.", "calm")]),
    dict(id="s40", bg="village", cast=["bramble"], name="Goodnight, dark", duration=9, motion="zoom_in",
         description="Bramble's window at night, the lantern on the sill, the dark corner now soft and familiar.",
         action="She yawns, pats the lantern, and the little cloud settles above her roof.", camera="medium shot, cozy",
         dialogue=[("bramble", "Goodnight, dark. See you tomorrow.", "happy")]),
    dict(id="s41", bg="village", cast=[], name="Bellhollow sleeps", duration=7, motion="pan_left",
         description="The village under a wide starry sky, bells at rest after a long night.",
         action="One last breeze moves the grass, then stillness.", camera="wide final shot"),
]


# ----------------------------------------------------------------------- helpers

def state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=180)


def wait_job(c: httpx.Client, job_id: str, timeout: float = 1200) -> dict:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        job = c.get(f"/api/jobs/{job_id}").json()
        if job.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(3)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def newest_asset(c: httpx.Client, path: str) -> str:
    items = c.get(path).json()
    if not items:
        raise RuntimeError(f"No media at {path}")
    return items[-1]["id"]


# ------------------------------------------------------------------------ stages

def stage_setup(c: httpx.Client) -> None:
    data = state()
    project_id = data.get("project_id")
    if project_id:
        projects = c.get("/api/projects").json()
        if any(p["id"] == project_id for p in projects):
            print(f"project exists: {project_id}")
        else:
            project_id = None
    if not project_id:
        project = c.post("/api/projects", json={
            "name": PROJECT_NAME,
            "description": (
                "Pilot Test 01 — 'Bramble and the Last Lantern'. A six-minute original preschool short about a "
                "girl who is afraid of the dark, a lonely grump, and the night the wind forgot to blow."
            ),
        }).json()
        project_id = project["id"]
        data["project_id"] = project_id
        print(f"project: {project_id}")

    chars = data.setdefault("characters", {})
    for spec in CHARACTERS:
        if spec["key"] in chars:
            continue
        payload = {
            "project_id": project_id,
            "name": spec["name"],
            "description": spec["description"],
            "style": spec["style"],
            "clothing": spec["clothing"],
            "appearance": spec["appearance"],
        }
        char = c.post("/api/characters", json=payload).json()
        chars[spec["key"]] = char["id"]
        print(f"character: {spec['key']} -> {char['id']}")

    bgs = data.setdefault("backgrounds", {})
    for spec in BACKGROUNDS:
        if spec["key"] in bgs:
            continue
        bg = c.post("/api/backgrounds", json={
            "project_id": project_id,
            "name": spec["name"],
            "description": spec["description"],
            "aspect_ratio": "16:9",
            "width": 1024,
            "height": 576,
        }).json()
        bgs[spec["key"]] = bg["id"]
        print(f"background: {spec['key']} -> {bg['id']}")

    episode_id = data.get("episode_id")
    if not episode_id:
        episode = c.post("/api/episodes", json={
            "project_id": project_id,
            "name": EPISODE_NAME,
            "description": "A girl, a mouse and a lonely grump bring the wind home.",
        }).json()
        episode_id = episode["id"]
        data["episode_id"] = episode_id
        print(f"episode: {episode_id}")

    scenes = data.setdefault("scenes", {})
    for shot in SHOTS:
        if shot["id"] in scenes:
            continue
        cast_ids = [chars[key] for key in shot["cast"]]
        settings = {
            "width": 1024,
            "height": 576,
            "steps": 24,
            "cfg": 6.0,
            "seed": 7000 + int(shot["id"][1:]),
            "reference_mode": "identity",
        }
        scene = c.post("/api/scenes", json={
            "project_id": project_id,
            "name": shot["name"],
            "description": shot["description"],
            "action": shot["action"],
            "camera": shot["camera"],
            "duration": shot["duration"],
            "background_id": bgs[shot["bg"]],
            "character_ids": cast_ids,
            "settings": settings,
        }).json()
        scenes[shot["id"]] = scene["id"]
        print(f"scene: {shot['id']} {shot['name']} -> {scene['id']}")

    save_state(data)
    print("setup complete")


def stage_art(c: httpx.Client) -> None:
    data = state()
    project_id = data["project_id"]
    art = data.setdefault("art", {})
    for spec in CHARACTERS:
        key = spec["key"]
        char_id = data["characters"][key]
        if key in art:
            print(f"{key}: done")
            continue
        char = c.get(f"/api/characters/{char_id}").json()
        if not char.get("canonical_asset_id"):
            result = c.post(f"/api/characters/{char_id}/generate", json={
                "kind": "reference",
                "label": "front",
                "width": 768,
                "height": 1152,
                "steps": 24,
                "cfg": 6.0,
                "seed": spec["seed"],
                "use_reference": False,
            }).json()
            job = wait_job(c, result["job"]["id"])
            if job["status"] != "completed":
                raise RuntimeError(f"{key} art failed: {job.get('error')}")
            asset_id = job["outputs"][0]["asset_id"]
            c.post(f"/api/characters/{char_id}/canonical", json={"asset_id": asset_id})
            print(f"{key}: canonical {asset_id}")
        char = c.get(f"/api/characters/{char_id}").json()
        c.patch(f"/api/characters/{char_id}/voice", json=spec["voice"])
        art[key] = {"canonical": char.get("canonical_asset_id")}
        save_state(data)
    print("art complete")


def stage_backgrounds(c: httpx.Client) -> None:
    data = state()
    made = data.setdefault("background_assets", {})
    for spec in BACKGROUNDS:
        key = spec["key"]
        bg_id = data["backgrounds"][key]
        if key in made:
            print(f"{key}: done")
            continue
        result = c.post(f"/api/backgrounds/{bg_id}/generate", json={
            "width": 1024,
            "height": 576,
            "seed": 5000 + len(made),
        }).json()
        job = wait_job(c, result["job"]["id"])
        if job["status"] != "completed":
            raise RuntimeError(f"{key} background failed: {job.get('error')}")
        made[key] = job["outputs"][0]["asset_id"]
        save_state(data)
        print(f"{key}: {made[key]}")
    print("backgrounds complete")


def stage_keyframes(c: httpx.Client) -> None:
    data = state()
    frames = data.setdefault("keyframes", {})
    project_id = data["project_id"]
    for shot in SHOTS:
        sid = shot["id"]
        if sid in frames:
            print(f"{sid}: done")
            continue
        scene_id = data["scenes"][sid]
        c.patch(f"/api/scenes/{scene_id}", json={"settings": {
            "width": 1024, "height": 576, "steps": 24, "cfg": 6.0,
            "seed": 7000 + int(sid[1:]),
            "reference_asset_id": "",
        }})
        result = c.post(f"/api/scenes/{scene_id}/generate", json={
            "kind": "keyframe",
            "prompt": KEYFRAME_EXTRA,
            "negative_prompt": KEYFRAME_NEGATIVE,
        }).json()
        job = wait_job(c, result["job"]["id"])
        if job["status"] != "completed":
            raise RuntimeError(f"{sid} keyframe failed: {job.get('error')}")
        frames[sid] = job["outputs"][0]["asset_id"]
        save_state(data)
        print(f"{sid}: {frames[sid]} ({result.get('mode')})")
    print("keyframes complete")


def stage_voices(c: httpx.Client) -> None:
    data = state()
    lines = data.setdefault("dialogue", {})
    for shot in SHOTS:
        sid = shot["id"]
        scene_id = data["scenes"][sid]
        existing = {line["id"] for line in c.get(f"/api/scenes/{scene_id}/dialogue").json()}
        for index, (who, text, emotion) in enumerate(shot.get("dialogue") or []):
            key = f"{sid}_{index}"
            if key in lines:
                continue
            line = c.post(f"/api/scenes/{scene_id}/dialogue", json={
                "character_id": data["characters"][who],
                "text": text,
                "emotion": emotion,
            }).json()
            generated = c.post(f"/api/dialogue/{line['id']}/generate").json()
            lines[key] = {
                "line_id": line["id"],
                "scene_id": scene_id,
                "character": who,
                "text": text,
                "audio_asset_id": generated.get("audio_asset_id"),
                "duration_ms": generated.get("duration_ms") or 0,
            }
            save_state(data)
            print(f"{key}: {lines[key]['duration_ms']} ms")
    print("voices complete")


def stage_music(c: httpx.Client) -> None:
    data = state()
    if data.get("music_asset_id"):
        print(f"music: {data['music_asset_id']}")
        return
    backend = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))
    from app.services import audio_service  # noqa: PLC0415

    result = asyncio.run(audio_service.generate_music(data["project_id"], duration=150.0))
    data["music_asset_id"] = result["asset_id"]
    save_state(data)
    print(f"music: {result['asset_id']}")


def stage_timeline(c: httpx.Client) -> None:
    data = state()
    segments = []
    audio = []
    cursor = 0
    act_starts = {"s01", "s09", "s16", "s21", "s29", "s37"}
    for shot in SHOTS:
        sid = shot["id"]
        asset_id = data["keyframes"][sid]
        duration_ms = int(shot["duration"] * 1000)
        segments.append({
            "scene_id": data["scenes"][sid],
            "asset_id": asset_id,
            "kind": "image",
            "duration_ms": duration_ms,
            "transition": "fade" if sid in act_starts else "cut",
            "motion": shot["motion"],
            "label": shot["name"],
        })
        offset = 700
        for index in range(len(shot.get("dialogue") or [])):
            entry = data["dialogue"].get(f"{sid}_{index}")
            if not entry or not entry.get("audio_asset_id"):
                continue
            audio.append({
                "asset_id": entry["audio_asset_id"],
                "start_ms": cursor + offset,
                "volume": 1.0,
                "loop": False,
                "label": f"{sid} line {index + 1}",
                "kind": "dialogue",
            })
            offset += int(entry["duration_ms"]) + 350
        cursor += duration_ms
    timeline = {
        "segments": segments,
        "audio": audio,
        "settings": {
            "width": 1280,
            "height": 720,
            "fps": 24,
            "subtitles": "soft",
            "background_music_asset_id": data.get("music_asset_id"),
            "background_music_volume": 0.30,
            "fade_duration_ms": 420,
        },
    }
    result = c.put(f"/api/episodes/{data['episode_id']}/timeline", json=timeline).json()
    print(f"timeline: {len(segments)} segments, {len(audio)} audio cues, {cursor/1000:.1f}s")
    return result


def stage_export(c: httpx.Client) -> None:
    data = state()
    episode_id = data["episode_id"]
    c.post(f"/api/episodes/{episode_id}/export")
    started = time.monotonic()
    while time.monotonic() - started < 3600:
        episode = c.get(f"/api/episodes/{episode_id}").json()
        status = episode.get("status")
        print(f"export: {status} {round(float(episode.get('progress') or 0), 1)}%")
        if status in {"completed", "failed", "cancelled"}:
            print(json.dumps({k: episode.get(k) for k in ("status", "output_url", "output_path", "error")}, indent=1))
            return
        time.sleep(8)
    raise TimeoutError("export did not finish")


def stage_status(c: httpx.Client) -> None:
    data = state()
    if not data.get("project_id"):
        print("no project yet")
        return
    project_id = data["project_id"]
    counts = {
        "characters": len(c.get(f"/api/characters?project_id={project_id}").json()),
        "backgrounds": len(c.get(f"/api/backgrounds?project_id={project_id}").json()),
        "scenes": len(c.get(f"/api/scenes?project_id={project_id}").json()),
        "keyframes": len(data.get("keyframes") or {}),
        "dialogue": len(data.get("dialogue") or {}),
        "music": bool(data.get("music_asset_id")),
    }
    print(json.dumps(counts, indent=1))
    jobs = c.get("/api/jobs?limit=8").json()
    for job in jobs[:8]:
        print(f"  {job['id']} {job['status']:10s} {job['workflow_id']}")


STAGES = {
    "setup": stage_setup,
    "art": stage_art,
    "backgrounds": stage_backgrounds,
    "keyframes": stage_keyframes,
    "voices": stage_voices,
    "music": stage_music,
    "timeline": stage_timeline,
    "export": stage_export,
    "status": stage_status,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        print("usage: pilot_test_01.py " + "|".join(STAGES))
        raise SystemExit(2)
    stage = sys.argv[1]
    with client() as c:
        STAGES[stage](c)


if __name__ == "__main__":
    main()
