"""
快速测试脚本 - 验证推理系统基本功能 (适配新版渐进式推理)

测试流程:
1. 加载少量9月数据构建记忆
2. 在2-3个10月样本上测试推理
3. 输出详细的推理过程
"""

import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入新版函数
from anker_identity_inference import (
    load_data,
    add_events_to_memory,
    infer_event,
    format_timestamp,
    parse_result,
    MetricsCalculator,
    get_time_period,
)
from memos.log import get_logger

logger = get_logger(__name__)

def quick_test(
    family_id: str = "T8030P1322100087",
    train_samples: int = 5,
    val_samples: int = 5,
    test_samples: int = 3,
):
    """
    快速测试推理功能
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 快速测试 - 家庭 {family_id}")
    logger.info(f"{'='*70}\n")
    
    # 1. 准备环境
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = f"test_{family_id}_{timestamp}"
    mem_cube_id = f"cube_test_{family_id}_{timestamp}"
    session_id = f"sess_test_{family_id}_{timestamp}"
    
    # 2. 加载数据
    logger.info(f"📥 步骤1: 加载数据...")
    train_all, test_all = load_data(family_id)
    
    # 准备训练/验证/测试划分
    if len(train_all) <= train_samples:
        train_events = train_all
        validation_events = []
    else:
        train_events = train_all[:train_samples]
        validation_events = train_all[train_samples:train_samples + val_samples]
    
    test_events = test_all[:test_samples] if len(test_all) > test_samples else test_all
    
    logger.info(f"✓ 选取训练样本: {len(train_events)} 条")
    logger.info(f"✓ 选取验证样本: {len(validation_events)} 条")
    logger.info(f"✓ 选取10月测试样本: {len(test_events)} 条\n")
    
    # 3. 构建记忆
    logger.info(f"🔨 步骤2: 构建记忆 (共 {len(train_events)} 条)...")
    
    # 这里不使用add_events_to_memory的内部进度条，而是自己控制，因为样本少，不需要太复杂
    total_add_time = 0
    from memos.api.product_models import APIADDRequest
    from memos.api.routers.server_router import add_memories
    
    for i, event in enumerate(train_events, 1):
        start_t = time.time()
        
        # 内容增强
        ts = event.get('timestamp', '')
        enhanced_content = f"""[Security Log]
Time: {format_timestamp(ts)} ({get_time_period(ts)})
Observation: {event['original_description']}

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
            elapsed = time.time() - start_t
            total_add_time += elapsed
            
            # 显示进度
            avg_time = total_add_time / i
            remaining = (len(train_events) - i) * avg_time
            # 简单的进度条 [====>....]
            bar_len = 20
            filled = int(i / len(train_events) * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            sys.stdout.write(f"\r    [{bar}] {i}/{len(train_events)} | 本次:{elapsed:.2f}s | 平均:{avg_time:.2f}s | 剩:{remaining:.0f}s")
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"\n❌ Error adding event {i}: {e}")
            
    sys.stdout.write(f"\n    ✅ 记忆构建完成! 总耗时: {total_add_time:.1f}s\n\n")
    
    # 4. 验证集准确率 (基于9月有标注数据)
    if validation_events:
        logger.info(f"📊 步骤3: 在验证集上评估准确率 ({len(validation_events)} 条)...")
        predictions = []
        ground_truth = {}
        
        for idx, event in enumerate(validation_events, 1):
            role, sub, conf, raw = infer_event(event, user_id, mem_cube_id)
            predictions.append({
                "video_path": event["video_path"],
                "predicted_role_type": role,
                "predicted_sub_role_type": sub,
                "confidence": conf,
            })
            ground_truth[event["video_path"]] = {
                "role_type": event["role_type"],
                "sub_role_type": event["sub_role_type"],
            }
        
        metrics = MetricsCalculator.calculate(predictions, ground_truth)
        logger.info("   ✅ 验证结果:")
        logger.info(f"     - 身份大类准确率: {metrics['role_acc']*100:.1f}%")
        logger.info(f"     - 身份子类准确率: {metrics['sub_role_acc']*100:.1f}%")
        logger.info(f"     - 家人识别准确率: {metrics['family_acc']*100:.1f}%")
        logger.info(f"     - 异常检测准确率: {metrics['anomaly_acc']*100:.1f}%\n")
    else:
        logger.info("⚠️ 验证集为空，跳过准确率评估\n")
    
    # 5. 10月推理示例
    logger.info(f"🔍 步骤4: 开始10月推理示例 ({len(test_events)} 条)...\n")
    
    results = []
    total_inference_time = 0
    
    for idx, event in enumerate(test_events, 1):
        logger.info(f"{'─'*70}")
        logger.info(f"🔄 测试样本 {idx}/{len(test_events)}")
        logger.info(f"{'─'*70}")
        logger.info(f"📅 时间: {format_timestamp(event['timestamp'])}")
        logger.info(f"📝 描述: {event['original_description'][:100]}...")
        logger.info(f"\n⚡ 正在推理...")
        
        start_t = time.time()
        # 调用新版推理函数
        role, sub, conf, raw = infer_event(event, user_id, mem_cube_id)
        cost = time.time() - start_t
        total_inference_time += cost
        
        logger.info(f"\n📤 推理结果:")
        logger.info(f"  • 身份大类: {role}")
        logger.info(f"  • 身份子类: {sub}")
        logger.info(f"  • 置信度: {conf}")
        logger.info(f"  • 耗时: {cost:.2f}s")
        
        logger.info(f"\n💬 完整推理响应:")
        preview = raw[:500] + "..." if len(raw) > 500 else raw
        logger.info(f"  {preview}")
        
        results.append({
            "sample_num": idx,
            "role": role,
            "sub": sub,
            "conf": conf
        })
        
        logger.info(f"{'─'*70}\n")
    
    # 总结
    logger.info(f"{'='*70}")
    logger.info(f"✅ 快速测试完成!")
    if results:
        avg_time = total_inference_time / len(results)
        logger.info(f"⏱️  平均推理耗时: {avg_time:.2f}s")
    logger.info(f"{'='*70}\n")
    
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=str, default="T8030P1322100087")
    parser.add_argument("--train-samples", type=int, default=5)
    parser.add_argument("--val-samples", type=int, default=5)
    parser.add_argument("--test-samples", type=int, default=3)
    args = parser.parse_args()
    
    try:
        quick_test(args.family, args.train_samples, args.val_samples, args.test_samples)
        
        # 修复: 给后台线程更多时间完成收尾工作，避免 "interpreter shutdown" 错误
        # MemOS 的后台任务(记忆整理)是异步的，如果脚本退出太快，会导致线程池关闭错误
        logger.info("⏳ 等待系统后台任务清理 (约10秒)...")
        time.sleep(10) 
        logger.info("👋 退出程序")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
