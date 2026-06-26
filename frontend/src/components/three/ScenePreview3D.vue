<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import finalSceneJson from '../../../../final.json'

type PreviewMode = 'json3d' | 'bbox2d'

interface SpatialObject {
  id: string
  category: string
  anchor?: {
    type?: string
    position?: number[]
  }
  dimensions?: {
    width?: number
    height?: number
    length?: number
    unit?: string
  }
  rotation?: {
    yaw?: number
    unit?: string
  }
  source?: {
    bbox?: number[]
  }
  confidence?: {
    detection?: number
  }
}

interface ScenePayload {
  taskId?: string
  objects?: SpatialObject[]
}

interface PreviewItem {
  object: SpatialObject
  x: number
  y: number
  z: number
  width: number
  depth: number
  height: number
  yaw: number
  opacity: number
}

const staticScenePayload = finalSceneJson as ScenePayload
const mountRef = ref<HTMLDivElement | null>(null)
const renderError = ref<string | null>(null)
const dialogVisible = ref(false)
const highConfidenceOnly = ref(false)
const previewMode = ref<PreviewMode>('json3d')

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let animationId = 0
let resizeObserver: ResizeObserver | null = null

const parsedObjects = computed(() => (Array.isArray(staticScenePayload.objects) ? staticScenePayload.objects : []))
const previewItems = computed(() => buildPreviewItems(parsedObjects.value, highConfidenceOnly.value, previewMode.value))
const previewDescription = computed(() =>
  previewMode.value === 'json3d'
    ? '当前按 final.json 的 anchor.position、dimensions、rotation.yaw 做统一缩放复原，用于验证后端三维空间求解结果。'
    : '当前按 source.bbox 做 2.5D 图像位置对照，只用于检查检测框和语义结果。',
)

const legendItems = [
  { category: 'building', label: '建筑', color: '#2563eb' },
  { category: 'road', label: '道路', color: '#475569' },
  { category: 'ground', label: '地面', color: '#d8c38a' },
  { category: 'vegetation_region', label: '绿化', color: '#22c55e' },
  { category: 'street_light', label: '路灯', color: '#f59e0b' },
]

watch(dialogVisible, (visible) => {
  if (visible) {
    void nextTick(renderScene)
  } else {
    disposeCurrentScene()
  }
})

watch([highConfidenceOnly, previewMode], () => {
  if (dialogVisible.value) void nextTick(renderScene)
})

function bboxOf(object: SpatialObject): number[] | null {
  const bbox = object.source?.bbox
  if (!bbox || bbox.length < 4) return null
  if (!bbox.every(Number.isFinite)) return null
  const [x1, y1, x2, y2] = bbox
  if (x2 <= x1 || y2 <= y1) return null
  return bbox
}

function positionOf(object: SpatialObject): number[] | null {
  const position = object.anchor?.position
  if (!position || position.length < 3) return null
  if (!position.every(Number.isFinite)) return null
  return position
}

function dimensionsOf(object: SpatialObject) {
  const width = Number(object.dimensions?.width)
  const height = Number(object.dimensions?.height)
  const depth = Number(object.dimensions?.length)
  if (![width, height, depth].every(Number.isFinite)) return null
  if (width <= 0 || height <= 0 || depth <= 0) return null
  return { width, height, depth }
}

function scoreOf(object: SpatialObject): number {
  return Number(object.confidence?.detection ?? 1)
}

function yawOf(object: SpatialObject): number {
  const yaw = Number(object.rotation?.yaw ?? 0)
  return Number.isFinite(yaw) ? THREE.MathUtils.degToRad(yaw) : 0
}

function isRegion(category: string): boolean {
  return ['ground', 'road', 'vegetation_region'].includes(category)
}

function passesConfidence(object: SpatialObject): boolean {
  if (isRegion(object.category)) return true
  const score = scoreOf(object)
  if (object.category === 'street_light') return score >= 0.45
  return score >= 0.55
}

function opacityFor(object: SpatialObject): number {
  const score = scoreOf(object)
  if (object.category === 'ground') return 0.22
  if (object.category === 'road') return 0.72
  if (object.category === 'vegetation_region') return 0.42
  if (object.category === 'street_light') return score < 0.45 ? 0.38 : 1
  return score < 0.55 ? 0.35 : 0.88
}

function buildPreviewItems(objects: SpatialObject[], onlyHighConfidence: boolean, mode: PreviewMode): PreviewItem[] {
  return mode === 'json3d'
    ? buildJson3dItems(objects, onlyHighConfidence)
    : buildBboxItems(objects, onlyHighConfidence)
}

