# 第一阶段：场景理解与三维空间落点验证实施方案

> 版本定位：手工语义提案 + 本地视觉模型 + 本地空间求解  
> 目标硬件：GPU 0，NVIDIA L20，显存 46068 MiB  
> 当前策略：第一阶段不部署本地多模态大模型，也不在程序中接入任何在线大模型 API  
> 语义获取方式：操作人员把图片和本文提供的提示词交给任意支持图片输入的在线多模态模型，手工取得 JSON，再导入本地项目  
> 本地模型：SAM 3 + MoGe-2 ViT-L Normal  
> 本地算法：Open3D + OpenCV + NumPy + SciPy  
> 数据边界：除手工提交给多模态模型的原始图片外，检测、Mask、点图、点云、空间结果和编辑器数据均在本地处理  
> 阶段边界：不讨论模型资产库、Agent 自动搭建、图生 3D、正式模型替换和最终生产场景保存

---

# 一、方案结论

第一阶段固定采用以下流程：

```text
场景图片
        ↓
人工把图片 + 固定提示词提交给在线多模态模型
        ↓
人工获得并保存 semantic_proposal.json
        ↓
本地程序校验和标准化 JSON
        ↓
本地 SAM 3 根据标准类别和概念提示进行检测、分割
        ↓
本地 MoGe-2 对完整图片生成 Point Map、Depth、Normal、Intrinsics
        ↓
Mask 与 Point Map 像素对齐
        ↓
Open3D / OpenCV / NumPy / SciPy 计算
地面、坐标系、对象点云、落点、尺寸、朝向、道路和阵列
        ↓
生成 SpatialSceneObservation
        ↓
3D 编辑器创建临时代理几何
        ↓
原图重投影验证
```

本阶段实际部署的 AI 模型只有两个：

```text
1. SAM 3
2. MoGe-2 ViT-L Normal
```

场景语义理解暂时不作为部署服务。

它被实现为一个人工输入步骤：

```text
图片 + 固定提示词
        ↓
任意在线多模态模型
        ↓
标准 JSON
        ↓
人工导入项目
```

以后无论改为：

```text
本地 VLM
在线 API
内部大模型平台
人工填写
```

只要继续输出同一个 `SceneSemanticProposal` 协议，SAM、MoGe、空间求解和编辑器端都不需要修改。

---

# 二、第一阶段核心目标

输入一张支持领域内的场景图片，验证系统能否：

1. 获得主要对象和区域的标准类别；
2. 获得每个主要实例对象的检测框和像素 Mask；
3. 获得整张图片的 Point Map、Depth、Normal 和相机内参；
4. 使用 Mask 从 Point Map 中提取对象局部点云；
5. 恢复主地面平面；
6. 建立编辑器验证坐标系；
7. 估计主要对象的落点、相对尺寸和朝向；
8. 提取道路区域和中心线；
9. 识别矩形处理池等重复对象的 Grid 关系；
10. 在 3D 编辑器中创建 Box、OpenBox、Polygon、Line 等代理几何；
11. 从参考相机观察代理场景时，与输入图主要轮廓基本对齐。

第一阶段输出：

```text
SpatialSceneObservation
+
代理几何预览
+
原图重投影结果
+
误差和置信度报告
```

第一阶段不输出：

```text
最终精细 3D 模型
完整工业设备模型
自动模型库匹配结果
图生 3D 结果
正式生产场景
测绘级真实尺寸
```

---

# 三、系统中各部分的职责

## 3.1 人工语义提案步骤

人工语义步骤只回答：

```text
这是什么类型的场景？
这是什么类型的图片或视角？
图中明显可见哪些受支持类别？
每个类别按独立实例还是连续区域处理？
是否可能存在规则排列？
当前图片中的视觉特征是什么？
```

它不负责：

```text
精确检测框
像素 Mask
最终对象数量
二维坐标
三维坐标
深度
真实尺寸
相机参数
地面平面
最终 Grid 行列
```

人工语义步骤最终只产生：

```text
semantic_proposal.json
```

---

## 3.2 SAM 3

SAM 3 负责：

```text
根据文本概念寻找对象
输出对象检测框
输出实例 Mask 或区域 Mask
输出分数
支持整图和切片推理
支持后续使用框或点进行修正
```

对当前项目而言：

```text
building
rectangular_treatment_pool
street_light
```

按实例对象处理。

```text
ground
road
water
vegetation_region
```

按区域对象处理。

---

## 3.3 MoGe-2

MoGe-2 对完整透视图片执行一次几何推理，输出：

```text
Point Map
Depth Map
Normal Map
Validity Mask
Camera Intrinsics
```

它不需要知道图片里的对象是什么。

MoGe-2 只回答：

```text
每个像素在相机三维空间中的位置是什么？
每个像素的深度是什么？
每个表面的法线方向是什么？
哪些像素的几何结果有效？
相机内参或视场角是什么？
```

---

## 3.4 本地几何算法

Open3D、OpenCV、NumPy 和 SciPy 负责：

```text
Mask 后处理
像素坐标对齐
地面候选点筛选
RANSAC 地面拟合
世界坐标系建立
对象局部点云提取
对象落点计算
尺寸估计
朝向估计
道路中心线
重复对象分组
尺度锚点换算
重投影评估
```

这部分不是大模型。

它是项目真正需要持续开发和调试的核心工程代码。

---

# 四、人工语义提案协议

## 4.1 最终采用的输出结构

在线多模态模型必须返回以下结构：

