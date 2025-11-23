"""
Anker 家庭安防 - 渐进式身份推理与评估系统

核心流程:
1. 数据排序: 从数据量少的家庭开始处理
2. 渐进式学习:
   - 将9月数据划分为: 训练流 + 验证集(随机采样50条，无交集)
   - 逐步将训练流加入记忆系统(分多个阶段)
   - 每次加入后,在验证集上评估准确率指标
3. 最终推理:
   - 补充完整9月记忆(包括验证集)
   - 对10月数据进行全量推理

评估指标:
- 身份大类准确率 (Role Type Accuracy)
- 身份子类准确率 (Sub-role Type Accuracy)
- 家人识别准确率 (Family Member Recognition)
- 异常检测准确率 (Anomaly Detection)
"""

import json
import sys
import time
import re
import math
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免在非主线程创建GUI
import matplotlib.pyplot as plt

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from memos.api.product_models import APIADDRequest, APIChatCompleteRequest
from memos.api.routers.server_router import add_memories, chat_complete, naive_mem_cube, llm
from memos.log import get_logger

logger = get_logger(__name__)

# 数据配置
DATA_DIR = project_root / "evaluation" / "data" / "anker" / "Test_data_22_pu_3_family_mothes_seperated"

# 家庭ID列表 (按数据量从小到大排序: F3 < F1 < F2)
FAMILY_ORDER = [
    "T8030P232228002B",  # ~1.8k events
    "T8030P1322100087",  # ~4.1k events
    "T8030P132215001F"   # ~5.7k events
]

class MetricsCalculator:
    """指标计算器"""
    
    @staticmethod
    def calculate(predictions: List[Dict], ground_truths: Dict[str, Dict]) -> Dict[str, float]:
        if not predictions:
            return {}
            
        total = 0
        correct_role = 0
        correct_sub_role = 0
        
        # 家人识别 (Binary: Family vs Non-Family)
        family_tp = 0
        family_tn = 0
        family_fp = 0
        family_fn = 0
        
        # 异常检测 (Binary: Abnormal vs Normal)
        # Abnormal = Suspicious Person OR Critical Non-Human Event
        anomaly_tp = 0
        anomaly_tn = 0
        anomaly_fp = 0
        anomaly_fn = 0
        
        for pred in predictions:
            vid = pred['video_path']
            if vid not in ground_truths:
                continue
                
            total += 1
            gt = ground_truths[vid]
            
            # 1. 基础准确率
            p_role = pred['predicted_role_type'].strip().lower()
            p_sub = pred['predicted_sub_role_type'].strip().lower()
            g_role = gt['role_type'].strip().lower()
            g_sub = gt['sub_role_type'].strip().lower()
            
            if p_role == g_role:
                correct_role += 1
            if p_sub == g_sub:
                correct_sub_role += 1
                
            # 2. 家人识别
            is_family_pred = (p_sub == 'family member')
            is_family_gt = (g_sub == 'family member')
            
            if is_family_pred and is_family_gt: family_tp += 1
            elif not is_family_pred and not is_family_gt: family_tn += 1
            elif is_family_pred and not is_family_gt: family_fp += 1
            elif not is_family_pred and is_family_gt: family_fn += 1
            
            # 3. 异常检测
            # 定义异常: role_type=Suspicious Person 或 sub_role_type=Critical Non-Human Event
            is_anomaly_gt = (g_role == 'suspicious person' or g_sub == 'critical non-human event')
            is_anomaly_pred = (p_role == 'suspicious person' or p_sub == 'critical non-human event')
            
            if is_anomaly_pred and is_anomaly_gt: anomaly_tp += 1
            elif not is_anomaly_pred and not is_anomaly_gt: anomaly_tn += 1
            elif is_anomaly_pred and not is_anomaly_gt: anomaly_fp += 1
            elif not is_anomaly_pred and is_anomaly_gt: anomaly_fn += 1

        # 计算指标
        def safe_div(a, b): return a / b if b > 0 else 0
        
        return {
            "role_acc": safe_div(correct_role, total),
            "sub_role_acc": safe_div(correct_sub_role, total),
            "family_acc": safe_div(family_tp + family_tn, total),
            "family_f1": safe_div(2 * family_tp, 2 * family_tp + family_fp + family_fn),
            "anomaly_acc": safe_div(anomaly_tp + anomaly_tn, total),
            "anomaly_recall": safe_div(anomaly_tp, anomaly_tp + anomaly_fn)
        }

def load_data(family_id: str) -> Tuple[List[Dict], List[Dict]]:
    """加载数据: 返回 (9月数据, 10月数据)"""
    
    # 1. Load Train (Sep)
    train_path = DATA_DIR / family_id / f"{family_id}_09.json"
    with open(train_path, 'r', encoding='utf-8') as f:
        train_raw = json.load(f)
        
    train_events = []
    for path, data in train_raw.items():
        data['video_path'] = path
        train_events.append(data)
    # 按时间排序
    train_events.sort(key=lambda x: x['timestamp'])
    
    # 2. Load Test (Oct)
    test_path = DATA_DIR / family_id / f"{family_id}_10_no_role.json"
    test_events = []
    if test_path.exists():
        with open(test_path, 'r', encoding='utf-8') as f:
            test_raw = json.load(f)
        for path, data in test_raw.items():
            data['video_path'] = path
            test_events.append(data)
        test_events.sort(key=lambda x: x['timestamp'])
        
    return train_events, test_events

def format_timestamp(ts):
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

def get_time_period(ts):
    try:
        h = int(ts[8:10])
        if 6 <= h < 12: return "Morning"
        elif 12 <= h < 18: return "Afternoon"
        elif 18 <= h < 22: return "Evening"
        return "Night"
    except:
        return "Unknown"


def _get_metadata_value(metadata, key):
    if metadata is None:
        return None
    if isinstance(metadata, dict):
        return metadata.get(key)
    return getattr(metadata, key, None)


def _extract_pattern_dimension(memory_item):
    metadata = getattr(memory_item, "metadata", None)
    key = _get_metadata_value(metadata, "key")
    if key:
        return key
    topic = _get_metadata_value(metadata, "topic")
    if topic:
        return topic
    memory_text = getattr(memory_item, "memory", "").lower()
    if "leave" in memory_text and "return" in memory_text:
        return "family_leave_return"
    if "delivery" in memory_text:
        return "delivery_pattern"
    if "visitor" in memory_text:
        return "visitor_pattern"
    return None


def merge_duplicate_patterns(user_id, mem_cube_id, session_id, min_cluster_size=3):
    """合并重复维度的规律记忆，并删除旧的"""
    try:
        pattern_memories = naive_mem_cube.text_mem.search(
            query="[Pattern Memory]",
            user_name=mem_cube_id,
            top_k=200,
        )
    except Exception as e:
        logger.warning(f"无法检索 Pattern Memory 进行合并: {e}")
        return []
    
    clusters = defaultdict(list)
    for mem in pattern_memories:
        # 跳过已经合并过的记忆
        memory_text = getattr(mem, "memory", "")
        if "[Merged]" in memory_text or "MASTER PATTERN" in memory_text:
            continue
        key = _extract_pattern_dimension(mem)
        if not key:
            continue
        clusters[key].append(mem)
    
    merge_reports = []
    for key, mems in clusters.items():
        if len(mems) < min_cluster_size:
            continue
        report = _merge_pattern_cluster(key, mems, user_id, mem_cube_id, session_id)
        if report:
            merge_reports.append(report)
    
    if merge_reports:
        print("\n" + "═" * 100)
        print("🧹 【Pattern Memory Consolidation Summary】")
        for report in merge_reports:
            print(f"  Key: {report['key']}")
            print(f"    ➕ 新增记忆: {report['new_id']}")
            print(f"    ➖ 删除旧记忆({len(report['deleted_ids'])}): {', '.join(report['deleted_ids'])}")
        print("═" * 100 + "\n")
    
    return merge_reports


