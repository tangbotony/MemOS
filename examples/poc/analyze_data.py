"""
Anker 测试数据统计分析脚本

分析所有家庭的监控事件数据，统计各字段的离散值分布。
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 测试数据路径
TEST_DATA_DIR = project_root / "evaluation" / "data" / "anker" / "test_data"


def load_all_events():
    """加载所有家庭的所有事件数据"""
    all_events = []
    families_stats = {}
    
    for family_id in range(1, 11):
        family_dir = TEST_DATA_DIR / str(family_id)
        if not family_dir.exists():
            continue
        
        family_events = {
            'general': [],
            'staff': []
        }
        
        # 加载 General_Identity 数据
        general_file = family_dir / "General_Identity_formatted.json"
        if general_file.exists():
            with open(general_file, 'r', encoding='utf-8') as f:
                general_data = json.load(f)
                family_events['general'] = general_data
                all_events.extend(general_data)
        
        # 加载 Staff 数据
        staff_file = family_dir / "Staff_formatted.json"
        if staff_file.exists():
            with open(staff_file, 'r', encoding='utf-8') as f:
                staff_data = json.load(f)
                family_events['staff'] = staff_data
                all_events.extend(staff_data)
        
        families_stats[family_id] = family_events
    
    return all_events, families_stats


def analyze_field_distribution(events):
    """分析各个字段的离散值分布"""
    
    if not events:
        print("❌ 没有找到任何事件数据")
        return
    
    # 获取所有字段名
    all_fields = set()
    for event in events:
        all_fields.update(event.keys())
    
    print("\n" + "=" * 80)
    print("📊 JSON 字段离散值统计")
    print("=" * 80)
    
    print(f"\n📋 总事件数: {len(events)}")
    print(f"📋 字段列表: {sorted(all_fields)}")
    
    # 分析每个字段
    for field in sorted(all_fields):
        print("\n" + "-" * 80)
        print(f"🔍 字段: {field}")
        print("-" * 80)
        
        # 收集该字段的所有值
        values = []
        null_count = 0
        
        for event in events:
            if field in event:
                value = event[field]
                if value is None or value == "":
                    null_count += 1
                else:
                    values.append(str(value))
            else:
                null_count += 1
        
        # 统计频次
        value_counter = Counter(values)
        
        print(f"   - 总数: {len(values)}")
        print(f"   - 空值数: {null_count}")
        print(f"   - 唯一值数量: {len(value_counter)}")
        
        # 显示离散值分布
        if len(value_counter) <= 50:  # 如果唯一值不超过50个，全部显示
            print(f"\n   离散值分布（共 {len(value_counter)} 个）:")
            for value, count in value_counter.most_common():
                percentage = (count / len(values)) * 100 if values else 0
                print(f"      • {value[:60]:<60} : {count:>6} 次 ({percentage:>5.1f}%)")
        else:  # 否则只显示前20个最常见的
            print(f"\n   离散值分布（Top 20，共 {len(value_counter)} 个唯一值）:")
            for value, count in value_counter.most_common(20):
                percentage = (count / len(values)) * 100 if values else 0
                print(f"      • {value[:60]:<60} : {count:>6} 次 ({percentage:>5.1f}%)")
            print(f"      ... 还有 {len(value_counter) - 20} 个其他值")


def analyze_time_distribution(events):
    """分析时间分布"""
    print("\n\n" + "=" * 80)
    print("⏰ 时间分布统计")
    print("=" * 80)
    
    # 按小时统计
    hour_counter = Counter()
    # 按时段统计
    period_counter = Counter()
    # 按日期统计
    date_counter = Counter()
    
    for event in events:
        timestamp_str = event.get("timestamp", "")
        if not timestamp_str:
            continue
        
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            # 小时统计
            hour_counter[dt.hour] += 1
            
            # 时段统计
            if 6 <= dt.hour < 12:
                period_counter["早 (06:00-11:59)"] += 1
            elif 12 <= dt.hour < 18:
                period_counter["中 (12:00-17:59)"] += 1
            elif 18 <= dt.hour < 22:
                period_counter["晚 (18:00-21:59)"] += 1
            else:
                period_counter["夜间 (22:00-05:59)"] += 1
            
            # 日期统计
            date_counter[dt.strftime("%Y-%m-%d")] += 1
        except:
            continue
    
    # 显示时段分布
    print("\n📊 时段分布:")
    for period in ["早 (06:00-11:59)", "中 (12:00-17:59)", "晚 (18:00-21:59)", "夜间 (22:00-05:59)"]:
        count = period_counter[period]
        percentage = (count / len(events)) * 100 if events else 0
        bar = "█" * int(percentage / 2)
        print(f"   {period:<25} : {count:>6} 次 ({percentage:>5.1f}%) {bar}")
    
    # 显示小时分布
    print("\n📊 小时分布:")
    for hour in range(24):
        count = hour_counter[hour]
        percentage = (count / len(events)) * 100 if events else 0
        bar = "█" * int(percentage / 2)
        print(f"   {hour:02d}:00 : {count:>6} 次 ({percentage:>5.1f}%) {bar}")
    
    # 显示日期范围
    if date_counter:
        dates = sorted(date_counter.keys())
        print(f"\n📅 日期范围:")
        print(f"   - 最早: {dates[0]}")
        print(f"   - 最晚: {dates[-1]}")
        print(f"   - 总天数: {len(dates)}")


def analyze_family_statistics(families_stats):
    """分析每个家庭的统计信息"""
    print("\n\n" + "=" * 80)
    print("🏠 各家庭数据统计")
    print("=" * 80)
    
    print(f"\n{'家庭ID':<10} {'家庭成员事件':<15} {'快递员事件':<15} {'总计':<10}")
    print("-" * 60)
    
    for family_id in sorted(families_stats.keys()):
        family_data = families_stats[family_id]
        general_count = len(family_data['general'])
        staff_count = len(family_data['staff'])
        total = general_count + staff_count
        
        print(f"{family_id:<10} {general_count:<15} {staff_count:<15} {total:<10}")
    
    # 总计
    total_general = sum(len(f['general']) for f in families_stats.values())
    total_staff = sum(len(f['staff']) for f in families_stats.values())
    total_all = total_general + total_staff
    
    print("-" * 60)
    print(f"{'总计':<10} {total_general:<15} {total_staff:<15} {total_all:<10}")


def analyze_event_description_length(events):
    """分析事件描述的长度分布"""
    print("\n\n" + "=" * 80)
    print("📝 事件描述长度统计")
    print("=" * 80)
    
    lengths = []
    for event in events:
        desc = event.get("event_description", "")
        lengths.append(len(desc))
    
    if lengths:
        print(f"\n   - 平均长度: {sum(lengths)/len(lengths):.1f} 字符")
        print(f"   - 最短: {min(lengths)} 字符")
        print(f"   - 最长: {max(lengths)} 字符")
        
        # 长度区间分布
        length_ranges = {
            "0-50": 0,
            "51-100": 0,
            "101-150": 0,
            "151-200": 0,
            "200+": 0
        }
        
        for length in lengths:
            if length <= 50:
                length_ranges["0-50"] += 1
            elif length <= 100:
                length_ranges["51-100"] += 1
            elif length <= 150:
                length_ranges["101-150"] += 1
            elif length <= 200:
                length_ranges["151-200"] += 1
            else:
                length_ranges["200+"] += 1
        
        print(f"\n   长度区间分布:")
        for range_name, count in length_ranges.items():
            percentage = (count / len(lengths)) * 100
            bar = "█" * int(percentage / 2)
            print(f"      {range_name:<15} : {count:>6} 次 ({percentage:>5.1f}%) {bar}")


def main():
    """主函数"""
    print("\n" + "🔍" * 40)
    print("Anker 测试数据统计分析")
    print("🔍" * 40)
    
    # 检查数据目录
    if not TEST_DATA_DIR.exists():
        print(f"\n❌ 测试数据目录不存在: {TEST_DATA_DIR}")
        return
    
    # 加载所有事件
    print("\n⚡ 正在加载数据...")
    all_events, families_stats = load_all_events()
    
    if not all_events:
        print("❌ 没有找到任何事件数据")
        return
    
    print(f"✅ 成功加载 {len(all_events)} 条事件数据")
    
    # 各项统计分析
    analyze_family_statistics(families_stats)
    analyze_field_distribution(all_events)
    analyze_time_distribution(all_events)
    analyze_event_description_length(all_events)
    
    print("\n\n" + "=" * 80)
    print("✅ 统计分析完成")
    print("=" * 80)


if __name__ == "__main__":
    main()


