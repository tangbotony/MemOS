"""
Demo 数据记忆提取验证脚本（完整流程）

该脚本在一个文件中完成：
1. 加载 General_Identity_samples.json 中的事件
2. 通过 MemOS 系统提取记忆
3. 将提取的非事实记忆与 long-term_memory_samples.json 对比
4. 使用 LLM 判断提取的完整性
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 导入必要的模块
from memos.api.product_models import APIADDRequest

# TeeOutput 类用于同时输出到控制台和文件
class TeeOutput:
    """同时输出到多个流的类"""
    def __init__(self, *files):
        self.files = files
    
    def write(self, text):
        for f in self.files:
            f.write(text)
            f.flush()
    
    def flush(self):
        for f in self.files:
            f.flush()

try:
    # 尝试导入 server_router 中的组件
    from memos.api.routers.server_router import add_memories, llm
    print("✓ 成功导入 add_memories 和 llm")
except Exception as e:
    print(f"⚠️ 无法导入 server_router: {e}")
    print("使用替代方案...")
    from memos.llms.factory import LLMFactory
    from memos.config import Config
    
    # 初始化 LLM
    def _build_llm_config():
        from memos.llms.config import LLMConfigFactory
        config = Config()
        return LLMConfigFactory.model_validate({
            "backend": config.llm_backend,
            "config": config.llm_config,
        })
    
    llm_config = _build_llm_config()
    llm = LLMFactory.from_config(llm_config)
    
    # add_memories 将设为 None，后续会报错提示
    add_memories = None


def load_demo_events():
    """加载 demo 事件数据"""
    demo_dir = Path(__file__).parent / "demo"
    events_file = demo_dir / "General_Identity_samples.json"
    
    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    # 按时间排序
    events.sort(key=lambda x: x.get("environment_memory", {}).get("timestamp", ""))
    
    return events


def load_expected_memories():
    """加载期望的长期记忆"""
    demo_dir = Path(__file__).parent / "demo"
    expected_file = demo_dir / "long-term_memory_samples.json"
    
    with open(expected_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_memories_from_events(events, max_events=None):
    """从事件中提取记忆"""
    if max_events:
        events = events[:max_events]
    
    # 生成唯一的用户ID（基于时间戳），避免历史记忆累积
    timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_user_id = f"demo_validation_user_{timestamp_id}"
    unique_cube_id = f"demo_validation_cube_{timestamp_id}"
    
    print(f"\n{'='*80}")
    print(f"步骤1: 从 {len(events)} 个事件中提取记忆...")
    print(f"本次运行使用的用户ID: {unique_user_id}")
    print(f"{'='*80}\n")
    
    all_memories = []
    
    for idx, event in enumerate(events, 1):
        env_mem = event.get('environment_memory', {})
        event_mem = event.get('event_memory', {})
        
        # 提取事件信息
        timestamp = env_mem.get('timestamp', '')
        location = env_mem.get('location', '')
        video_id = env_mem.get('video_id', '')
        description = event_mem.get('event_description', '')
        key_scene = event_mem.get('key_scene', '')
        role_type = event_mem.get('role_type', '')
        
        print(f"处理事件 {idx}/{len(events)} | {timestamp} | {description[:60]}...")
        
        # 构造元数据
        metadata = {
            "timestamp": timestamp,
            "location": location,
            "video_id": video_id,
            "key_scene": key_scene,
            "role_type": role_type
        }
        
        # 构造请求（关键：指定 source="anker_security" 使用安防场景的 prompt）
        request = APIADDRequest(
            user_id=unique_user_id,
            mem_cube_id=unique_cube_id,
            messages=[
                {
                    "role": "user",
                    "content": description
                }
            ],
            session_id=f"demo_session_{idx}",
            source="anker_security",  # 使用安防场景处理，避免 [user viewpoint] 标签
            metadata=json.dumps(metadata, ensure_ascii=False)
        )
        
        # 提取记忆（add_memories 是同步函数，不需要 await）
        try:
            result = add_memories(request)
            
            if result.data:
                for mem in result.data:
                    mem_content = mem.get('memory', '')
                    mem_id = mem.get('memory_id', '')
                    mem_type = mem.get('memory_type', '')
                    
                    # 判断记忆类型
                    is_factual = "[实时记忆]" in mem_content or "[Factual Memory]" in mem_content
                    is_pattern = "[规律记忆]" in mem_content or "[Pattern Memory]" in mem_content
                    is_inference = "[推理记忆]" in mem_content or "[Inference Memory]" in mem_content
                    
                    all_memories.append({
                        "event_idx": idx,
                        "event_time": timestamp,
                        "event_description": description,
                        "memory_type": mem_type,
                        "memory_content": mem_content,
                        "memory_id": mem_id,
                        "is_factual": is_factual,
                        "is_pattern": is_pattern,
                        "is_inference": is_inference
                    })
                    
                    if not is_factual:
                        label = "🔄 规律" if is_pattern else ("🤔 推理" if is_inference else "📝")
                        print(f"  ✓ {label}: {mem_content[:60]}...")
        
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            continue
    
    # 统计
    non_factual = [m for m in all_memories if not m['is_factual']]
    pattern = [m for m in all_memories if m['is_pattern']]
    inference = [m for m in all_memories if m['is_inference']]
    
    print(f"\n{'='*80}")
    print(f"提取完成！")
    print(f"- 总记忆数: {len(all_memories)}")
    print(f"- 非事实记忆数: {len(non_factual)}")
    print(f"  - 规律记忆: {len(pattern)}")
    print(f"  - 推理记忆: {len(inference)}")
    print(f"{'='*80}\n")
    
    return all_memories


def validate_with_llm(non_factual_memories, expected_memories):
    """使用 LLM 验证提取的记忆是否完整包含期望的内容"""
    
    print(f"\n{'='*80}")
    print(f"步骤2: 使用 LLM 验证记忆提取的完整性...")
    print(f"{'='*80}\n")
    
    # 准备提取的非事实记忆文本
    extracted_text = "\n".join([
        f"{i+1}. [{mem['memory_type']}] {mem['memory_content']}"
        for i, mem in enumerate(non_factual_memories)
    ])
    
    # 准备期望的记忆文本
    expected_text = json.dumps(expected_memories, indent=2, ensure_ascii=False)
    
    # 构造验证 prompt
    validation_prompt = f"""你是一个记忆系统验证专家。我需要你判断从事件中提取的非事实记忆（Pattern Memory 和 Inference Memory）是否完整涵盖了期望的长期记忆内容。