def _merge_pattern_cluster(key, mems, user_id, mem_cube_id, session_id):
    mems = sorted(
        mems,
        key=lambda m: _get_metadata_value(getattr(m, "metadata", None), "created_at") or "",
        reverse=True,
    )
    snippet_lines = []
    for mem in mems[:20]:
        created = _get_metadata_value(getattr(mem, "metadata", None), "created_at")
        snippet_lines.append(f"- ID:{getattr(mem, 'id', 'N/A')} | Time:{created} | {getattr(mem, 'memory', '')}")
    snippet_text = "\n".join(snippet_lines)
    
    prompt = f"""You are merging overlapping security pattern memories for a smart home.
Pattern dimension (key): {key}

Existing pattern memories:
{snippet_text}

Please consolidate them into a single, more accurate pattern.
Return JSON:
{{
  "merged_pattern": "<concise pattern sentence>",
  "time_range": "<HH:MM-HH:MM or description>",
  "evidence_summary": "<how many observations support it>",
  "confidence": "<High/Medium/Low>"
}}"""
    
    req = APIChatCompleteRequest(
        user_id=user_id,
        mem_cube_id=mem_cube_id,
        query=prompt,
        moscube=True,
        top_k=5,
        threshold=0.3,
        internet_search=False,
        session_id=session_id,
    )
    
    try:
        res = chat_complete(req)
        raw = res.get("data", {}).get("response", "") if isinstance(res, dict) else ""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        merged_result = json.loads(cleaned)
    except Exception as e:
        logger.warning(f"合并模式 LLM 响应解析失败，跳过此维度 {key}: {e}")
        return None
    
    merged_pattern = merged_result.get("merged_pattern")
    if not merged_pattern:
        return None
    time_range = merged_result.get("time_range", "N/A")
    evidence_summary = merged_result.get("evidence_summary", "")
    confidence = merged_result.get("confidence", "Medium")
    
    merged_content = (
        f"[Pattern Memory][Merged][Key: {key}] {merged_pattern}\n"
        f"Time Range: {time_range}\n"
        f"Evidence: {evidence_summary}\n"
        f"Confidence: {confidence}\n"
        f"Source: Consolidated from {len(mems)} historical memories."
    )
    
    add_req = APIADDRequest(
        user_id=user_id,
        mem_cube_id=mem_cube_id,
        messages=[{"role": "user", "content": merged_content}],
        session_id=session_id,
        source="anker_security_merge",
    )
    add_res = add_memories(add_req)
    new_ids = []
    if add_res and add_res.data:
        new_ids = [entry.get("memory_id") for entry in add_res.data if entry.get("memory_id")]
    
    delete_ids = [getattr(mem, "id", None) for mem in mems if getattr(mem, "id", None)]
    if delete_ids:
        try:
            naive_mem_cube.text_mem.delete(delete_ids)
        except Exception as e:
            logger.warning(f"删除旧记忆失败 {delete_ids}: {e}")
    
    print("\n" + "-" * 100)
    print(f"🧹 Pattern Consolidation - Key: {key}")
    print("   删除的记忆:")
    for mem in mems:
        print(f"     • {getattr(mem, 'id', 'N/A')}: {getattr(mem, 'memory', '')}")
    print("   新增记忆:")
    for new_id in new_ids:
        print(f"     ➕ {new_id}: {merged_pattern}")
    print("-" * 100 + "\n")
    
    return {
        "key": key,
        "new_id": new_ids[0] if new_ids else "N/A",
        "deleted_ids": delete_ids,
        "merged_pattern": merged_pattern,
    }


def _search_memories_for_user(query, mem_cube_id, top_k=2000):
    """基于 query 和 user，检索记忆并去重"""
    try:
        results = naive_mem_cube.text_mem.search(
            query=query,
            user_name=mem_cube_id,
            top_k=top_k,
        )
    except Exception as e:
        logger.warning(f"    ⚠️ 检索记忆失败 ({query}): {e}")
        return []
    
    memories = []
    seen_ids = set()
    for mem in results or []:
        mem_id = getattr(mem, "id", None)
        if not mem_id or mem_id in seen_ids:
            continue
        seen_ids.add(mem_id)
        memories.append({
            "id": mem_id,
            "memory": getattr(mem, "memory", ""),
            "created_at": _get_metadata_value(getattr(mem, "metadata", None), "created_at") or "N/A"
        })
    return memories


def _filter_memories_by_tags(memories, tags):
    return [
        mem for mem in memories
        if any(tag in mem["memory"] for tag in tags)
    ]


def save_all_memories_and_stats(family_id, mem_cube_id, output_dir, family_logger=None, memory_stats=None):
    """保存当前家庭的记忆快照（事实/规律/推理）及统计信息"""
    log = family_logger if family_logger else logger
    
    try:
        factual_mems = _search_memories_for_user("[Factual Memory]", mem_cube_id)
        if not factual_mems:
            factual_mems = _search_memories_for_user("Ground Truth Label", mem_cube_id)
        factual_mems = _filter_memories_by_tags(factual_mems, ["[Factual Memory]", "Ground Truth Label"])
        
        pattern_mems = _search_memories_for_user("[Pattern Memory]", mem_cube_id)
        pattern_mems = _filter_memories_by_tags(pattern_mems, ["[Pattern Memory]", "[规律记忆]"])
        
        inference_mems = _search_memories_for_user("[Inference Memory]", mem_cube_id)
        inference_mems = _filter_memories_by_tags(inference_mems, ["[Inference Memory]", "[推理记忆]"])
        
        memory_dir = output_dir / "memories"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot = {
            "family_id": family_id,
            "timestamp": datetime.now().isoformat(),
            "memory_counts": {
                "factual": len(factual_mems),
                "pattern": len(pattern_mems),
                "inference": len(inference_mems),
                "total_active": len(factual_mems) + len(pattern_mems) + len(inference_mems),
            },
            "deletion_stats": memory_stats or {"deletion_ops": 0, "deleted_count": 0},
            "memories": {
                "factual": factual_mems,
                "pattern": pattern_mems,
                "inference": inference_mems,
            },
        }
        
        with open(memory_dir / f"{family_id}_memories.json", 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        log.info(
            f"    💾 记忆快照已保存: memories/{family_id}_memories.json "
            f"(Factual={len(factual_mems)}, Pattern={len(pattern_mems)}, Infer={len(inference_mems)})"
        )
        if memory_stats:
            log.info(
                f"    🧹 删除统计: 操作 {memory_stats.get('deletion_ops', 0)} 次, "
                f"共删除 {memory_stats.get('deleted_count', 0)} 条记忆"
            )
        
    except Exception as e:
        log.error(f"    ❌ 保存记忆快照失败: {e}")
        import traceback
        log.error(traceback.format_exc())


def plot_progress_metrics(progress_log, family_id, output_dir, mode_label, family_logger=None):
    """绘制并保存准确率进度曲线图
    
    Args:
        progress_log: 包含各阶段指标的列表
        family_id: 家庭ID
        output_dir: 输出目录
        mode_label: 模式标签
        family_logger: 可选的logger，如果未提供则使用全局logger
    """
    if not progress_log:
        return None
    
    log = family_logger if family_logger else logger
    
    try:
        phases = [entry["phase"] for entry in progress_log]
        role_acc = [entry["metrics"]["role_acc"] * 100 for entry in progress_log]
        sub_acc = [entry["metrics"]["sub_role_acc"] * 100 for entry in progress_log]
        family_acc = [entry["metrics"]["family_acc"] * 100 for entry in progress_log]
        anomaly_acc = [entry["metrics"]["anomaly_acc"] * 100 for entry in progress_log]
        
        plt.figure(figsize=(10, 6))
        plt.plot(phases, role_acc, marker='o', label="Role Type")
        plt.plot(phases, sub_acc, marker='s', label="Sub-role")
        plt.plot(phases, family_acc, marker='^', label="Family Recognition")
        plt.plot(phases, anomaly_acc, marker='d', label="Anomaly Detection")
        plt.xlabel("Training Phase")
        plt.ylabel("Accuracy (%)")
        plt.title(f"{family_id} - Accuracy Progress ({mode_label})")
        plt.ylim(0, 100)
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend()
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        plot_path = output_dir / f"{family_id}_{mode_label.replace(' ', '_')}_accuracy_progress.png"
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150)
        plt.close()
        log.info(f"📈 进度曲线已保存: {plot_path}")
        return plot_path
    except Exception as e:
        log.error(f"❌ 绘制进度曲线失败: {e}")
        import traceback
        log.error(traceback.format_exc())
        return None

