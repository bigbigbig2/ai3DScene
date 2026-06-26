<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { useTaskStore } from '../../stores/taskStore'
import JsonViewer from '../artifacts/JsonViewer.vue'

const task = useTaskStore()
</script>

<template>
  <div class="stage-result-viewer">
    <div class="subsection-title">
      <span>阶段运行记录 JSON</span>
      <el-button :icon="Refresh" size="small" text @click="task.loadSelectedStageResult">刷新</el-button>
    </div>
    <JsonViewer v-if="task.stageResultJson" :content="task.stageResultJson" />
    <el-empty v-else description="该阶段还没有运行记录文件" :image-size="72" />
  </div>
</template>
