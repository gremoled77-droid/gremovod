"""Reviewed-source candidate for isolated Blender 4.5 testing, NOT VERIFIED.

Only a neutral synthetic proxy; never loads user .blend, Python or URLs. Do not
execute on the owner account. G1 is enforced by the outer offline-only planner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main() -> None:
    import bpy
    from mathutils import Vector

    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['diagnostic', 'keyframes', 'full'], required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    shot = json.loads(args.manifest.read_text(encoding='utf-8'))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'environment.json').write_text(json.dumps({
        'blender': bpy.app.version_string, 'build_hash': bpy.app.build_hash.decode(),
        'background': bpy.app.background, 'asset_policy': 'NON_CANONICAL_PROXY'}), encoding='utf-8')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1

    def box(name, location, size, color):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.color = (*color, 1)
        return obj

    # +X front, +Y left, +Z up. No VAZ/canonical likeness is asserted.
    body = box('NON_CANONICAL_PROXY', (0, 0, 1), (7, 1.8, 1.2), (.35, .35, .35))
    for x in (-2.5, 2.5):
        for y in (-.95, .95):
            box(f'wheel_{x}_{y}', (x, y, .4), (.65, .25, .65), (.06, .06, .06))
    box('LEFT_GREEN', (0, .92, 1.2), (.4, .08, .4), (0, 1, 0))
    box('RIGHT_RED', (0, -.92, 1.2), (.4, .08, .4), (1, 0, 0))
    box('ground', (0, 0, -.1), (60, 60, .2), (.16, .16, .16))
    protected = [o for o in scene.objects if o.type == 'MESH']

    def snapshot():
        return {o.name: {'matrix': [list(row) for row in o.matrix_world],
                         'vertices': [list(v.co) for v in o.data.vertices]}
                for o in protected}

    baseline = snapshot()
    baseline_hash = hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.lens = shot['camera']['lens_mm']
    camera.data.sensor_width = shot['camera']['sensor_width_mm']
    camera.data.clip_start = shot['camera']['clip_start_m']
    camera.data.clip_end = shot['camera']['clip_end_m']
    # Bake the validated linear path every frame; look-at orientation is explicit.
    keys = shot['camera']['keys']
    for frame in range(shot['start_frame'], shot['end_frame_exclusive']):
        i = next((i for i, k in enumerate(keys) if k['frame'] >= frame), len(keys)-1)
        a, b = keys[max(0, i-1)], keys[i]
        t = (frame-a['frame'])/(b['frame']-a['frame']) if b['frame'] != a['frame'] else 0
        pos, target = [Vector([x+(y-x)*t for x, y in zip(a[field], b[field])])
                       for field in ('position_m', 'look_at_m')]
        camera.location = pos
        camera.rotation_euler = (target-pos).to_track_quat('-Z', 'Y').to_euler()
        camera.keyframe_insert('location', frame=frame)
        camera.keyframe_insert('rotation_euler', frame=frame)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'OBJECT'
    scene.render.resolution_x, scene.render.resolution_y = shot['resolution']
    scene.render.resolution_percentage = 100
    scene.render.fps = shot['fps']
    scene.frame_start = shot['start_frame']
    scene.frame_end = shot['end_frame_exclusive'] - 1
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'scene.blend'))
    frames = [scene.frame_start] if args.phase == 'diagnostic' else sorted({
        scene.frame_start, (scene.frame_start+scene.frame_end)//2, scene.frame_end})
    if args.phase == 'full':
        frames = range(scene.frame_start, scene.frame_end+1)
    (out / 'frames').mkdir(exist_ok=True)
    for frame in frames:
        scene.frame_set(frame)
        if snapshot() != baseline:
            raise RuntimeError('PROTECTED_GEOMETRY_CHANGED')
        scene.render.filepath = str(out / 'frames' / f'{frame:06}.png')
        bpy.ops.render.render(write_still=True)
    (out / 'geometry.json').write_text(json.dumps({
        'before_sha256': baseline_hash, 'after_sha256': hashlib.sha256(
            json.dumps(snapshot(), sort_keys=True).encode()).hexdigest(),
        'human_status': 'PENDING', 'visibility': 'UNVERIFIED',
        'canonical_asset': False}), encoding='utf-8')


if __name__ == '__main__':
    main()
