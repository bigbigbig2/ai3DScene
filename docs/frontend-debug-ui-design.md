# Scene Spatial PoC 前端调试台设计

本文档描述一个基于 Vue 3、Axios、Vite 的本地前端调试台设计。它主要用于调试当前服务端接口：

```text
http://10.7.3.50:8181/
```

前端目标不是做最终产品编辑器，而是先做一个工程调试工作台，用来完成第一阶段“一张图到空间观察结果”的闭环调试，并为后续阶段的编辑器执行、资源匹配、批量生成、人工修正留下界面位置。

## 1. 调试台目标

当前阶段要解决的问题：

1. 上传一张图片，创建后端任务。
2. 导入或编辑 `SceneSemanticProposal`。
3. 触发任务运行。
4. 观察每个 pipeline stage 的状态和产物。
5. 查看中间 artifact，例如输入图、mask、detections、MoGe 几何、ground/object/group/result JSON。
6. 对失败阶段快速定位错误。
7. 支持从某个阶段 rerun。
8. 支持提交人工修正，例如地面点、尺度锚点、对象 transform。
9. 后续扩展为三维预览和编辑器联调入口。

因此这个前端应该是“工程控制台”风格，而不是营销页或展示页。

## 2. 推荐技术栈

```text
Vue 3
Vite
TypeScript
Axios
Pinia
Vue Router
```

建议额外使用：

```text
Monaco Editor        JSON 编辑与查看
Element Plus         表单、表格、上传、弹窗、Tabs
VueUse               轮询、localStorage、快捷状态管理
Three.js             后续点云/三维空间预览
```

如果第一版想保持轻量，可以先只用：

```text
Vue 3 + TypeScript + Vite + Axios + Pinia + Element Plus
```

Three.js 和 Monaco 可以第二步接入。

## 3. 关键网络设计

后端目前没有 CORS 中间件。前端本地开发时不建议让浏览器直接请求：

```text
http://10.7.3.50:8181/api/v1/...
```

建议使用 Vite dev proxy：

```ts
// vite.config.ts
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://10.7.3.50:8181',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://10.7.3.50:8181',
        changeOrigin: true,
      },
      '/ready': {
        target: 'http://10.7.3.50:8181',
        changeOrigin: true,
      },
    },
  },
})
```

前端 Axios baseURL 使用相对路径：

```ts
const http = axios.create({
  baseURL: '',
  timeout: 30000,
})
```

这样前端调用：

```text
GET /health
GET /ready
POST /api/v1/tasks
```

浏览器看到的是本地 Vite 服务，不会遇到跨域问题。

生产或独立部署时有两种方式：

1. 在 Nginx 中把 `/api`、`/health`、`/ready` 反代到后端。
2. 给 FastAPI 增加 CORSMiddleware，允许前端域名访问。

调试阶段优先使用 Vite proxy。

## 4. 页面信息架构

建议第一版只有一个主页面，做成多面板工作台：

```text
Scene Spatial Debug Console
├─ 顶部服务栏
│  ├─ API Base URL
│  ├─ health / ready 状态
│  ├─ 当前 taskId
│  └─ 自动刷新开关
├─ 左侧任务与输入区
│  ├─ 图片上传
│  ├─ domain 选择
│  ├─ semantic mode
│  ├─ 创建任务
│  ├─ 任务状态卡片
│  └─ 最近 taskId 历史
├─ 中间阶段调试区
│  ├─ Pipeline timeline
│  ├─ 当前阶段详情
│  ├─ run / rerun 控制
│  └─ stage result JSON
└─ 右侧产物查看区
   ├─ Artifacts 列表
   ├─ 图片/mask 预览
   ├─ JSON 查看器
   ├─ result 查看
   └─ correction 表单
```

后续扩展三维预览时，可以把右侧产物查看区扩展成：

```text
Artifact / JSON / 2D Preview / 3D Preview / Corrections
```

## 5. 第一版主页面布局

推荐布局：