```json
{
  "schemaVersion": "1.0",
  "scene": {
    "sceneType": "wastewater_treatment_plant",
    "imageType": "oblique_aerial_view",
    "supportedDomain": true,
    "semanticConfidence": 0.92
  },
  "categoryProposals": [
    {
      "category": "building",
      "objectMode": "instance",
      "semanticConfidence": 0.93,
      "promptHints": [
        "large industrial buildings with rectangular roofs"
      ],
      "expectedScale": "large",
      "visibleEvidence": [
        "rectangular roof",
        "visible building facade"
      ]
    },
    {
      "category": "rectangular_treatment_pool",
      "objectMode": "instance",
      "semanticConfidence": 0.88,
      "promptHints": [
        "repeated long rectangular open-air treatment basins"
      ],
      "expectedScale": "medium",
      "visibleEvidence": [
        "multiple elongated rectangular water-containing structures"
      ]
    },
    {
      "category": "road",
      "objectMode": "region",
      "semanticConfidence": 0.91,
      "promptHints": [
        "paved internal roads between the facility buildings"
      ],
      "expectedScale": "large",
      "visibleEvidence": [
        "continuous paved strips connecting facility areas"
      ]
    },
    {
      "category": "vegetation_region",
      "objectMode": "region",
      "semanticConfidence": 0.84,
      "promptHints": [
        "continuous grass and tree-covered areas"
      ],
      "expectedScale": "large",
      "visibleEvidence": [
        "large green areas around the facility"
      ]
    }
  ],
  "patternHints": [
    {
      "category": "rectangular_treatment_pool",
      "patternType": "grid",
      "semanticConfidence": 0.76
    }
  ],
  "warnings": []
}
```

---

## 4.2 字段解释

### `schemaVersion`

内部协议版本。

当前固定：

```text
1.0
```

以后修改字段时必须提升版本，避免旧结果被新程序错误读取。

---

### `scene.sceneType`

整张图所属的场景类型。

第一阶段允许值：

```text
wastewater_treatment_plant
industrial_park
warehouse_yard
urban_road
unknown
```

当前业务优先支持：

```text
wastewater_treatment_plant
```

这个字段用于：

- 选择领域配置；
- 选择类别字典；
- 选择几何规则；
- 判断是否属于当前支持范围。

---

### `scene.imageType`

图片类型或视角。

允许值：

```text
oblique_aerial_view
top_down_aerial_view
ground_level_photo
editor_render
architectural_render
site_plan
unknown
```

第一阶段主线支持：

```text
oblique_aerial_view
editor_render
architectural_render
ground_level_photo
```

`site_plan` 只允许进入语义分析，不直接保证使用 MoGe 按普通透视照片恢复空间。

---

### `scene.supportedDomain`

表示图片是否属于当前第一阶段支持的业务范围。

```json
{
  "supportedDomain": true
}
```

当在线模型无法判断，或图片明显不是污水厂、工业园区、仓储园区等场景时：

```json
{
  "supportedDomain": false
}
```

本地项目在 `false` 时停止自动执行，等待人工确认。

---

### `scene.semanticConfidence`

表示在线多模态模型对整体场景语义判断的自评置信度。

它不是数学意义上的真实概率，也不参与最终检测分数计算。

使用目的：

```text
低于阈值时提醒人工复核
```

---

### `categoryProposals`

表示在线模型认为图中明显可见、值得让 SAM 继续检测的标准类别。

它是候选提案，不是最终检测结果。

---

### `category`

内部固定类别 ID。

第一阶段只允许：

```text
ground
building
rectangular_treatment_pool
road
water
vegetation_region
street_light
```

不允许在线模型自由创建新类别。

无法映射时不要输出该类别，改为在 `warnings` 中记录。

---

### `objectMode`

表示后续 SAM 和几何程序如何处理该类别。

允许值：

```text
instance
region
```

`instance`：

```text
一件一件分开的对象
```

适用于：

```text
building
rectangular_treatment_pool
street_light
```

`region`：

```text
连续区域
```

适用于：

```text
ground
road
water
vegetation_region
```

本地校验器会检查类别与 `objectMode` 是否匹配，在线模型填错时自动修正或拒绝。

---

### `semanticConfidence`

表示在线模型认为图片中存在该类别的语义置信度。

它与 SAM 的分割分数不是同一个概念。

建议重命名并保持：

```text
semanticConfidence
```

禁止使用模糊字段名：

```text
confidence
```

---

### `promptHints`

这是在线模型根据当前图片补充的视觉描述。

例如：

```text
large industrial buildings with rectangular roofs
```

它不是最终传给 SAM 的唯一提示词。

SAM 的基础提示词由本地 `categories.yaml` 固定保存。

本地 `prompt_builder.py` 将：

```text
固定概念词
+
当前图片的 promptHints
```

组合为 SAM 推理任务。

这样可以避免在线模型每次自由创造完全不同的提示词。

---

### `expectedScale`

表示对象在图片中的大致像素尺度。

允许值：

```text
small
medium
large
unknown
```

用途：

```text
large：
优先使用整图结果

medium：
整图为主，必要时使用 2×2 切片

small：
默认允许切片补检
```

它只用于选择推理策略，不表示对象真实尺寸。

---

### `visibleEvidence`

表示在线模型在图片中看到哪些直接证据。

例如：

```text
rectangular roof
visible building facade
```

用途：

- 人工检查模型是否胡乱猜测；
- 调试语义提案；
- 生成语义报告。

该字段不直接传给 SAM。

---

### `patternHints`

表示图片中可能存在的排列结构。

允许的 `patternType`：

```text
grid
row
along_path
cluster
symmetric
repeated
unknown
```

该字段只用于：

```text
决定后面是否运行对应的几何分组算法
```

它不能直接确定：

```text
rows
columns
spacing
rotation
```

这些数据必须在 SAM 和 MoGe 完成后由三维几何计算得到。

---

### `warnings`

用于记录无法确定、可能超出能力边界或需要人工确认的问题。

例如：

```json
{
  "warnings": [
    {
      "code": "IMAGE_TYPE_UNCERTAIN",
      "message": "无法确认图片是实景航拍图还是编辑器渲染图。"
    }
  ]
}
```

---

# 五、提交给在线多模态模型的固定提示词

## 5.1 使用方法

操作人员执行：

1. 打开任意支持图片输入的多模态模型；
2. 上传当前场景图片；
3. 将下面整段提示词原样提交；
4. 等待模型返回；
5. 只复制 JSON 内容；
6. 保存为 `semantic_proposal.raw.json`；
7. 使用本地校验脚本导入；
8. 校验成功后生成 `semantic_proposal.json`。

