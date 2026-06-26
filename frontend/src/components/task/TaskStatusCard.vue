<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { stageDisplay } from '../../constants/pipeline'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()

const statusType = computed(() => {
  if (!task.taskStatus) return 'info'
  if (task.taskStatus.status === 'COMPLETED') return 'success'
  if (task.taskStatus.status === 'FAILED') return 'danger'
  if (task.isTaskActive) return 'primary'
  return 'warning'
})

const currentStageTitle = computed(() => {
  if (!task.taskStatus?.currentStage) return '-'
  return `${stageDisplay(task.taskStatus.currentStage).title} (${task.taskStatus.currentStage})`
})

const canRunTask = computed(() => task.taskStatus?.status === 'SEMANTIC_READY')

const runHint = computed(() => {
  if (!task.taskStatus) return ''
  if (task.taskStatus.status === 'WAITING_SEMANTIC_PROPOSAL') return '请先导入语义提案'
  if (task.taskStatus.status === 'COMPLETED') return '任务已完成，可读取最终结果或从某个阶段重跑'
  if (task.taskStatus.status === 'FAILED') return '任务失败，可查看错误或从失败阶段重跑'
  if (task.isTaskActive) return '任务正在运行或排队中'
  return ''
})
</script>

<template>
  <section class="card">
    <div class="card-title">
      <span>任务状态</span>
      <el-button :icon="Refresh" size="small" text @click="task.refreshAll">刷新</el-button>
    </div>

    <template v-if="task.taskStatus">
      <el-tag :type="statusType" effect="dark">{{ task.taskStatus.status }}</el-tag>
      <dl class="meta-list">
        <dt>任务 ID</dt>
        <dd>{{ task.taskStatus.taskId }}</dd>
        <dt>当前阶段</dt>
        <dd>{{ currentStageTitle }}</dd>
        <dt>场景领域</dt>
        <dd>{{ task.taskStatus.domain }}</dd>
        <dt>更新时间</dt>
        <dd>{{ task.taskStatus.updatedAt || '-' }}</dd>
      </dl>
      <el-alert
        v-if="task.taskStatus.errorMessage"
        type="error"
        :title="task.taskStatus.errorCode || '任务失败'"
        :description="task.taskStatus.errorMessage"
        show-icon
        :closable="false"
      />
      <div class="button-row">
        <el-button type="primary" :loading="task.loading" :disabled="!canRunTask" @click="task.runCurrentTask">
          运行任务
        </el-button>
        <el-button @click="task.loadResult">读取最终结果</el-button>
      </div>
      <p v-if="runHint" class="field-help">{{ runHint }}</p>
    </template>

    <el-empty v-else description="还没有选择任务" :image-size="72" />

    <el-alert v-if="task.error" type="error" :title="task.error" show-icon :closable="false" />
    <el-alert v-if="task.message" type="success" :title="task.message" show-icon :closable="false" />
  </section>
</template>
