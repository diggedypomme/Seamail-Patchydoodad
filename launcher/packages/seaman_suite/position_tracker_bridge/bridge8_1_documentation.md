# Bridge v8.1 Documentation

**Seaman Master Dashboard** - Real-time visualization and monitoring tool for Seaman game memory.

## Overview

Bridge v8.1 receives UDP packets (736 bytes) from the XP tracker and provides:
- Real-time 3D position preview (side view)
- Semantic field labels for known values
- Raw memory exploration with multiple format views
- Color-coded change tracking

## Architecture

### Data Flow
```
Seaman.exe (XP)
  → xp_debug_tracker_v8.1.exe (memory reader)
  → UDP packet (192.168.0.6:8888)
  → bridge8_1.py (visualization)
```

### Packet Structure (736 bytes)
- **Bytes 0-399:** param_4 (100 floats) - Position, velocity, angles, etc.
- **Bytes 400-735:** Instance (84 DWORDs) - State machine, animation, targets

## View Modes

### 1. Position & Movement (Default)
Shows spatial and motion data with 3D preview:
- **Location:** X, Y, Z world position
- **Movement:** Velocity X/Y/Z, Pitch, Yaw

### 2. State & Animation
Shows behavioral state machine:
- **State Machine:** Current state, sub-state
- **Animation:** Anim ID, counter
- **Destination:** Target X/Y/Z (decoded from DWORDs)

### 3. All Fields
Combined view of both position and state data.

### 4. Raw param_4
Grid display of all 100 param_4 floats with:
- 4 columns × 25 rows
- Semantic names for known fields
- Color coding: Green=increasing, Red=decreasing
- **Format toggles:**
  - **Float** (default): Just float value `123.45`
  - **Float+Hex**: Float + hex bits `123.45 (0x42f6e666)`
  - **Float+Int**: Float + integer cast `123.45 = 123`
  - **Hex**: As hex 32-bit `0x42f6e666`
  - **Int**: As 32-bit integer `1123418726`

### 5. Raw Instance
Grid display of all 84 instance DWORDs with:
- 3 columns × 28 rows
- Memory offsets shown `[0xa4]` to `[0x1f0]`
- Semantic names for known fields
- Color coding: Yellow=changed
- **Format toggles:**
  - **Auto** (default): Decode known floats only
  - **All Float**: Decode all fields as floats
  - **Int+Float**: Show both int and float, no hex
  - **Int+Hex**: Integer + hex, no float decode

## 3D Preview Visualization

### View Type: Side View (X/Y plane)
- **X axis:** Horizontal (left/right)
- **Y axis:** Vertical (up/down)
- **Z axis:** Not displayed (used for depth scaling only)

### Visual Elements

#### Tank Boundary (Gray Rectangle)
- **Default range:** 150×100 units
- X: -75 to +75 units
- Y: -50 to +50 units
- Configurable via `tank_x_range` and `tank_y_range` (lines 482-483)

#### Seaman Body (Cyan Circle)
- **Radius:** 15 units × depth_scale
- Outline: `#00ffff` (cyan/blue)
- Configurable via `br = 15 * depth_scale` (line 535)

#### Face Indicator (Magenta Circle)
- **Radius:** 6 units × depth_scale
- Fill: `#ff00ff` (magenta)
- Position: Offset from body center based on body + head rotation

#### Velocity Vector (Red Arrow)
- Shows movement direction and speed
- Color: `#ff0000` (red)
- Length: Proportional to velocity magnitude

#### Gaze Direction (Green Arrow)
- Shows combined body orientation + head rotation
- Color: `#00ff00` (green)
- Calculation: `body_angle - yaw_rad` (horizontal), `body_angle + pitch_rad` (vertical)

#### Destination Target (Yellow Dashed Circle)
- Shows target position from instance fields 15/16/17
- Color: `#ffff00` (yellow)

### Rotation Handling

**Body Orientation:**
- Calculated from velocity vector: `atan2(-vel_y, vel_x)`
- Fish rotates to face direction of movement

**Head Rotation:**
- **Yaw (horizontal):** `body_angle - yaw_rad` (negated to fix inversion)
- **Pitch (vertical):** `body_angle + pitch_rad` (NOT negated)
- Face circle positioned based on combined rotation
- Gaze arrow extends from face position

**Why different signs?**
- Yaw was inverted in game data (left/right flipped)
- Pitch is correct in game data
- Fixed empirically by testing rotation directions

### Depth Scaling
```python
depth_scale = max(0.2, 1.0 - pos_z/400)
```
- Fish appears smaller when deeper (higher Z value)
- Minimum scale: 0.2 (never smaller than 20%)
- Maximum scale: 1.0 (at Z=0)

## Known Field Mappings