```text
┌─────────────────────────────────────────────────────────────────────┐
│ API: http://10.7.3.50:8181  Health ● Ready ●  Task: xxx  Auto Refresh │
├───────────────┬──────────────────────────────┬──────────────────────┤
│ Task Panel    │ Stage Timeline / Stage Detail │ Artifact Inspector   │
│               │                              │                      │
│ Upload        │ build_sam_tasks  completed   │ artifacts list        │
│ Domain        │ sam_segment      running     │ preview/json          │
│ Create        │ mask_postprocess pending     │ result                │
│ Semantic JSON │ ...                          │ corrections           │
│ Run           │                              │                      │
└───────────────┴──────────────────────────────┴──────────────────────┘
```

建议宽度：

```text
左侧 320px
中间 minmax(520px, 1fr)
右侧 480px
```

移动端不是主要目标，第一版按桌面调试台设计即可。

## 6. 核心功能模块

### 6.1 服务连接状态

顶部显示：

```text
API Target: http://10.7.3.50:8181
Health: OK / Failed
Ready: OK / Failed
Latency: xx ms
```

调用：

```text
GET /health
GET /ready
```

建议每 10 秒自动检查一次，也提供手动刷新按钮。

### 6.2 图片上传与任务创建

表单字段：

```text
file
domain
semanticMode
```

默认值：

```text
domain = wastewater
semanticMode = manual
```

调用：

```text
POST /api/v1/tasks
```

请求类型：

```text
multipart/form-data
```

创建成功后保存：

```text
taskId
taskDir
status
```

并自动：

```text
GET /api/v1/tasks/{taskId}
GET /api/v1/tasks/{taskId}/artifacts
```

### 6.3 语义提案编辑与导入

左侧或中间下方放一个 JSON 编辑器。

第一版可以提供一个模板按钮：

```json
{
  "schemaVersion": "1.0",
  "scene": {
    "sceneType": "wastewater_treatment_plant",
    "imageType": "oblique_aerial_view",
    "supportedDomain": true,
    "semanticConfidence": 0.8
  },
  "categoryProposals": [
    {
      "category": "building",
      "objectMode": "instance",
      "semanticConfidence": 0.8,
      "promptHints": ["building"],
      "expectedScale": "large",
      "visibleEvidence": []
    },
    {
      "category": "rectangular_treatment_pool",
      "objectMode": "instance",
      "semanticConfidence": 0.8,
      "promptHints": ["rectangular treatment pool"],
      "expectedScale": "large",
      "visibleEvidence": []
    },
    {
      "category": "road",
      "objectMode": "region",
      "semanticConfidence": 0.7,
      "promptHints": ["road"],
      "expectedScale": "large",
      "visibleEvidence": []
    },
    {
      "category": "ground",
      "objectMode": "region",
      "semanticConfidence": 0.7,
      "promptHints": ["ground"],
      "expectedScale": "large",
      "visibleEvidence": []
    }
  ],
  "patternHints": [
    {
      "category": "rectangular_treatment_pool",
      "patternType": "grid",
      "semanticConfidence": 0.6
    }
  ],
  "warnings": []
}
```

调用：

```text
POST /api/v1/tasks/{taskId}/semantic-proposal
```

导入成功后显示：

```text
validation
status
```

同时刷新任务状态和 artifacts。

### 6.4 运行与重跑

运行按钮：

```text
POST /api/v1/tasks/{taskId}/run
```

重跑按钮：

```text
POST /api/v1/tasks/{taskId}/rerun
{
  "fromStage": "ground_solve"
}
```

UI 上不要只给一个“重跑”按钮，应该在每个 stage 行上提供：

```text
从此阶段重跑
```

这样调试 `ground_solve`、`object_solve`、`group_solve` 会方便很多。

### 6.5 阶段 Timeline

当前后端状态接口只返回：

```text
taskId
status
currentStage
domain
inputImagePath
createdAt
updatedAt
errorCode
errorMessage
```

所以前端第一版可以基于固定 pipeline 和 task status 推断展示。

固定阶段：

```ts
const PIPELINE = [
  'build_sam_tasks',
  'sam_segment',
  'mask_postprocess',
  'moge_estimate',
  'pixel_align',
  'ground_solve',
  'object_solve',
  'group_solve',
  'export',
  'evaluate',
]
```

阶段状态推断：

```text
currentStage == stage        -> running
任务已完成且 artifact 存在       -> completed
任务 failed 且 currentStage == stage -> failed
还未执行                       -> pending
```

更准确的阶段状态可以通过 artifact 列表里的：

```text
stages/<stage>_attempt_1.json
```

读取 stage result JSON 后展示：

