<script setup lang="ts">
import { onMounted, watch } from 'vue'
import ArtifactList from '../components/artifacts/ArtifactList.vue'
import ArtifactPreview from '../components/artifacts/ArtifactPreview.vue'
import CorrectionPanel from '../components/corrections/CorrectionPanel.vue'
import ServiceStatusBar from '../components/connection/ServiceStatusBar.vue'
import ResultJsonPanel from '../components/result/ResultJsonPanel.vue'
import ScenePreview3D from '../components/three/ScenePreview3D.vue'
import ResultSummary from '../components/result/ResultSummary.vue'
import SemanticProposalEditor from '../components/semantic/SemanticProposalEditor.vue'
import PipelineTimeline from '../components/stages/PipelineTimeline.vue'
import StageDetailPanel from '../components/stages/StageDetailPanel.vue'
import TaskCreatePanel from '../components/task/TaskCreatePanel.vue'
import TaskStatusCard from '../components/task/TaskStatusCard.vue'
import { useConnectionStore } from '../stores/connectionStore'
import { useTaskStore } from '../stores/taskStore'

const connection = useConnectionStore()
const task = useTaskStore()

onMounted(() => {
  void connection.check()
})

watch(
  () => task.autoRefresh,
  (enabled) => {
    if (enabled) {
      task.ensurePolling()
    } else {
      task.stopPolling()
    }
  },
)
</script>

<template>
  <div class="app-shell">
    <ServiceStatusBar />

    <main class="workbench-grid">
      <aside class="panel panel-left">
        <TaskCreatePanel />
        <TaskStatusCard />
        <SemanticProposalEditor />
      </aside>

      <section class="panel panel-center">
        <PipelineTimeline />
        <StageDetailPanel />
      </section>

      <aside class="panel panel-right">
        <ArtifactList />
        <ArtifactPreview />
        <ResultSummary />
        <ScenePreview3D />
        <ResultJsonPanel />
        <CorrectionPanel />
      </aside>
    </main>
  </div>
</template>


