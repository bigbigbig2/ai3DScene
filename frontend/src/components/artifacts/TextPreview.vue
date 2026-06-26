<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <pre class="text-viewer">{{ content }}</pre>
</template>
