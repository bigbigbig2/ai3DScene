<script setup lang="ts">
import { UploadFilled } from '@element-plus/icons-vue'
import { ref } from 'vue'
import { useTaskStore } from '../../stores/taskStore'
import RecentTasks from './RecentTasks.vue'

const task = useTaskStore()
const domain = ref('industrial_park')
const semanticMode = ref('manual')
const selectedFile = ref<File | null>(null)

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

async function createTask() {
  if (!selectedFile.value) return
  await task.create(selectedFile.value, domain.value, semanticMode.value)
}
</script>

<template>
  <section class="card">
    <div class="card-title">
      <span>任务输入</span>
      <el-tag size="small" effect="plain">上传图片</el-tag>
    </div>

    <label class="upload-box">
      <el-icon size="28"><UploadFilled /></el-icon>
      <span>{{ selectedFile?.name || '选择一张场景图片' }}</span>
      <input type="file" accept="image/*" @change="onFileChange" />
    </label>

    <div class="form-grid">
      <label>
        <span>场景领域 Domain</span>
        <el-input v-model="domain" />
        <small class="field-help">industrial_park = 工业园区 / 城市办公园区 / 商业综合体场景</small>
      </label>
      <label>
        <span>语义方式 Semantic Mode</span>
        <el-select v-model="semanticMode">
          <el-option label="手工语义提案 manual" value="manual" />
        </el-select>
        <small class="field-help">manual = 先由人工或外部 VLM 填写语义 JSON</small>
      </label>
    </div>

    <el-button type="primary" :loading="task.loading" :disabled="!selectedFile" @click="createTask">
      创建任务
    </el-button>

    <RecentTasks />
  </section>
</template>