function buildJson3dItems(objects: SpatialObject[], onlyHighConfidence: boolean): PreviewItem[] {
  const rawItems = objects
    .filter((object) => !onlyHighConfidence || passesConfidence(object))
    .map((object) => ({ object, position: positionOf(object), dimensions: dimensionsOf(object) }))
    .filter(
      (item): item is { object: SpatialObject; position: number[]; dimensions: { width: number; height: number; depth: number } } =>
        Boolean(item.position && item.dimensions),
    )

  if (!rawItems.length) return []

  const extents = rawItems.flatMap(({ position, dimensions }) => {
    const [x, rawY, z] = position
    return [
      { x: x - dimensions.width / 2, y: rawY, z: z - dimensions.depth / 2 },
      { x: x + dimensions.width / 2, y: rawY + dimensions.height, z: z + dimensions.depth / 2 },
    ]
  })
  const minX = Math.min(...extents.map((item) => item.x))
  const maxX = Math.max(...extents.map((item) => item.x))
  const minY = Math.min(...extents.map((item) => item.y))
  const maxY = Math.max(...extents.map((item) => item.y))
  const minZ = Math.min(...extents.map((item) => item.z))
  const maxZ = Math.max(...extents.map((item) => item.z))
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2
  const centerZ = (minZ + maxZ) / 2
  const maxSpan = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 1)
  const scale = 86 / maxSpan

  return rawItems.map(({ object, position, dimensions }) => {
    const [rawX, rawY, rawZ] = position
    return {
      object,
      x: (rawX - centerX) * scale,
      y: (rawY - centerY) * scale,
      z: (rawZ - centerZ) * scale,
      width: Math.max(dimensions.width * scale, 0.08),
      depth: Math.max(dimensions.depth * scale, 0.08),
      height: Math.max(dimensions.height * scale, 0.08),
      yaw: yawOf(object),
      opacity: opacityFor(object),
    }
  })
}

function buildBboxItems(objects: SpatialObject[], onlyHighConfidence: boolean): PreviewItem[] {
  const boxed = objects
    .filter((object) => !onlyHighConfidence || passesConfidence(object))
    .map((object) => ({ object, bbox: bboxOf(object) }))
    .filter((item): item is { object: SpatialObject; bbox: number[] } => Boolean(item.bbox))

  if (!boxed.length) return []

  const imageWidth = Math.max(...boxed.map((item) => item.bbox[2]), 1)
  const imageHeight = Math.max(...boxed.map((item) => item.bbox[3]), 1)
  const sceneWidth = 96
  const sceneDepth = 54

  return boxed.map(({ object, bbox }) => {
    const [x1, y1, x2, y2] = bbox
    const bw = x2 - x1
    const bh = y2 - y1
    const cx = (x1 + x2) * 0.5
    const cy = (y1 + y2) * 0.5
    const baseY = y2
    const x = (cx / imageWidth - 0.5) * sceneWidth
    const zFromCenter = (cy / imageHeight - 0.5) * sceneDepth
    const zFromBottom = (baseY / imageHeight - 0.5) * sceneDepth

    if (object.category === 'building') {
      const width = THREE.MathUtils.clamp((bw / imageWidth) * sceneWidth, 0.8, 12)
      const depth = THREE.MathUtils.clamp(width * 0.55, 0.7, 6.5)
      const height = THREE.MathUtils.clamp((bh / imageHeight) * 40, 2, 24)
      return { object, x, y: 0, z: zFromBottom, width, depth, height, yaw: 0, opacity: opacityFor(object) }
    }

    if (object.category === 'street_light') {
      const height = THREE.MathUtils.clamp((bh / imageHeight) * 22, 1.1, 5)
      return { object, x, y: 0, z: zFromBottom, width: 0.18, depth: 0.18, height, yaw: 0, opacity: opacityFor(object) }
    }

    const width = THREE.MathUtils.clamp((bw / imageWidth) * sceneWidth, 0.8, sceneWidth)
    const depth = THREE.MathUtils.clamp((bh / imageHeight) * sceneDepth, 0.8, sceneDepth)
    const height = object.category === 'road' ? 0.12 : object.category === 'vegetation_region' ? 0.16 : 0.08
    return { object, x, y: 0, z: zFromCenter, width, depth, height, yaw: 0, opacity: opacityFor(object) }
  })
}

function categoryColor(category: string): number {
  return {
    building: 0x2563eb,
    road: 0x475569,
    ground: 0xd8c38a,
    vegetation_region: 0x22c55e,
    street_light: 0xf59e0b,
  }[category] ?? 0x8b5cf6
}

function disposeCurrentScene() {
  if (animationId) cancelAnimationFrame(animationId)
  animationId = 0
  resizeObserver?.disconnect()
  resizeObserver = null
  controls?.dispose()
  controls = null
  renderer?.dispose()
  if (renderer?.domElement.parentElement) {
    renderer.domElement.parentElement.removeChild(renderer.domElement)
  }
  renderer = null
  scene = null
  camera = null
}

function materialFor(item: PreviewItem) {
  return new THREE.MeshStandardMaterial({
    color: categoryColor(item.object.category),
    roughness: 0.82,
    metalness: 0.04,
    transparent: item.opacity < 1 || isRegion(item.object.category),
    opacity: item.opacity,
    depthWrite: !isRegion(item.object.category),
  })
}

