<script setup lang="ts">
import { useTaskStore } from '../../stores/taskStore'

const task = useTaskStore()
</script>

<template>
  <div v-if="task.recentTaskIds.length" class="recent-tasks">
    <span class="section-label">最近任务</span>
    <button
      v-for="taskId in task.recentTaskIds"
      :key="taskId"
      class="recent-task"
      type="button"
      @click="task.loadTask(taskId).then(() => task.loadArtifacts())"
    >
      {{ taskId }}
    </button>
  </div>
</template>
