from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "building": (37, 99, 235),
    "road": (71, 85, 105),
    "ground": (216, 195, 138),
    "vegetation_region": (34, 197, 94),
    "street_light": (245, 158, 11),
}


def object_layout_preview_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "object_layout.png"


def group_layout_preview_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "group_layout.png"


def scene_preview_report_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "scene_preview.html"


def render_object_layout_preview(task_dir: Path) -> Path | None:
    objects_payload = _read_json(task_dir / "spatial" / "objects.json")
    objects = objects_payload.get("objects", [])
    if not isinstance(objects, list) or not objects:
        return None
    return _render_topdown(objects, object_layout_preview_path(task_dir), title="Object solve top-down layout")


def render_group_layout_preview(task_dir: Path) -> Path | None:
    objects_payload = _read_json(task_dir / "spatial" / "objects.json")
    groups_payload = _read_json(task_dir / "spatial" / "groups.json")
    objects = objects_payload.get("objects", [])
    groups = groups_payload.get("groups", [])
    if not isinstance(objects, list) or not objects:
        return None
    return _render_topdown(objects, group_layout_preview_path(task_dir), title="Group solve layout", groups=groups)


def render_scene_preview_report(task_dir: Path) -> Path | None:
    result = _read_json(task_dir / "spatial" / "spatial_scene_observation.json")
    objects = result.get("objects", [])
    if not isinstance(objects, list) or not objects:
        return None
    counts: dict[str, int] = {}
    suspicious: list[dict[str, Any]] = []
    for obj in objects:
        category = str(obj.get("category", "unknown"))
        counts[category] = counts.get(category, 0) + 1
        dims = obj.get("dimensions", {}) if isinstance(obj.get("dimensions"), dict) else {}
        width = float(dims.get("width", 0) or 0)
        height = float(dims.get("height", 0) or 0)
        length = float(dims.get("length", 0) or 0)
        if max(width, height, length) > 300 or min(width, height, length) <= 0:
            suspicious.append(obj)

    objects_json = json.dumps(objects, ensure_ascii=False)
    counts_rows = "".join(
        f"<tr><td>{escape(category)}</td><td>{count}</td></tr>" for category, count in sorted(counts.items())
    )
    suspicious_rows = "".join(
        "<tr>"
        f"<td>{escape(str(obj.get('id', '-')))}</td>"
        f"<td>{escape(str(obj.get('category', '-')))}</td>"
        f"<td>{escape(json.dumps(obj.get('dimensions', {}), ensure_ascii=False))}</td>"
        "</tr>"
        for obj in suspicious[:80]
    )
    target = scene_preview_report_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>Scene Spatial Preview</title>