```text
status
duration_ms
outputs
metrics
warnings
error
```

### 6.6 Artifact Inspector

调用：

```text
GET /api/v1/tasks/{taskId}/artifacts
GET /api/v1/tasks/{taskId}/artifacts/{artifactId}
```

列表字段：

```text
id
stageName
artifactType
relativePath
mimeType
sizeBytes
createdAt
```

UI 分组方式：

```text
All
Input
Semantic
Detection
Geometry
Spatial
Evaluation
Logs
```

预览策略：

| 类型 | 预览方式 |
| --- | --- |
| image/png、image/jpeg | 直接 `<img>` |
| application/json | JSON viewer |
| text/plain、log | text viewer |
| npy | 第一版只显示下载/路径；后续后端可增加转换接口 |
| ply | 后续 Three.js 点云预览 |
| directory | 显示目录 artifact 说明，不直接预览 |

第一版最重要的 artifact：

```text
semantic/normalized_proposal.json
semantic/sam_tasks.json
detection/detections.json
geometry/pixel_mapping.json
spatial/ground.json
spatial/coordinate_system.json
spatial/objects.json
spatial/roads.json
spatial/groups.json
spatial/spatial_scene_observation.json
evaluation/metrics.json
stages/<stage>_attempt_1.json
```

### 6.7 Result 查看

调用：

```text
GET /api/v1/tasks/{taskId}/result
```

展示方式：

1. 总览卡片：
   - objects 数量
   - roads 数量
   - groups 数量
   - schemaVersion
2. JSON 原文。
3. 后续增加 2D/3D 可视化。

如果接口返回 404，显示：

```text
Result is not available yet
```

这不是错误，而是任务还没跑到 export。

### 6.8 Corrections 调试

当前后端支持：

```text
POST /api/v1/tasks/{taskId}/corrections/ground-points
POST /api/v1/tasks/{taskId}/corrections/scale-anchor
POST /api/v1/tasks/{taskId}/corrections/object-transform
```

第一版 UI 可以先做 JSON payload 表单：

```text
correction type 下拉框
payload JSON editor
submit
submit 后刷新 artifacts/task status
```

后续再做可视化交互：

```text
图片上点选地面点
图片上点选尺度锚点
对象 transform gizmo
```

## 7. 推荐前端目录结构

建议在项目根目录新建：

```text
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.ts
    App.vue
    styles/
      base.css
      layout.css
    router/
      index.ts
    stores/
      taskStore.ts
      connectionStore.ts
    api/
      http.ts
      health.ts
      tasks.ts
      semantic.ts
      artifacts.ts
      corrections.ts
      types.ts
    constants/
      pipeline.ts
      semanticTemplates.ts
    views/
      DebugWorkbench.vue
    components/
      connection/
        ServiceStatusBar.vue
      task/
        TaskCreatePanel.vue
        TaskStatusCard.vue
        RecentTasks.vue
      semantic/
        SemanticProposalEditor.vue
      stages/
        PipelineTimeline.vue
        StageDetailPanel.vue
        StageResultViewer.vue
      artifacts/
        ArtifactList.vue
        ArtifactPreview.vue
        JsonViewer.vue
        ImagePreview.vue
        TextPreview.vue
      result/
        ResultSummary.vue
        ResultJsonPanel.vue
      corrections/
        CorrectionPanel.vue
```

第一版可以只做一个 route：

```text
/
```

后续再拆：

```text
/tasks/:taskId
/tasks/:taskId/artifacts
/tasks/:taskId/preview
```

## 8. 前端 API 封装设计

类型定义：

```ts
export interface CreateTaskResponse {
  taskId: string
  status: string
  taskDir: string
}

export interface TaskStatusResponse {
  taskId: string
  status: string
  currentStage: string | null
  domain: string
  inputImagePath: string
  createdAt: string
  updatedAt: string
  errorCode?: string | null
  errorMessage?: string | null
}

export interface ArtifactItem {
  id: number
  stageName: string
  artifactType: string
  relativePath: string
  mimeType?: string | null
  sizeBytes?: number | null
  createdAt: string
}
```

API 方法：