不要让在线模型输出检测框、Mask 或三维坐标。

---

## 5.2 完整提示词

```text
你是“场景语义提案生成器”。

你的任务不是进行精确检测、分割或三维重建，而是分析我上传的整张场景图片，为后续本地视觉分割模型生成一份严格受约束的场景语义提案 JSON。

【当前业务领域】
污水处理厂、工业园区和类似基础设施场景。

【必须遵守的规则】

1. 只根据图片中明确可见的内容判断。
2. 不要根据污水厂领域知识猜测图片中没有直接视觉证据的对象。
3. 不要输出二维坐标、检测框、Mask、点位、深度、三维坐标、尺寸、距离或相机参数。
4. 不要输出最终对象数量。
5. 不要直接确定阵列的行数、列数和间距。
6. 只允许从下面的标准类别中选择，不允许发明新类别：
   - ground
   - building
   - rectangular_treatment_pool
   - road
   - water
   - vegetation_region
   - street_light
7. 实例对象使用 objectMode = "instance"：
   - building
   - rectangular_treatment_pool
   - street_light
8. 连续区域使用 objectMode = "region"：
   - ground
   - road
   - water
   - vegetation_region
9. promptHints 必须使用简短英文视觉描述，只描述当前图片中可见的形态、颜色、材质、位置特征或排列特征。
10. visibleEvidence 必须是图片中直接可见的证据，不能写业务常识。
11. semanticConfidence 使用 0 到 1 之间的小数。
12. 如果无法判断场景或图片类型，使用 unknown。
13. 如果图片明显不属于当前支持领域，supportedDomain = false。
14. 只返回合法 JSON。
15. 不要使用 Markdown 代码块。
16. 不要在 JSON 前后添加解释、标题或注释。

【允许的 sceneType】

- wastewater_treatment_plant
- industrial_park
- warehouse_yard
- urban_road
- unknown

【允许的 imageType】

- oblique_aerial_view
- top_down_aerial_view
- ground_level_photo
- editor_render
- architectural_render
- site_plan
- unknown

【允许的 expectedScale】

- small
- medium
- large
- unknown

【允许的 patternType】

- grid
- row
- along_path
- cluster
- symmetric
- repeated
- unknown

【必须返回的 JSON 结构】

{
  "schemaVersion": "1.0",
  "scene": {
    "sceneType": "从允许值中选择",
    "imageType": "从允许值中选择",
    "supportedDomain": true,
    "semanticConfidence": 0.0
  },
  "categoryProposals": [
    {
      "category": "从允许类别中选择",
      "objectMode": "instance 或 region",
      "semanticConfidence": 0.0,
      "promptHints": [
        "简短英文视觉描述"
      ],
      "expectedScale": "small、medium、large 或 unknown",
      "visibleEvidence": [
        "图片中直接可见的证据"
      ]
    }
  ],
  "patternHints": [
    {
      "category": "必须是 categoryProposals 中已出现的实例类别",
      "patternType": "从允许值中选择",
      "semanticConfidence": 0.0
    }
  ],
  "warnings": [
    {
      "code": "大写下划线错误码",
      "message": "简短中文说明"
    }
  ]
}

【额外要求】

- categoryProposals 中相同 category 只能出现一次。
- 如果没有可靠 patternHints，返回空数组。
- 如果没有 warning，返回空数组。
- 不要为了填满类别而输出图片中不明显的对象。
- ground、road、water、vegetation_region 是区域，不要尝试拆成多个独立实例。
- rectangular_treatment_pool 是处理池类视觉候选，只有看到明确矩形池体或盆状结构时才输出。
- street_light 只有在图片分辨率足以明确看到时才输出。
```

---

## 5.3 JSON 修复提示词

如果在线模型返回了 Markdown、解释文字或格式错误，可新开一轮提交：

```text
请把你上一条回答修复为合法 JSON。

要求：
1. 保留原有语义判断，不新增类别；
2. 严格符合我提供的 JSON 结构；
3. 删除 Markdown 代码块；
4. 删除 JSON 前后的所有说明；
5. 不输出注释；
6. 只返回 JSON。
```

本地导入程序仍然必须进行严格校验，不能因为在线模型说“已经修复”就直接信任。

---

# 六、本地固定类别和 SAM 提示词

## 6.1 为什么不能完全使用在线模型的 promptHints

在线模型生成的描述可能每次不同。

例如同一类别可能返回：

```text
factory building
industrial facility building
large blue-roof structure
rectangular plant building
```

如果直接将这些不稳定内容作为唯一提示词，SAM 的结果难以复现。

因此本地维护固定提示词库：

```text
categories.yaml
```

在线模型只负责：

```text
选择类别
+
提供当前图片的补充视觉特征
```

---

## 6.2 categories.yaml

```yaml
categories:
  ground:
    display_name: "地面"
    object_mode: "region"
    base_prompts:
      - "ground"
      - "paved ground"
      - "open ground area"
    allow_tile_inference: false

  building:
    display_name: "建筑"
    object_mode: "instance"
    base_prompts:
      - "industrial building"
      - "factory building"
      - "plant building"
    allow_tile_inference: true

  rectangular_treatment_pool:
    display_name: "矩形处理池"
    object_mode: "instance"
    base_prompts:
      - "rectangular wastewater treatment pool"
      - "rectangular treatment basin"
      - "long rectangular open-air basin"
    allow_tile_inference: true

  road:
    display_name: "道路"
    object_mode: "region"
    base_prompts:
      - "road"
      - "paved internal road"
      - "facility access road"
    allow_tile_inference: false

  water:
    display_name: "水面"
    object_mode: "region"
    base_prompts:
      - "water surface"
      - "river water"
      - "open water area"
    allow_tile_inference: false

  vegetation_region:
    display_name: "植被区域"
    object_mode: "region"
    base_prompts:
      - "vegetation area"
      - "grass and trees area"
      - "green planted area"
    allow_tile_inference: false

  street_light:
    display_name: "路灯"
    object_mode: "instance"
    base_prompts:
      - "street light"
      - "road lamp"
      - "lamp post"
    allow_tile_inference: true
```

