# Scene Spatial PoC 当前工程详细说明

本文档用于说明当前 `scene-spatial-poc` 工程已经搭建到什么程度、各模块如何协作、如何在服务器上部署验证，以及后续接入真实模型和完善算法时应该从哪里入手。

当前工程以 `scene-spatial-poc-工程架构与启动实施方案-中等规模版.md` 为主设计依据。`第一阶段-场景理解与三维空间落点验证-手工语义提案与本地模型实施方案.md` 作为语义、空间求解和验收细节的补充参考。

## 1. 项目定位

这个工程的目标是搭建一个单机可部署的场景空间理解 PoC 后端，输入一张场景图片，通过语义提案、SAM 分割、MoGe 几何估计和本地空间求解，输出一个结构化的 `SpatialSceneObservation` 结果。

当前重点不是做编辑器前端，而是先把后端流水线跑通：

```text
上传图片
  -> 创建任务
  -> 导入语义提案
  -> 生成 SAM 分割任务
  -> SAM 产出 mask/detection
  -> MoGe 产出 depth/points/normals/camera
  -> 像素对齐
  -> 地面/坐标系求解
  -> 对象空间落点、尺寸、朝向求解
  -> 道路、阵列/组关系求解
  -> 导出空间观察结果
  -> 评估和人工修正
```

当前工程已经具备完整后端骨架、任务生命周期、Fake Pipeline、模型子进程协议、第一版真实空间求解算法和服务器部署材料。真实 SAM/MoGe 模型主体还需要在服务器环境里补齐。

## 2. 当前完成度总览

| 模块 | 当前状态 | 说明 |
| --- | --- | --- |
| 工程骨架 | 已完成 | FastAPI、SQLAlchemy、SQLite、Alembic、配置、运行目录、日志、artifact 存储已搭建 |
| API 接口 | 已完成基础版 | 任务创建、状态查询、语义导入、运行/重跑、结果/artifact 查询、修正接口已实现 |
| Worker | 已完成基础版 | 支持 SQLite 队列、任务 claim、heartbeat、超时恢复、stage run 记录 |
| Fake Pipeline | 已完成 | 可在不接 GPU 模型时跑完整任务生命周期 |
| SAM 接入协议 | 已完成协议，待真实模型体 | 已实现 request/response 文件协议和子进程调用 |
| MoGe 接入协议 | 已完成协议，待真实模型体 | 已实现 request/response 文件协议和子进程调用 |
| 空间求解 | 已实现第一版 | 包含 pixel align、ground、object、road、group、evaluate |
| 部署脚本 | 已完成基础版 | 提供 API/Worker 启动脚本、systemd service、服务器下一步文档 |
| 测试 | 已写基础测试 | 因当前本地 Windows Python 不可用，尚未在本机执行验证 |
| 编辑器前端 | 未实现 | 当前明确暂不做，后续可消费后端导出的 JSON 和 artifacts |

## 3. 技术栈

核心依赖：

```text
Python >= 3.11
FastAPI
Uvicorn
Pydantic v2
pydantic-settings
SQLAlchemy 2
Alembic
Pillow
PyYAML
NumPy
```

开发与测试依赖：

```text
pytest
httpx
pytest-cov
```

几何增强依赖：

```text
OpenCV
Open3D
SciPy
scikit-image
```

核心工程包使用 `src/` 布局：

```text
src/scene_spatial/
```

命令入口：

```text
scene-spatial
scene-spatial-worker
```

## 4. 总体架构

工程采用单机模块化后端架构，运行时分为三类进程：

```text
FastAPI API process
Pipeline Worker process
Short-lived SAM / MoGe model subprocesses
```

设计原则：

1. API 进程只处理 HTTP 请求、数据库状态和轻量文件操作，不加载 SAM、MoGe、Torch 或重型几何依赖。
2. Worker 进程负责从 SQLite 队列 claim 任务，并按 pipeline 执行各阶段。
3. SAM/MoGe 作为短生命周期子进程被 Worker 调起，通过 JSON 文件协议交换输入输出。
4. 大文件放磁盘，SQLite 只保存任务状态、artifact 路径、错误、阶段耗时、置信度等轻量元数据。
5. 每个任务拥有独立 artifact 目录，便于排查、重跑和后续人工审核。

## 5. 目录结构说明

主要目录：

