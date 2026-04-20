import json
import re

# Load the memory map
with open("C:/2026_projects/ghi/memory_address_map.json", "r") as f:
    dat_mapping = json.load(f)

# Manually identified / High value ones
named_vars = {
    # Creature Relative (using Hooked ECX as root)
    "creature": [
        {"name": "POS X", "offsets": [-0x250], "is_pointer": False, "type": "float", "root": "creature"},
        {"name": "POS Y", "offsets": [-0x24c], "is_pointer": False, "type": "float", "root": "creature"},
        {"name": "POS Z", "offsets": [-0x248], "is_pointer": False, "type": "float", "root": "creature"},
        {"name": "Hunger Acc", "offsets": [0x1f4], "is_pointer": False, "type": "float", "root": "creature"},
        {"name": "AI State", "offsets": [0xa4], "is_pointer": False, "type": "int", "root": "creature"},
        {"name": "Anim ID", "offsets": [0x1b0], "is_pointer": False, "type": "int", "root": "creature"},
    ],
    "0x004689fc": [
        {"name": "Mouth Position", "offsets": [0x0c], "is_pointer": False, "type": "int", "root": "static"},
        {"name": "Face Expression", "offsets": [0x10], "is_pointer": False, "type": "int", "root": "static"},
        {"name": "Action Event", "offsets": [0x14], "is_pointer": False, "type": "int", "root": "static"}
    ],
    "0x00468bbc": [{"name": "Desktop Refresh Timer", "offsets": [], "is_pointer": False, "type": "int", "root": "static"}],
    "0x0046906c": [{"name": "Global Frame Counter", "offsets": [], "is_pointer": False, "type": "int", "root": "static"}],
    "0x0046907c": [{"name": "FPS Display Buffer", "offsets": [], "is_pointer": False, "type": "string", "root": "static"}],
    "0x00469070": [{"name": "Mouse Click Time (ms)", "offsets": [], "is_pointer": False, "type": "int", "root": "static"}],
    "0x00469074": [{"name": "Prev Frame Time (ms)", "offsets": [], "is_pointer": False, "type": "hex", "root": "static"}],
    "0x00465098": [{"name": "Swim Speed Constant", "offsets": [], "is_pointer": False, "type": "float", "root": "static"}],
    "0x00468b90": [{"name": "Sound Identity Flag", "offsets": [], "is_pointer": False, "type": "int", "root": "static"}],
    "0x00452680": [{"name": "Animation Phase Inc", "offsets": [], "is_pointer": False, "type": "float", "root": "static"}],
    "0x00452678": [{"name": "Angle Wrap Limit", "offsets": [], "is_pointer": False, "type": "float", "root": "static"}],
    "0x00452664": [{"name": "DeltaTime Factor", "offsets": [], "is_pointer": False, "type": "float", "root": "static"}],
    "0x004526ac": [{"name": "Hunger Rate", "offsets": [], "is_pointer": False, "type": "float", "root": "static"}],
    "0x00468a30": [{"name": "Magic ID (face?)", "offsets": [], "is_pointer": False, "type": "magic", "root": "static"}]
}

final_variables = []

# First, add the named ones
for addr, configs in named_vars.items():
    for cfg in configs:
        final_variables.append({
            "name": cfg['name'],
            "address": addr if addr != "creature" else "0x00000000",
            "offsets": cfg.get('offsets', []),
            "is_pointer": cfg.get('is_pointer', False),
            "type": cfg.get('type', "pointer"),
            "root": cfg.get('root', "static"),
            "description": "Manually Identified"
        })

# Then add all other DAT_ pointers that aren't already named
for addr, info in dat_mapping.items():
    if addr not in named_vars:
        name = f"DAT_{addr[2:]}"
        if info['potential_systems']:
            name += f" ({info['potential_systems'][0]})"
        
        final_variables.append({
            "name": name,
            "address": addr,
            "offsets": [],
            "is_pointer": False,
            "type": "pointer",
            "description": info['functions'][0]['summary_snippet'] if info['functions'] else ""
        })

with open("C:/2026_projects/ghi/gem_var_tracker/scripts/variables.json", "w") as f:
    json.dump({"high_value": final_variables}, f, indent=2)

print(f"Merged config generated with {len(final_variables)} entries.")
