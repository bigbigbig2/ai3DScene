<script setup lang="ts">
import { DataAnalysis, Refresh } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()

const summary = computed(() => {
  if (!task.resultJson) return null
  try {
    const parsed = JSON.parse(task.resultJson) as Record<string, unknown>
    const objects = Array.isArray(parsed.objects) ? parsed.objects.length : 0
    const roads = Array.isArray(parsed.roads) ? parsed.roads.length : 0
    const groups = Array.isArray(parsed.groups) ? parsed.groups.length : 0
    return {
      schemaVersion: String(parsed.schemaVersion ?? '-'),
      objects,
      roads,
      groups,
    }
  } catch {
    return null
  }
})
</script>

<template>
  <section class="card">
    <div class="card-title">
      <span>最终结果摘要</span>
      <el-button :icon="Refresh" size="small" text @click="task.loadResult">读取结果</el-button>
    </div>

    <div v-if="summary" class="summary-grid">
      <div>
        <el-icon><DataAnalysis /></el-icon>
        <strong>{{ summary.objects }}</strong>
        <span>对象 Objects</span>
      </div>
      <div>
        <strong>{{ summary.roads }}</strong>
        <span>道路 Roads</span>
      </div>
      <div>
        <strong>{{ summary.groups }}</strong>
        <span>组/阵列 Groups</span>
      </div>
      <div>
        <strong>{{ summary.schemaVersion }}</strong>
        <span>结构版本 Schema</span>
      </div>
    </div>

    <el-empty v-else description="结果尚未读取或尚未生成" :image-size="72" />
  </section>
</template>