def clean_duplicate_dimension_memories(mem_cube_id, family_logger=None, memory_stats=None):
    """清理相同维度的重复记忆，只保留最新的
    
    这个函数会检索所有 Pattern Memory，按维度分组，
    对于每个维度，只保留创建时间最新的记忆，删除旧的。
    
    Args:
        mem_cube_id: 记忆立方体ID
        family_logger: 日志记录器
        memory_stats: 统计字典
    """
    log = family_logger if family_logger else logger
    
    try:
        # 检索所有 Pattern Memory
        pattern_memories = naive_mem_cube.text_mem.search(
            query="[Pattern Memory]",
            user_name=mem_cube_id,
            top_k=200,
        )
        
        if not pattern_memories:
            return
        
        # 按维度分组
        dimension_groups = defaultdict(list)
        for mem in pattern_memories:
            memory_text = getattr(mem, "memory", "")
            # 跳过已经合并过的记忆
            if "[Merged]" in memory_text:
                continue
            
            # 提取维度
            dimension = _extract_pattern_dimension(mem)
            if not dimension:
                dimension = "unknown"
            
            dimension_groups[dimension].append(mem)
        
        # 对于每个维度，只保留最新的一条
        total_deleted = 0
        for dimension, mems in dimension_groups.items():
            if len(mems) <= 1:
                continue  # 只有一条，不需要清理
            
            # 按创建时间排序，保留最新的
            mems_sorted = sorted(
                mems,
                key=lambda m: _get_metadata_value(getattr(m, "metadata", None), "created_at") or "",
                reverse=True
            )
            
            # 保留第一条（最新），删除其他
            latest_mem = mems_sorted[0]
            old_mems = mems_sorted[1:]
            
            # 删除旧记忆
            old_ids = [getattr(m, "id", None) for m in old_mems if getattr(m, "id", None)]
            if old_ids:
                try:
                    naive_mem_cube.text_mem.delete(old_ids)
                    deleted_count = len(old_ids)
                    total_deleted += deleted_count
                    
                    if memory_stats is not None:
                        memory_stats["deletion_ops"] += 1
                        memory_stats["deleted_count"] += deleted_count
                    
                    log.info(
                        f"    🧹 维度 '{dimension}': 保留最新记忆 "
                        f"(ID: {getattr(latest_mem, 'id', 'N/A')[:8]}...), "
                        f"删除 {deleted_count} 条旧记忆"
                    )
                except Exception as e:
                    log.warning(f"    ⚠️  删除维度 '{dimension}' 的旧记忆失败: {e}")
        
        if total_deleted > 0:
            log.info(f"    ✅ 总共清理了 {total_deleted} 条重复维度的旧记忆")
    
    except Exception as e:
        log.warning(f"    ⚠️  清理重复维度记忆时出错: {e}")


def add_events_to_memory(
    events,
    user_id,
    mem_cube_id,
    session_id,
    phase_info=None,
    include_labels=False,
    clean_duplicates=True,
    family_logger=None,
    memory_stats=None,
):
    """批量添加事件到记忆 (包含内容增强 + 进度展示 + 自动去重)
    
    Args:
        phase_info: dict with keys: current_phase, total_phases, phase_start_time
        include_labels: 是否包含标签（role_type 和 sub_role_type）用于训练学习
        clean_duplicates: 是否在添加后清理相同维度的重复记忆（默认True）
        family_logger: 日志记录器
        memory_stats: 统计字典，用于记录删除操作次数和数量 {"deletion_ops": 0, "deleted_count": 0}
    """
    log = family_logger if family_logger else logger
    total = len(events)
    start_t = time.time()
    accumulated = 0.0
    
    for i, event in enumerate(events, 1):
        event_start = time.time()
        ts = event.get('timestamp', '')
        time_str = format_timestamp(ts)
        period = get_time_period(ts)
        
        # 基础观察内容
        enhanced_content = f"""[Security Log]
Time: {time_str} ({period})
Observation: {event['original_description']}"""

        # 如果是训练阶段，添加标签信息帮助学习
        if include_labels and 'role_type' in event and 'sub_role_type' in event:
            role = event['role_type']
            sub_role = event['sub_role_type']
            desc = event['original_description']
            
            # 强制引导生成包含身份的 Pattern Memory
            # 我们将身份信息直接嵌入到描述中，使其成为"特征"的一部分
            enhanced_content += f"""

[Historical Labeled Sample]
Ground Truth Label: Role={role}, Sub-role={sub_role}
Visual Context: Matches visual profile for {sub_role}.

[CRITICAL INSTRUCTION FOR MEMORY EXTRACTION]
1. For the Factual Memory (UserMemory): Embed BOTH the observation text and labels in ONE sentence. Use this template:
   "[Factual Memory] Time: {time_str} | Observation: {desc} | Ground Truth Label: Role={role}, Sub-role={sub_role}"
2. Never emit an empty factual memory containing only the label.
3. For the Pattern Memory: You MUST include the specific identity label. Format it exactly like this:
   "Identity: {sub_role} ({role}) | Visuals: {desc}" """
        else:
            enhanced_content += f"""

Note: Extract key visual features (clothes, colors), vehicle details, and behavioral patterns to aid future identity re-identification."""

        add_req = APIADDRequest(
            user_id=user_id,
            mem_cube_id=mem_cube_id,
            messages=[{"role": "user", "content": enhanced_content}],
            session_id=session_id,
            source="anker_security"
        )
        try:
            add_memories(add_req)
            
            iter_cost = time.time() - event_start
            accumulated += iter_cost
            
            if total <= 50 or i % 20 == 0 or i == total:
                avg_cost = accumulated / i
                remaining = max(total - i, 0) * avg_cost
                speed = (1 / avg_cost) if avg_cost > 0 else 0
                percent = (i / total * 100) if total else 100
                
                # 计算预计完成时间
                eta_timestamp = time.time() + remaining
                eta_str = datetime.fromtimestamp(eta_timestamp).strftime("%H:%M:%S")
                
                phase_prefix = ""
                if phase_info:
                    phase_prefix = f"[阶段 {phase_info['current_phase']}/{phase_info['total_phases']}] "
                
                log.info(
                    f"    {phase_prefix}[写入] {i}/{total} ({percent:.1f}%) | "
                    f"本次 {iter_cost:.2f}s | 平均 {avg_cost:.2f}s | "
                    f"速率 {speed:.1f}条/s | 本批剩余 {remaining:.0f}s | ETA {eta_str}"
                )
        except Exception as e:
            log.error(f"    ❌ 写入第 {i}/{total} 条事件时失败: {e}")
            
    elapsed = time.time() - start_t
    log.info(f"    ✅ 批次写入完成，共 {total} 条，耗时 {elapsed:.1f}s")
    
    # 添加完成后，等待一小段时间让 MemOS 处理记忆提取
    time.sleep(2)
    
    # 清理相同维度的重复记忆
    if clean_duplicates:
        log.info(f"    🔍 检查并清理相同维度的重复记忆...")
        clean_duplicate_dimension_memories(mem_cube_id, family_logger=log, memory_stats=memory_stats)
    
    return elapsed

def infer_event(event, user_id, mem_cube_id):
    """推理单个事件（包含检索记忆）
    
    Returns:
        tuple: (role_type, sub_role_type, confidence, reasoning, retrieved_memories, prompt)
    """
    desc = event['original_description']
    ts = event['timestamp']
    period = get_time_period(ts)
    fmt_time = format_timestamp(ts)
    
    # 先检索相关记忆
    retrieved_memories = []
    few_shot_examples = []
    learned_prototypes = []
    
    try:
        # 1. 检索相似事件（用于 Few-Shot）
        # 使用描述检索具体的历史事件
        search_query = f"Similar event: {desc[:200]}"
        memories = naive_mem_cube.text_mem.search(
            query=search_query,
            user_name=mem_cube_id,
            top_k=15,  # 增加数量以筛选高质量样本
        )
        
        for mem in memories:
            mem_text = getattr(mem, "memory", "")
            mem_id = getattr(mem, "id", "N/A")
            metadata = getattr(mem, "metadata", None)
            created_at = _get_metadata_value(metadata, "created_at") or "N/A"
            
            # 分类记忆类型
            is_pattern = "[Pattern Memory]" in mem_text
            is_gt_sample = "Ground Truth Label" in mem_text or "[Historical Labeled Sample]" in mem_text
            
            # 收集 Few-Shot 样本 (必须包含 GT 标签)
            if is_gt_sample:
                few_shot_examples.append(mem_text)
            
            # 收集原型 (Pattern Memory)
            if is_pattern and ("Identity:" in mem_text or "Visuals:" in mem_text):
                learned_prototypes.append(mem_text)
            
            # 记录检索到的所有相关记忆（用于调试和分析）
            retrieved_memories.append({
                "memory_id": mem_id,
                "memory_text": mem_text[:500],  # 截断太长的记忆
                "created_at": created_at,
                "type": "Pattern" if is_pattern else ("GT Sample" if is_gt_sample else "Other")
            })
            
        # 限制数量
        few_shot_examples = few_shot_examples[:5]
        learned_prototypes = learned_prototypes[:5]
            
    except Exception as e:
        logger.warning(f"Failed to retrieve memories: {e}")
    
    # 构建增强 Prompt
    few_shot_block = ""
    if few_shot_examples:
        few_shot_block = "\n[Historical Similar Events (Few-Shot Examples)]\n" + "\n".join([f"{i+1}. {m}" for i, m in enumerate(few_shot_examples)])
        
    prototype_block = ""
    if learned_prototypes:
        prototype_block = "\n[Learned Identity Prototypes]\n" + "\n".join([f"- {p}" for p in learned_prototypes])

    query = f"""Analyze this home security event and classify the identity based on learned family patterns.
{prototype_block}
{few_shot_block}

Current Event:
- Time: {fmt_time} ({period})
- Description: {desc}

## Classification System
**role_type**: General Identity | Passerby | Staff | Suspicious Person | Unspecified | Non-Human
**sub_role_type**: 
- General Identity → Family Member | Visitor | Other General Identity
- Passerby → Passerby
- Staff → Delivery Person | Police | Service Worker | Other Staff
- Suspicious Person → Unauthorized Entry | Property Damage | Armed Person | Fighting | Other Suspicious Person
- Non-Human → Vehicle Activity | Pet/Animal Activity | Environmental Change Only

⚠️ CRITICAL: "Family Member" and "Visitor" are sub_role_type ONLY, never use them as role_type.

## Key Guidance

**Location is critical:**
- Person exiting FROM or inside courtyard/residence → likely Family Member (not Passerby)
- Person walking PAST outside with no interaction → likely Passerby
- Interacting with residence (door, car, mailbox) → Family Member or Visitor

**Identity signals:**
- Visual match with learned family patterns → Family Member
- Uniform or delivery behavior → Staff
- Forced entry, weapons, breaking things → Suspicious Person

Output format:
role_type: [one of the 6 types above]
sub_role_type: [corresponding sub-type]
confidence: [High/Medium/Low]
reasoning: [Your analysis: location, interaction, visual match, and conclusion]
"""
    try:
        response = llm.generate([{"role": "user", "content": query}])
        role, sub, conf, reasoning = parse_result(response)
        # 后处理：修正常见的分类错误（传入描述用于基于位置的修正）
        role, sub = fix_classification_errors(role, sub, desc)
        return role, sub, conf, reasoning, retrieved_memories, query
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        return "Unspecified", "Unspecified", "Low", "", retrieved_memories, query

