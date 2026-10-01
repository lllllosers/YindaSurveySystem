"""沟段工程状况调查表
分项评价项目配置。

评价文字按正式调查评价表录入；本表采用 A/B/C 三级评价。
"""

DITCH_SECTION_EVALUATION_ITEMS = ({'item_code': 'hydraulic_drainage_capacity',
  'category': '水力条件',
  'item_name': '排水能力',
  'standards': {'A': '排水能力符合设计要求。', 'B': '排水能力为设计值的80%以上。', 'C': '排水能力小于设计值的80%。'}},
 {'item_code': 'hydraulic_discharge_capacity',
  'category': '水力条件',
  'item_name': '承泄能力',
  'standards': {'A': '承泄能力满足设计要求，滞流时间不超过作物耐淹历时。',
                'B': '承泄能力基本满足要求，滞流时间超过作物耐淹历时，不引起作物减产。',
                'C': '承泄能力不满足要求，滞流时间超过作物耐淹历时，引起作物减产。'}},
 {'item_code': 'hydraulic_outflow_status',
  'category': '水力条件',
  'item_name': '出流情况',
  'standards': {'A': '出流顺畅，无淤积或冲刷。', 'B': '出流局部有淤积或冲刷。', 'C': '出流受阻，淤积或冲刷严重。'}},
 {'item_code': 'section_bottom_status',
  'category': '断面状况',
  'item_name': '沟底状况',
  'standards': {'A': '沟底平整，比降合理。', 'B': '沟底局部阻水，比降基本合理。', 'C': '沟底凹凸不平，比降不合理。'}},
 {'item_code': 'section_slope_status',
  'category': '断面状况',
  'item_name': '边坡状况',
  'standards': {'A': '边坡稳定完好。', 'B': '坡面有雨水侵蚀，有滑塌迹象。', 'C': '边坡滑塌，行水受阻，影响沟道安全运行。'}},
 {'item_code': 'section_embankment_top_status',
  'category': '断面状况',
  'item_name': '堤顶状况',
  'standards': {'A': '堤顶满足管理通行要求，能有效防止地表水无序入沟，坡面无冲刷。',
                'B': '堤顶基本满足管理通行要求，局部有地表水入沟迹象，不影响沟道运行。',
                'C': '堤顶不满足管理通行要求，地表水无序入沟，冲淤严重，影响沟道运行。'}})
