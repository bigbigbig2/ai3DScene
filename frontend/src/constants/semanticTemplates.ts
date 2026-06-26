export const defaultSemanticProposal = {
  schemaVersion: '1.0',
  scene: {
    sceneType: 'industrial_park',
    imageType: 'editor_render',
    supportedDomain: true,
    semanticConfidence: 0.82,
  },
  categoryProposals: [
    {
      category: 'building',
      objectMode: 'instance',
      semanticConfidence: 0.95,
      promptHints: [
        'high-rise office towers',
        'glass curtain wall buildings',
        'commercial podium building',
        'rectangular modern buildings',
        'main building cluster',
      ],
      expectedScale: 'large',
      visibleEvidence: [
        '画面中央和右侧有多栋高层办公楼',
        '底部有连续商业裙房和入口空间',
        '建筑立面清晰可见，属于主要实例对象',
      ],
    },
    {
      category: 'road',
      objectMode: 'region',
      semanticConfidence: 0.92,
      promptHints: [
        'wide asphalt roads',
        'multi-lane urban road',
        'road intersection',
        'lane markings',
        'crosswalk',
      ],
      expectedScale: 'large',
      visibleEvidence: [
        '画面前景和右侧有明显多车道道路',
        '可见车道线、斑马线和道路交叉口',
      ],
    },
    {
      category: 'ground',
      objectMode: 'region',
      semanticConfidence: 0.86,
      promptHints: [
        'open ground plane',
        'plaza pavement',
        'building courtyard',
        'sidewalk',
        'site base plane',
      ],
      expectedScale: 'large',
      visibleEvidence: [
        '建筑前方有广场、铺装和人行区域',
        '建筑群周围存在连续地面平面',
      ],
    },
    {
      category: 'vegetation_region',
      objectMode: 'region',
      semanticConfidence: 0.82,
      promptHints: [
        'grass areas',
        'green landscape zones',
        'trees along road',
        'landscaped courtyard',
        'green belt',
      ],
      expectedScale: 'large',
      visibleEvidence: [
        '画面前景和道路两侧有大面积草地',
        '建筑周边和道路边缘有树木绿化',
      ],
    },
    {
      category: 'street_light',
      objectMode: 'instance',
      semanticConfidence: 0.62,
      promptHints: [
        'street lamps',
        'small vertical light poles',
        'roadside light poles',
        'plaza lighting poles',
      ],
      expectedScale: 'small',
      visibleEvidence: [
        '道路边和广场区域可见细小竖向灯杆',
        '该类目标较小，建议作为低置信度辅助检测',
      ],
    },
  ],
  patternHints: [
    {
      category: 'building',
      patternType: 'cluster',
      semanticConfidence: 0.78,
    },
    {
      category: 'street_light',
      patternType: 'along_path',
      semanticConfidence: 0.68,
    },
  ],
  warnings: [
    {
      code: 'CATEGORY_LIMITED',
      message:
        '当前后端类别枚举较少，未包含车辆、行人、商业裙房、城市背景建筑等类别，因此语义提案只使用当前可校验类别。',
    },
    {
      code: 'SMALL_OBJECT_LOW_CONFIDENCE',
      message: '路灯等小目标在该视角下较小，SAM 分割和空间落点可能不稳定。',
    },
  ],
}

export function defaultSemanticProposalText(): string {
  return JSON.stringify(defaultSemanticProposal, null, 2)
}
