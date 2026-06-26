declare module 'three' {
  export class Object3D {
    name: string
    position: { set: (...args: number[]) => void; y: number }
    rotation: { y: number; x: number }
    add: (...objects: Object3D[]) => void
  }
  export class Scene extends Object3D {
    background: unknown
  }
  export class Color {
    constructor(value: number)
  }
  export class PerspectiveCamera extends Object3D {
    aspect: number
    constructor(...args: unknown[])
    updateProjectionMatrix: () => void
  }
  export class WebGLRenderer {
    domElement: HTMLCanvasElement
    constructor(options?: Record<string, unknown>)
    setPixelRatio: (value: number) => void
    setSize: (width: number, height: number) => void
    render: (scene: Scene, camera: PerspectiveCamera) => void
    dispose: () => void
  }
  export class MeshStandardMaterial {
    constructor(options?: Record<string, unknown>)
  }
  export class Mesh extends Object3D {
    geometry: { parameters: { height: number } }
    constructor(geometry: unknown, material: unknown)
  }
  export class Group extends Object3D {}
  export class CylinderGeometry { constructor(...args: unknown[]) }
  export class SphereGeometry { constructor(...args: unknown[]) }
  export class BoxGeometry { constructor(...args: unknown[]) }
  export class PlaneGeometry { constructor(...args: unknown[]) }
  export class GridHelper extends Object3D { constructor(...args: unknown[]) }
  export class AxesHelper extends Object3D { constructor(...args: unknown[]) }
  export class HemisphereLight extends Object3D { constructor(...args: unknown[]) }
  export class DirectionalLight extends Object3D { constructor(...args: unknown[]) }
  export const MathUtils: {
    clamp: (value: number, min: number, max: number) => number
    degToRad: (value: number) => number
  }
}

declare module 'three/examples/jsm/controls/OrbitControls.js' {
  import type { Object3D } from 'three'
  export class OrbitControls {
    target: { set: (...args: number[]) => void }
    enableDamping: boolean
    maxPolarAngle: number
    constructor(camera: Object3D, domElement: HTMLElement)
    update: () => void
    dispose: () => void
  }
}