```text
configs/                  领域、类别、模型、阈值配置
deploy/systemd/           服务器 systemd service 文件
docs/                     工程说明、部署说明、实现审计
migrations/               Alembic 数据库迁移
model_workers/            SAM/MoGe 子进程 worker
schemas/                  API 和模型文件协议 JSON Schema
scripts/                  启动、验证、smoke、GPU 检查脚本
src/scene_spatial/        核心后端代码
tests/                    单元测试和集成测试
```

核心代码目录：

```text
api/                      FastAPI app、依赖注入、HTTP routes
application/              应用服务、pipeline 编排、stage 注册
domain/                   Pydantic 领域模型、枚举、错误类型
infrastructure/           数据库、仓储、artifact、GPU lock、子进程等基础设施
perception/               图片预处理、tile、mask 后处理、detection 合并
semantics/                语义提案校验、归一化、SAM task 生成
spatial/                  空间算法工具和边界模块
stages/                   pipeline stage 实现
visualization/            后端可视化 artifact 辅助模块
worker/                   任务 claim、heartbeat、recovery、worker main
```

## 6. 运行目录和环境变量

默认本地运行目录在：

```text
.runtime/
```

默认服务器路径规划：

```text
/home/ai3d/src/scene-spatial-poc
/home/ai3d/data/scene-spatial
/home/ai3d/inputs/scene-spatial
/home/ai3d/outputs/scene-spatial
/home/ai3d/logs/scene-spatial
/home/ai3d/tmp/scene-spatial
/home/ai3d/models/scene-spatial
```

主要环境变量使用 `SCENE_` 前缀：

```text
SCENE_ENV
SCENE_DATABASE_URL
SCENE_OUTPUT_ROOT
SCENE_INPUT_ROOT
SCENE_LOG_ROOT
SCENE_TMP_ROOT
SCENE_GPU_PHYSICAL_ID
SCENE_SAM_PYTHON
SCENE_MOGE_PYTHON
SCENE_SAM_WORKER
SCENE_MOGE_WORKER
SCENE_WORKER_POLL_SECONDS
SCENE_TASK_LEASE_SECONDS
SCENE_FAKE_MODELS
```

其中：

```text
SCENE_FAKE_MODELS=true
```

表示不调用真实 SAM/MoGe，而使用 Fake Pipeline 产物，适合先验证工程链路。

```text
SCENE_FAKE_MODELS=false
```

表示 Worker 会调用 `model_workers/sam3_worker.py` 和 `model_workers/moge2_worker.py` 对应的真实子进程逻辑。

## 7. API 接口

API 前缀：

```text
/api/v1
```

健康检查：

```text
GET /health
GET /ready
```

任务接口：

```text
POST /api/v1/tasks
GET  /api/v1/tasks/{task_id}
POST /api/v1/tasks/{task_id}/run
POST /api/v1/tasks/{task_id}/rerun
```

语义提案接口：

```text
POST /api/v1/tasks/{task_id}/semantic-proposal
```

结果和 artifact：

```text
GET /api/v1/tasks/{task_id}/artifacts
GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}
GET /api/v1/tasks/{task_id}/result
```

人工修正接口：

```text
POST /api/v1/tasks/{task_id}/corrections/ground-points
POST /api/v1/tasks/{task_id}/corrections/scale-anchor
POST /api/v1/tasks/{task_id}/corrections/object-transform
```

创建任务时使用 multipart form：

```text
file           上传图片
domain         领域名，例如 wastewater
semantic_mode  manual，默认 manual
```

## 8. 任务状态

主要任务状态包含：

```text
CREATED
PREPROCESSING
WAITING_SEMANTIC_PROPOSAL
SEMANTIC_VALIDATING
SEMANTIC_READY
QUEUED
RUNNING
BUILDING_SAM_TASKS
SEGMENTING
MASK_POSTPROCESSING
GEOMETRY_ESTIMATING
PIXEL_ALIGNING
GROUND_SOLVING
OBJECT_SOLVING
GROUP_SOLVING
EXPORTING
EVALUATING
PREVIEW_READY
COMPLETED
FAILED
CANCELLED
WAITING_MANUAL_GROUND
WAITING_SCALE_ANCHOR
```

典型流转：

```text
CREATED
  -> WAITING_SEMANTIC_PROPOSAL
  -> SEMANTIC_READY
  -> QUEUED
  -> RUNNING
  -> COMPLETED
```