---

## 6.3 SAM 任务生成

`prompt_builder.py` 输入：

```text
semantic_proposal.json
+
categories.yaml
```

输出：

```text
sam_tasks.json
```

示例：

```json
{
  "tasks": [
    {
      "category": "building",
      "objectMode": "instance",
      "conceptPrompts": [
        "industrial building",
        "factory building",
        "plant building",
        "large industrial buildings with rectangular roofs"
      ],
      "runFullImage": true,
      "runTiles": true,
      "expectedScale": "large"
    },
    {
      "category": "road",
      "objectMode": "region",
      "conceptPrompts": [
        "road",
        "paved internal road",
        "facility access road",
        "paved internal roads between the facility buildings"
      ],
      "runFullImage": true,
      "runTiles": false,
      "expectedScale": "large"
    }
  ]
}
```

本地程序执行以下处理：

1. 加载固定 `base_prompts`；
2. 加入经过清理的 `promptHints`；
3. 去重；
4. 限制单类别提示词数量；
5. 检查提示词长度；
6. 生成 SAM 推理任务；
7. 保存最终实际使用的提示词，保证结果可复现。

---

# 七、GPU 和本地部署方案

## 7.1 当前 GPU

固定使用：

```text
GPU 0
NVIDIA L20
总显存 46068 MiB
```

当前 GPU 0 上存在其他进程，因此运行前必须检查空闲显存。

本阶段只有 SAM 3 和 MoGe-2 使用 GPU，二者串行运行。

```text
SAM 3
        ↓
进程退出并释放显存
        ↓
MoGe-2
        ↓
进程退出并释放显存
        ↓
CPU 几何求解
```

---

## 7.2 环境划分

不安装 Qwen 环境。

建立三个环境：

```text
/home/ai3d/envs/scene-core
/home/ai3d/envs/scene-sam3
/home/ai3d/envs/scene-moge2
```

用途：

```text
scene-core：
FastAPI、Pydantic、OpenCV、Open3D、NumPy、SciPy、任务编排、评估

scene-sam3：
SAM 3 及其独立 PyTorch / CUDA 依赖

scene-moge2：
MoGe-2 及其独立 PyTorch / CUDA 依赖
```

不修改：

```text
/home/ai3d/envs/pixal3d
```

---

## 7.3 目录规划

```text
/home/ai3d/src/scene-spatial-poc
/home/ai3d/models/scene-spatial/sam3
/home/ai3d/models/scene-spatial/moge-2-vitl-normal
/home/ai3d/inputs/scene-spatial
/home/ai3d/outputs/scene-spatial
/home/ai3d/logs/scene-spatial
/home/ai3d/tmp/scene-spatial
```

统一缓存：

```text
HF_HOME=/home/ai3d/cache/huggingface
HUGGINGFACE_HUB_CACHE=/home/ai3d/cache/huggingface/hub
PIP_CACHE_DIR=/home/ai3d/cache/pip
TORCH_HOME=/home/ai3d/cache/torch
TORCH_EXTENSIONS_DIR=/home/ai3d/cache/torch_extensions
TMPDIR=/home/ai3d/tmp/scene-spatial
```

---

# 八、项目目录

```text
scene-spatial-poc/
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes_analyze.py
│   │   ├── routes_tasks.py
│   │   ├── routes_results.py
│   │   ├── routes_semantic.py
│   │   └── routes_corrections.py
│   └── worker/
│       ├── worker.py
│       ├── orchestrator.py
│       ├── gpu_lock.py
│       └── stage_runner.py
│
├── semantics/
│   ├── manual_provider.py
│   ├── proposal_validator.py
│   ├── proposal_normalizer.py
│   ├── prompt_builder.py
│   ├── prompt_template.md
│   └── schemas/
│       └── scene_semantic_proposal.schema.json
│
├── stages/
│   ├── preprocess_stage.py
│   ├── wait_semantic_stage.py
│   ├── semantic_import_stage.py
│   ├── sam3_stage.py
│   ├── mask_postprocess_stage.py
│   ├── moge2_stage.py
│   ├── pixel_alignment_stage.py
│   ├── geometry_stage.py
│   ├── export_stage.py
│   └── evaluation_stage.py
│
├── adapters/
│   ├── sam3_adapter.py
│   ├── moge2_adapter.py
│   └── fallback/
│       ├── grounding_dino_adapter.py
│       └── sam21_adapter.py
│
├── perception/
│   ├── image_preprocessor.py
│   ├── tile_generator.py
│   ├── tile_merger.py
│   ├── detection_merger.py
│   └── mask_postprocess.py
│
├── geometry/
│   ├── geometry_pipeline.py
│   ├── ground_candidates.py
│   ├── ground_plane_solver.py
│   ├── coordinate_system.py
│   ├── object_pointcloud.py
│   ├── object_anchor.py
│   ├── object_dimensions.py
│   ├── object_orientation.py
│   ├── road_solver.py
│   ├── group_solver.py
│   └── scale_solver.py
│
├── protocols/
│   ├── input_models.py
│   ├── semantic_models.py
│   ├── detection_models.py
│   ├── geometry_models.py
│   ├── task_models.py
│   └── spatial_scene_observation.py
│
├── visualization/
│   ├── draw_boxes.py
│   ├── draw_masks.py
│   ├── draw_depth.py
│   ├── draw_normals.py
│   ├── export_pointcloud.py
│   ├── draw_ground.py
│   └── draw_reprojection.py
│
├── evaluation/
│   ├── dataset_loader.py
│   ├── detection_metrics.py
│   ├── geometry_metrics.py
│   ├── reprojection_metrics.py
│   └── report_builder.py
│
├── configs/
│   ├── runtime.yaml
│   ├── models.yaml
│   ├── categories.yaml
│   ├── thresholds.yaml
│   └── domains/
│       └── wastewater.yaml
│
├── scripts/
│   ├── create_task.py
│   ├── import_semantic_proposal.py
│   ├── run_sam3.py
│   ├── run_moge2.py
│   ├── run_geometry.py
│   ├── run_pipeline.py
│   ├── inspect_gpu.py
│   └── verify_models.py
│
├── tests/
├── pyproject.toml
└── README.md
```

