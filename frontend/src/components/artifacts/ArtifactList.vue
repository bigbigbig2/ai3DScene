<script setup lang="ts">
import { Refresh, Search } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import type { ArtifactItem } from '../../api/types'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()
const query = ref('')
const group = ref('all')

const groups = [
  { key: 'all', label: '全部' },
  { key: 'input', label: '输入' },
  { key: 'semantic', label: '语义' },
  { key: 'detection', label: '检测/分割' },
  { key: 'geometry', label: '几何' },
  { key: 'spatial', label: '空间结果' },
  { key: 'evaluation', label: '评估' },
  { key: 'logs', label: '日志' },
] as const

const filteredArtifacts = computed(() => {
  const source = task.artifactGroups[group.value as keyof typeof task.artifactGroups] ?? task.artifacts
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return source
  return source.filter((artifact: ArtifactItem) =>
    `${artifact.relativePath} ${artifact.stageName} ${artifact.artifactType}`
      .toLowerCase()
      .includes(keyword),
  )
})

function formatSize(value?: number | null) {
  if (!value) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <section class="card artifact-list-card">
    <div class="card-title">
      <span>阶段产物</span>
      <el-button :icon="Refresh" size="small" text @click="task.loadArtifacts">刷新</el-button>
    </div>

    <el-input v-model="query" :prefix-icon="Search" placeholder="搜索路径 / 阶段 / 类型" clearable />

    <div class="artifact-groups">
      <button
        v-for="item in groups"
        :key="item.key"
        class="group-tab"
        :class="{ active: group === item.key }"
        type="button"
        @click="group = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="artifact-list">
      <button
        v-for="artifact in filteredArtifacts"
        :key="artifact.id"
        class="artifact-row"
        :class="{ active: task.selectedArtifactId === artifact.id }"
        type="button"
        @click="task.previewArtifact(artifact)"
      >
        <span>
          <strong>{{ artifact.relativePath }}</strong>
          <small>{{ artifact.stageName }} · {{ artifact.artifactType }} · {{ formatSize(artifact.sizeBytes) }}</small>
        </span>
      </button>
      <el-empty v-if="!filteredArtifacts.length" description="暂无阶段产物" :image-size="72" />
    </div>
  </section>
</template>