```ts
createTask(file: File, domain: string, semanticMode: string)
getTask(taskId: string)
runTask(taskId: string)
rerunTask(taskId: string, fromStage: string)
importSemanticProposal(taskId: string, proposal: unknown)
listArtifacts(taskId: string)
getArtifactBlob(taskId: string, artifactId: number)
getResult(taskId: string)
submitCorrection(taskId: string, type: CorrectionType, payload: unknown)
```

轮询策略：

```text
任务处于 QUEUED/RUNNING/阶段状态时，每 2 秒刷新任务状态。
每 4 秒刷新 artifacts。
任务 COMPLETED/FAILED 后停止自动轮询。
用户可以手动刷新。
```

## 9. UI 状态设计

全局 store 建议拆成两个：

```text
connectionStore
taskStore
```

`connectionStore`：

```text
health
ready
latencyMs
lastCheckedAt
checking
error
```

`taskStore`：

```text
currentTaskId
taskStatus
artifacts
selectedArtifactId
selectedStage
semanticProposalDraft
autoRefresh
recentTaskIds
loading flags
errors
```

`recentTaskIds` 放 localStorage，方便刷新页面后继续看刚才任务。

## 10. 第一阶段最小可用版本

建议第一版先做这些功能：

1. 服务状态栏：`/health`、`/ready`。
2. 上传图片创建任务。
3. 语义 JSON 模板编辑和导入。
4. 运行任务。
5. 自动轮询任务状态。
6. Pipeline timeline。
7. Artifact 列表。
8. 图片/JSON/日志预览。
9. Result JSON 查看。
10. 从指定 stage rerun。

暂时不做：

```text
三维点云预览
mask 叠加绘制
人工点选地面点
复杂对象编辑
多任务批处理
登录鉴权
```

这些等后端真模型链路稳定后再加。

## 11. 第二阶段增强

后续可以继续加：

1. 图片 + mask overlay。
2. detection bbox 可视化。
3. ground plane 可视化。
4. object anchor 投影到图片。
5. road centerline 叠加显示。
6. group/grid 叠加显示。
7. Three.js 点云预览。
8. object transform 可视化编辑。
9. correction 提交后自动 rerun。
10. 多任务对比和回归测试面板。

这时前端就会从“调试台”逐步演进到“半编辑器”。

## 12. 后端可能需要补的接口

当前后端接口已经够第一版使用，但为了更好调试，后续建议补几个接口：

```text
GET /api/v1/tasks
```

用于查看最近任务列表。

```text
GET /api/v1/tasks/{task_id}/stage-runs
```

直接返回每个 stage 的运行记录，避免前端从 artifacts 里猜。

```text
GET /api/v1/tasks/{task_id}/artifacts/by-path?path=...
```

方便按固定路径拿 artifact。

```text
GET /api/v1/tasks/{task_id}/preview/mask-overlay
GET /api/v1/tasks/{task_id}/preview/detections
GET /api/v1/tasks/{task_id}/preview/pointcloud
```

用于前端直接展示可视化结果，而不是读取 `.npy` 自己解析。

```text
GET /api/v1/runtime/config
```

让前端知道当前 fake/real 模型模式、服务器路径、版本等。

这些不是第一版必须项，但会显著提升调试体验。

## 13. 推荐实现顺序

前端实现建议分 5 步：

```text
Step 1: Vite + Vue3 + Axios 项目骨架
Step 2: 服务状态栏 + API proxy
Step 3: 任务创建、语义导入、运行、轮询
Step 4: Pipeline timeline + artifact inspector
Step 5: result/correction/rerun 调试能力
```

完成 Step 4 后，已经可以支撑第一阶段大部分调试工作。

## 14. 页面风格建议

这是工程调试工具，建议视觉上克制、信息密度高：

```text
浅色背景
左中右三栏
阶段状态用颜色点/标签
按钮尽量短
JSON 和日志使用等宽字体
错误信息明显展示
重要操作如 rerun/submit correction 需要二次确认
```

阶段状态颜色：

```text
pending     gray
running     blue
completed   green
failed      red
skipped     slate
```

不要做大 hero 页。打开页面后第一屏就应该是可操作的调试台。

## 15. 一句话方案

第一版前端就做成“任务调试工作台”：左边上传和语义输入，中间看 pipeline 阶段，右边看 artifact/result/correction。它先服务于后端和模型链路调试，等真实 SAM/MoGe 和空间求解稳定后，再逐步扩展成可视化编辑器。