---

# 九、统一内部协议

## 9.1 SceneSemanticProposal

使用第四章定义的结构。

导入后保存：

```text
semantic/proposal.raw.json
semantic/proposal.json
semantic/validation.json
```

`proposal.raw.json`：

```text
操作人员从在线模型复制的原始内容
```

`proposal.json`：

```text
经过本地 Schema 校验、枚举修正、去重和标准化后的内容
```

`validation.json`：

```text
记录原始 JSON 是否有效、哪些字段被修正、是否需要人工确认
```

---

## 9.2 DetectionMask

```json
{
  "id": "pool_001",
  "category": "rectangular_treatment_pool",
  "objectMode": "instance",
  "sourcePrompt": "rectangular wastewater treatment pool",
  "bbox2d": [623, 382, 781, 455],
  "maskPath": "detection/masks/pool_001.png",
  "score": 0.87,
  "partial": false,
  "touchesImageBorder": false,
  "sourceModel": "sam3"
}
```

---

## 9.3 GeometryFrame

```json
{
  "width": 1280,
  "height": 606,
  "pointMapPath": "geometry/points.npy",
  "depthMapPath": "geometry/depth.npy",
  "normalMapPath": "geometry/normals.npy",
  "validityMaskPath": "geometry/validity.npy",
  "camera": {
    "projection": "perspective",
    "fovY": 52.4,
    "intrinsics": {
      "fx": 1035.2,
      "fy": 1034.7,
      "cx": 640.0,
      "cy": 303.0
    }
  },
  "sourceModel": "moge_2"
}
```

---

# 十、任务状态

```text
created
preprocessing
waiting_semantic_proposal
semantic_validating
semantic_ready
waiting_for_gpu
segmenting
mask_postprocessing
geometry_estimating
pixel_aligning
ground_solving
object_solving
group_solving
exporting
preview_ready
completed
failed
```

关键变化：

```text
waiting_semantic_proposal
```

表示本地预处理完成，正在等待操作人员把外部模型生成的 JSON 导入。

---

# 十一、详细执行流程

## 步骤 0：服务器和 GPU 检查

检查：

1. GPU 0 是否可见；
2. GPU 0 当前空闲显存；
3. 是否有其他任务可能突然增加显存；
4. SAM 和 MoGe 环境是否独立；
5. 模型文件是否完整；
6. 输出目录是否可写；
7. 根分区是否有足够空间；
8. 所有缓存是否位于 `/home/ai3d`；
9. 系统内存是否满足点图和点云处理；
10. GPU 文件锁是否可用。

输出：

```text
runtime/environment_check.json
runtime/gpu_snapshot_before.json
```

---

## 步骤 1：创建任务

输入：

```text
PNG
JPEG
WEBP
```

创建：

```text
taskId
任务目录
初始状态
输入副本
```

示例命令：

```bash
/home/ai3d/envs/scene-core/bin/python scripts/create_task.py \
  --image /home/ai3d/inputs/scene-spatial/scene_001.png \
  --domain wastewater_treatment_plant
```

输出：

```text
task_001
```

---

## 步骤 2：输入预处理

处理：

1. 校验图片；
2. 读取宽高、颜色空间、EXIF；
3. 应用 EXIF 方向；
4. 保存原图；
5. 生成在线语义分析副本；
6. 生成 SAM 整图副本；
7. 生成 MoGe 完整图副本；
8. 记录每个副本与原图之间的缩放和 Padding；
9. 可提前生成 2×2 SAM 切片；
10. 不执行改变透视关系的裁剪。

输出：

```text
input/
├── original.png
├── semantic_input.png
├── sam_full.png
├── moge_input.png
├── tiles/
└── metadata.json
```

完成后任务状态：

```text
waiting_semantic_proposal
```

---

## 步骤 3：人工生成语义提案

操作人员：

1. 打开 `input/semantic_input.png`；
2. 上传给支持图片输入的在线多模态模型；
3. 提交第五章固定提示词；
4. 复制返回 JSON；
5. 保存为：

```text
semantic/proposal.raw.json
```

不要修改图片比例。

不要请求在线模型生成：

```text
框
Mask
三维坐标
尺寸
深度
```

---

## 步骤 4：本地校验语义 JSON

运行：

```bash
/home/ai3d/envs/scene-core/bin/python scripts/import_semantic_proposal.py \
  --task-id task_001 \
  --json /path/to/semantic_proposal.raw.json
```

校验内容：

1. 是否为合法 JSON；
2. `schemaVersion` 是否支持；
3. 是否只包含允许的类别；
4. `objectMode` 是否与类别匹配；
5. 置信度是否在 0～1；
6. 同一类别是否重复；
7. `promptHints` 是否为英文短语；
8. `patternHints.category` 是否已出现在类别提案中；
9. 枚举值是否有效；
10. 是否有未知字段；
11. 是否包含禁止的框、坐标、尺寸字段；
12. 是否需要人工复核。

导入成功后输出：

```text
semantic/proposal.json
semantic/validation.json
semantic/sam_tasks.json
```

---

## 步骤 5：生成 SAM 推理任务

组合：

```text
categories.yaml.base_prompts
+
semantic_proposal.promptHints
```

规则：

- 基础提示词始终保留；
- promptHints 只作为补充；
- 去除重复词；
- 单类别提示词不超过设定数量；
- 保存最终使用顺序；
- 实例类与区域类分开执行；
- `small` 对象允许切片；
- `large` 区域优先整图。

输出：

```text
semantic/sam_tasks.json
```

---

## 步骤 6：SAM 3 整图推理

启动独立 `scene-sam3` 子进程。

输入：

```text
input/sam_full.png
semantic/sam_tasks.json
```

执行顺序：

```text
实例类
        ↓
区域类
```

第一批优先：

```text
building
rectangular_treatment_pool
road
water
vegetation_region
ground
```