def fix_classification_errors(role_type, sub_role_type, description=""):
    """修正常见的分类层级错误
    
    常见错误：
    1. Family Member / Visitor 被错误地用作 role_type
    2. 需要确保 Family Member/Visitor 的 role_type 是 General Identity
    3. 从院子/住宅里出来的人被误判为Passerby
    """
    desc_lower = description.lower()
    
    # 🚨 关键修正：基于位置语义的强制修正
    # 如果描述包含"从院子里出来"等关键词，但被分类为Passerby，强制改为Family Member
    exit_phrases = [
        "out of the courtyard",
        "from the courtyard", 
        "exits residence",
        "walks out of",
        "exiting from",
        "leaves the residence",
        "from the residence"
    ]
    
    inside_phrases = [
        "in the courtyard",
        "in the property",
        "in a residential courtyard",
        "inside the courtyard"
    ]
    
    # 检查是否从内部出来或在内部活动
    is_exiting = any(phrase in desc_lower for phrase in exit_phrases)
    is_inside = any(phrase in desc_lower for phrase in inside_phrases)
    
    if (is_exiting or is_inside) and role_type == "Passerby":
        logger.warning(f"⚠️ 位置修正: '{desc_lower[:50]}...' 包含住宅内部活动，Passerby → General Identity / Family Member")
        return "General Identity", "Family Member"
    
    # 修正Family Member错误
    if role_type.lower() in ["family member", "family"]:
        logger.warning(f"⚠️ 层级修正: role_type='Family Member' → 'General Identity' / 'Family Member'")
        return "General Identity", "Family Member"
    
    # 修正Visitor错误  
    if role_type.lower() == "visitor":
        logger.warning(f"⚠️ 层级修正: role_type='Visitor' → 'General Identity' / 'Visitor'")
        return "General Identity", "Visitor"
    
    # 修正其他可能的sub_role被用作role_type的情况
    sub_role_values = {
        "delivery person": ("Staff", "Delivery Person"),
        "police": ("Staff", "Police"),
        "service worker": ("Staff", "Service Worker"),
        "government worker": ("Staff", "Government Worker"),
        "unauthorized entry": ("Suspicious Person", "Unauthorized Entry"),
        "property damage": ("Suspicious Person", "Property Damage"),
        "armed person": ("Suspicious Person", "Armed Person"),
        "fighting": ("Suspicious Person", "Fighting"),
    }
    
    role_lower = role_type.lower()
    if role_lower in sub_role_values:
        correct_role, correct_sub = sub_role_values[role_lower]
        logger.warning(f"⚠️ 修正错误: role_type='{role_type}' → '{correct_role}' / '{correct_sub}'")
        return correct_role, correct_sub
    
    return role_type, sub_role_type

def parse_result(text):
    role = "Unspecified"
    sub = "Unspecified"
    conf = "Low"
    reason = ""
    
    rm = re.search(r'role_type:\s*\[?([^\]\n]+)\]?', text, re.IGNORECASE)
    if rm: role = rm.group(1).strip()
    
    sm = re.search(r'sub_role_type:\s*\[?([^\]\n]+)\]?', text, re.IGNORECASE)
    if sm: sub = sm.group(1).strip()
    
    cm = re.search(r'confidence:\s*\[?([^\]\n]+)\]?', text, re.IGNORECASE)
    if cm: conf = cm.group(1).strip()
    
    return role, sub, conf, text

def _partition_predictions(predictions, ground_truths):
    """将预测结果按正确/错误类型分组"""
    partitions = {
        "correct": [],
        "wrong_role_type": [],
        "wrong_sub_role_type": [],
        "wrong_both": [],
        "total": 0,
    }
    
    for pred in predictions:
        vid = pred['video_path']
        gt = ground_truths.get(vid)
        if not gt:
            continue
        
        partitions["total"] += 1
        
        p_role = pred['predicted_role_type'].strip().lower()
        p_sub = pred['predicted_sub_role_type'].strip().lower()
        g_role = gt['role_type'].strip().lower()
        g_sub = gt['sub_role_type'].strip().lower()
        
        role_correct = (p_role == g_role)
        sub_correct = (p_sub == g_sub)
        
        comparison = {
            "video_path": vid,
            "timestamp": gt.get('timestamp', 'N/A'),
            "description": gt.get('original_description', 'N/A'),
            "ground_truth": {
                "role_type": gt['role_type'],
                "sub_role_type": gt['sub_role_type']
            },
            "predicted": {
                "role_type": pred['predicted_role_type'],
                "sub_role_type": pred['predicted_sub_role_type'],
                "confidence": pred.get('confidence', 'N/A')
            },
            "reasoning": pred.get('reasoning', 'N/A'),
            "retrieved_memories_count": len(pred.get('retrieved_memories', []))
        }
        
        if role_correct and sub_correct:
            partitions["correct"].append(comparison)
        elif not role_correct and not sub_correct:
            partitions["wrong_both"].append(comparison)
        elif not role_correct:
            partitions["wrong_role_type"].append(comparison)
        else:
            partitions["wrong_sub_role_type"].append(comparison)
    
    return partitions


