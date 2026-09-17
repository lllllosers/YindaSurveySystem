from __future__ import annotations

import json

import database


OFFICIAL_MASTER_DATA_VERSION = "2026-09-official-v1"

OFFICIAL_MASTER_DATA_SOURCE = (
    "工程状况调查表编码对照表.xlsx + "
    "引大入秦工程统计表骨干渠道及所属水管所.xlsx"
)

OFFICIAL_DEPARTMENTS = ({'master_key': 'ORG-D01',
  'name': '总干渠处',
  'business_code': '1',
  'sort_order': 100,
  'description': None},
 {'master_key': 'ORG-D02',
  'name': '东一干灌区处',
  'business_code': '2',
  'sort_order': 200,
  'description': None},
 {'master_key': 'ORG-D03',
  'name': '东二干灌区处',
  'business_code': '3',
  'sort_order': 300,
  'description': None},
 {'master_key': 'ORG-D04',
  'name': '兰州新区供水处',
  'business_code': '4',
  'sort_order': 400,
  'description': None},
 {'master_key': 'ORG-D05',
  'name': '白银供水处',
  'business_code': '5',
  'sort_order': 500,
  'description': None})

OFFICIAL_OFFICES = ({'master_key': 'ORG-D01-O01',
  'parent_master_key': 'ORG-D01',
  'name': '渠首水管所',
  'business_code': '01',
  'sort_order': 101,
  'description': None},
 {'master_key': 'ORG-D01-O02',
  'parent_master_key': 'ORG-D01',
  'name': '天王沟水管所',
  'business_code': '02',
  'sort_order': 102,
  'description': None},
 {'master_key': 'ORG-D01-O03',
  'parent_master_key': 'ORG-D01',
  'name': '通远水管所',
  'business_code': '03',
  'sort_order': 103,
  'description': None},
 {'master_key': 'ORG-D01-O04',
  'parent_master_key': 'ORG-D01',
  'name': '香炉山水管所',
  'business_code': '04',
  'sort_order': 104,
  'description': None},
 {'master_key': 'ORG-D02-O01',
  'parent_master_key': 'ORG-D02',
  'name': '柳树水管所',
  'business_code': '01',
  'sort_order': 201,
  'description': None},
 {'master_key': 'ORG-D02-O02',
  'parent_master_key': 'ORG-D02',
  'name': '长涝池水管所',
  'business_code': '02',
  'sort_order': 202,
  'description': None},
 {'master_key': 'ORG-D02-O03',
  'parent_master_key': 'ORG-D02',
  'name': '陈家井水管所',
  'business_code': '03',
  'sort_order': 203,
  'description': None},
 {'master_key': 'ORG-D02-O04',
  'parent_master_key': 'ORG-D02',
  'name': '史喇口水管所',
  'business_code': '04',
  'sort_order': 204,
  'description': None},
 {'master_key': 'ORG-D03-O01',
  'parent_master_key': 'ORG-D03',
  'name': '汪家湾水管所',
  'business_code': '01',
  'sort_order': 301,
  'description': None},
 {'master_key': 'ORG-D03-O02',
  'parent_master_key': 'ORG-D03',
  'name': '清水水管所',
  'business_code': '02',
  'sort_order': 302,
  'description': None},
 {'master_key': 'ORG-D03-O03',
  'parent_master_key': 'ORG-D03',
  'name': '东古山水管所',
  'business_code': '03',
  'sort_order': 303,
  'description': None},
 {'master_key': 'ORG-D03-O04',
  'parent_master_key': 'ORG-D03',
  'name': '古山电力提灌所',
  'business_code': '04',
  'sort_order': 304,
  'description': '编码对照表简称：古山电灌水管所'},
 {'master_key': 'ORG-D03-O05',
  'parent_master_key': 'ORG-D03',
  'name': '黄茨滩水管所',
  'business_code': '05',
  'sort_order': 305,
  'description': None},
 {'master_key': 'ORG-D03-O06',
  'parent_master_key': 'ORG-D03',
  'name': '五墩水管所',
  'business_code': '06',
  'sort_order': 306,
  'description': None},
 {'master_key': 'ORG-D04-O01',
  'parent_master_key': 'ORG-D04',
  'name': '中川水管所',
  'business_code': '01',
  'sort_order': 401,
  'description': None},
 {'master_key': 'ORG-D04-O02',
  'parent_master_key': 'ORG-D04',
  'name': '尖山庙水库管理所',
  'business_code': '02',
  'sort_order': 402,
  'description': '编码对照表简称：尖山庙水管所'},
 {'master_key': 'ORG-D04-O03',
  'parent_master_key': 'ORG-D04',
  'name': '石门沟水库管理所',
  'business_code': '03',
  'sort_order': 403,
  'description': '编码对照表简称：石门沟水管所'},
 {'master_key': 'ORG-D05-O01',
  'parent_master_key': 'ORG-D05',
  'name': '黑石川水管所',
  'business_code': '01',
  'sort_order': 501,
  'description': None},
 {'master_key': 'ORG-D05-O02',
  'parent_master_key': 'ORG-D05',
  'name': '武川水管所',
  'business_code': '02',
  'sort_order': 502,
  'description': None},
 {'master_key': 'ORG-D05-O03',
  'parent_master_key': 'ORG-D05',
  'name': '英武水管所',
  'business_code': '03',
  'sort_order': 503,
  'description': None})

