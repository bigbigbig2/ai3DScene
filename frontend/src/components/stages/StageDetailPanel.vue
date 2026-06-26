<script setup lang="ts">
import { computed } from 'vue'
import { stageDisplay, stageResultPath } from '../../constants/pipeline'
import { useTaskStore } from '../../stores/taskStore'
import StageResultViewer from './StageResultViewer.vue'

const task = useTaskStore()

const selectedArtifact = computed(() =>
  task.artifacts.find((artifact) => artifact.relativePath === stageResultPath(task.selectedStage)),
)

const display = computed(() => stageDisplay(task.selectedStage))
</script>

<template>
  <section class="card stage-detail">
    <div class="card-title">
      <span>阶段详情</span>
      <el-tag size="small">{{ task.selectedStage }}</el-tag>
    </div>

    <dl class="meta-list compact">
      <dt>阶段名称</dt>
      <dd>{{ display.title }}</dd>
      <dt>阶段说明</dt>
      <dd>{{ display.description }}</dd>
      <dt>结果文件</dt>
      <dd>{{ selectedArtifact?.relativePath || '暂未生成' }}</dd>
      <dt>产物 ID</dt>
      <dd>{{ selectedArtifact?.id || '-' }}</dd>
    </dl>

    <StageResultViewer />
  </section>
</template>
