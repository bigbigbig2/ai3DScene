<script setup lang="ts">
import { RefreshRight } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed } from 'vue'
import { PIPELINE, STATUS_LABELS, inferStageStatus, stageDisplay } from '../../constants/pipeline'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()

const rows = computed(() =>
  PIPELINE.map((stage, index) => {
    const display = stageDisplay(stage)
    const status = inferStageStatus(stage, task.taskStatus, task.artifacts)
    return {
      stage,
      index: index + 1,
      title: display.title,
      description: display.description,
      status,
      statusLabel: STATUS_LABELS[status],
    }
  }),
)

async function confirmRerun(stage: string, title: string) {
  await ElMessageBox.confirm(`确认从「${title}」阶段重新入队运行？`, '从指定阶段重跑', {
    type: 'warning',
    confirmButtonText: '重跑',
    cancelButtonText: '取消',
  })
  await task.rerunFrom(stage)
}
</script>

<template>
  <section class="card">
    <div class="card-title">
      <span>处理流水线</span>
      <el-tag size="small" effect="plain">{{ task.artifacts.length }} 个阶段产物</el-tag>
    </div>

    <div class="timeline-list">
      <button
        v-for="row in rows"
        :key="row.stage"
        class="stage-row"
        :class="[`stage-${row.status}`, { active: task.selectedStage === row.stage }]"
        type="button"
        @click="task.setSelectedStage(row.stage)"
      >
        <span class="stage-index">{{ row.index }}</span>
        <span class="stage-main">
          <strong>{{ row.title }}</strong>
          <small>{{ row.stage }} · {{ row.description }}</small>
        </span>
        <span class="stage-status">{{ row.statusLabel }}</span>
        <el-button
          :icon="RefreshRight"
          size="small"
          text
          @click.stop="confirmRerun(row.stage, row.title)"
        >
          从此重跑
        </el-button>
      </button>
    </div>
  </section>
</template>