OFFICIAL_CANALS = ({'master_key': 'CANAL-G01',
  'name': '总干渠',
  'canal_level': '01',
  'parent_master_key': None,
  'organization_master_key': None,
  'sort_order': 1000,
  'description': None},
 {'master_key': 'CANAL-S001',
  'name': '通远支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G01',
  'organization_master_key': 'ORG-D01-O03',
  'sort_order': 1001,
  'description': None},
 {'master_key': 'CANAL-S002',
  'name': '晓林支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G01',
  'organization_master_key': 'ORG-D01-O03',
  'sort_order': 1002,
  'description': '移交通远乡管理'},
 {'master_key': 'CANAL-G02',
  'name': '东一干渠',
  'canal_level': '01',
  'parent_master_key': None,
  'organization_master_key': None,
  'sort_order': 2000,
  'description': None},
 {'master_key': 'CANAL-S003',
  'name': '右岸支',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D01-O04',
  'sort_order': 2003,
  'description': None},
 {'master_key': 'CANAL-S004',
  'name': '二支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2004,
  'description': None},
 {'master_key': 'CANAL-S005',
  'name': '一分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S004',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2005,
  'description': None},
 {'master_key': 'CANAL-S006',
  'name': '二分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S004',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2006,
  'description': None},
 {'master_key': 'CANAL-S007',
  'name': '康家井支',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2007,
  'description': None},
 {'master_key': 'CANAL-S008',
  'name': '三支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2008,
  'description': None},
 {'master_key': 'CANAL-S009',
  'name': '四支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O01',
  'sort_order': 2009,
  'description': None},
 {'master_key': 'CANAL-S010',
  'name': '五支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2010,
  'description': None},
 {'master_key': 'CANAL-S011',
  'name': '六支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2011,
  'description': None},
 {'master_key': 'CANAL-S012',
  'name': '七支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2012,
  'description': None},
 {'master_key': 'CANAL-S013',
  'name': '八支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2013,
  'description': None},
 {'master_key': 'CANAL-S014',
  'name': '八支一分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S013',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2014,
  'description': None},
 {'master_key': 'CANAL-S015',
  'name': '八支二分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S013',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2015,
  'description': None},
 {'master_key': 'CANAL-S016',
  'name': '庙沟分支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O02',
  'sort_order': 2016,
  'description': None},
 {'master_key': 'CANAL-S017',
  'name': '九支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O04',
  'sort_order': 2017,
  'description': None},
 {'master_key': 'CANAL-S018',
  'name': '九支一分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S017',
  'organization_master_key': 'ORG-D02-O04',
  'sort_order': 2018,
  'description': None},
 {'master_key': 'CANAL-S019',
  'name': '九支二分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S017',
  'organization_master_key': 'ORG-D02-O04',
  'sort_order': 2019,
  'description': None},
 {'master_key': 'CANAL-S020',
  'name': '九支三分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S017',
  'organization_master_key': 'ORG-D02-O04',
  'sort_order': 2020,
  'description': None},
 {'master_key': 'CANAL-S021',
  'name': '十支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D02-O03',
  'sort_order': 2021,
  'description': None},
 {'master_key': 'CANAL-S022',
  'name': '十一支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G02',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 2022,
  'description': None},
 {'master_key': 'CANAL-S023',
  'name': '十一一分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S022',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 2023,
  'description': None},
 {'master_key': 'CANAL-S024',
  'name': '十一二分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S022',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 2024,
  'description': None},
 {'master_key': 'CANAL-S025',
  'name': '十一三分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S022',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 2025,
  'description': None},
 {'master_key': 'CANAL-S026',
  'name': '十一四分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S022',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 2026,
  'description': None},
 {'master_key': 'CANAL-G03',
  'name': '东二干渠',
  'canal_level': '01',
  'parent_master_key': None,
  'organization_master_key': None,
  'sort_order': 3000,
  'description': None},
 {'master_key': 'CANAL-S027',
  'name': '六支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O02',
  'sort_order': 3027,
  'description': None},
 {'master_key': 'CANAL-S028',
  'name': '七支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O02',
  'sort_order': 3028,
  'description': None},
 {'master_key': 'CANAL-S029',
  'name': '八支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O02',
  'sort_order': 3029,
  'description': None},
 {'master_key': 'CANAL-S030',
  'name': '九支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O03',
  'sort_order': 3030,
  'description': None},
 {'master_key': 'CANAL-S031',
  'name': '十支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O03',
  'sort_order': 3031,
  'description': None},
 {'master_key': 'CANAL-S032',
  'name': '十一支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O03',
  'sort_order': 3032,
  'description': None},
 {'master_key': 'CANAL-S033',
  'name': '十二支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O03',
  'sort_order': 3033,
  'description': None},
 {'master_key': 'CANAL-S034',
  'name': '十三支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O03',
  'sort_order': 3034,
  'description': None},
 {'master_key': 'CANAL-S035',
  'name': '十四支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O05',
  'sort_order': 3035,
  'description': None},
 {'master_key': 'CANAL-S036',
  'name': '十六支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O05',
  'sort_order': 3036,
  'description': None},
 {'master_key': 'CANAL-S037',
  'name': '十七支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3037,
  'description': None},
 {'master_key': 'CANAL-S038',
  'name': '甘分干',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3038,
  'description': None},
 {'master_key': 'CANAL-S039',
  'name': '段家川支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G03',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3039,
  'description': '移交西电'},
 {'master_key': 'CANAL-S040',
  'name': '一分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S039',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3040,
  'description': '移交西电'},
 {'master_key': 'CANAL-S041',
  'name': '二分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S039',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3041,
  'description': '移交西电'},
 {'master_key': 'CANAL-S042',
  'name': '三分支',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S039',
  'organization_master_key': 'ORG-D03-O06',
  'sort_order': 3042,
  'description': '移交西电'},
 {'master_key': 'CANAL-G04',
  'name': '电灌分干渠',
  'canal_level': '02',
  'parent_master_key': None,
  'organization_master_key': None,
  'sort_order': 4000,
  'description': None},
 {'master_key': 'CANAL-S043',
  'name': '一支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4043,
  'description': None},
 {'master_key': 'CANAL-S044',
  'name': '二支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4044,
  'description': None},
 {'master_key': 'CANAL-S045',
  'name': '三支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4045,
  'description': None},
 {'master_key': 'CANAL-S046',
  'name': '四支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4046,
  'description': None},
 {'master_key': 'CANAL-S047',
  'name': '五支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4047,
  'description': None},
 {'master_key': 'CANAL-S048',
  'name': '六支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4048,
  'description': None},
 {'master_key': 'CANAL-S049',
  'name': '庙沟支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G04',
  'organization_master_key': 'ORG-D03-O04',
  'sort_order': 4049,
  'description': None},
 {'master_key': 'CANAL-G05',
  'name': '黑武分干渠',
  'canal_level': '02',
  'parent_master_key': None,
  'organization_master_key': None,
  'sort_order': 5000,
  'description': None},
 {'master_key': 'CANAL-S050',
  'name': '黑一支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O01',
  'sort_order': 5050,
  'description': None},
 {'master_key': 'CANAL-S051',
  'name': '羌坟沟分支渠',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S050',
  'organization_master_key': 'ORG-D05-O01',
  'sort_order': 5051,
  'description': None},
 {'master_key': 'CANAL-S052',
  'name': '黑二支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O01',
  'sort_order': 5052,
  'description': None},
 {'master_key': 'CANAL-S053',
  'name': '红拉排分支渠',
  'canal_level': '04',
  'parent_master_key': 'CANAL-S052',
  'organization_master_key': 'ORG-D05-O01',
  'sort_order': 5053,
  'description': None},
 {'master_key': 'CANAL-S054',
  'name': '马道沟支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D04-O03',
  'sort_order': 5054,
  'description': None},
 {'master_key': 'CANAL-S055',
  'name': '马道沟石门沟1#水库引水渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D04-O03',
  'sort_order': 5055,
  'description': '向石门沟水库引水'},
 {'master_key': 'CANAL-S056',
  'name': '尖山庙支渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D04-O02',
  'sort_order': 5056,
  'description': None},
 {'master_key': 'CANAL-S057',
  'name': '石门沟1#水库引水渠',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D04-O03',
  'sort_order': 5057,
  'description': None},
 {'master_key': 'CANAL-S058',
  'name': '1#供水管道',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D04-O01',
  'sort_order': 5058,
  'description': None},
 {'master_key': 'CANAL-S059',
  'name': '武一支',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O02',
  'sort_order': 5059,
  'description': '武川乡水利管理站管理'},
 {'master_key': 'CANAL-S060',
  'name': '武三支',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O02',
  'sort_order': 5060,
  'description': '武川乡水利管理站管理'},
 {'master_key': 'CANAL-S061',
  'name': '武四支斗',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O02',
  'sort_order': 5061,
  'description': '武川乡水利管理站管理'},
 {'master_key': 'CANAL-S062',
  'name': '武五支斗',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O02',
  'sort_order': 5062,
  'description': '武川乡水利管理站管理'},
 {'master_key': 'CANAL-S063',
  'name': '武六支斗',
  'canal_level': '03',
  'parent_master_key': 'CANAL-G05',
  'organization_master_key': 'ORG-D05-O02',
  'sort_order': 5063,
  'description': '武川乡水利管理站管理'})


