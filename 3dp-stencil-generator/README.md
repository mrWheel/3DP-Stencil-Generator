# 3DP Stencil Generator (KiCad Action Plugin)

This project is a KiCad Action Plugin that generates an OpenSCAD stencil model from SMD pads on the selected copper side.

The plugin:
- Collects SMD pads from the board.
- Applies pad scaling logic to improve manufacturability.
- Enforces a minimum web (gap) between neighboring apertures.
- Exports a `.scad` file for 3D-printable solder stencils.

## Main Workflow

1. Open a PCB in KiCad.
2. Run the plugin from Action Plugins.
3. Choose parameters in the dialog.
4. The plugin generates stencil SCAD output in the project `stencil` folder.

---

## Core Parameters (Most Important)

These are the key values that control pad adaptation behavior.

### `minGapBetweenPads` (mm)
Minimum allowed stencil web between two nearby apertures.

- **Role:** Hard safety constraint.
- **Effect:** If two pads would violate this gap, scaling is reduced until the gap is safe.
- **Higher value:** Safer/stronger web, but more shrinking can occur.
- **Lower value:** Less shrinking, but thinner web.

### `minPadWidth` (mm)
Target minimum pad width used during narrow-pad optimization.

- **Role:** Target value for increasing very narrow pads (best effort).
- **Effect:** Narrow pads are expanded toward this value when gap constraints allow.
- **Important relation:** `minPadWidth >= narrowPadThreshold` is enforced.

### `narrowPadThreshold` (mm)
Threshold that decides when a pad is considered *narrow*.

- **Role:** Trigger for narrow-pad optimization.
- **Effect:** Pads with width below this threshold enter the narrow optimization pass.
- **Higher value:** More pads are treated as narrow.
- **Lower value:** Fewer pads are treated as narrow.

### `pcbClearence` (mm)
Clearance offset used when generating stencil frame/outline geometry.

- **Role:** Geometric offset from PCB edges for stencil base features.
- **Effect:** Larger value increases outline offset.

### `prySlotPosition`
Selects where the pry slot is placed.

- `0 = Top`
- `1 = Right`
- `2 = Bottom`
- `3 = Left`
- `4 = None`

---

## Width / Height Convention

For diagnostics and optimization in this project:

- **Width (W) = smaller pad side**
- **Height (H) = larger pad side**

So if an original pad is `1.475 x 0.600`, it is represented as:
- `W = 0.600`
- `H = 1.475`

This convention is used consistently in logs (`Orig W/H` and `New W/H`).

---

## Dialog Parameter Order

The dialog is intentionally ordered as:

1. `minGapBetweenPads`
2. `minPadWidth`
3. `narrowPadThreshold`
4. `pcbClearence`
5. `prySlotPosition`

---

## Dialog Field Help

This section mirrors the tooltip help shown in the plugin dialog.

### `Copper side`
- Selects which copper layer is used to collect SMD pads (`Front` or `Back`).
- **Inter-field validation:** none.

### `Minimum Gap Between Pads (mm)`
- Hard minimum web between neighboring apertures.
- Higher values increase safety but can force more pad shrinking.
- **Inter-field validation:** none.

### `Minimum pad width (mm)`
- Target minimum width used by narrow-pad optimization (best effort).
- **Inter-field validation:** must be **greater than or equal to** `Narrow Pad Threshold`.

### `Narrow Pad Threshold (mm)`
- Pads with width below this threshold are treated as narrow and optimized first.
- **Inter-field validation:** must be **less than or equal to** `Minimum pad width`.

### `PCB clearance (mm)`
- Outline/frame offset around PCB geometry.
- Higher values increase stencil clearance from board edges.
- **Inter-field validation:** none.

### `Pry Slot Position`
- Selects where the pry slot is placed (`Top`, `Right`, `Bottom`, `Left`, `None`).
- **Inter-field validation:** none.

---

## How Pad Scaling Works (High Level)

The pad scaling pipeline is roughly:

1. **Narrow pad optimization**  
   Pads below `narrowPadThreshold` are expanded toward `minPadWidth` (gap-safe).

2. **Soft minimum pass**  
   Best-effort raising of tiny pads toward `minPadWidth` without violating minimum gap.

3. **Uniform small-footprint scaling**  
   Pin-like clusters in the same footprint are kept uniform where possible.

4. **Global gap safety enforcement**  
   Final hard pass that guarantees `minGapBetweenPads` constraints.

If there is a conflict between target width and spacing, **spacing wins**.

---

## Diagnostic Log Output

The plugin emits diagnostic lines per footprint and per pad.

Typical pad line fields:
- `Orig W/H ...` original dimensions in mm.
- `New W/H ...` final dimensions after scaling.
- `factor W/H ...` multiplicative factors.
- `status=changed|unchanged`
- `reason=...` explanation (`narrow-opt`, `uniform-footprint`, `global-gap-safety`, etc.).

This helps verify exactly why each pad changed (or not).

---

## Configuration Storage

Settings are read from and written to:

- `stencil/3dpStencil.ini`

Stored keys include:
- `minGapBetweenPads`
- `minPadWidth`
- `pcbCearance`
- `narrowPadThreshold`
- `prySlotPosition`

---

## Deploy Helper Script

A helper script is included:

- `deploy_plugin.sh`

It can:
1. Ensure the KiCad plugin directory exists.
2. Increment `BUILD` in `__init__.py`.
3. Copy `__init__.py` to the KiCad plugin folder.

---

## Notes

- This plugin is intended for KiCad + OpenSCAD stencil workflows.
- Some parameter names preserve historical spelling (`pcbClearence`, `pcbCearance`) for compatibility.

---

## Recommended Starting Values

Use these as practical starting points, then fine-tune based on your board density and printing process.

### Standard footprints (0603/0805, SOIC, larger pitch)

- `minGapBetweenPads`: `0.30` to `0.40`
- `minPadWidth`: `0.45` to `0.60`
- `narrowPadThreshold`: `0.45` to `0.70`
- `pcbClearence`: `0.10` to `0.20`
- `prySlotPosition`: as needed (`4 = None` if not required)

### Fine-pitch footprints (QFN/TQFP with tight spacing)

- `minGapBetweenPads`: `0.40` to `0.55`
- `minPadWidth`: `0.35` to `0.50`
- `narrowPadThreshold`: `0.35` to `0.55`
- `pcbClearence`: `0.10` to `0.20`
- `prySlotPosition`: as needed

### Tuning guidance

- If bridges/web breaks occur, increase `minGapBetweenPads` first.
- If apertures become too small, raise `minPadWidth` carefully.
- Keep `narrowPadThreshold` close to your intended minimum useful aperture width.
- Remember: when there is conflict, gap safety (`minGapBetweenPads`) always wins.