【期望的长期记忆内容】（这是标准答案，结构化的JSON格式）：
{expected_text}

【实际提取出的非事实记忆】（这是从事件流中自动提取的文本记忆）：
{extracted_text}

请仔细对比以上两部分内容，判断实际提取的记忆是否涵盖了期望的所有关键信息。注意：
1. 实际提取的记忆是文本形式，可能用不同的表述方式，但应该在语义上包含期望的信息
2. 重点关注以下几个方面是否都被涵盖：
   - family_commute（家庭成员出入时间规律）
   - pet（宠物信息）
   - vehicle（车辆信息）
   - family_composition（家庭成员组成）
   - recurring_activities（重复性活动）
   - interaction_patterns（互动模式）
3. 不需要一字一句完全匹配，但核心信息点应该都有体现

请以JSON格式返回你的判断结果：
{{
  "is_complete": true/false,
  "coverage_analysis": {{
    "family_commute": {{"covered": true/false, "details": "具体说明"}},
    "pet": {{"covered": true/false, "details": "具体说明"}},
    "vehicle": {{"covered": true/false, "details": "具体说明"}},
    "family_composition": {{"covered": true/false, "details": "具体说明"}},
    "recurring_activities": {{"covered": true/false, "details": "具体说明"}},
    "interaction_patterns": {{"covered": true/false, "details": "具体说明"}}
  }},
  "missing_aspects": ["列出缺失的关键信息"],
  "suggestions": "如果有缺失，建议如何改进提取prompt"
}}
"""
    
    print(f"正在调用 LLM 进行验证...\n")
    
    # 调用内置的 LLM（与 server_router 中的去重功能相同的方式）
    try:
        messages = [{"role": "user", "content": validation_prompt}]
        response = llm.generate(messages)
        
        # 清理响应中的markdown代码块标记（与 _check_memory_duplication 相同的处理方式）
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        # 解析 JSON
        result = json.loads(response_clean)
        return result, response
        
    except json.JSONDecodeError as e:
        print(f"⚠️ 无法解析 LLM 返回的 JSON: {e}")
        print(f"原始响应: {response}")
        return {
            "is_complete": False,
            "raw_response": response,
            "error": str(e)
        }, response
    except Exception as e:
        print(f"✗ LLM 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "is_complete": False,
            "error": str(e)
        }, None


def main():
    """主函数"""
    
    # 创建输出目录
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"demo_validation_{timestamp}.log"
    result_file = logs_dir / f"demo_validation_{timestamp}.json"
    
    # 打开日志文件，使用 TeeOutput 同时输出到控制台和文件
    with open(log_file, 'w', encoding='utf-8') as log_f:
        # 重定向 stdout
        original_stdout = sys.stdout
        sys.stdout = TeeOutput(original_stdout, log_f)
        
        try:
            print(f"\n{'='*80}")
            print(f"Demo 数据记忆提取验证（完整流程）")
            print(f"{'='*80}")
            print(f"日志文件: {log_file}")
            print(f"结果文件: {result_file}")
            print(f"{'='*80}\n")
            
            # 步骤1: 加载数据
            print(f"加载 demo 数据...")
            events = load_demo_events()
            expected_memories = load_expected_memories()
            print(f"✓ 加载了 {len(events)} 个事件")
            print(f"✓ 加载了期望的长期记忆\n")
            
            # 步骤2: 提取记忆（先处理所有事件进行完整验证）
            # 如果需要快速测试，可以设置 max_events 参数，例如: max_events=10
            all_memories = extract_memories_from_events(events, max_events=None)
            non_factual_memories = [m for m in all_memories if not m['is_factual']]
            
            # 步骤3: LLM 验证
            validation_result, llm_response = validate_with_llm(non_factual_memories, expected_memories)
            
            # 保存完整结果
            full_result = {
                "timestamp": timestamp,
                "events_count": len(events),
                "total_memories": len(all_memories),
                "non_factual_memories": len(non_factual_memories),
                "extracted_memories": all_memories,
                "expected_memories": expected_memories,
                "validation_result": validation_result,
                "llm_raw_response": llm_response
            }
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(full_result, f, indent=2, ensure_ascii=False)
            
            # 打印结果
            print(f"\n{'='*80}")
            print(f"验证结果")
            print(f"{'='*80}\n")
            
            if validation_result.get('is_complete'):
                print("✅ 记忆提取完整，包含了所有期望的长期记忆内容！\n")
            else:
                print("⚠️ 记忆提取分析：\n")
            
            if 'coverage_analysis' in validation_result:
                for aspect, info in validation_result['coverage_analysis'].items():
                    covered = info.get('covered', False)
                    status = "✅" if covered else "❌"
                    details = info.get('details', 'N/A')
                    print(f"{status} {aspect}")
                    print(f"   {details}\n")
            
            if 'missing_aspects' in validation_result and validation_result['missing_aspects']:
                print(f"\n❌ 缺失的关键信息：")
                for aspect in validation_result['missing_aspects']:
                    print(f"  - {aspect}")
                print()
            
            if 'suggestions' in validation_result and validation_result['suggestions']:
                print(f"\n💡 改进建议：")
                print(f"  {validation_result['suggestions']}\n")
            
            print(f"{'='*80}")
            print(f"完整结果已保存到:")
            print(f"  日志: {log_file}")
            print(f"  JSON: {result_file}")
            print(f"{'='*80}\n")
            
            # 返回验证状态
            return validation_result.get('is_complete', False)
        
        except Exception as e:
            print(f"\n❌ 验证过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # 恢复 stdout
            sys.stdout = original_stdout


if __name__ == "__main__":
    success = main()
    
    if success:
        print("✅ 验证通过！可以继续处理 test_data 下的所有数据。")
        sys.exit(0)
    else:
        print("⚠️ 验证未完全通过，请根据建议调整 prompt。")
        sys.exit(1)