def get_official_master_data_status():
    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                seed_key,
                source_description,
                details_json,
                applied_at
            FROM master_data_seed_history
            WHERE seed_key = ?
            """,
            (OFFICIAL_MASTER_DATA_VERSION,),
        ).fetchone()

    if row is None:
        return {
            "applied": False,
            "seed_key": (
                OFFICIAL_MASTER_DATA_VERSION
            ),
        }

    return {
        "applied": True,
        "seed_key": row["seed_key"],
        "source_description": (
            row["source_description"]
        ),
        "details": json.loads(
            row["details_json"] or "{}"
        ),
        "applied_at": row["applied_at"],
    }


def _rows(
    connection,
    sql,
    params=(),
):
    return connection.execute(
        sql,
        params,
    ).fetchall()


def _one_id_by_master_key(
    connection,
    table_name,
    master_key,
):
    row = connection.execute(
        (
            "SELECT id "
            f"FROM {table_name} "
            "WHERE master_key = ?"
        ),
        (master_key,),
    ).fetchone()

    if row is None:
        return None

    return int(row["id"])


def _set_description_if_empty(
    current_description,
    official_description,
):
    current = str(
        current_description or ""
    ).strip()

    if current:
        return current_description

    official = str(
        official_description or ""
    ).strip()

    return official or None


def _seed_department(
    connection,
    spec,
):
    existing_id = (
        _one_id_by_master_key(
            connection,
            "organization_units",
            spec["master_key"],
        )
    )

    if existing_id is not None:
        return existing_id, "existing"

    candidates = _rows(
        connection,
        """
        SELECT
            id,
            description
        FROM organization_units
        WHERE unit_type = 'department'
          AND parent_id IS NULL
          AND business_code = ?
        ORDER BY id
        """,
        (
            spec["business_code"],
        ),
    )

    if len(candidates) > 1:
        raise ValueError(
            "正式基层处无法安全匹配："
            f"{spec['name']}（代码 "
            f"{spec['business_code']}）"
            "存在多条候选记录。"
        )

    if candidates:
        row = candidates[0]

        connection.execute(
            """
            UPDATE organization_units
            SET
                master_key = ?,
                name = ?,
                business_code = ?,
                status = 'active',
                sort_order = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                spec["master_key"],
                spec["name"],
                spec["business_code"],
                spec["sort_order"],
                _set_description_if_empty(
                    row["description"],
                    spec["description"],
                ),
                row["id"],
            ),
        )

        return int(row["id"]), "adopted"

    cursor = connection.execute(
        """
        INSERT INTO organization_units (
            parent_id,
            name,
            unit_type,
            business_code,
            status,
            description,
            master_key,
            sort_order
        )
        VALUES (
            NULL, ?, 'department',
            ?, 'active', ?, ?, ?
        )
        """,
        (
            spec["name"],
            spec["business_code"],
            spec["description"],
            spec["master_key"],
            spec["sort_order"],
        ),
    )

    return int(cursor.lastrowid), "created"