def _build_analysis_summary(partitions):
    """基于分组结果生成深度分析摘要"""
    total = partitions["total"]
    correct = len(partitions["correct"])
    wrong_role = len(partitions["wrong_role_type"])
    wrong_sub = len(partitions["wrong_sub_role_type"])
    wrong_both = len(partitions["wrong_both"])
    
    all_wrong = partitions["wrong_role_type"] + partitions["wrong_sub_role_type"] + partitions["wrong_both"]
    role_related_errors = partitions["wrong_role_type"] + partitions["wrong_both"]
    sub_related_errors = partitions["wrong_sub_role_type"] + partitions["wrong_both"]
    
    avg_retrieved = sum(s['retrieved_memories_count'] for s in all_wrong) / len(all_wrong) if all_wrong else 0
    zero_retrieval = sum(1 for s in all_wrong if s['retrieved_memories_count'] == 0)
    min_retrieved = min((s['retrieved_memories_count'] for s in all_wrong), default=0)
    max_retrieved = max((s['retrieved_memories_count'] for s in all_wrong), default=0)
    zero_ratio = (zero_retrieval / len(all_wrong)) if all_wrong else 0
    
    def _extract_confusions(records, label):
        counter = defaultdict(int)
        for rec in records:
            gt = rec['ground_truth'].get(label, "Unknown")
            pred = rec['predicted'].get(label, "Unknown")
            if gt == pred:
                continue
            counter[(gt, pred)] += 1
        sorted_pairs = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:5]
        return [
            {"from": pair[0], "to": pair[1], "count": count}
            for (pair, count) in sorted_pairs
        ]
    
    role_confusions = _extract_confusions(role_related_errors, "role_type")
    sub_confusions = _extract_confusions(sub_related_errors, "sub_role_type")
    
    # 提取高频视觉关键词（支持中英文）
    confusion_keywords = defaultdict(int)
    stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'of', 'with', 'and', 'to', 'is', 'are',
                  'wearing', 'dressed', 'scene', 'near', 'from', 'toward', 'into', 'person', 'people'}
    for err in all_wrong:
        desc = err['description']
        if not desc or desc == 'N/A':
            continue
        words = re.findall(r'[a-zA-Z]{3,}', desc.lower())
        chinese_tokens = re.findall(r'[\u4e00-\u9fff]{1,2}', desc)
        for w in words:
            if w not in stop_words:
                confusion_keywords[w] += 1
        for token in chinese_tokens:
            confusion_keywords[token] += 1
    
    top_keywords = sorted(confusion_keywords.items(), key=lambda x: x[1], reverse=True)[:5]
    if not top_keywords and all_wrong:
        top_keywords = [{"keyword": "描述不足，无法提取视觉模式", "count": len(all_wrong)}]
    elif not top_keywords:
        top_keywords = [{"keyword": "全部预测正确，无视觉混淆", "count": 0}]
    
    suggestions = []
    
    if not all_wrong:
        suggestions.append("验证集中样本全部预测正确，可增加困难样本验证泛化。")
    else:
        role_error_ratio = len(role_related_errors) / len(all_wrong)
        sub_error_ratio = len(sub_related_errors) / len(all_wrong)
        
        if zero_ratio > 0.3:
            suggestions.append("检索召回不足：超过30%的错误样本未检索到记忆，需检查向量索引或增大 top_k。")
        if avg_retrieved > 3 and len(partitions["wrong_both"]) / len(all_wrong) > 0.5:
            suggestions.append("推理一致性较差：检索数量充足但仍大量错误，建议优化 Prompt 或提升 Pattern Memory 质量。")
        if role_error_ratio >= 0.4:
            top_pair = role_confusions[0] if role_confusions else None
            detail = f"Top: {top_pair['from']}→{top_pair['to']}" if top_pair else "Top: N/A"
            suggestions.append(f"身份大类混淆占比高（{role_error_ratio*100:.1f}%）。{detail}")
        if sub_error_ratio >= 0.4:
            top_pair = sub_confusions[0] if sub_confusions else None
            detail = f"Top: {top_pair['from']}→{top_pair['to']}" if top_pair else "Top: N/A"
            suggestions.append(f"身份子类混淆占比高（{sub_error_ratio*100:.1f}%）。{detail}")
        def _kw_label(item):
            if isinstance(item, dict):
                return item.get("keyword", "")
            return item[0]
        
        if any(_kw_label(k) in {"black", "dark", "blue", "white"} for k in top_keywords):
            suggestions.append("视觉特征过于依赖颜色，建议在描述中加入服饰细节或物品特征以增强区分度。")
        if not suggestions:
            suggestions.append("错误样本数量有限，建议扩展验证集或主动标注以暴露更多失败模式。")
    
    summary = {
        "overview": {
            "total": total,
            "correct": correct,
            "accuracy": (correct / total) if total else 0,
            "wrong_role_only": wrong_role,
            "wrong_sub_only": wrong_sub,
            "wrong_both": wrong_both,
        },
        "retrieval_quality": {
            "avg_retrieved_for_errors": avg_retrieved,
            "min_retrieved_for_errors": min_retrieved,
            "max_retrieved_for_errors": max_retrieved,
            "zero_retrieval_ratio": zero_ratio,
        },
        "visual_confusion_keywords": [
            item if isinstance(item, dict) else {"keyword": item[0], "count": item[1]}
            for item in top_keywords
        ],
        "dominant_confusions": {
            "role_type": role_confusions,
            "sub_role_type": sub_confusions,
        },
        "suggestions": suggestions,
    }
    
    return summary


def analyze_evaluation_results(all_eval_results, family_id, output_dir, family_logger=None):
    """分析所有评估结果，找出抽取好的和不好的样本"""
    log = family_logger if family_logger else logger
    
    log.info(f"\n{'='*80}")
    log.info(f"📊 最终评估分析 - 家庭 {family_id}")
    log.info(f"{'='*80}")
    
    # 收集所有预测结果（使用最后一次评估）
    if not all_eval_results:
        log.warning("  ⚠️  没有评估结果可供分析")
        return
    
    last_eval = all_eval_results[-1]
    predictions = last_eval.get("predictions", [])
    ground_truths = last_eval.get("ground_truths", {})
    
    partitions = _partition_predictions(predictions, ground_truths)
    summary = _build_analysis_summary(partitions)
    
    total = summary["overview"]["total"]
    correct_count = summary["overview"]["correct"]
    wrong_role_type = partitions["wrong_role_type"]
    wrong_sub_role_type = partitions["wrong_sub_role_type"]
    wrong_both = partitions["wrong_both"]
    correct_predictions = partitions["correct"]
    
    # 输出统计
    log.info(f"\n  ✅ 完全正确: {correct_count}/{total} ({correct_count/total*100:.1f}%)")
    log.info(f"  ❌ Role Type 错误: {len(wrong_role_type)}")
    log.info(f"  ❌ Sub-role Type 错误: {len(wrong_sub_role_type)}")
    log.info(f"  ❌ 两者都错误: {len(wrong_both)}")
    
    # 分析常见错误模式
    log.info(f"\n  🔍 常见错误模式分析:")
    
    # Role Type 错误统计
    if wrong_role_type or wrong_both:
        role_errors = wrong_role_type + wrong_both
        error_patterns = defaultdict(int)
        for err in role_errors:
            pattern = f"{err['ground_truth']['role_type']} → {err['predicted']['role_type']}"
            error_patterns[pattern] += 1
        
        log.info(f"\n    Role Type 混淆矩阵 (Top 5):")
        for pattern, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]:
            log.info(f"      • {pattern}: {count}次")
    
    # Sub-role Type 错误统计
    if wrong_sub_role_type or wrong_both:
        sub_errors = wrong_sub_role_type + wrong_both
        error_patterns = defaultdict(int)
        for err in sub_errors:
            pattern = f"{err['ground_truth']['sub_role_type']} → {err['predicted']['sub_role_type']}"
            error_patterns[pattern] += 1
        
        log.info(f"\n    Sub-role Type 混淆矩阵 (Top 5):")
        for pattern, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]:
            log.info(f"      • {pattern}: {count}次")

    log.info(f"\n  🧠 深度错误归因分析:")
    log.info(f"    • 错误样本平均检索记忆数: {summary['retrieval_quality']['avg_retrieved_for_errors']:.1f}")
    log.info(f"    • 无记忆检索样本占比: {summary['retrieval_quality']['zero_retrieval_ratio']*100:.1f}%")
    if summary["visual_confusion_keywords"]:
        keywords_str = ", ".join([f"{item['keyword']}({item['count']})" for item in summary["visual_confusion_keywords"]])
        log.info(f"    • 高频混淆视觉特征词: {keywords_str}")
    for sug in summary["suggestions"]:
        log.info(f"    ⚠️  {sug}")

    # 保存详细分析
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = analysis_dir / f"{family_id}_final_analysis.json"
    
    analysis_data = {
        "family_id": family_id,
        "timestamp": datetime.now().isoformat(),
        "summary": summary["overview"],
        "deep_analysis": {
            "retrieval_quality": summary["retrieval_quality"],
            "visual_confusion_keywords": summary["visual_confusion_keywords"],
            "automated_suggestions": summary["suggestions"]
        },
        "correct_samples": correct_predictions[:10],  # 保存前10个正确样本
        "wrong_samples": {
            "wrong_role_type": wrong_role_type[:10],
            "wrong_sub_role_type": wrong_sub_role_type[:10],
            "wrong_both": wrong_both[:10]
        }
    }
    
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    
    log.info(f"\n  💾 详细分析已保存到: {analysis_file}")
    log.info(f"{'='*80}\n")