<style>
body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #f8fafc; }}
header {{ padding: 16px 20px; background: #fff; border-bottom: 1px solid #dce4f2; }}
main {{ display: grid; grid-template-columns: 1fr 360px; gap: 14px; padding: 14px; }}
#canvas {{ height: calc(100vh - 98px); min-height: 620px; background: #fff; border: 1px solid #dce4f2; border-radius: 8px; }}
aside {{ display: grid; align-content: start; gap: 14px; }}
.card {{ background: #fff; border: 1px solid #dce4f2; border-radius: 8px; padding: 12px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
td, th {{ border-bottom: 1px solid #e2e8f0; padding: 6px; text-align: left; vertical-align: top; }}
.badge {{ display: inline-block; padding: 3px 7px; border-radius: 999px; background: #e2e8f0; margin-right: 6px; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <strong>Scene Spatial Preview</strong>
  <span class="badge">objects {len(objects)}</span>
  <span class="badge">task {escape(str(result.get('taskId', '-')))}</span>
</header>
<main>
  <div id="canvas"></div>
  <aside>
    <section class="card"><h3>对象数量</h3><table><tbody>{counts_rows}</tbody></table></section>
    <section class="card"><h3>可疑尺寸对象</h3><table><tbody>{suspicious_rows or '<tr><td>暂无</td></tr>'}</tbody></table></section>
  </aside>
</main>
<script type="module">
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js';
import {{ OrbitControls }} from 'https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/controls/OrbitControls.js';
const objects = {objects_json};
const colorMap = {{ building: 0x2563eb, road: 0x475569, ground: 0xd8c38a, vegetation_region: 0x22c55e, street_light: 0xf59e0b }};
const container = document.getElementById('canvas');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf8fafc);
const camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 2000);
camera.position.set(0, 58, 82);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.25));
const sun = new THREE.DirectionalLight(0xffffff, 1.7);
sun.position.set(28, 60, 32);
scene.add(sun);
const grid = new THREE.GridHelper(100, 25, 0x94a3b8, 0xd5dde8);
scene.add(grid);
const raw = objects.map(o => {{
  const p = o.anchor?.position || [0,0,0];
  const d = o.dimensions || {{ width: 1, height: 1, length: 1 }};
  return {{ o, p, d }};
}});
const ext = [];
raw.forEach(({{p,d}}) => {{ ext.push([p[0]-d.width/2,p[1],p[2]-d.length/2], [p[0]+d.width/2,p[1]+d.height,p[2]+d.length/2]); }});
const min = [0,1,2].map(i => Math.min(...ext.map(v => v[i])));
const max = [0,1,2].map(i => Math.max(...ext.map(v => v[i])));
const center = min.map((v,i)=>(v+max[i])/2);
const span = Math.max(...min.map((v,i)=>max[i]-v), 1);
const scale = 86 / span;
raw.forEach(({{o,p,d}}) => {{
  const color = colorMap[o.category] || 0x8b5cf6;
  const opacity = ['ground','road','vegetation_region'].includes(o.category) ? 0.45 : 0.86;
  const material = new THREE.MeshStandardMaterial({{ color, transparent: opacity < 1, opacity }});
  let mesh;
  if (o.category === 'street_light') {{
    mesh = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, Math.max(d.height, d.length) * scale, 10), material);
  }} else {{
    mesh = new THREE.Mesh(new THREE.BoxGeometry(Math.max(d.width*scale, .08), Math.max(d.height*scale, .08), Math.max(d.length*scale, .08)), material);
  }}
  mesh.position.set((p[0]-center[0])*scale, (p[1]-center[1])*scale + mesh.geometry.parameters.height / 2, (p[2]-center[2])*scale);
  mesh.rotation.y = THREE.MathUtils.degToRad(o.rotation?.yaw || 0);
  mesh.name = o.id;
  scene.add(mesh);
}});
function loop() {{ requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); }}
loop();
window.addEventListener('resize', () => {{ renderer.setSize(container.clientWidth, container.clientHeight); camera.aspect = container.clientWidth / container.clientHeight; camera.updateProjectionMatrix(); }});
</script>
</body>
</html>
""".strip(),
        encoding="utf-8",
    )
    return target


def _render_topdown(
    objects: list[dict[str, Any]],
    target: Path,
    title: str,
    groups: list[dict[str, Any]] | None = None,
) -> Path | None:
    positioned = []
    for obj in objects:
        position = obj.get("anchor", {}).get("position") if isinstance(obj.get("anchor"), dict) else None
        dims = obj.get("dimensions", {}) if isinstance(obj.get("dimensions"), dict) else {}
        if not isinstance(position, list | tuple) or len(position) < 3:
            continue
        positioned.append((obj, float(position[0]), float(position[2]), float(dims.get("width", 1) or 1), float(dims.get("length", 1) or 1)))
    if not positioned:
        return None

    width, height = 1400, 900
    margin = 70
    xs = [x for _, x, _, w, _ in positioned for x in (x - w / 2, x + w / 2)]
    zs = [z for _, _, z, _, d in positioned for z in (z - d / 2, z + d / 2)]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    span_x = max(max_x - min_x, 1.0)
    span_z = max(max_z - min_z, 1.0)
    scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_z)

    def px(x: float) -> float:
        return margin + (x - min_x) * scale

    def py(z: float) -> float:
        return height - margin - (z - min_z) * scale

    image = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((24, 20), title, fill=(15, 23, 42), font=font)
    for obj, x, z, obj_w, obj_d in positioned:
        category = str(obj.get("category", "unknown"))
        color = CATEGORY_COLORS.get(category, (139, 92, 246))
        half_w = max(obj_w * scale * 0.5, 2.0)
        half_d = max(obj_d * scale * 0.5, 2.0)
        cx, cy = px(x), py(z)
        draw.rectangle([cx - half_w, cy - half_d, cx + half_w, cy + half_d], outline=color, fill=(*color,), width=2)
        draw.text((cx + 4, cy + 4), str(obj.get("id", "-"))[:22], fill=(15, 23, 42), font=font)

    if groups:
        by_id = {str(obj.get("id")): (px(x), py(z)) for obj, x, z, _, _ in positioned}
        for group in groups:
            ids = group.get("objectIds", [])
            pts = [by_id[str(obj_id)] for obj_id in ids if str(obj_id) in by_id]
            if len(pts) >= 2:
                draw.line(pts, fill=(239, 68, 68), width=3)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
