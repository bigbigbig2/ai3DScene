<script setup lang="ts">
import { useTaskStore } from '../../stores/taskStore'
import ImagePreview from './ImagePreview.vue'
import JsonViewer from './JsonViewer.vue'
import TextPreview from './TextPreview.vue'

const task = useTaskStore()
</script>

<template>
  <section class="card artifact-preview-card">
    <div class="card-title">
      <span>产物预览</span>
      <el-tag v-if="task.selectedArtifact" size="small" effect="plain">
        #{{ task.selectedArtifact.id }}
      </el-tag>
    </div>

    <el-skeleton v-if="task.artifactLoading" animated :rows="5" />

    <template v-else>
      <ImagePreview
        v-if="task.selectedArtifactPreview.kind === 'image' && task.selectedArtifactPreview.objectUrl"
        :src="task.selectedArtifactPreview.objectUrl"
        :title="task.selectedArtifactPreview.title"
      />
      <JsonViewer
        v-else-if="task.selectedArtifactPreview.kind === 'json' && task.selectedArtifactPreview.content"
        :content="task.selectedArtifactPreview.content"
      />
      <TextPreview
        v-else-if="task.selectedArtifactPreview.content"
        :content="task.selectedArtifactPreview.content"
      />
      <el-alert
        v-else-if="task.selectedArtifactPreview.kind === 'error'"
        type="error"
        :title="task.selectedArtifactPreview.error || '预览失败'"
        show-icon
        :closable="false"
      />
      <el-empty v-else description="选择阶段产物后预览" :image-size="72" />
    </template>
  </section>
</template>
