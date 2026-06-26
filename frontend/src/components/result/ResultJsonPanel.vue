<script setup lang="ts">
import { useTaskStore } from '../../stores/taskStore'
import JsonViewer from '../artifacts/JsonViewer.vue'

const task = useTaskStore()
</script>

<template>
  <section class="card result-json-card">
    <div class="card-title">
      <span>最终空间观察结果</span>
      <el-tag size="small" effect="plain">SpatialSceneObservation</el-tag>
    </div>
    <JsonViewer v-if="task.resultJson" :content="task.resultJson" />
    <el-empty v-else description="点击读取结果查看最终 JSON" :image-size="72" />
  </section>
</template>
