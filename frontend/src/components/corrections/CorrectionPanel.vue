<script setup lang="ts">
import { Position, Select } from '@element-plus/icons-vue'
import { ref } from 'vue'
import type { CorrectionType } from '../../api/types'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()
const correctionType = ref<CorrectionType>('ground-points')

const options: Array<{ label: string; value: CorrectionType }> = [
  { label: '地面点修正 ground-points', value: 'ground-points' },
  { label: '尺度锚点 scale-anchor', value: 'scale-anchor' },
  { label: '对象位姿 object-transform', value: 'object-transform' },
]
</script>

<template>
  <section class="card correction-card">
    <div class="card-title">
      <span>人工修正</span>
      <el-tag size="small" effect="plain">Corrections</el-tag>
    </div>

    <el-select v-model="correctionType">
      <el-option
        v-for="option in options"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>

    <el-input
      v-model="task.correctionPayloadDraft"
      type="textarea"
      resize="vertical"
      :autosize="{ minRows: 7, maxRows: 12 }"
      spellcheck="false"
      class="code-input"
      placeholder="填写要提交给后端 corrections 接口的 JSON payload"
    />

    <div class="button-row">
      <el-button
        type="primary"
        :icon="Select"
        :loading="task.loading"
        :disabled="!task.currentTaskId"
        @click="task.submitCorrection(correctionType)"
      >
        提交修正
      </el-button>
      <el-button :icon="Position" :disabled="!task.currentTaskId" @click="task.rerunFrom('ground_solve')">
        修正后重跑空间求解
      </el-button>
    </div>
  </section>
</template>