`street_light` 后置。

输出：

```text
detection/raw/detections.json
detection/raw/masks/
detection/raw/model_info.json
```

子进程退出后检查 GPU 显存是否回落。

---

## 步骤 7：SAM 切片补检

只在以下情况启用：

- 实例数量明显偏少；
- 处理池粘连；
- 小建筑漏检；
- 路灯需要验证；
- 整图缩放后目标太小。

流程：

```text
2×2 切片
        ↓
保留重叠区域
        ↓
逐切片推理
        ↓
映射回原图
        ↓
Box NMS
        ↓
Mask IoU 去重
        ↓
与整图结果合并
```

第一版不默认启用 3×3。

输出：

```text
detection/tiles/
detection/merged_detections.json
detection/merged_masks/
```

---

## 步骤 8：Mask 后处理

实例类：

1. 删除小连通域；
2. 填补小孔洞；
3. 保留主要实例区域；
4. 平滑边界；
5. 检测是否触边；
6. 标记遮挡和截断；
7. 合并重复 Mask；
8. 根据最终 Mask 重新计算 bbox。

区域类：

1. 允许多个连通区域；
2. 合并邻近区域；
3. 填补小洞；
4. 去除实例对象区域；
5. 输出区域轮廓；
6. 保存覆盖率。

输出：

```text
detection/detections.json
detection/masks/
visualizations/detections.png
visualizations/masks.png
```

---

## 步骤 9：MoGe-2 完整图几何推理

启动独立 `scene-moge2` 子进程。

输入：

```text
input/moge_input.png
```

MoGe 不进行切片。

必须保存：

```text
geometry/points.npy
geometry/depth.npy
geometry/normals.npy
geometry/validity.npy
geometry/camera.json
```

预览：

```text
visualizations/depth.png
visualizations/normals.png
pointcloud/scene.ply
```

子进程退出后检查显存回落。

---

## 步骤 10：Mask 与 Point Map 像素对齐

需要统一：

```text
原图尺寸
EXIF 方向
SAM 整图尺寸
SAM 切片坐标
SAM Padding
MoGe 输入尺寸
MoGe 输出尺寸
```

生成：

```text
geometry/pixel_mapping.json
```

如果 Mask 需要重采样到 Point Map 尺寸：

```text
必须使用最近邻插值
```

禁止使用双线性插值破坏类别边界。

验证方法：

1. 在 Mask 中抽样像素；
2. 查找对应三维点；
3. 导出抽样点云；
4. 确认点位于目标对象而不是背景；
5. 生成像素对齐调试图。

---

## 步骤 11：地面候选生成

来源：

```text
road Mask
ground Mask
vegetation_region 中低矮区域
MoGe 法线接近主水平面的区域
Point Map 中较低且连续的区域
```

排除：

```text
building
rectangular_treatment_pool
street_light
water
```

输出：

```text
spatial/ground_candidate_mask.png
pointcloud/ground_candidates.ply
```

人工语义提案不能直接作为地面像素输入。

---

## 步骤 12：地面拟合

流程：

```text
候选点
        ↓
体素降采样
        ↓
统计离群点过滤
        ↓
RANSAC 多次拟合
        ↓
选择主地面
        ↓
法线方向统一
        ↓
最小二乘优化
```

输出：

```json
{
  "plane": [0.0, 1.0, 0.0, 0.0],
  "normal": [0.0, 1.0, 0.0],
  "inlierRatio": 0.74,
  "pointCount": 185240,
  "method": "ransac",
  "confidence": 0.86
}
```

失败后允许用户在原图点选 3～8 个地面点重新拟合。

---

## 步骤 13：建立世界坐标系

```text
Y 轴：
地面法线

Z 轴优先级：
1. 主要道路方向
2. 建筑群主方向
3. 处理池阵列主方向
4. 相机前方向在地面上的投影

X 轴：
cross(Y, Z)

原点：
主要对象群中心投影到地面
```

第一阶段单位：

```text
relative
```

设置尺度锚点后：

```text
meter
```

输出：

```text
spatial/coordinate_system.json
```

---

## 步骤 14：对象局部点云

对每个 Mask：

```python
object_points = point_map[mask & validity_mask]
```

过滤：

1. Mask 向内腐蚀 2～5 像素；
2. 删除无效点；
3. 删除深度突变边缘；
4. 深度分位数过滤；
5. 局部中位数距离过滤；
6. 统计离群点过滤；
7. 去除地面以下点；
8. 保存原始和清理点云。

输出：

```text
pointcloud/objects/
├── building_001_raw.ply
├── building_001_clean.ply
├── pool_001_raw.ply
└── pool_001_clean.ply
```

---

## 步骤 15：对象落点

建筑：

```text
点云投影到地面
→ 可见占地轮廓
→ 稳健矩形或凸包
→ bottom_center
```

矩形处理池：

```text
Mask 边缘 + 局部点云
→ 地面投影
→ 矩形拟合
→ 中心和主方向
```

路灯：

```text
Mask 底部区域
→ 邻近可靠 Point
→ 地面投影
→ base_point
```

道路、水面和植被：

```text
输出 polygon3d
```

---

## 步骤 16：尺寸估计

相对坐标中计算：

```text
width
height
length
```

使用：

```text
2%～98% 分位数
```

避免 min/max 被离群点影响。

第一阶段不依赖单图直接获得真实米制。

支持用户输入：

```text
pool_001.length = 30 meter
```

计算全局尺度：

```text
scaleFactor = 30 / predictedLength
```

---

## 步骤 17：对象朝向

优先级：

```text
1. 地面占地最小旋转矩形
2. 地面投影点 PCA
3. Mask 主边方向
4. 同组对象排列方向
5. 人工语义 patternHint 只作为触发条件
```

人工语义结果不能直接提供最终角度。

---

## 步骤 18：道路中心线

```text
road Mask
→ 映射地面
→ 形态学清理
→ polygon3d
→ 骨架化
→ 删除短分支
→ Douglas-Peucker 简化
→ centerline
```

输出：