### param_4 Fields (Floats)
| Index | Name | Description |
|-------|------|-------------|
| 0 | Location X | World X position |
| 1 | Location Y | World Y position |
| 2 | Location Z | World Z position (depth) |
| 6 | Velocity X | X-axis movement speed |
| 7 | Velocity Y | Y-axis movement speed |
| 8 | Velocity Z | Z-axis movement speed |
| 26 | Pitch | Head pitch angle (degrees) |
| 27 | Yaw | Head yaw angle (degrees) |

### Instance Fields (DWORDs)
| Index | Offset | Name | Type |
|-------|--------|------|------|
| 0 | 0xa4 | State Machine | uint32 |
| 1 | 0xa8 | Sub-State | uint32 |
| 15 | 0xe0 | Target X | float (as DWORD) |
| 16 | 0xe4 | Target Y | float (as DWORD) |
| 17 | 0xe8 | Target Z | float (as DWORD) |
| 67 | 0x1b0 | Animation ID | uint32 |
| 68 | 0x1b4 | Anim Counter | uint32 |

## Configuration Reference

### Preview Dimensions (draw_preview, lines 481-483)
```python
tank_x_range = 150  # Total X range (-75 to +75)
tank_y_range = 100  # Total Y range (-50 to +50)
```

### Visual Sizes (lines 535, 552)
```python
br = 15 * depth_scale  # Body radius
fr = 6 * depth_scale   # Face radius
```

### Color Scheme
- **Increasing values:** `#00ff00` (green)
- **Decreasing values:** `#ff0000` (red)
- **Instance changes:** `#ffff00` (yellow)
- **Inactive values:** `#555555` (dark gray)
- **Timeout:** 2 seconds (values return to gray after no change)

## Change Detection Logic

### param_4 Fields
```python
if abs(delta) > 0.01:  # Threshold for float comparison
    color = green if delta > 0 else red
    change_times[i] = now
elif now - change_times[i] > 2.0:
    color = gray  # Fade to gray after 2 seconds
```

### Instance Fields
```python
if val != prev_val:  # Exact comparison for integers
    color = yellow
    change_times[i] = now
elif now - change_times[i] > 2.0:
    color = gray
```

## Network Configuration
- **Protocol:** UDP
- **Port:** 8888
- **Target IP:** 192.168.0.6 (dev machine)
- **Packet rate:** ~10Hz from tracker

## Usage

### Starting the Bridge
```bash
cd C:\2026_projects\ghi\bridge
python bridge8_1.py
```

### Starting the XP Tracker
On Windows XP machine:
```
xp_debug_tracker_v8.1.exe
```

### View Mode Shortcuts
Click the button bar at top to switch between views:
- Position & Movement
- State & Animation
- All Fields
- Raw param_4
- Raw Instance

### Exploring Unknown Fields
1. Switch to Raw param_4 or Raw Instance view
2. Use format toggle buttons to decode values different ways
3. Watch for color changes to identify active fields
4. Compare Float/Hex/Int formats to determine data type

## Implementation Details

### UI Framework
- **Tkinter** for GUI
- **Threading** for UDP receiver (non-blocking)
- **Canvas** for 3D preview rendering

### Update Rate
- **UDP receiver:** Non-blocking socket, processes packets as they arrive
- **UI refresh:** 50ms (20 FPS) via `root.after()`

### Memory Efficiency
- Previous values stored for delta calculation
- Change timestamps tracked per field
- Labels updated in-place (no recreation)

## Troubleshooting

### No Data Received
- Check XP tracker is running
- Verify network connectivity (192.168.0.6)
- Confirm UDP port 8888 not blocked by firewall

### Preview Not Moving
- Check Position & Movement view shows changing values
- Verify Location X/Y/Z fields are updating
- Ensure tracker is attached to running Seaman process

### Rotation Inverted
- Yaw should use `body_angle - yaw_rad`
- Pitch should use `body_angle + pitch_rad`
- If still wrong, check param_4[26] and param_4[27] are correct fields

### Values Cut Off
- Increase label width in create_raw_*_grid functions
- Current widths: param_4=25, instance=35

## Version History

### v8.1 (Current)
- Added format toggle buttons for Raw param_4 and Raw Instance
- Fixed pitch rotation inversion
- Reduced body radius to 15 units
- Adjusted tank boundary to 150×100
- Added semantic field labels
- Implemented color-coded change tracking
- Fixed preview layout (stays on top)

### v8.0
- Initial version with basic visualization
- Preview had incorrect boundaries and inverted rotations

### v7.x
- Terminal-based display
- No GUI preview

## Related Files
- **xp_debug_tracker_v8.1.cpp** - XP memory reader/sender
- **BUILD_TRACKER_V8.1.bat** - Tracker build script
- **bridge7.py** - Previous terminal version (reference)
- **bridge8_1_documentation.md** - This file