def _seed_office(
    connection,
    spec,
    organization_ids,
):
    existing_id = (
        _one_id_by_master_key(
            connection,
            "organization_units",
            spec["master_key"],
        )
    )

    if existing_id is not None:
        return existing_id, "existing"

    parent_id = organization_ids[
        spec["parent_master_key"]
    ]

    candidates = _rows(
        connection,
        """
        SELECT
            id,
            description
        FROM organization_units
        WHERE unit_type = 'water_office'
          AND parent_id = ?
          AND business_code = ?
        ORDER BY id
        """,
        (
            parent_id,
            spec["business_code"],
        ),
    )

    if len(candidates) > 1:
        raise ValueError(
            "正式管理单位无法安全匹配："
            f"{spec['name']}（代码 "
            f"{spec['business_code']}）"
            "存在多条候选记录。"
        )

    if candidates:
        row = candidates[0]

        connection.execute(
            """
            UPDATE organization_units
            SET
                master_key = ?,
                parent_id = ?,
                name = ?,
                business_code = ?,
                status = 'active',
                sort_order = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                spec["master_key"],
                parent_id,
                spec["name"],
                spec["business_code"],
                spec["sort_order"],
                _set_description_if_empty(
                    row["description"],
                    spec["description"],
                ),
                row["id"],
            ),
        )

        return int(row["id"]), "adopted"

    cursor = connection.execute(
        """
        INSERT INTO organization_units (
            parent_id,
            name,
            unit_type,
            business_code,
            status,
            description,
            master_key,
            sort_order
        )
        VALUES (
            ?, ?, 'water_office',
            ?, 'active', ?, ?, ?
        )
        """,
        (
            parent_id,
            spec["name"],
            spec["business_code"],
            spec["description"],
            spec["master_key"],
            spec["sort_order"],
        ),
    )

    return int(cursor.lastrowid), "created"


def _canal_reference_count(
    connection,
    canal_id,
):
    asset_count = connection.execute(
        """
        SELECT COUNT(*) AS count_value
        FROM engineering_assets
        WHERE canal_unit_id = ?
        """,
        (canal_id,),
    ).fetchone()["count_value"]

    survey_count = connection.execute(
        """
        SELECT COUNT(*) AS count_value
        FROM survey_records
        WHERE canal_unit_id = ?
        """,
        (canal_id,),
    ).fetchone()["count_value"]

    return (
        int(asset_count)
        + int(survey_count)
    )


def _seed_canal(
    connection,
    spec,
    canal_ids,
    organization_ids,
):
    existing_id = (
        _one_id_by_master_key(
            connection,
            "canal_units",
            spec["master_key"],
        )
    )

    if existing_id is not None:
        return existing_id, "existing"

    parent_id = None

    if spec["parent_master_key"]:
        parent_id = canal_ids[
            spec["parent_master_key"]
        ]

    organization_id = None

    if spec["organization_master_key"]:
        organization_id = (
            organization_ids[
                spec[
                    "organization_master_key"
                ]
            ]
        )

    candidates = _rows(
        connection,
        """
        SELECT
            id,
            organization_unit_id,
            description
        FROM canal_units
        WHERE name = ?
          AND canal_level = ?
          AND (
                parent_id = ?
                OR (
                    parent_id IS NULL
                    AND ? IS NULL
                )
          )
        ORDER BY id
        """,
        (
            spec["name"],
            spec["canal_level"],
            parent_id,
            parent_id,
        ),
    )

    if len(candidates) > 1:
        raise ValueError(
            "正式渠系无法安全匹配："
            f"{spec['name']} "
            "在同一结构位置存在多条候选记录。"
        )

    if candidates:
        row = candidates[0]
        canal_id = int(row["id"])

        current_org_id = (
            int(row["organization_unit_id"])
            if (
                row["organization_unit_id"]
                is not None
            )
            else None
        )

        if (
            current_org_id
            != organization_id
            and _canal_reference_count(
                connection,
                canal_id,
            )
            > 0
        ):
            raise ValueError(
                "正式渠系匹配到已有业务数据，"
                "但管理单位与甲方新表不一致："
                f"{spec['name']}。"
                "为避免改写既有调查归属，"
                "本次初始化已停止。"
            )

        connection.execute(
            """
            UPDATE canal_units
            SET
                master_key = ?,
                organization_unit_id = ?,
                status = 'active',
                sort_order = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                spec["master_key"],
                organization_id,
                spec["sort_order"],
                _set_description_if_empty(
                    row["description"],
                    spec["description"],
                ),
                canal_id,
            ),
        )

        return canal_id, "adopted"

    cursor = connection.execute(
        """
        INSERT INTO canal_units (
            parent_id,
            name,
            canal_level,
            organization_unit_id,
            status,
            description,
            master_key,
            sort_order
        )
        VALUES (
            ?, ?, ?, ?,
            'active', ?,
            ?, ?
        )
        """,
        (
            parent_id,
            spec["name"],
            spec["canal_level"],
            organization_id,
            spec["description"],
            spec["master_key"],
            spec["sort_order"],
        ),
    )

    return int(cursor.lastrowid), "created"