```text
polygon3d
centerline
estimatedWidth
mainDirection
```

---

## 步骤 19：重复对象分组

输入：

```text
类别
三维中心
尺寸
朝向
```

算法：

1. 同类聚类；
2. 过滤尺寸差异大的对象；
3. PCA 获得两条主轴；
4. 中心投影；
5. 行列聚类；
6. 计算中位间距；
7. 检查缺失格位；
8. 计算 Grid 置信度。

在线模型只提示：

```text
可能存在 grid
```

最终：

```text
rows
columns
spacing
rotation
```

全部由本地几何算法决定。

---

## 步骤 20：生成 SpatialSceneObservation

合并：

```text
人工语义提案
SAM 检测和 Mask
MoGe 几何
地面
坐标系
对象位置
尺寸
方向
道路
分组
```

输出：

```text
spatial/spatial_scene_observation.json
```

每个对象必须具有分项置信度：

```text
category
detection
mask
position
dimensions
rotation
```

---

## 步骤 21：编辑器代理几何预览

| 类别 | 代理几何 |
| --- | --- |
| building | Box |
| rectangular_treatment_pool | OpenBox / Box |
| road | Polygon / Ribbon |
| water | Polygon |
| vegetation_region | Polygon + Density Preview |
| street_light | Cylinder + Marker |
| unknown | Billboard / Marker |

代理对象：

- 只进入 AI Preview Layer；
- 不调用正式保存接口；
- 不写正式场景对象表；
- 不生成正式 objId；
- 关闭任务时统一销毁；
- 允许导出修正后的空间 JSON。

---

## 步骤 22：重投影和评估

展示：

```text
原图
检测框
Mask
Depth
Normal
Point Cloud
代理场景
半透明叠加
```

允许调整：

```text
FOV
相机旋转
地面
尺度
对象位置
对象尺寸
对象朝向
```

最终指标：

```text
Proxy Reprojection IoU
```

---

# 十二、本地服务接口

本节接口只服务内网项目。

不调用在线多模态 API。

在线语义结果由人工导入。

## 12.1 创建任务

```http
POST /api/v1/spatial-scene/analyze
```

```json
{
  "imagePath": "/home/ai3d/inputs/scene-spatial/scene_001.png",
  "domain": "wastewater_treatment_plant",
  "semanticMode": "manual"
}
```

返回：

```json
{
  "taskId": "task_001",
  "status": "waiting_semantic_proposal"
}
```

---

## 12.2 导入语义提案

```http
POST /api/v1/spatial-scene/tasks/{taskId}/semantic-proposal
```

请求体：

```text
完整 SceneSemanticProposal JSON
```

成功后：

```text
semantic_ready
```

---

## 12.3 启动本地流水线

```http
POST /api/v1/spatial-scene/tasks/{taskId}/run
```

执行：

```text
SAM
→ MoGe
→ Geometry
→ Export
```

---

## 12.4 查询任务

```http
GET /api/v1/spatial-scene/tasks/{taskId}
```

---

## 12.5 获取结果

```http
GET /api/v1/spatial-scene/tasks/{taskId}/result
```

---

## 12.6 重跑单阶段

```http
POST /api/v1/spatial-scene/tasks/{taskId}/rerun
```

```json
{
  "stage": "sam"
}
```

---

# 十三、输出目录

```text
outputs/task_001/
├── task.json
├── runtime/
│   ├── environment_check.json
│   ├── gpu_snapshot_before.json
│   └── stage_metrics.json
├── input/
│   ├── original.png
│   ├── semantic_input.png
│   ├── sam_full.png
│   ├── moge_input.png
│   ├── tiles/
│   └── metadata.json
├── semantic/
│   ├── proposal.raw.json
│   ├── proposal.json
│   ├── validation.json
│   └── sam_tasks.json
├── detection/
│   ├── raw/
│   ├── detections.json
│   ├── masks/
│   ├── tiles/
│   └── stage.json
├── geometry/
│   ├── points.npy
│   ├── depth.npy
│   ├── normals.npy
│   ├── validity.npy
│   ├── camera.json
│   ├── pixel_mapping.json
│   └── stage.json
├── pointcloud/
│   ├── scene.ply
│   ├── ground_candidates.ply
│   └── objects/
├── spatial/
│   ├── ground.json
│   ├── coordinate_system.json
│   ├── scale.json
│   ├── objects.json
│   ├── roads.json
│   ├── groups.json
│   └── spatial_scene_observation.json
├── visualizations/
│   ├── detections.png
│   ├── masks.png
│   ├── depth.png
│   ├── normals.png
│   ├── ground.png
│   ├── pixel_alignment.png
│   └── reprojection.png
├── evaluation/
│   ├── metrics.json
│   └── report.html
└── logs/
    ├── orchestrator.log
    ├── semantic_import.log
    ├── sam.log
    ├── moge.log
    └── geometry.log
```

---

# 十四、实施里程碑

## M0：项目和环境

交付：

- 项目目录；
- `scene-core` 环境；
- `scene-sam3` 环境；
- `scene-moge2` 环境；
- GPU 0 锁；
- 输出目录；
- 模型加载检查。

验收：

```text
SAM 单独运行成功
MoGe 单独运行成功
进程退出后显存正常回落
```

---

## M1：人工语义导入

交付：

- 固定在线模型提示词；
- JSON Schema；
- 手工导入脚本；
- 校验器；
- 标准化器；
- `categories.yaml`；
- `sam_tasks.json` 生成器。

验收：

```text
上传图片
→ 任务进入 waiting_semantic_proposal
→ 人工导入 JSON
→ 本地校验成功
→ 生成 SAM 任务
```

---

## M2：SAM 检测和 Mask

交付：

- 整图推理；
- 实例类和区域类；
- 2×2 切片；
- 结果合并；
- Mask 后处理；
- 可视化。

验收：

```text
单建筑
2×4 水池
道路
```

能够生成可检查的 Mask。

---

## M3：MoGe 和像素对齐

交付：

