<script setup lang="ts">
defineProps<{
  src: string
  title: string
}>()
</script>

<template>
  <figure class="image-preview">
    <img :src="src" :alt="title" />
    <figcaption>{{ title }}</figcaption>
  </figure>
</template>
