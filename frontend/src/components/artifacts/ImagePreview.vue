<script setup lang="ts">
import { computed, ref } from 'vue'

defineProps<{
  src: string
  title: string
}>()

const dialogVisible = ref(false)
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const dragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)
const dragOriginX = ref(0)
const dragOriginY = ref(0)

const imageStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  cursor: dragging.value ? 'grabbing' : scale.value > 1 ? 'grab' : 'zoom-in',
}))

function resetView() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
  dragging.value = false
}

function zoomBy(delta: number) {
  scale.value = Math.min(8, Math.max(0.25, scale.value + delta))
  if (scale.value <= 1) {
    translateX.value = 0
    translateY.value = 0
  }
}

function handleWheel(event: WheelEvent) {
  event.preventDefault()
  zoomBy(event.deltaY > 0 ? -0.15 : 0.15)
}

function startDrag(event: MouseEvent) {
  if (event.button !== 0) return
  dragging.value = true
  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  dragOriginX.value = translateX.value
  dragOriginY.value = translateY.value
}

function moveDrag(event: MouseEvent) {
  if (!dragging.value) return
  translateX.value = dragOriginX.value + event.clientX - dragStartX.value
  translateY.value = dragOriginY.value + event.clientY - dragStartY.value
}

function endDrag() {
  dragging.value = false
}
</script>

<template>
  <figure class="image-preview">
    <button class="image-preview-button" type="button" @click="dialogVisible = true">
      <img :src="src" :alt="title" />
    </button>
    <figcaption>{{ title }}</figcaption>

    <el-dialog
      v-model="dialogVisible"
      :title="title"
      width="92vw"
      top="4vh"
      class="image-preview-dialog"
      destroy-on-close
      @closed="resetView"
    >
      <div class="image-preview-toolbar">
        <el-button size="small" @click="zoomBy(-0.25)">缩小</el-button>
        <span>{{ Math.round(scale * 100) }}%</span>
        <el-button size="small" @click="zoomBy(0.25)">放大</el-button>
        <el-button size="small" @click="resetView">复位</el-button>
        <span class="field-help">滚轮缩放，左键拖拽，双击复位</span>
      </div>
      <div
        class="image-preview-large-wrap"
        @wheel="handleWheel"
        @mousedown="startDrag"
        @mousemove="moveDrag"
        @mouseup="endDrag"
        @mouseleave="endDrag"
        @dblclick="resetView"
      >
        <img class="image-preview-large" :src="src" :alt="title" :style="imageStyle" draggable="false" />
      </div>
    </el-dialog>
  </figure>
</template>