如果某个 stage 失败，任务进入 `FAILED`，并记录错误信息。后续可以通过 rerun 接口从指定阶段重新执行。

## 9. Pipeline 阶段

当前 pipeline 定义在：

```text
src/scene_spatial/application/pipeline_definition.py
```

阶段顺序：

```text
build_sam_tasks
sam_segment
mask_postprocess
moge_estimate
pixel_align
ground_solve
object_solve
group_solve
export
evaluate
```

阶段注册在：

```text
src/scene_spatial/application/stage_registry.py
```

当前 stage 实现来源：

| Stage | 实现位置 | 当前说明 |
| --- | --- | --- |
| build_sam_tasks | `stages/fake_pipeline.py` | 从语义提案生成 SAM task |
| sam_segment | `stages/model_stages.py` | Fake 模式走 fake；真实模式调用 SAM worker |
| mask_postprocess | `stages/fake_pipeline.py` | mask 后处理占位实现 |
| moge_estimate | `stages/model_stages.py` | Fake 模式走 fake；真实模式调用 MoGe worker |
| pixel_align | `stages/spatial_solve.py` | 记录 SAM/MoGe 尺寸映射关系 |
| ground_solve | `stages/spatial_solve.py` | 基于 mask 和 point map 拟合地面平面 |
| object_solve | `stages/spatial_solve.py` | 计算对象锚点、尺寸、朝向、road |
| group_solve | `stages/spatial_solve.py` | 基于对象中心做 row/grid 分组估计 |
| export | `stages/fake_pipeline.py` | 导出 `spatial_scene_observation.json` |
| evaluate | `stages/spatial_solve.py` | 生成基础 evaluation metrics |

## 10. Artifact 目录

每个任务一个独立目录：

```text
outputs/<task_id>/
  task.json
  config_snapshot/
  stages/
  input/
  semantic/
  detection/
  geometry/
  pointcloud/
  spatial/
  visualizations/
  evaluation/
  logs/
```

典型产物：

```text
input/original.*
input/semantic_input.png
input/sam_full.png
input/moge_input.png
input/metadata.json

semantic/raw_proposal.json
semantic/normalized_proposal.json
semantic/validation.json
semantic/sam_tasks.json

detection/detections.json
detection/masks/

geometry/points.npy
geometry/depth.npy
geometry/normals.npy
geometry/validity.npy
geometry/camera.json
geometry/pixel_mapping.json

spatial/ground.json
spatial/coordinate_system.json
spatial/objects.json
spatial/roads.json
spatial/groups.json
spatial/spatial_scene_observation.json

evaluation/metrics.json
logs/*.log
```

SQLite 中不会存大数组或图片，只登记相对路径和必要元数据。

## 11. 语义提案链路

语义提案模型定义在：

```text
src/scene_spatial/domain/semantic.py
```

处理逻辑：

```text
semantics/validator.py
semantics/normalizer.py
semantics/manual_provider.py
semantics/prompt_builder.py
application/semantic_service.py
```

当前支持流程：

1. 创建任务后，任务进入等待语义提案状态。
2. 外部人工或在线 VLM 生成 `SceneSemanticProposal` JSON。
3. 调用 `/api/v1/tasks/{task_id}/semantic-proposal` 导入。
4. 后端做 schema 校验、类别归一化、领域配置检查。
5. 输出 `semantic/sam_tasks.json`，供 SAM stage 使用。

类别和领域配置：

```text
configs/categories.yaml
configs/domains/wastewater.yaml
```

## 12. SAM 接入方式

SAM stage 位于：

```text
src/scene_spatial/stages/model_stages.py
model_workers/sam3_worker.py
```

真实模型模式下，Worker 会写入请求文件：

```text
stages/sam_request_attempt_1.json
```

然后执行：

```text
<SCENE_SAM_PYTHON> <SCENE_SAM_WORKER> --request <request> --response <response>
```

SAM worker 需要返回：

```text
status
detectionsPath
maskDir
durationMs
peakGpuMemoryMiB
```

最终标准输出位置：

```text
detection/detections.json
detection/masks/
```

注意：当前真实 SAM 模型体未实现，`sam3_worker.py` 中保留了接入位置。你后面在服务器上补真实推理即可，不需要改 API 和 Worker 编排。

## 13. MoGe 接入方式

MoGe stage 位于：