function createPreviewMesh(item: PreviewItem): THREE.Object3D {
  const { object, x, y, z, width, depth, height, yaw } = item
  const material = materialFor(item)

  if (object.category === 'street_light') {
    const group = new THREE.Group()
    const poleHeight = Math.max(height, width, depth)
    const radius = THREE.MathUtils.clamp(Math.min(width, depth) * 0.25, 0.025, 0.14)
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius * 1.2, poleHeight, 10), material)
    pole.position.y = poleHeight / 2
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(radius * 2.4, 12, 8), material)
    lamp.position.y = poleHeight + radius * 1.5
    group.add(pole, lamp)
    group.position.set(x, y, z)
    group.rotation.y = yaw
    return group
  }

  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material)
  mesh.position.set(x, y + height / 2, z)
  mesh.rotation.y = yaw
  return mesh
}

function addSceneFrame(targetScene: THREE.Scene) {
  const base = new THREE.Mesh(
    new THREE.PlaneGeometry(100, 58),
    new THREE.MeshStandardMaterial({ color: 0xf3f6fb, roughness: 0.9 }),
  )
  base.rotation.x = -Math.PI / 2
  base.position.y = -0.04
  targetScene.add(base)

  const grid = new THREE.GridHelper(100, 25, 0x94a3b8, 0xd5dde8)
  targetScene.add(grid)

  const axes = new THREE.AxesHelper(8)
  axes.position.set(-47, 0.05, -26)
  targetScene.add(axes)
}

function renderScene() {
  renderError.value = null
  disposeCurrentScene()

  const mount = mountRef.value
  if (!mount || !previewItems.value.length) return

  try {
    scene = new THREE.Scene()
    scene.background = new THREE.Color(0xf8fafc)

    const width = mount.clientWidth || 1200
    const height = mount.clientHeight || 680
    camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1200)
    camera.position.set(0, 48, 72)

    renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(width, height)
    mount.appendChild(renderer.domElement)

    controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 0, 0)
    controls.enableDamping = true
    controls.maxPolarAngle = Math.PI * 0.62

    scene.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.25))
    const sun = new THREE.DirectionalLight(0xffffff, 1.7)
    sun.position.set(28, 60, 32)
    scene.add(sun)
    addSceneFrame(scene)

    const regionItems = previewItems.value.filter((item) => isRegion(item.object.category))
    const solidItems = previewItems.value.filter((item) => !isRegion(item.object.category))
    ;[...regionItems, ...solidItems].forEach((item) => {
      const mesh = createPreviewMesh(item)
      mesh.name = item.object.id
      scene?.add(mesh)
    })

    resizeObserver = new ResizeObserver(() => {
      if (!mountRef.value || !renderer || !camera) return
      const nextWidth = mountRef.value.clientWidth || 1200
      const nextHeight = mountRef.value.clientHeight || 680
      renderer.setSize(nextWidth, nextHeight)
      camera.aspect = nextWidth / nextHeight
      camera.updateProjectionMatrix()
    })
    resizeObserver.observe(mount)

    const tick = () => {
      animationId = requestAnimationFrame(tick)
      controls?.update()
      if (renderer && scene && camera) renderer.render(scene, camera)
    }
    tick()
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : String(error)
  }
}

onBeforeUnmount(disposeCurrentScene)
</script>

<template>
  <section class="card scene-preview-card compact">
    <div class="card-title">
      <span>三维简化复原预览</span>
      <el-tag size="small" effect="plain">final.json</el-tag>
    </div>

    <div class="scene-legend">
      <span v-for="item in legendItems" :key="item.category">
        <i :style="{ backgroundColor: item.color }" />
        {{ item.label }}
      </span>
    </div>

    <div class="scene-preview-actions">
      <div>
        <strong>{{ previewItems.length }} / {{ parsedObjects.length }}</strong>
        <span>根目录 final.json 对象参与复原</span>
      </div>
      <el-button type="primary" :disabled="!previewItems.length" @click="dialogVisible = true">
        打开大屏三维预览
      </el-button>
    </div>

    <p class="field-help">{{ previewDescription }}</p>

    <el-dialog
      v-model="dialogVisible"
      title="三维简化复原预览"
      width="88vw"
      top="4vh"
      class="scene-preview-dialog"
      destroy-on-close
    >
      <div class="scene-dialog-toolbar">
        <div class="scene-legend">
          <span v-for="item in legendItems" :key="item.category">
            <i :style="{ backgroundColor: item.color }" />
            {{ item.label }}
          </span>
        </div>
        <div class="scene-dialog-controls">
          <el-radio-group v-model="previewMode" size="small">
            <el-radio-button label="json3d">JSON 三维坐标</el-radio-button>
            <el-radio-button label="bbox2d">bbox 对照</el-radio-button>
          </el-radio-group>
          <el-switch v-model="highConfidenceOnly" active-text="只看高可信" />
          <span class="field-help">鼠标左键旋转，滚轮缩放，右键平移</span>
        </div>
      </div>

      <div v-if="previewItems.length" ref="mountRef" class="scene-preview-canvas large" />
      <el-alert
        v-else-if="renderError"
        type="error"
        :title="renderError"
        show-icon
        :closable="false"
      />
      <el-empty v-else description="final.json 里没有可预览对象" :image-size="72" />
    </el-dialog>
  </section>
</template>
