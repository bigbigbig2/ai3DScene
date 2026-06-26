<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useConnectionStore } from '../../stores/connectionStore'
import { useTaskStore } from '../../stores/taskStore'

const connection = useConnectionStore()
const task = useTaskStore()

const statusClass = computed(() => `status-${connection.overallState}`)
</script>

<template>
  <header class="service-bar">
    <div>
      <div class="eyebrow">Scene Spatial Debug Console</div>
      <strong>第一阶段调试工作台</strong>
    </div>

    <div class="service-bar-main">
      <span class="api-target">后端服务 API {{ connection.apiTargetLabel }}</span>
      <span class="status-pill" :class="statusClass">健康检查 {{ connection.healthOk ? 'OK' : 'FAIL' }}</span>
      <span class="status-pill" :class="statusClass">就绪状态 {{ connection.readyOk ? 'OK' : 'FAIL' }}</span>
      <span v-if="connection.latencyMs !== null" class="muted">{{ connection.latencyMs }} ms</span>
      <span class="task-chip">当前任务 {{ task.currentTaskId || '-' }}</span>
    </div>

    <div class="service-actions">
      <el-switch v-model="task.autoRefresh" active-text="自动刷新" />
      <el-button :icon="Refresh" :loading="connection.checking" @click="connection.check">
        检查服务
      </el-button>
    </div>
  </header>
</template>
