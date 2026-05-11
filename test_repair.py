#!/usr/bin/env python3
"""Test _repair_json_string against real failed LLM responses from cron.log"""

import sys
sys.path.insert(0, "/root/code/wyRss")

from src.clients.llm_client import LLMClient
import json

test_cases = [
    {
        "name": "Trump-Jesus (截断 + 中文引号)",
        "raw": '''{
  "overall_score": 78,
  "relevance_score": 88,
  "novelty_score": 72,
  "actionability_score": 35,
  "summary": "特朗普在社交媒体发布AI生成的"特朗普-耶稣"图像，引发宗教团体争议。这些AI图像在传播过程中发生了诡异变化——云中士兵变成尖头无面的恶魔形象，人物表情从慈祥变得恐惧，建筑背景模糊化。文章揭示了AI生成图像在转发过程中的变形现象，并穿插了导演赫尔佐格对自己"疯狂企鹅"场景被制成梗图的幽默反应，以及华盛顿记者协会晚宴期间媒体与科技公司的合作动态分析。",
  "rec''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary"},
    },
    {
        "name": "量子位AIGC评选 (截断 + 中文引号)",
        "raw": '''{
  "overall_score": 58,
  "relevance_score": 75,
  "novelty_score": 55,
  "actionability_score": 70,
  "summary": "量子位发布2026年度AIGC企业&产品评选活动通知，征集具有真实落地场景、用户规模增长、差异化体验的AI企业和产品参选。评选维度涵盖技术、产品、市场、潜力四个方面，报名截止4月27日，5月将公布结果并举办中国AIGC产业峰会。文章指出当前AI产品"爆火多、留存少"的现象，旨在挖掘真正跑通场景的产品和具备潜力的企业。",
  "recommendation": "这''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary"},
    },
    {
        "name": "马斯克XChat (截断 + 中文引号)",
        "raw": '''{
  "overall_score": 78,
  "relevance_score": 85,
  "novelty_score": 72,
  "actionability_score": 45,
  "summary": "马斯克正式推出名为XChat的聊天应用，定于4月17日上线，支持中文和加密聊天功能。该应用定位为"下一代端到端加密通讯应用"，集成Grok AI助手，但更像是从X平台独立出来的私信系统，缺乏微信的熟人社交特性。马斯克多年来公开表达对微信的赞赏，此次推出XChat是其打造"超级应用"战略的重要一步，但网友普遍对其能否成功持怀疑态度。",
  "recommendati''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary"},
    },
    {
        "name": "北大DataFlex (截断在summary中间)",
        "raw": '''{
  "overall_score": 83,
  "relevance_score": 88,
  "novelty_score": 75,
  "actionability_score": 85,
  "summary": "北京大学联合LLaMA-Factory等机构发布DataFlex框架。

我注意到北京大学与LLaMA-Factory团队合作推出的DataFlex框架具有显著的技术创新性。这个开源项目不仅解决了动态数据处理的技术难题，还提供了统一的实践平台。整体而言，这是一个值得关注的AI基础设施项目。
```json
{
  "overall_score": 83,
 ''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary"},
    },
    {
        "name": "正常完整JSON (不应破坏)",
        "raw": '''{
  "overall_score": 85,
  "relevance_score": 90,
  "novelty_score": 80,
  "actionability_score": 75,
  "summary": "This is a normal summary without issues.",
  "recommendation": "Worth reading.",
  "keywords": ["AI", "tech"]
}''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary", "recommendation", "keywords"},
    },
    {
        "name": "智在世界模型 (截断 + 中文引号)",
        "raw": '''{
  "overall_score": 92,
  "relevance_score": 95,
  "novelty_score": 88,
  "actionability_score": 75,
  "summary": "智在无界发布第三代具身世界模型Being-H0.7，基于20万小时人类视频数据训练，提出潜空间推理的全新范式。该模型不再追求像素级重建，而是学习类似"物理直觉"的快速判断机制，采用双分支设计（后验与先验视角）实现对未来演化的隐式建模。在6项全球权威评测中综合排名第一，是首个覆盖七大关键维度的通用世界模型。其训练成本不到Cosmos Policy的1%，推理速度是Fa''',
        "expect_fields": {"overall_score", "relevance_score", "novelty_score", "actionability_score", "summary"},
    },
]

passed = 0
failed = 0

for tc in test_cases:
    try:
        result = LLMClient._extract_json(tc["raw"])
        # Check expected fields exist
        missing = tc["expect_fields"] - set(result.keys())
        if missing:
            print(f"❌ {tc['name']}: 缺少字段 {missing}")
            print(f"   解析结果: {list(result.keys())}")
            failed += 1
        else:
            print(f"✅ {tc['name']}: 成功 (字段: {list(result.keys())})")
            if tc["name"] != "正常完整JSON (不应破坏)":
                print(f"   summary: {result.get('summary', '')[:60]}...")
            passed += 1
    except Exception as e:
        print(f"❌ {tc['name']}: {e}")
        failed += 1

print(f"\n{'='*50}")
print(f"结果: {passed} 通过, {failed} 失败 / 共 {len(test_cases)} 个")
if failed == 0:
    print("🎉 全部通过！")
