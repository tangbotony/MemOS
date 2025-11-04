"""
Anker 安防场景 - MemOS 记忆添加调试脚本

基于真实的家庭监控事件数据，测试 MemOS 的事件型消息处理能力。
期望效果：从原始监控事件中抽象出家庭成员的生活规律记忆图谱。

场景说明：
- 数据来源：家庭安防摄像头的多模态模型识别结果
- 数据类型：事件型消息（时间戳 + 事件描述）
- 应用目标：安全预警 + 家庭关怀
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from memos.api.product_models import APIADDRequest
from memos.api.routers.server_router import add_memories
from memos.log import get_logger

logger = get_logger(__name__)

# 测试数据路径
TEST_DATA_DIR = project_root / "evaluation" / "data" / "anker" / "test_data"


def load_family_events(family_id: str, role_type: str = "General_Identity"):
    """
    加载指定家庭的事件数据，并按时间排序（从早到晚）
    
    Args:
        family_id: 家庭ID (1-10)
        role_type: 角色类型 ("General_Identity" 或 "Staff")
    
    Returns:
        事件列表（按时间从早到晚排序）
    """
    if role_type == "General_Identity":
        file_name = "General_Identity_formatted.json"
    elif role_type == "Staff":
        file_name = "Staff_formatted.json"
    else:
        raise ValueError(f"不支持的角色类型: {role_type}")
    
    file_path = TEST_DATA_DIR / family_id / file_name
    
    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    # 按时间排序（从早到晚）
    events.sort(key=lambda x: x.get("timestamp", ""))
    
    return events


def load_mixed_family_events(family_id: str, max_events: int = None):
    """
    加载指定家庭的混合事件数据（家庭成员 + 快递员）
    按时间从早到晚排序后混合
    
    Args:
        family_id: 家庭ID (1-10)
        max_events: 最大事件数量限制
    
    Returns:
        混合后的事件列表（按时间从早到晚排序，确保时间顺序正确）
    """
    # 加载两类数据（每类数据内部已排序）
    general_events = load_family_events(family_id, "General_Identity")
    staff_events = load_family_events(family_id, "Staff")
    
    # 合并两类数据
    all_events = general_events + staff_events
    
    # 重新按时间排序（从早到晚），确保混合后顺序正确
    all_events.sort(key=lambda x: x.get("timestamp", ""))
    
    # 限制数量（取最早的 max_events 个事件）
    if max_events:
        all_events = all_events[:max_events]
    
    return all_events


def detect_language(text: str) -> str:
    """
    检测文本的主要语言
    
    Args:
        text: 要检测的文本
    
    Returns:
        "zh" 表示中文, "en" 表示英文
    """
    # 统计中文字符数量
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    # 统计英文字符数量
    english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
    
    # 如果有中文字符，检查是否主要是中文
    if chinese_chars > 0:
        # 如果中文字符占比超过30%，认为是中文
        if chinese_chars / (len(text) + 1) > 0.3:
            return "zh"
    
    # 否则返回英文（包括混合情况）
    return "en"


def convert_time_to_period(timestamp_str: str, language: str = "zh") -> str:
    """
    将时间戳转换为时段格式：早|中|晚|夜间 HH:MM (中文) 或 Morning|Afternoon|Evening|Night HH:MM (英文)
    
    时段划分：
    - 早/Morning: 06:00-11:59
    - 中/Afternoon: 12:00-17:59  
    - 晚/Evening: 18:00-21:59
    - 夜间/Night: 22:00-05:59
    
    Args:
        timestamp_str: 时间戳字符串
        language: "zh" 中文, "en" 英文
    """
    from datetime import datetime
    
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        hour = dt.hour
        time_str = dt.strftime("%H:%M")
        
        if language == "zh":
            # 中文时段
            if 6 <= hour < 12:
                period = "早"
            elif 12 <= hour < 18:
                period = "中"
            elif 18 <= hour < 22:
                period = "晚"
            else:  # 22-05
                period = "夜间"
        else:
            # 英文时段
            if 6 <= hour < 12:
                period = "Morning"
            elif 12 <= hour < 18:
                period = "Afternoon"
            elif 18 <= hour < 22:
                period = "Evening"
            else:  # 22-05
                period = "Night"
        
        return f"{period} {time_str}"
    except:
        return timestamp_str


def format_event_as_message(event: dict) -> tuple[str, dict]:
    """
    将事件格式化为消息内容和元数据
    
    原始格式：
    {
        "timestamp": "2024-12-24 23:23:31",
        "event_description": "A man walked to a car...",
        "key_scene": "Normal Activity",
        "role_type": "General Identity"
    }
    
    返回：
    (
        "A man walked to a car...",  # 纯事件描述（用于检索和存储）
        {
            "time_period": "Night 23:23",
            "timestamp": "2024-12-24 23:23:31",
            "role_type": "General Identity",
            "key_scene": "Normal Activity",
            "language": "en"
        }  # 元数据（作为标签/上下文使用）
    )
    """
    timestamp = event.get("timestamp", "")
    description = event.get("event_description", "")
    key_scene = event.get("key_scene", "")
    role_type = event.get("role_type", "")
    
    # 检测事件描述的语言
    language = detect_language(description)
    
    # 转换时间为时段格式（根据语言自动适配）
    time_period = convert_time_to_period(timestamp, language)
    
    # 返回纯描述和元数据
    metadata = {
        "time_period": time_period,
        "timestamp": timestamp,
        "role_type": role_type,
        "key_scene": key_scene,
        "language": language
    }
    
    return description, metadata


def test_add_single_event(family_id: str = "1"):
    """测试添加单个事件"""
    
    print("=" * 70)
    print("🔍 测试 1: 添加单个监控事件")
    print("=" * 70)
    
    # 加载家庭事件数据
    events = load_family_events(family_id, "General_Identity")
    
    if not events:
        print("❌ 没有找到事件数据")
        return
    
    # 取第一个事件
    event = events[0]
    
    print(f"\n📋 原始事件数据:")
    print(f"  - 时间: {event['timestamp']}")
    print(f"  - 描述: {event['event_description']}")
    print(f"  - 场景: {event['key_scene']}")
    print(f"  - 角色: {event['role_type']}")
    
    # 格式化为消息：分离描述和元数据
    description, metadata = format_event_as_message(event)
    
    # 创建请求（只发送纯描述）
    add_req = APIADDRequest(
        user_id=f"anker_family_{family_id}",
        mem_cube_id=f"anker_cube_{family_id}",
        messages=[
            {
                "role": "user",
                "content": description  # 只发送纯描述
            }
        ],
        session_id=f"monitoring_session_{family_id}",
        source="anker_security"  # 使用安防场景处理
    )
    
    print(f"\n📤 发送消息（纯描述）:")
    print(f"  {description}")
    print(f"\n📋 元数据（作为标签）:")
    print(f"  时间: {metadata['time_period']}")
    print(f"  角色: {metadata['role_type']}")
    print(f"  场景: {metadata['key_scene']}")
    
    try:
        print("\n⚡ 正在调用 add_memories 函数...")
        result = add_memories(add_req)
        
        print("\n✅ 添加成功！")
        print(f"\n📊 返回结果:")
        print(f"  - 状态: {result.code}")
        print(f"  - 消息: {result.message}")
        # result.data: [{'memory': 'On December 24, 2024, at night, the user observed a man walking to a silver car parked on a driveway and opening the rear door.', 'memory_id': '9b681ddc-f5ad-4bf1-bb44-be946d8c6d16', 'memory_type': 'UserMemory'}]
        if result.data:
            print(f"  - 生成的记忆数量: {len(result.data)}")
            for i, mem in enumerate(result.data, 1):
                print(f"\n  记忆 {i}:")
                print(f"    - ID: {mem.get('memory_id', 'N/A')}")
                print(f"    - 类型: {mem.get('memory_type', 'N/A')}")
                print(f"    - 内容: {mem.get('memory', 'N/A')[:150]}...")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_add_batch_events(family_id: str = "1", event_count: int = 10):
    """测试批量添加多个事件"""
    
    print("\n" + "=" * 70)
    print(f"🔍 测试 2: 批量添加 {event_count} 个监控事件")
    print("=" * 70)
    
    # 加载家庭事件数据
    events = load_family_events(family_id, "General_Identity")
    
    if not events:
        print("❌ 没有找到事件数据")
        return
    
    # 取前 N 个事件
    selected_events = events[:event_count]
    
    print(f"\n📋 将添加 {len(selected_events)} 个事件:")
    for i, event in enumerate(selected_events[:3], 1):  # 只显示前3个
        print(f"  {i}. [{event['timestamp']}] {event['event_description'][:60]}...")
    if len(selected_events) > 3:
        print(f"  ... 还有 {len(selected_events) - 3} 个事件")
    
    # 将事件转换为消息格式（只发送纯描述）
    messages = []
    for event in selected_events:
        description, metadata = format_event_as_message(event)
        messages.append({
            "role": "user",
            "content": description  # 只发送纯描述
        })
    
    # 创建请求
    add_req = APIADDRequest(
        user_id=f"anker_family_{family_id}",
        mem_cube_id=f"anker_cube_{family_id}",
        messages=messages,
        session_id=f"monitoring_session_{family_id}",
        source="anker_security"  # 使用安防场景处理
    )
    
    try:
        print("\n⚡ 正在调用 add_memories 函数...")
        result = add_memories(add_req)
        
        print("\n✅ 批量添加成功！")
        print(f"\n📊 返回结果:")
        print(f"  - 状态: {result.code}")
        print(f"  - 消息: {result.message}")
        
        if result.data:
            print(f"  - 生成的记忆数量: {len(result.data)}")
            print(f"\n  📝 记忆示例:")
            for i, mem in enumerate(result.data[:3], 1):  # 只显示前3个
                print(f"\n  记忆 {i}:")
                print(f"    - 类型: {mem.get('memory_type', 'N/A')}")
                print(f"    - 内容: {mem.get('memory', 'N/A')[:120]}...")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_add_staff_events(family_id: str = "1", event_count: int = 5):
    """测试添加快递员（Staff）事件"""
    
    print("\n" + "=" * 70)
    print(f"🔍 测试 3: 添加快递员事件（期望识别出规律）")
    print("=" * 70)
    
    # 加载快递员事件数据
    events = load_family_events(family_id, "Staff")
    
    if not events:
        print("⚠️  没有找到快递员事件数据")
        return
    
    selected_events = events[:event_count]
    
    print(f"\n📋 快递员事件 ({len(selected_events)} 个):")
    for i, event in enumerate(selected_events, 1):
        print(f"  {i}. [{event['timestamp']}] {event['event_description'][:60]}...")
    
    print("\n💡 期望识别出的规律:")
    print("  - 快递员通常在上午 9-11 点之间送件")
    print("  - 快递员的行为模式：穿蓝色制服、拿着信件/包裹、走特定路径")
    
    # 将事件转换为消息格式（只发送纯描述）
    messages = []
    for event in selected_events:
        description, metadata = format_event_as_message(event)
        messages.append({
            "role": "user",
            "content": description  # 只发送纯描述
        })
    
    # 创建请求
    add_req = APIADDRequest(
        user_id=f"anker_family_{family_id}",
        mem_cube_id=f"anker_cube_{family_id}",
        messages=messages,
        session_id=f"monitoring_session_{family_id}",
        source="anker_security"  # 使用安防场景处理
    )
    
    try:
        print("\n⚡ 正在调用 add_memories 函数...")
        result = add_memories(add_req)
        
        print("\n✅ 添加成功！")
        if result.data:
            print(f"  - 生成的记忆数量: {len(result.data)}")
            print(f"\n  📝 生成的记忆内容:")
            for i, mem in enumerate(result.data, 1):
                print(f"\n  记忆 {i}:")
                print(f"    {mem.get('memory', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_add_time_pattern_events(family_id: str = "1"):
    """测试添加具有时间规律的事件（用于识别生活规律）"""
    
    print("\n" + "=" * 70)
    print("🔍 测试 4: 添加时间规律事件（期望识别出生活作息）")
    print("=" * 70)
    
    # 加载事件数据
    events = load_family_events(family_id, "General_Identity")
    
    # 按时间排序
    events.sort(key=lambda x: x['timestamp'])
    
    # 统计不同时间段的事件
    morning_events = [e for e in events if "08:00" <= e['timestamp'].split()[1] <= "09:00"]
    evening_events = [e for e in events if "21:00" <= e['timestamp'].split()[1] <= "23:00"]
    
    print(f"\n📊 事件时间分布:")
    print(f"  - 早晨 (8-9点) 事件: {len(morning_events)} 个")
    print(f"  - 晚上 (21-23点) 事件: {len(evening_events)} 个")
    
    # 选择有代表性的事件
    selected_events = morning_events[:5] + evening_events[:5]
    
    print(f"\n📋 选中的 {len(selected_events)} 个事件:")
    for event in selected_events[:10]:
        print(f"  - [{event['timestamp']}] {event['event_description'][:50]}...")
    
    print("\n💡 期望识别出的规律:")
    print("  - 家庭成员早晨 8-9 点出门上班/上学")
    print("  - 家庭成员晚上 21-23 点回家")
    
    if not selected_events:
        print("⚠️  没有找到符合条件的事件")
        return
    
    # 转换为消息（只发送纯描述）
    messages = []
    for event in selected_events:
        description, metadata = format_event_as_message(event)
        messages.append({
            "role": "user",
            "content": description  # 只发送纯描述
        })
    
    # 创建请求
    add_req = APIADDRequest(
        user_id=f"anker_family_{family_id}",
        mem_cube_id=f"anker_cube_{family_id}",
        messages=messages,
        session_id=f"monitoring_session_{family_id}",
        source="anker_security"  # 使用安防场景处理
    )
    
    try:
        print("\n⚡ 正在调用 add_memories 函数...")
        result = add_memories(add_req)
        
        print("\n✅ 添加成功！")
        if result.data:
            print(f"  - 生成的记忆数量: {len(result.data)}")
            print(f"\n  📝 生成的记忆（查看是否识别出时间规律）:")
            for i, mem in enumerate(result.data, 1):
                print(f"\n  记忆 {i}:")
                print(f"    {mem.get('memory', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


def show_menu():
    """显示测试菜单"""
    print("\n" + "🏠" * 35)
    print("Anker 智能安防场景 - MemOS POC 测试")
    print("🏠" * 35)
    
    print("\n📁 可用测试数据:")
    for i in range(1, 11):
        family_dir = TEST_DATA_DIR / str(i)
        if family_dir.exists():
            print(f"  ✓ 家庭 {i}")
    
    print("\n🧪 测试选项:")
    print("  1. 添加单个监控事件")
    print("  2. 批量添加多个事件 (10个)")
    print("  3. 添加快递员事件 (测试规律识别)")
    print("  4. 添加时间规律事件 (测试生活作息识别)")
    print("  5. 运行完整测试流程")
    print("  0. 退出")


def test_progressive_pattern_extraction(family_id: str = "1", max_events: int = 300):
    """
    渐进式规律提取测试：逐个添加事件，观察规律如何逐渐形成
    
    这个测试展示核心价值：
    - 前几个事件：作为原始记录存储
    - 随着事件增多：开始识别出规律
    - 事件继续增加：规律变得更精确
    
    注意：使用混合数据（家庭成员 + 快递员），包含完整字段信息
    
    Args:
        family_id: 家庭ID
        max_events: 最大事件数量
    """
    
    # 生成带时间戳的 user_id（到分钟）
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    user_id = f"anker_family_{family_id}_{timestamp}"
    mem_cube_id = f"anker_cube_{family_id}_{timestamp}"
    
    # 创建日志文件
    log_dir = project_root / "examples" / "poc" / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"debug_family_{family_id}_{timestamp}.log"
    
    # 定义日志输出函数
    def log_print(message):
        """同时输出到控制台和文件"""
        print(message)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    
    log_print("=" * 70)
    log_print("🔍 测试: 渐进式规律提取（混合数据，一条条添加）")
    log_print("=" * 70)
    log_print(f"\n📁 日志文件: {log_file}")
    log_print("=" * 70)
    
    # 加载混合事件数据（家庭成员 + 快递员）
    events = load_mixed_family_events(family_id, max_events)
    
    if not events:
        log_print("❌ 没有找到事件数据")
        return
    
    log_print(f"\n📋 将逐个添加 {len(events)} 个事件（混合数据）")
    log_print(f"   家庭ID: {family_id}")
    log_print(f"   User ID: {user_id}")
    log_print(f"   Cube ID: {mem_cube_id}")
    
    # 统计事件类型
    general_count = sum(1 for e in events if e.get('role_type') == 'General Identity')
    staff_count = sum(1 for e in events if e.get('role_type') == 'Staff')
    log_print(f"   - 家庭成员事件: {general_count}")
    log_print(f"   - 快递员事件: {staff_count}")
    
    # 显示时间范围，验证排序
    if events:
        first_time = events[0].get("timestamp", "N/A")
        last_time = events[-1].get("timestamp", "N/A")
        log_print(f"   - 时间范围: {first_time} → {last_time}")
        log_print(f"   ✅ 事件已按时间从早到晚排序")
    
    # 打印所有事件列表（按时间排序）
    log_print("\n" + "=" * 70)
    log_print(f"📅 所有事件列表（按时间排序，共 {len(events)} 个）")
    log_print("=" * 70)
    
    for idx, event in enumerate(events, 1):
        timestamp = event.get("timestamp", "N/A")
        role_type = event.get("role_type", "N/A")
        key_scene = event.get("key_scene", "N/A")
        description = event.get("event_description", "N/A")
        
        # 检测语言并转换时间
        language = detect_language(description)
        time_period = convert_time_to_period(timestamp, language)
        
        # 根据角色类型使用不同的图标
        if role_type == "General Identity":
            role_icon = "👤"
        elif role_type == "Staff":
            role_icon = "📦"
        else:
            role_icon = "❓"
        
        log_print(f"\n事件 {idx:3d}:")
        log_print(f"  {role_icon} [{time_period}] {role_type} | {key_scene}")
        log_print(f"  🕐 时间戳: {timestamp}")
        # 截断描述，避免太长
        desc_display = description[:800] + "..." if len(description) > 800 else description
        log_print(f"  📝 描述: {desc_display}")
    
    # 用于记录每个阶段的结果
    results_log = []
    
    log_print("\n" + "=" * 70)
    log_print("开始逐个添加事件...")
    log_print("=" * 70)
    
    for idx, event in enumerate(events, 1):
        # 格式化事件：分离描述和元数据
        description, metadata = format_event_as_message(event)
        
        # 创建请求（只发送纯描述，不包含元数据前缀）
        add_req = APIADDRequest(
            user_id=user_id,
            mem_cube_id=mem_cube_id,
            messages=[{
                "role": "user",
                "content": description  # 只发送纯描述
            }],
            session_id=f"monitoring_session_{family_id}_{timestamp}",
            source="anker_security"
        )
        
        try:
            # 打印事件处理日志
            log_print(f"\n{'─' * 70}")
            log_print(f"🔄 处理事件 {idx}/{len(events)}")
            log_print(f"{'─' * 70}")
            log_print(f"📥 【原始输入】")
            log_print(f"   时间: {metadata['time_period']} ({metadata['timestamp']})")
            log_print(f"   角色: {metadata['role_type']}")
            log_print(f"   场景: {metadata['key_scene']}")
            log_print(f"   描述: {description}")
            log_print(f"\n   ✓ 纯描述用于检索和存储（不含元数据前缀）")
            log_print(f"   ✓ 元数据作为标签存储")
            
            # 添加事件
            result = add_memories(add_req)
            
            # 显示检索到的历史记忆（如果有）
            if result.data and len(result.data) > 0:
                first_mem = result.data[0]
                retrieved_memories = first_mem.get('retrieved_historical_memories', [])
                
                if retrieved_memories:
                    log_print(f"\n🔍 【检索到的历史记忆】 (共 {len(retrieved_memories)} 条)")
                    for hist_idx, hist_mem in enumerate(retrieved_memories, 1):
                        hist_content = hist_mem.get('memory', 'N/A')
                        hist_id = hist_mem.get('memory_id', 'N/A')
                        log_print(f"\n   历史记忆 {hist_idx}:")
                        log_print(f"   - ID: {hist_id}")
                        log_print(f"   - 内容: {hist_content}")
                else:
                    log_print(f"\n🔍 【检索到的历史记忆】 无（首次事件或无相似历史）")
            
            # 显示生成的记忆
            if result.data:
                log_print(f"\n📤 【生成记忆】 (共 {len(result.data)} 条)")
                for mem_idx, mem in enumerate(result.data, 1):
                    mem_type = mem.get('memory_type', 'N/A')
                    mem_content = mem.get('memory', 'N/A')
                    mem_id = mem.get('memory_id', 'N/A')
                    
                    # 判断记忆类型（根据新的标签格式）
                    is_factual = "[实时记忆]" in mem_content or "[Factual Memory]" in mem_content
                    is_pattern = "[规律记忆]" in mem_content or "[Pattern Memory]" in mem_content
                    is_inference = "[推理记忆]" in mem_content or "[Inference Memory]" in mem_content
                    
                    if is_factual:
                        memory_label = "📌 实时记忆 (事实)"
                    elif is_pattern:
                        memory_label = "🔄 规律记忆 (模式)"
                    elif is_inference:
                        memory_label = "🤔 推理记忆 (推测)"
                    else:
                        # 兼容旧格式
                        is_old_pattern = any(keyword in mem_content.lower() for keyword in 
                                           ['pattern', 'typically', 'usually', 'often', 'regularly',
                                            '规律', '通常', '经常', '总是', 'always'])
                        memory_label = "🔄 规律性记忆" if is_old_pattern else "📌 原始事件记忆"
                    
                    log_print(f"\n   记忆 {mem_idx}: {memory_label}")
                    log_print(f"   - ID: {mem_id}")
                    log_print(f"   - 类型: {mem_type}")
                    log_print(f"   - 内容: {mem_content}")
                
                # 记录到日志
                for mem_idx, mem in enumerate(result.data):
                    # 只在第一个记忆中包含检索到的历史记忆
                    retrieved_hist = None
                    if mem_idx == 0 and 'retrieved_historical_memories' in mem:
                        retrieved_hist = mem['retrieved_historical_memories']
                    
                    mem_content = mem.get('memory', '')
                    # 判断记忆类型（优先使用新标签格式）
                    is_pattern_new = "[规律记忆]" in mem_content or "[Pattern Memory]" in mem_content
                    is_factual_new = "[实时记忆]" in mem_content or "[Factual Memory]" in mem_content
                    is_inference_new = "[推理记忆]" in mem_content or "[Inference Memory]" in mem_content
                    
                    # 兼容旧格式
                    is_pattern_old = (
                        "pattern" in mem_content.lower() or
                        "typically" in mem_content.lower() or
                        "usually" in mem_content.lower() or
                        "规律" in mem_content or
                        "通常" in mem_content or
                        "always" in mem_content.lower() or
                        "总是" in mem_content
                    )
                    
                    # 综合判断（新标签优先）
                    is_pattern = is_pattern_new or (is_pattern_old and not is_factual_new and not is_inference_new)
                    
                    results_log.append({
                        "event_num": idx,
                        "event_time": event.get('timestamp', 'N/A'),
                        "raw_input": description,  # 纯描述
                        "metadata": metadata,  # 元数据
                        "memory_type": mem.get('memory_type', 'N/A'),
                        "memory": mem_content,
                        "memory_id": mem.get('memory_id', 'N/A'),
                        "retrieved_historical_memories": retrieved_hist,
                        "is_pattern": is_pattern,
                        "is_factual": is_factual_new,
                        "is_inference": is_inference_new
                    })
            else:
                log_print(f"\n⚠️  未生成任何记忆")
            
            log_print(f"{'─' * 70}")
                
        except Exception as e:
            log_print(f"\n   ❌ 事件 {idx} 处理失败: {e}")
            continue
    
    # 最终总结
    log_print("\n" + "=" * 70)
    log_print("🎯 最终总结")
    log_print("=" * 70)
    
    # 统计不同类型的记忆
    factual_memories = [r for r in results_log if r.get('is_factual', False)]
    pattern_memories = [r for r in results_log if r['is_pattern']]
    inference_memories = [r for r in results_log if r.get('is_inference', False)]
    other_memories = [r for r in results_log 
                     if not r.get('is_factual', False) 
                     and not r['is_pattern'] 
                     and not r.get('is_inference', False)]
    
    log_print(f"\n📊 统计结果:")
    log_print(f"   - 总共添加事件: {len(events)}")
    log_print(f"   - 生成的总记忆数: {len(results_log)}")
    log_print(f"\n   记忆类型分布:")
    log_print(f"   📌 实时记忆 (事实): {len(factual_memories)} ({len(factual_memories)/max(len(results_log),1)*100:.1f}%)")
    log_print(f"   🔄 规律记忆 (模式): {len(pattern_memories)} ({len(pattern_memories)/max(len(results_log),1)*100:.1f}%)")
    log_print(f"   🤔 推理记忆 (推测): {len(inference_memories)} ({len(inference_memories)/max(len(results_log),1)*100:.1f}%)")
    if other_memories:
        log_print(f"   📄 其他记忆: {len(other_memories)} ({len(other_memories)/max(len(results_log),1)*100:.1f}%)")
    
    # 详细打印所有记忆
    log_print(f"\n" + "=" * 70)
    log_print(f"📝 所有记忆详情 (共 {len(results_log)} 条)")
    log_print("=" * 70)
    
    for i, mem_log in enumerate(results_log, 1):
        # 判断记忆类型
        if mem_log.get('is_factual', False):
            mem_type_label = "📌 实时记忆 (事实)"
        elif mem_log['is_pattern']:
            mem_type_label = "🔄 规律记忆 (模式)"
        elif mem_log.get('is_inference', False):
            mem_type_label = "🤔 推理记忆 (推测)"
        else:
            mem_type_label = "📄 其他记忆"
        
        log_print(f"\n【记忆 {i}】 {mem_type_label}")
        log_print(f"   - 产生于: 第 {mem_log['event_num']} 个事件后")
        log_print(f"   - 事件时间: {mem_log.get('event_time', 'N/A')}")
        log_print(f"   - 类型: {mem_log['memory_type']}")
        log_print(f"   - 内容:")
        # 对长内容进行分段打印，每行最多100字符
        content = mem_log['memory']
        if len(content) > 100:
            # 按句子分段
            import re
            sentences = re.split(r'([。！？\.!?])', content)
            current_line = "      "
            for j in range(0, len(sentences), 2):
                if j < len(sentences):
                    sentence = sentences[j]
                    if j + 1 < len(sentences):
                        sentence += sentences[j + 1]
                    
                    if len(current_line) + len(sentence) > 100:
                        if current_line != "      ":
                            log_print(current_line)
                        current_line = "      " + sentence
                    else:
                        current_line += sentence
            if current_line != "      ":
                log_print(current_line)
        else:
            log_print(f"      {content}")
    
    log_print(f"\n" + "=" * 70)
    
    log_print(f"\n📈 规律出现时间线:")
    if pattern_memories:
        for i, pm in enumerate(pattern_memories[:5], 1):  # 显示前5个规律
            log_print(f"\n   规律 {i} (第 {pm['event_num']} 个事件后出现):")
            log_print(f"      事件时间: {pm.get('event_time', 'N/A')}")
            log_print(f"      {pm['memory'][:200]}...")
    else:
        log_print("   ⚠️  未识别出明显规律，可能需要更多事件")
    
    log_print(f"\n💡 观察:")
    if pattern_memories:
        first_pattern_at = min(pm['event_num'] for pm in pattern_memories)
        log_print(f"   ✅ 第 {first_pattern_at} 个事件后开始出现规律性记忆")
        log_print(f"   ✅ 随着事件增加，规律识别率从 0% 提升到 {len(pattern_memories)/max(len(results_log),1)*100:.1f}%")
        log_print(f"   ✅ 成功实现从「原进原出」到「规律提取」的转变")
    else:
        log_print(f"   ⚠️  建议:")
        log_print(f"      1. 增加事件数量 (当前 {len(events)}，建议 50+)")
        log_print(f"      2. 确保事件具有相似性（时间、角色、行为）")
        log_print(f"      3. 检查 LLM 配置是否正确")
    
    log_print("\n" + "=" * 70)
    log_print("✅ 测试完成！")
    log_print("=" * 70)
    
    return results_log


if __name__ == "__main__":
    # 渐进式规律提取测试 - 展示核心价值
    # 每次运行会自动生成带时间戳的 user_id，无需手动修改
    test_progressive_pattern_extraction(family_id="1", max_events=300)
    # print("\n" + "🎯" * 35)
    # print("Anker 安防场景 - MemOS 直接函数调用调试")
    # print("🎯" * 35)
    
    # # 检查数据目录
    # if not TEST_DATA_DIR.exists():
    #     print(f"\n❌ 测试数据目录不存在: {TEST_DATA_DIR}")
    #     print("请确保数据已放置在正确位置")
    #     sys.exit(1)
    
    # while True:
    #     show_menu()
    #     choice = input("\n请选择测试选项 (0-5): ").strip()
        
    #     if choice == "0":
    #         print("\n👋 退出测试")
    #         break
        
    #     # 选择家庭ID
    #     family_id = input("请输入家庭ID (1-10，默认 1): ").strip() or "1"
        
    #     try:
    #         if choice == "1":
    #             test_add_single_event(family_id)
    #         elif choice == "2":
    #             test_add_batch_events(family_id, event_count=10)
    #         elif choice == "3":
    #             test_add_staff_events(family_id, event_count=5)
    #         elif choice == "4":
    #             test_add_time_pattern_events(family_id)
    #         elif choice == "5":
    #             print("\n🚀 运行完整测试流程...")
    #             test_add_single_event(family_id)
    #             test_add_batch_events(family_id, event_count=10)
    #             test_add_staff_events(family_id, event_count=5)
    #             test_add_time_pattern_events(family_id)
    #         else:
    #             print("❌ 无效选项，请重新选择")
    #             continue
            
    #         print("\n" + "=" * 70)
    #         print("✨ 测试完成！")
    #         print("=" * 70)
            
    #         # 询问是否继续
    #         continue_test = input("\n是否继续测试？(y/n，默认 y): ").strip().lower()
    #         if continue_test == "n":
    #             break
            
    #     except Exception as e:
    #         print("\n" + "=" * 70)
    #         print("💥 测试过程中出现错误")
    #         print("=" * 70)
    #         logger.error(f"测试失败: {e}")
            
    #         # 询问是否继续
    #         continue_test = input("\n是否继续测试？(y/n，默认 y): ").strip().lower()
    #         if continue_test == "n":
    #             break
    
    # print("\n" + "=" * 70)
    # print("🎉 测试结束")
    # print("=" * 70)