```text
src/scene_spatial/stages/model_stages.py
model_workers/moge2_worker.py
```

真实模型模式下，Worker 会写入请求文件：

```text
stages/moge_request_attempt_1.json
```

然后执行：

```text
<SCENE_MOGE_PYTHON> <SCENE_MOGE_WORKER> --request <request> --response <response>
```

MoGe worker 需要返回：

```text
status
pointsPath
depthPath
normalsPath
validityPath
cameraPath
durationMs
peakGpuMemoryMiB
```

最终标准输出位置：

```text
geometry/points.npy
geometry/depth.npy
geometry/normals.npy
geometry/validity.npy
geometry/camera.json
```

空间求解阶段依赖 `geometry/points.npy` 和 `geometry/validity.npy`。如果真实 MoGe 输出坐标系和当前假设不一致，优先在 MoGe worker 或 `pixel_align/ground_solve` 中统一坐标约定。

## 14. 空间求解链路

空间求解主实现：

```text
src/scene_spatial/stages/spatial_solve.py
src/scene_spatial/spatial/solver_utils.py
```

当前算法能力：

1. `pixel_align`
   - 读取输入图片尺寸和 point map 尺寸。
   - 输出 `geometry/pixel_mapping.json`。
   - 当前采用 nearest scale 关系记录，后续可接更严谨的相机/裁剪映射。

2. `ground_solve`
   - 从 detection mask 中选择 `ground`、`road`、`vegetation_region` 作为候选。
   - 排除 `building`、`rectangular_treatment_pool`、`street_light`、`water` 等类别。
   - 基于候选点云拟合地面平面。
   - 默认 NumPy RANSAC/SVD，安装 Open3D 时可使用 Open3D 拟合。
   - 输出 `spatial/ground.json` 和 `spatial/coordinate_system.json`。

3. `object_solve`
   - 对 instance 类型 detection 提取 mask 内点云。
   - 将点投影到地面平面。
   - 估计 bottom center、长宽高、yaw、置信度。
   - 对 road region 估计 centerline、estimatedWidth、mainDirection。
   - 输出 `spatial/objects.json` 和 `spatial/roads.json`。

4. `group_solve`
   - 按类别聚合同类对象。
   - 当同类对象数量大于等于 3 时，用 PCA/SVD 估计主轴。
   - 根据中心点间距估计 row/grid。
   - 输出 `spatial/groups.json`。

5. `evaluate`
   - 重新从 mask 计算 bbox。
   - 与 detection bbox 做 IoU。
   - 输出 `evaluation/metrics.json`。

当前空间求解是第一版可运行算法骨架，后续需要根据真实 SAM/MoGe 输出做调参，包括：

```text
地面候选类别策略
点云异常值过滤
MoGe 坐标系方向
真实尺度恢复
池体/建筑物尺寸估计
道路 polygon/centerline 精细化
grid/row 稳定性
置信度计算
人工修正回灌
```

## 15. Worker 执行机制

Worker 入口：

```text
src/scene_spatial/worker/main.py
```

核心组件：

```text
worker/job_claimer.py
worker/heartbeat.py
worker/recovery.py
application/orchestrator.py
application/stage_registry.py
application/pipeline_definition.py
```

执行逻辑：

1. Worker 轮询数据库中 `QUEUED` 的任务。
2. claim 成功后写入 lease 和 worker 信息。
3. Orchestrator 按 pipeline 顺序执行 stage。
4. 每个 stage 生成 `StageResult`。
5. stage 结果写入 `stage_runs`，artifact 写入 `artifacts`。
6. 如果成功执行到 export/evaluate，任务进入完成状态。
7. 如果 stage 报错，任务进入 `FAILED`。
8. 如果 Worker 崩溃，recovery 可把超时 RUNNING 任务恢复。

重跑机制：

```text
POST /api/v1/tasks/{task_id}/rerun
{
  "fromStage": "ground_solve"
}
```

当前设计是保守重跑，不删除旧 artifacts。后续如需更强版本管理，可以增加 attempt/version 维度。

## 16. 数据库

数据库默认使用 SQLite：

```text
.runtime/data/scene_spatial.db
```

主要表：

```text
tasks
stage_runs
artifacts
corrections
```

模型定义：

```text
src/scene_spatial/infrastructure/db_models.py
```

仓储：

```text
src/scene_spatial/infrastructure/repositories/
```

迁移：