- Point Map；
- Depth；
- Normal；
- Intrinsics；
- 场景点云；
- Mask 与 Point Map 对齐。

验收：

```text
建筑 Mask 能提取出正确建筑局部点云
```

---

## M4：地面和单对象落点

交付：

- 地面候选；
- RANSAC；
- 坐标系；
- building bottom_center；
- 尺寸；
- 朝向。

验收：

```text
单建筑 Box 从参考相机观察时与原图建筑基本对齐
```

---

## M5：水池 Grid 和道路

交付：

- 水池矩形拟合；
- 行列和间距；
- 道路 polygon；
- 道路 centerline。

验收：

```text
2×4 池体阵列的数量、方向和间距基本合理
主道路方向基本正确
```

---

## M6：编辑器预览和评估

交付：

- AI Spatial Validation 页面；
- 代理几何；
- 相机设置；
- 原图叠加；
- 人工修正；
- 报告。

验收：

```text
主要对象代理重投影达到项目设定目标
```

---

# 十五、第一批开发任务顺序

严格按以下顺序推进：

1. 创建项目目录；
2. 创建 `scene-core` 环境；
3. 创建 `scene-sam3` 环境；
4. 创建 `scene-moge2` 环境；
5. 固定 GPU 0；
6. 实现 GPU 文件锁；
7. 验证 SAM 加载；
8. 验证 MoGe 加载；
9. 准备“地面 + 单建筑”图片；
10. 创建任务目录；
11. 生成 `semantic_input.png`；
12. 使用本文提示词获得第一份 JSON；
13. 实现 JSON Schema；
14. 实现手工导入；
15. 实现 `categories.yaml`；
16. 实现 SAM 任务生成；
17. 运行建筑整图分割；
18. 保存建筑 Mask；
19. 运行 MoGe；
20. 保存 Point Map；
21. 完成像素对齐；
22. 导出建筑局部点云；
23. 实现地面候选；
24. 实现 RANSAC；
25. 建立世界坐标系；
26. 计算建筑 bottom_center；
27. 计算建筑相对尺寸；
28. 计算建筑朝向；
29. 在编辑器创建一个 Box；
30. 设置估计相机；
31. 执行原图半透明叠加；
32. 加入 2×4 水池；
33. 实现 Grid；
34. 加入道路；
35. 实现中心线；
36. 生成 SpatialSceneObservation；
37. 输出第一份评估报告。

---

# 十六、验收指标

第一阶段项目目标：

```text
主要类别 Recall ≥ 85%
主要对象 Mask IoU ≥ 0.70
地面法线误差 ≤ 8°
相对深度排序准确率 ≥ 90%
规则阵列行列准确率 ≥ 85%
主要对象代理重投影 IoU ≥ 0.60
人工修正后重投影 IoU ≥ 0.75
```

必须额外记录：

```text
人工语义 JSON 校验成功率
每次人工修复次数
SAM 阶段耗时
MoGe 阶段耗时
几何阶段耗时
峰值显存
失败阶段
人工修正次数
```

---

# 十七、风险和回退

## 风险 1：在线模型生成的 JSON 不合法

处理：

- 使用固定修复提示词；
- 本地 Schema 严格校验；
- 禁止直接进入 SAM；
- 允许人工编辑 JSON；
- 保存原始版本和修复版本。

---

## 风险 2：在线模型遗漏类别

处理：

- 人工在 JSON 中补充标准类别；
- 使用固定类别模板；
- 记录人工修改；
- 不改变 SAM 和几何程序。

---

## 风险 3：SAM 概念分割效果差

处理顺序：

```text
调整固定 base_prompts
→ 调整 promptHints
→ 整图 + 2×2 切片
→ 使用框或点提示修正
→ 本地 Grounding DINO + SAM 2.1 回退
```

---

## 风险 4：MoGe 远景失真

处理：

- 远景作为背景；
- 限制空间恢复范围；
- 低有效点对象不输出精确尺寸；
- 使用相对尺度；
- 要求尺寸锚点；
- 降低对应置信度。

---

## 风险 5：地面拟合错误

处理：

- road / ground Mask 约束；
- Normal 过滤；
- 多平面候选；
- 用户点选地面；
- 低置信度时停止代理场景创建。

---

## 风险 6：单图遮挡

处理：

- 标记 `partial`；
- 降低尺寸置信度；
- 只拟合可见占地；
- 使用同组对象几何辅助；
- 不承诺不可见部分精确。

---

# 十八、后续自动化扩展边界

本阶段只实现：

```text
ManualSemanticProposalProvider
```

未来可以增加：

```text
LocalVLMProvider
OnlineAPIProvider
InternalModelPlatformProvider
```

但所有 Provider 必须输出相同的：

```text
SceneSemanticProposal
```

下游固定为：

```text
SceneSemanticProposal
→ Prompt Builder
→ SAM
→ MoGe
→ Geometry
```

因此后续决定部署本地 VLM 或接入在线 API 时，不需要重构 SAM、MoGe 和空间算法。

---

# 十九、最终交付物

1. `scene-spatial-poc` 项目；
2. 人工语义提案固定提示词；
3. SceneSemanticProposal JSON Schema；
4. 人工 JSON 导入和校验工具；
5. 本地 SAM 3 Adapter；
6. 本地 MoGe-2 Adapter；
7. GPU 0 串行调度器；
8. Mask 后处理；
9. Point Map、Depth、Normal 和 Camera；
10. 像素映射和对齐检查；
11. 地面和世界坐标系；
12. 对象局部点云；
13. 对象落点、尺寸和朝向；
14. 道路中心线；
15. Grid 分组；
16. SpatialSceneObservation；
17. 编辑器代理几何验证；
18. 重投影叠加；
19. 自动评估报告；
20. 后续是否自动接入 VLM 的技术结论。

最终只验证一个问题：

> 在语义类别暂时由人工借助在线多模态模型生成、本地仅部署 SAM 3 和 MoGe-2 的条件下，系统能否把一张场景图片中的主要对象转换为位置、尺寸和朝向合理的代理几何场景，并从参考视角与原图主要轮廓基本对齐？
