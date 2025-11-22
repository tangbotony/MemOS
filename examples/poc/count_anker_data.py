"""
统计Anker三个家庭的训练集和测试集数量
"""

import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 数据目录
DATA_DIR = project_root / "evaluation" / "data" / "anker" / "Test_data_22_pu_3_family_mothes_seperated"

# 家庭ID列表
FAMILY_IDS = [
    "T8030P1322100087",
    "T8030P132215001F", 
    "T8030P232228002B"
]

def count_events(family_id):
    """统计指定家庭的事件数量"""
    
    # 1. 训练数据 (9月)
    train_file = DATA_DIR / family_id / f"{family_id}_09.json"
    train_count = 0
    if train_file.exists():
        with open(train_file, 'r', encoding='utf-8') as f:
            train_data = json.load(f)
            train_count = len(train_data)
    
    # 2. 测试数据 (10月)
    test_file = DATA_DIR / family_id / f"{family_id}_10_no_role.json"
    test_count = 0
    if test_file.exists():
        with open(test_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            test_count = len(test_data)
            
    return train_count, test_count

def main():
    print("\n" + "="*60)
    print(f"{'家庭ID':<25} | {'训练集(9月)':<12} | {'测试集(10月)':<12} | {'总计':<8}")
    print("-" * 60)
    
    total_train = 0
    total_test = 0
    
    for family_id in FAMILY_IDS:
        train_count, test_count = count_events(family_id)
        total_count = train_count + test_count
        
        total_train += train_count
        total_test += test_count
        
        print(f"{family_id:<25} | {train_count:<12} | {test_count:<12} | {total_count:<8}")
    
    print("-" * 60)
    print(f"{'Total':<25} | {total_train:<12} | {total_test:<12} | {total_train + total_test:<8}")
    print("="*60 + "\n")
    
    # 估算耗时 (假设每条训练2.5s，每条推理3s)
    est_train_time = total_train * 2.5 / 60  # 分钟
    est_test_time = total_test * 3.0 / 60    # 分钟
    
    print(f"⏱️  估算耗时:")
    print(f"  - 训练耗时: 约 {est_train_time:.1f} 分钟")
    print(f"  - 推理耗时: 约 {est_test_time:.1f} 分钟")
    print(f"  - 总计耗时: 约 {est_train_time + est_test_time:.1f} 分钟")
    print("\n")

if __name__ == "__main__":
    main()