```text
migrations/versions/0001_initial_task_tables.py
```

SQLite 已配置 WAL、busy timeout 和 foreign key pragma，适合当前单机 PoC。

## 17. 部署方式

服务器推荐准备三个 Python 环境：

```text
/home/ai3d/envs/scene-core    API、Worker、空间求解
/home/ai3d/envs/scene-sam3    SAM 3 模型环境
/home/ai3d/envs/scene-moge2   MoGe 2 模型环境
```

核心环境安装：

```bash
cd /home/ai3d/src/scene-spatial-poc
/home/ai3d/envs/scene-core/bin/pip install -e ".[dev,geometry]"
```

启动 API：

```bash
bash scripts/start_api.sh
```

启动 Worker：

```bash
bash scripts/start_worker.sh
```

一次性跑 Worker：

```bash
bash scripts/run_worker_once.sh
```

systemd 文件：

```text
deploy/systemd/scene-spatial-api.service
deploy/systemd/scene-spatial-worker.service
```

## 18. 验证命令

在目标服务器或可用 Python 3.11+ 环境中执行：

```bash
pip install -e ".[dev,geometry]"
python scripts/smoke_fake_pipeline.py
pytest
python scripts/verify_sam3.py --fake
python scripts/verify_moge2.py --fake
bash scripts/inspect_gpu.sh
```

验证顺序建议：

1. 先安装 core 环境。
2. 跑 `/health` 和 `/ready`。
3. 跑 Fake Pipeline。
4. 跑 pytest。
5. 分别验证 SAM/MoGe worker fake 模式。
6. 接真实 SAM/MoGe。
7. 设置 `SCENE_FAKE_MODELS=false`。
8. 用真实图片跑完整任务。
9. 检查 `spatial_scene_observation.json` 和 `evaluation/metrics.json`。

注意：当前开发机环境中 Python 不可用，因此本地未实际执行 `pytest` 或 smoke。需要在服务器上完成第一次真实验证。

## 19. 典型调用流程

启动 API 和 Worker 后，典型使用顺序：

```text
1. POST /api/v1/tasks
   上传图片，得到 taskId

2. POST /api/v1/tasks/{task_id}/semantic-proposal
   导入人工或 VLM 生成的 SceneSemanticProposal

3. POST /api/v1/tasks/{task_id}/run
   将任务放入队列

4. GET /api/v1/tasks/{task_id}
   轮询状态

5. GET /api/v1/tasks/{task_id}/result
   获取空间观察结果

6. GET /api/v1/tasks/{task_id}/artifacts
   查看中间产物

7. 如果需要修正，调用 corrections 接口后从指定阶段 rerun
```

## 20. 后续开发重点

下一阶段最值得优先做的事：

1. 在服务器补齐真实 `sam3_worker.py`。
2. 在服务器补齐真实 `moge2_worker.py`。
3. 跑通 fake smoke 和 pytest。
4. 用 3-5 张真实场景图片验证完整链路。
5. 对 `spatial_solve.py` 做真实数据调参。
6. 明确 MoGe 点云坐标系、尺度单位和相机参数约定。
7. 增加 golden fixture 测试，固定一组真实/半真实输入输出。
8. 增强 object dimensions、road polygon、grid/group 结果。
9. 把人工修正结果真正回灌到 ground/object/group solve。
10. 后续再接编辑器或可视化前端。

## 21. 当前风险和注意事项

1. 真实模型未接入前，工程只能验证后端链路，不能代表最终空间精度。
2. Open3D/OpenCV 分支尚未在本地执行过，需要服务器验证。
3. MoGe 输出的坐标方向、尺度和 mask 对齐方式会直接影响后续空间求解。
4. 当前 `group_solve` 是基于对象中心点的简单 PCA/grid 推断，复杂场景需要增强。
5. 当前 `evaluate` 只是基础 bbox IoU，不是完整几何质量评估。
6. 当前 artifact 保守保留旧产物，长时间运行后需要考虑清理策略。
7. 如果后续并发任务增多，SQLite 队列可能需要换成更强的任务队列或数据库。

## 22. 一句话总结

当前工程已经完成了从“文档方案”到“可部署后端 PoC 骨架”的主要落地工作。现在最核心的缺口不是后端架构，而是服务器侧真实 SAM/MoGe 接入、第一次完整验证，以及基于真实输出对空间求解算法进行调参。

