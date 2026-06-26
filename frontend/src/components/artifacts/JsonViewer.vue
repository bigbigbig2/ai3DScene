<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <pre class="code-viewer">{{ content }}</pre>
</template>
