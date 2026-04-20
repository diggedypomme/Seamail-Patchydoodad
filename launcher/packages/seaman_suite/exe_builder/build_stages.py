"""
build_stages.py
Builds the four stage EXEs from the clean original Seaman.exe.
Reads source path from launcher config; writes to the configured SeaMail folder.

Stages:
  Stage1_Baby   (stage byte 1)
  Stage3_Child  (stage byte 3)
  Stage5_Adult  (stage byte 5)
  Stage8_Frog   (stage byte 8)
"""

import json
import shutil
import sys
from pathlib import Path

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_seamail_root  # noqa: E402

SCRIPT_DIR = Path(__file__).parent
PATCH_FILE = SCRIPT_DIR / "patches.json"

# adult patches that carry a stage-number byte, and which byte index to substitute
STAGE_BYTE_INDEX = {
    "adult_grow_creation":          0,
    "adult_scene_transition_reset": 0,
    "adult_struct_init_bypass":     4,
    "adult_db_read_override":       1,
}

STAGES = [
    (1, "Stage1_Baby",  "stage1_baby"),
    (3, "Stage3_Child", "stage3_child"),
    (5, "Stage5_Adult", "stage5_adult"),
    (8, "Stage8_Frog",  "stage8_frog"),
]


def apply_patches(f, patches_def, keys, stage_num=None, label=""):
    for key in keys:
        patch = patches_def.get(key)
        if not patch:
            print(f"  [WARN] Patch key '{key}' not found — skipping")
            continue
        offset = int(patch["offset"], 16)
        b = bytearray(bytes.fromhex(patch["bytes"]))
        if stage_num is not None and key in STAGE_BYTE_INDEX:
            b[STAGE_BYTE_INDEX[key]] = stage_num
        f.seek(offset)
        f.write(b)
        print(f"  [{label}] {patch['name']:45s}  offset={patch['offset']}  bytes={b.hex()}")


def build_exe(stage_num, stage_name, patches_def, presets, exe_source, out_dir):
    target = out_dir / f"Seaman_{stage_name}.exe"
    shutil.copy2(exe_source, target)
    print(f"\nBuilding {target.name} (stage {stage_num})...")
    with open(target, "r+b") as f:
        apply_patches(f, patches_def, presets["required_base"], label="base")
        apply_patches(f, patches_def, presets["stage"], stage_num=stage_num, label="stage")
    print(f"  Done → {target}")


def verify(stage_name, stage_num, patches_def, presets, out_dir):
    target = out_dir / f"Seaman_{stage_name}.exe"
    data = open(target, "rb").read()
    print(f"\nVerifying {target.name} (stage {stage_num})...")
    all_ok = True
    for key in presets["required_base"] + presets["stage"]:
        patch = patches_def.get(key)
        if not patch:
            continue
        offset = int(patch["offset"], 16)
        expected = bytearray(bytes.fromhex(patch["bytes"]))
        if key in STAGE_BYTE_INDEX:
            expected[STAGE_BYTE_INDEX[key]] = stage_num
        n = len(expected)
        actual = data[offset:offset + n]
        ok = actual == bytes(expected)
        if not ok:
            all_ok = False
        print(f"  {'OK' if ok else 'FAIL':4s}  {patch['name']:45s}  got={actual.hex()}  want={expected.hex()}")
    return all_ok


def main():
    out_dir = resolve_seamail_root()
    exe_source = out_dir / "Seaman.exe"

    print(f"Source EXE : {exe_source}")
    print(f"Output dir : {out_dir}")

    if not exe_source.exists():
        print(f"\nError: Seaman.exe not found in SeaMail folder: {exe_source}")
        print("Place the original unpatched Seaman.exe in the SeaMail folder first.")
        sys.exit(1)

    if not out_dir.exists():
        print(f"\nError: SeaMail folder not found: {out_dir}")
        print("Set the SeaMail folder path in Settings first.")
        sys.exit(1)

    with open(PATCH_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    patches_def = config["patches"]
    presets = config["presets"]

    for stage_num, stage_name, preset_key in STAGES:
        build_exe(stage_num, stage_name, patches_def, {
            "required_base": presets["required_base"],
            "stage":         presets[preset_key],
        }, exe_source, out_dir)

    print("\n--- Verification ---")
    all_passed = True
    for stage_num, stage_name, preset_key in STAGES:
        ok = verify(stage_name, stage_num, patches_def, {
            "required_base": presets["required_base"],
            "stage":         presets[preset_key],
        }, out_dir)
        if not ok:
            all_passed = False

    print(f"\n{'All EXEs verified OK.' if all_passed else 'Some verifications FAILED — check output above.'}")


if __name__ == "__main__":
    main()
