<script setup lang="ts">
import { DocumentChecked, RefreshLeft } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()

const canImport = computed(() => Boolean(task.currentTaskId))
</script>

<template>
  <section class="card semantic-editor">
    <div class="card-title">
      <span>语义提案 JSON</span>
      <el-button :icon="RefreshLeft" size="small" text @click="task.setSemanticTemplate">
        模板
      </el-button>
    </div>

    <el-input
      v-model="task.semanticProposalDraft"
      type="textarea"
      resize="vertical"
      :autosize="{ minRows: 12, maxRows: 18 }"
      spellcheck="false"
      class="code-input"
    />

    <el-button
      type="primary"
      :icon="DocumentChecked"
      :disabled="!canImport"
      :loading="task.loading"
      @click="task.importSemanticDraft"
    >
      导入语义提案
    </el-button>
  </section>
</template>
