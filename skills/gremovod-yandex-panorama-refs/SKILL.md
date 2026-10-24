---
name: gremovod-yandex-panorama-refs
description: Location references for the GremoVOD cartoon from Yandex Panoramas. Use when grem sends an address, a point or a panorama link and asks for place references ("сделай референсы Минска/места для мультфильма", "4 ракурса вокруг точки", "панорамы Яндекса", "Real Reference"). Opens the panorama in the built-in browser, captures 4 sides (0/90/180/270), paints out Yandex UI and POI marks, saves to the hidden Real Reference folder named after the address. No paid calls.
---

# Yandex Panorama location refs

Goal: from an address/point, make 4 views around the point (later redrawn in cartoon style) and save to `projects/<project>/Real Reference/<place name>/`. Private references: never publish, never send to generation unless grem decides.

Script: `~/.claude/skills/gremovod-yandex-panorama-refs/grab_panorama.py` (repo copy: `skills/gremovod-yandex-panorama-refs/`). Run with `C:/AI_Workflow_Studio/.venv/Scripts/python.exe -X utf8 <script> ...` (Pillow, numpy, opencv present).

## Rules
- Built-in browser only (`mcp__Claude_Browser__*`). Yandex serves headless Chrome a "limited" page: do not bypass, do not fake the User-Agent. On captcha/block stop and tell grem.
- The script grabs screen pixels, so the browser window must be on top and fully visible: `tabs_select` before each grab, then LOOK at the result (other windows such as Explorer/Total Commander can pop over). Discard and redo bad frames.
- Delete temp screen grabs (`--thumb`, `C:/Temp/...`) right after use: they show the private desktop.
- Panoramas are copyrighted: private Real Reference only. Signs on buildings are not removed (done at redraw time).
- Never overwrite owner files: if the folder exists add `_2`. No paid calls.

## Steps
1. Point. Link given: take `panorama[point]=lon,lat`. Address given: open `https://yandex.by/maps/157/minsk/search/<address>/`, wait 2 s, read `ll=` from `location.href`. If it is a street, not a yard, ask which yard (try neighbouring points).
2. Panorama URL (fill lon/lat/AZ):
   `https://yandex.by/maps/157/minsk/?l=stv%2Csta&ll=<lon>%2C<lat>&panorama%5Bdirection%5D=<AZ>%2C-5&panorama%5Bfull%5D=true&panorama%5Bpoint%5D=<lon>%2C<lat>&panorama%5Bspan%5D=95.657841%2C60.000000&z=17`
   Yandex snaps to the nearest panorama: after the first load read the final `panorama[point]` from the URL and reuse it for all 4 sides. AZ = 0, 90, 180, 270 (N/E/S/W), pitch -5.
3. Calibrate once per window layout: `--thumb C:/Temp/desk.png`, `Read` it, find the panorama rectangle (no map strip, no tab bar), multiply by the printed factor, store with `--box X0 Y0 X1 Y1 --save-box`. grem's layout (3840x1600, detached browser window) is built in: 1459 225 3178 1123.
4. Per side: `navigate` (AZ) -> `computer wait 3` -> `tabs_select` -> `grab_panorama.py --out C:/Temp/pano/az<AZ>.png`.
5. Check: `--sheet az000.png az090.png az180.png az270.png --out sheet.png`, view it. Leftover pink/blue/green POI circles, stars or captions: regrab with `--mask x,y,w,h` (image coordinates, repeatable). Orange POI circles are painted out automatically.
6. Save to `projects/GremoVOD/Real Reference/<name>/` (name from the address, e.g. "Двор на Немиге (Герцена)"): `север_0.png`, `восток_90.png`, `юг_180.png`, `запад_270.png` and `ОПИСАНИЕ.txt` (source, coordinates, directions, what was painted out, "do not publish"). `projects/` is git-ignored.
7. Remove temp: `C:/Temp/pano`, `C:/Temp/desk.png`.
8. Show grem the 4-image sheet plus a short note (what is on each side, visible brands, which side to use).

## Later (separate, paid)
Cartoon redraw goes through the studio with a price estimate and grem's approval. Prompt help: `docs/model-guides/`, `docs/master-prompts/`.

## Limits
- The crop box depends on grem's window layout; recalibrate on another screen/window size.
- Auto-paint catches only orange POI circles; others need `--mask`.
- Screen grab quality equals the window size (about 1600x900); enlarge the browser window for more.