def evaluate_on_set(eval_events, user_id, mem_cube_id, desc="Validation", phase_info=None, 
                    family_id=None, output_dir=None, family_logger=None, save_details=True):
    """在指定数据集上评估（并行推理）
    
    Args:
        phase_info: dict with keys: current_phase, total_phases
        family_id: 家庭ID（用于保存详细结果）
        output_dir: 输出目录
        family_logger: 日志记录器
        save_details: 是否保存详细结果
    """
    log = family_logger if family_logger else logger
    log.info(f"  🔍 正在进行 {desc} 评估 (共 {len(eval_events)} 条，并行推理)...")
    
    ground_truths = {e['video_path']: e for e in eval_events}
    predictions = [None] * len(eval_events)
    
    start_t = time.time()
    total = len(eval_events)
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def _eval_infer(idx_event):
        idx, event = idx_event
        role, sub, conf, reasoning, retrieved_memories, prompt = infer_event(event, user_id, mem_cube_id)
        return idx, {
            "video_path": event['video_path'],
            "predicted_role_type": role,
            "predicted_sub_role_type": sub,
            "confidence": conf,
            "reasoning": reasoning,
            "retrieved_memories": retrieved_memories,
            "prompt": prompt
        }
    
    # 并行推理，无worker限制
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_eval_infer, (idx, event)) for idx, event in enumerate(eval_events)]
        completed = 0
        
        for future in as_completed(futures):
            idx, pred = future.result()
            predictions[idx] = pred
            completed += 1
            
            # 优化进度显示
            elapsed = time.time() - start_t
            avg_time = elapsed / completed if completed else 0
            remaining = (total - completed) * avg_time
            eta_timestamp = time.time() + remaining
            eta_str = datetime.fromtimestamp(eta_timestamp).strftime("%H:%M:%S")
            
            if completed % 5 == 0 or completed == total:  # 每5条更新一次
                bar_len = 20
                filled = int(completed / total * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                
                phase_prefix = ""
                if phase_info:
                    phase_prefix = f"[阶段 {phase_info['current_phase']}/{phase_info['total_phases']}] "
                
                sys.stdout.write(
                    f"\r    {phase_prefix}[评估] [{bar}] {completed}/{total} | "
                    f"耗时 {elapsed:.1f}s | 剩余 {remaining:.0f}s | ETA {eta_str}"
                )
                sys.stdout.flush()
    
    sys.stdout.write("\n")
    metrics = MetricsCalculator.calculate(predictions, ground_truths)
    partitions = _partition_predictions(predictions, ground_truths)
    analysis_summary = _build_analysis_summary(partitions)
    
    # 输出所有错误案例的推理原因（完整描述，不截断）
    # 收集所有错误样本（按优先级）
    all_wrong = partitions["wrong_both"] + partitions["wrong_role_type"] + partitions["wrong_sub_role_type"]
    
    if all_wrong:
        log.info(f"\n  🔍 错误样本推理分析 (共 {len(all_wrong)} 个错误):")
        # 显示所有错误样本（无限制）
        for i, sample in enumerate(all_wrong, 1):
            log.info(f"    【错误样本 {i}】")
            log.info(f"      描述: {sample['description']}")  # 完整描述，不截断
            log.info(f"      真实标签: {sample['ground_truth']['role_type']} / {sample['ground_truth']['sub_role_type']}")
            log.info(f"      预测标签: {sample['predicted']['role_type']} / {sample['predicted']['sub_role_type']}")
            log.info(f"      置信度: {sample['predicted']['confidence']}")
            log.info(f"      使用记忆数: {sample['retrieved_memories_count']}")
            # 提取reasoning的核心部分（去掉重复的标签信息）
            reasoning_text = sample.get('reasoning', '')
            if 'reasoning:' in reasoning_text:
                reasoning_core = reasoning_text.split('reasoning:')[-1].strip()
                # 完整显示推理依据，不截断
                log.info(f"      推理依据: {reasoning_core}")
            log.info("")
    
    if phase_info and phase_info.get('current_phase') == phase_info.get('total_phases'):
        log.info(f"  🧠 最终阶段错误分析:")
        log.info(f"    - 平均检索记忆数(错误样本): {analysis_summary['retrieval_quality']['avg_retrieved_for_errors']:.1f}")
        log.info(f"    - 无检索命中占比: {analysis_summary['retrieval_quality']['zero_retrieval_ratio']*100:.1f}%")
        if analysis_summary["visual_confusion_keywords"]:
            keywords_str = ", ".join([f"{item['keyword']}({item['count']})" for item in analysis_summary["visual_confusion_keywords"]])
            log.info(f"    - 高频视觉混淆特征: {keywords_str}")
        for sug in analysis_summary["suggestions"]:
            log.info(f"    ⚠️  {sug}")
    
    log.info(f"  📊 评估结果 ({desc}):")
    log.info(f"    - 身份大类准确率: {metrics['role_acc']*100:.1f}%")
    log.info(f"    - 身份子类准确率: {metrics['sub_role_acc']*100:.1f}%")
    log.info(f"    - 家人识别准确率: {metrics['family_acc']*100:.1f}%")
    log.info(f"    - 异常检测准确率: {metrics['anomaly_acc']*100:.1f}%")
    
    # 保存详细评估结果
    if save_details and family_id and output_dir:
        eval_dir = output_dir / "evaluations"
        eval_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建文件名
        phase_str = f"phase_{phase_info['current_phase']}" if phase_info else "final"
        eval_file = eval_dir / f"{family_id}_{phase_str}_eval.json"
        
        # 构建详细对比
        detailed_results = []
        for pred in predictions:
            vid = pred['video_path']
            if vid in ground_truths:
                gt = ground_truths[vid]
                detailed_results.append({
                    "video_path": vid,
                    "timestamp": gt.get('timestamp', 'N/A'),
                    "description": gt.get('original_description', 'N/A'),
                    "ground_truth": {
                        "role_type": gt['role_type'],
                        "sub_role_type": gt['sub_role_type']
                    },
                    "predicted": {
                        "role_type": pred['predicted_role_type'],
                        "sub_role_type": pred['predicted_sub_role_type'],
                        "confidence": pred['confidence']
                    },
                    "correct": {
                        "role_type": pred['predicted_role_type'].strip().lower() == gt['role_type'].strip().lower(),
                        "sub_role_type": pred['predicted_sub_role_type'].strip().lower() == gt['sub_role_type'].strip().lower()
                    },
                    "reasoning": pred.get('reasoning', 'N/A'),
                    "retrieved_memories": pred.get('retrieved_memories', []),
                    "prompt": pred.get('prompt', 'N/A')
                })
        
        eval_data = {
            "family_id": family_id,
            "phase": phase_str,
            "description": desc,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "total_samples": total,
            "detailed_results": detailed_results,
            "analysis_summary": analysis_summary
        }
        
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(eval_data, f, indent=2, ensure_ascii=False)
        
        log.info(f"  💾 详细评估结果已保存到: {eval_file}")
    
    return metrics, predictions, ground_truths

def process_family(
    family_id: str,
    output_dir: Path,
    split_ratio=0.1,
    max_train_events: int | None = None,
    max_test_samples: int | None = None,
    preflight: bool = False,
    family_logger=None,
):
    """处理单个家庭的完整流程"""
    
    # 如果没有传入family_logger，使用全局logger
    if family_logger is None:
        family_logger = logger
    
    # 注意：不要修改全局logger，直接使用family_logger
    
    family_logger.info(f"\n{'#'*60}")
    family_logger.info(f"🏠 处理家庭: {family_id}")
    family_logger.info(f"{'#'*60}")
    
    # 1. 准备环境
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = f"anker_{family_id}_{timestamp}"
    mem_cube_id = f"cube_{family_id}_{timestamp}"
    session_id = f"sess_{family_id}_{timestamp}"
    
    # 2. 加载并切分数据
    train_all, test_oct = load_data(family_id)
    
    if max_train_events is not None:
        train_all = train_all[:max_train_events]
    if max_test_samples is not None:
        test_oct = test_oct[:max_test_samples]
    
    # 随机切分 Validation Set (固定50条，从9月数据中随机采样)
    val_size = 50  # 固定验证集大小为50条
    # 确保数据量足够
    if len(train_all) < val_size + 10:  # 至少需要50条验证+10条训练
        # 如果数据太少，动态调整验证集大小
        val_size = max(3, int(len(train_all) * 0.2))  # 至少3条，最多20%
    
    # 随机采样验证集索引
    all_indices = list(range(len(train_all)))
    random.seed(42)  # 设置随机种子以保证可复现
    val_indices = set(random.sample(all_indices, val_size))
    
    # 分离训练集和验证集（确保无交集）
    validation_set = [train_all[i] for i in range(len(train_all)) if i in val_indices]
    train_stream = [train_all[i] for i in range(len(train_all)) if i not in val_indices]
    
    # 3. 渐进式训练与验证
    # split_ratio 控制训练流每次加入的比例（默认 20%）
    chunk_size = int(len(train_stream) * split_ratio)
    # 确保chunk不为0
    chunk_size = max(chunk_size, 1)
    total_phases = math.ceil(len(train_stream) / chunk_size) if len(train_stream) > 0 else 0
    
    mode_label = "PRE-FLIGHT" if preflight else "FULL RUN"
    family_logger.info(f"📊 数据概览 ({mode_label}):")
    family_logger.info(f"  - 9月总数据: {len(train_all)}")
    family_logger.info(f"  - 训练流 (Training Stream): {len(train_stream)} (随机采样)")
    family_logger.info(f"  - 验证集 (Validation Set): {len(validation_set)} (随机采样，无交集)")
    family_logger.info(f"  - 10月测试集: {len(test_oct)}")
    family_logger.info(f"  - 训练阶段数: {total_phases} (chunk size={chunk_size})")
    
    family_logger.info(f"\n🔄 开始渐进式学习 ({mode_label}) (Chunk size: {chunk_size})...")
    
    progress_log = []
    all_eval_results = []  # 保存所有评估结果用于最终分析
    phase_start_time = time.time()
    
    # 初始化记忆操作统计
    memory_stats = {"deletion_ops": 0, "deleted_count": 0}
    
    # 预估每个阶段的时间（基于首个阶段的实际耗时动态调整）
    estimated_phase_time = None
    
    current_idx = 0
    chunk_num = 1
    
    while current_idx < len(train_stream):
        end_idx = min(current_idx + chunk_size, len(train_stream))
        current_chunk = train_stream[current_idx:end_idx]
        
        phase_info = {"current_phase": chunk_num, "total_phases": total_phases, "phase_start_time": phase_start_time}
        
        family_logger.info(f"\n👉 第 {chunk_num}/{total_phases} 阶段: 加入 {len(current_chunk)} 条记忆 ({current_idx}-{end_idx}) [{mode_label}]")
        family_logger.info(f"   📈 家庭 {family_id} 训练进度: {end_idx}/{len(train_stream)} ({end_idx/len(train_stream)*100:.1f}%)")
        
        phase_iter_start = time.time()
        
        # A. 加入记忆（包含标签信息用于学习，并自动清理重复维度）
        add_events_to_memory(current_chunk, user_id, mem_cube_id, session_id, 
                            phase_info=phase_info, include_labels=True,
                            clean_duplicates=True, family_logger=family_logger,
                            memory_stats=memory_stats)
        
        # B. 验证
        family_logger.info(f"   🧪 在验证集上评估 (基于前 {end_idx} 条记忆)...")
        metrics, predictions, ground_truths = evaluate_on_set(
            validation_set, user_id, mem_cube_id, f"Phase {chunk_num}", 
            phase_info=phase_info,
            family_id=family_id,
            output_dir=output_dir,
            family_logger=family_logger,
            save_details=True
        )
        
        # 保存评估结果用于最终分析
        all_eval_results.append({
            "phase": chunk_num,
            "predictions": predictions,
            "ground_truths": ground_truths,
            "metrics": metrics
        })
        
        # 记录单阶段耗时并预估剩余时间
        phase_elapsed = time.time() - phase_iter_start
        if estimated_phase_time is None:
            estimated_phase_time = phase_elapsed  # 首次记录
        else:
            # 动态平均
            estimated_phase_time = (estimated_phase_time + phase_elapsed) / 2
        
        remaining_phases = total_phases - chunk_num
        estimated_remaining = remaining_phases * estimated_phase_time
        total_eta_timestamp = time.time() + estimated_remaining
        total_eta_str = datetime.fromtimestamp(total_eta_timestamp).strftime("%H:%M:%S")
        
        family_logger.info(
            f"   ⏱️  本阶段耗时: {phase_elapsed:.1f}s | "
            f"剩余 {remaining_phases} 阶段 | 预计完成时间: {total_eta_str}"
        )
        
        progress_log.append({
            "phase": chunk_num,
            "trained_events": end_idx,
            "metrics": metrics
        })
        
        current_idx = end_idx
        chunk_num += 1
    
    # 绘制准确率进度曲线
    plot_progress_metrics(progress_log, family_id, output_dir, mode_label, family_logger=family_logger)
        
    # 最终分析评估结果（仅在非预检模式下执行）
    if not preflight and all_eval_results:
        analyze_evaluation_results(all_eval_results, family_id, output_dir, family_logger)
        
    # 4. 补充验证集到记忆（包含标签）
    family_logger.info(f"\n📦 补充验证集到记忆库 (为了10月推理)...")
    add_events_to_memory(validation_set, user_id, mem_cube_id, session_id, 
                        phase_info=None, include_labels=True,
                        clean_duplicates=True, family_logger=family_logger,
                        memory_stats=memory_stats)
    
    # 保存最终的全量记忆和统计
    save_all_memories_and_stats(family_id, mem_cube_id, output_dir, family_logger, memory_stats)
    
    # 5. 最终10月推理（实时写入）
    family_logger.info(f"\n🔮 开始10月数据全量推理 ({len(test_oct)} 条) [{mode_label}]...")
    
    suffix = "preflight" if preflight else "full_results"
    out_file = output_dir / f"{family_id}_{suffix}.json"
    
    # 初始化文件，写入基础结构
    initial_data = {
        "family_id": family_id,
        "progress_metrics": progress_log,
        "october_predictions": [],
        "status": "in_progress",
        "total": len(test_oct),
        "completed": 0
    }
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, indent=2, ensure_ascii=False)
    
    oct_predictions = [None] * len(test_oct)
    start_t = time.time()
    completed_count = 0
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    write_lock = threading.Lock()
    
    def _infer(idx_event):
        idx, event = idx_event
        role, sub, conf, reasoning, retrieved_memories, prompt = infer_event(event, user_id, mem_cube_id)
        return idx, {
            "video_path": event['video_path'],
            "timestamp": event['timestamp'],
            "original_description": event['original_description'],
            "predicted_role_type": role,
            "predicted_sub_role_type": sub,
            "confidence": conf,
            "reasoning": reasoning,
            "retrieved_memories": retrieved_memories,
            "prompt": prompt
        }
    
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_infer, (idx, event)) for idx, event in enumerate(test_oct)]
        total = len(futures)
        
        for future in as_completed(futures):
            idx, pred = future.result()
            oct_predictions[idx] = pred
            completed_count += 1
            
            # 实时写入文件（每完成一条就更新）
            with write_lock:
                current_data = {
                    "family_id": family_id,
                    "progress_metrics": progress_log,
                    "october_predictions": [p for p in oct_predictions if p is not None],
                    "status": "in_progress" if completed_count < total else "completed",
                    "total": total,
                    "completed": completed_count
                }
                with open(out_file, 'w', encoding='utf-8') as f:
                    json.dump(current_data, f, indent=2, ensure_ascii=False)
            
            if completed_count % 5 == 0 or completed_count == total:
                percent = completed_count / total * 100 if total else 100
                elapsed = time.time() - start_t
                avg = elapsed / completed_count if completed_count else 0
                remaining = (total - completed_count) * avg
                eta_timestamp = time.time() + remaining
                eta_str = datetime.fromtimestamp(eta_timestamp).strftime("%H:%M:%S")
                logger.info(
                    f"    [10月推理] {completed_count}/{total} ({percent:.1f}%) | "
                    f"耗时 {elapsed:.1f}s | 剩余 {remaining:.0f}s | ETA {eta_str}"
                )
    
    total_time = time.time() - start_t
    family_logger.info(f"\n✅ 10月推理完成! 并发耗时: {total_time:.1f}s")
    family_logger.info(f"💾 结果实时保存至: {out_file}")
    
    # 最终数据
    final_data = {
        "family_id": family_id,
        "progress_metrics": progress_log,
        "october_predictions": oct_predictions,
        "status": "completed",
        "total": len(test_oct),
        "completed": len([p for p in oct_predictions if p is not None])
    }
    
    return final_data

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Anker家庭安防渐进式推理")
    parser.add_argument(
        "--mode",
        choices=["quick", "single", "all", "fast_test"],
        default="single",
        help="运行模式：quick=最小数据家庭，single=单个家庭，all=全部家庭，fast_test=快速全流程验证(训练200+验证50+推理10)",
    )
    parser.add_argument(
        "--family",
        type=str,
        default=None,
        help="指定家庭ID（single模式必填，all模式可选）",
    )
    parser.add_argument(
        "--max-train-events",
        type=int,
        default=None,
        help="限制训练事件数量（可选）",
    )
    parser.add_argument(
        "--max-test-samples",
        type=int,
        default=None,
        help="限制10月推理事件数量（可选）",
    )
    parser.add_argument(
        "--split-ratio",
        type=float,
        default=0.26,
        help="训练流每阶段比例（默认0.26=26%，确保最多4个阶段）",
    )
    
    args = parser.parse_args()
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = project_root / "examples" / "poc" / "inference_results" / f"progressive_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"🚀 任务开始 - 模式: {args.mode} - 输出目录: {output_dir}")
    
    summary = {}
    
    def run_preflight_check(target_family: str):
        logger.info(f"🧪 预检: 在家庭 {target_family} 上执行小样本流程以验证管线...")
        preflight_dir = output_dir / "preflight_checks"
        preflight_dir.mkdir(exist_ok=True)
        process_family(
            target_family,
            preflight_dir,
            split_ratio=0.5,  # 预检阶段使用50%，只需2个阶段
            max_train_events=15,  # 15条数据 → 训练流12条+验证集3条 → 2个阶段(每阶段6条)
            max_test_samples=3,   # 只推理3条测试数据
            preflight=True,
        )
        logger.info("🧪 预检完成，开始正式流程...\n")
    
    if args.mode == "fast_test":
        # 快速全流程验证：所有家庭，训练200条+验证50条，推理10条
        families = FAMILY_ORDER if not args.family else [args.family]
        total = len(families)
        logger.info(f"⚡ 快速验证模式：并行测试所有家庭 ({total}个) - 训练200条+验证50条+推理10条")
        
        # 为每个家庭创建独立的日志文件
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        family_loggers = {}
        log_dir = output_dir / "family_logs"
        log_dir.mkdir(exist_ok=True)
        
        def setup_family_logger(family_id):
            """为每个家庭创建独立的 logger"""
            family_logger = logging.getLogger(f"family_{family_id}")
            family_logger.setLevel(logging.INFO)
            family_logger.handlers.clear()
            family_logger.propagate = False  # 防止日志向上传播到根logger
            
            # 文件handler
            fh = logging.FileHandler(log_dir / f"{family_id}.log", encoding='utf-8', mode='w')
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            fh.setFormatter(formatter)
            family_logger.addHandler(fh)
            
            # 同时输出到控制台（带家庭ID前缀）
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch_formatter = logging.Formatter(f'[{family_id}] %(message)s')
            ch.setFormatter(ch_formatter)
            family_logger.addHandler(ch)
            
            return family_logger
        
        for fam in families:
            family_loggers[fam] = setup_family_logger(fam)
        
        def process_family_fast_test(family_id):
            """快速测试单个家庭"""
            family_logger = family_loggers[family_id]
            try:
                family_logger.info(f"▶ 快速测试家庭 {family_id}")
                
                process_family(
                    family_id,
                    output_dir,
                    split_ratio=0.25,  # 每次加入25%，4个批次
                    max_train_events=250,  # 快速测试：250条训练数据（训练流200条+验证集50条）→ 4批次，每批50条
                    max_test_samples=10,   # 快速测试：10条10月数据
                    preflight=False,
                    family_logger=family_logger,
                )
                
                family_logger.info(f"✅ 完成家庭 {family_id}")
                return family_id, "Success", None
            except Exception as e:
                family_logger.error(f"❌ 家庭 {family_id} 处理失败: {e}")
                import traceback
                family_logger.error(traceback.format_exc())
                return family_id, "Failed", str(e)
        
        # 并行处理所有家庭
        logger.info(f"🚀 开始并行快速测试 {total} 个家庭...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(total, 3)) as executor:
            futures = {executor.submit(process_family_fast_test, fam): fam for fam in families}
            completed = 0
            
            for future in as_completed(futures):
                family_id, status, error = future.result()
                completed += 1
                summary[family_id] = status if status == "Success" else f"Failed: {error}"
                
                elapsed = time.time() - start_time
                logger.info(
                    f"📊 进度: {completed}/{total} ({completed/total*100:.1f}%) | "
                    f"已完成: {family_id} ({status}) | 总耗时: {elapsed:.1f}s"
                )
        
        total_elapsed = time.time() - start_time
        logger.info(f"\n🎉 快速测试完成！总耗时: {total_elapsed:.1f}s")
    
    elif args.mode == "quick":
        target_family = args.family or FAMILY_ORDER[0]
        logger.info(f"🔹 快速模式：仅处理数据量最小的家庭 {target_family}")
        process_family(
            target_family,
            output_dir,
            split_ratio=args.split_ratio,
            max_train_events=args.max_train_events or 10,
            max_test_samples=args.max_test_samples or 10,
        )
        summary[target_family] = "Success"
    
    elif args.mode == "single":
        if not args.family:
            args.family = FAMILY_ORDER[0]  # 默认使用数据量最小的家庭
        logger.info(f"🔹 单家庭模式：{args.family}")
        run_preflight_check(args.family)
        process_family(
            args.family,
            output_dir,
            split_ratio=args.split_ratio,
            max_train_events=args.max_train_events,
            max_test_samples=args.max_test_samples,
            preflight=False,
        )
        summary[args.family] = "Success"
    
    else:  # 全量模式 - 并行处理所有家庭
        families = FAMILY_ORDER if not args.family else [args.family]
        total = len(families)
        
        logger.info("🧪 全量模式预检：将并行对每个家庭执行小样本流程...")
        
        # 并行执行预检
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(total, 3)) as executor:
            preflight_futures = {executor.submit(run_preflight_check, fam): fam for fam in families}
            for future in as_completed(preflight_futures):
                fam = preflight_futures[future]
                try:
                    future.result()
                    logger.info(f"✅ 家庭 {fam} 预检完成")
                except Exception as e:
                    logger.error(f"❌ 家庭 {fam} 预检失败: {e}")
        
        logger.info("🧪 所有家庭预检完成，开始并行全量运行。\n")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        # 为每个家庭创建独立的日志文件
        family_loggers = {}
        log_dir = output_dir / "family_logs"
        log_dir.mkdir(exist_ok=True)
        
        def setup_family_logger(family_id):
            """为每个家庭创建独立的 logger"""
            family_logger = logging.getLogger(f"family_{family_id}")
            family_logger.setLevel(logging.INFO)
            family_logger.handlers.clear()
            family_logger.propagate = False  # 防止日志向上传播到根logger
            
            # 文件handler
            fh = logging.FileHandler(log_dir / f"{family_id}.log", encoding='utf-8', mode='w')
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            fh.setFormatter(formatter)
            family_logger.addHandler(fh)
            
            # 同时输出到控制台（带家庭ID前缀）
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch_formatter = logging.Formatter(f'[{family_id}] %(message)s')
            ch.setFormatter(ch_formatter)
            family_logger.addHandler(ch)
            
            return family_logger
        
        for fam in families:
            family_loggers[fam] = setup_family_logger(fam)
        
        def process_family_with_logging(family_id):
            """带独立日志的家庭处理函数"""
            family_logger = family_loggers[family_id]
            try:
                family_logger.info(f"▶ 开始处理家庭 {family_id}")
                
                # 直接传入family_logger，避免内部再创建
                process_family(
                    family_id,
                    output_dir,
                    split_ratio=args.split_ratio,
                    max_train_events=args.max_train_events,
                    max_test_samples=args.max_test_samples,
                    preflight=False,
                    family_logger=family_logger,
                )
                
                family_logger.info(f"✅ 完成家庭 {family_id}")
                return family_id, "Success", None
            except Exception as e:
                family_logger.error(f"❌ 家庭 {family_id} 处理失败: {e}")
                import traceback
                family_logger.error(traceback.format_exc())
                return family_id, "Failed", str(e)
        
        # 并行处理所有家庭
        logger.info(f"🚀 开始并行处理 {total} 个家庭...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(total, 3)) as executor:
            futures = {executor.submit(process_family_with_logging, fam): fam for fam in families}
            completed = 0
            
            for future in as_completed(futures):
                family_id, status, error = future.result()
                completed += 1
                summary[family_id] = status if status == "Success" else f"Failed: {error}"
                
                elapsed = time.time() - start_time
                logger.info(
                    f"📊 进度: {completed}/{total} ({completed/total*100:.1f}%) | "
                    f"已完成: {family_id} ({status}) | 总耗时: {elapsed:.1f}s"
                )
        
        total_elapsed = time.time() - start_time
        logger.info(f"\n🎉 所有家庭处理完成！总耗时: {total_elapsed:.1f}s")
    
    logger.info(f"\n📊 任务总结: {summary}")

if __name__ == "__main__":
    main()
    
    logger.info("⏳ 等待系统后台任务清理 (约10秒)...")
    time.sleep(10)