def seed_official_master_data():
    """
    首次导入甲方确认的正式组织机构和渠系主数据。

    规则：
    - 新表名称优先；
    - 编码对照表用于组织业务代码；
    - 5 个干渠/分干渠的管理单位保持 NULL；
    - 新表备注直接写入渠道 description；
    - 渠道层级以新表所在列为准，不根据名称猜测；
    - 首次导入可接管能够唯一匹配的既有基础资料；
    - 一旦本版本种子成功，后续重复执行不覆盖人工修改。
    """

    with database.get_connection() as connection:
        already = connection.execute(
            """
            SELECT seed_key
            FROM master_data_seed_history
            WHERE seed_key = ?
            """,
            (OFFICIAL_MASTER_DATA_VERSION,),
        ).fetchone()

        if already is not None:
            return {
                "applied": False,
                "already_applied": True,
                "seed_key": (
                    OFFICIAL_MASTER_DATA_VERSION
                ),
            }

        counters = {
            "organization_created": 0,
            "organization_adopted": 0,
            "organization_existing": 0,
            "canal_created": 0,
            "canal_adopted": 0,
            "canal_existing": 0,
        }

        organization_ids = {}

        for spec in OFFICIAL_DEPARTMENTS:
            unit_id, action = (
                _seed_department(
                    connection,
                    spec,
                )
            )

            organization_ids[
                spec["master_key"]
            ] = unit_id

            counters[
                f"organization_{action}"
            ] += 1

        for spec in OFFICIAL_OFFICES:
            unit_id, action = (
                _seed_office(
                    connection,
                    spec,
                    organization_ids,
                )
            )

            organization_ids[
                spec["master_key"]
            ] = unit_id

            counters[
                f"organization_{action}"
            ] += 1

        canal_ids = {}

        for spec in OFFICIAL_CANALS:
            canal_id, action = (
                _seed_canal(
                    connection,
                    spec,
                    canal_ids,
                    organization_ids,
                )
            )

            canal_ids[
                spec["master_key"]
            ] = canal_id

            counters[
                f"canal_{action}"
            ] += 1

        details = {
            **counters,
            "department_count": len(
                OFFICIAL_DEPARTMENTS
            ),
            "office_count": len(
                OFFICIAL_OFFICES
            ),
            "canal_count": len(
                OFFICIAL_CANALS
            ),
        }

        connection.execute(
            """
            INSERT INTO master_data_seed_history (
                seed_key,
                source_description,
                details_json
            )
            VALUES (?, ?, ?)
            """,
            (
                OFFICIAL_MASTER_DATA_VERSION,
                OFFICIAL_MASTER_DATA_SOURCE,
                json.dumps(
                    details,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )

    return {
        "applied": True,
        "already_applied": False,
        "seed_key": (
            OFFICIAL_MASTER_DATA_VERSION
        ),
        **details,
    }
