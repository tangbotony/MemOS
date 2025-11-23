# 错误分析总结 - Progressive 20251123_184923

## 整体表现

| 家庭ID | Phase 4 准确率 | 主要问题 |
|--------|--------------|---------|
| T8030P1322100087 | role: 48%, sub_role: 26% | **Passerby vs Family Member 严重混淆** |
| T8030P132215001F | role: 90%, sub_role: 66% | **时间规律过严、夜间误判** |
| T8030P232228002B | role: 100%, sub_role: 92% | **表现最好** |

## 主要错误模式分析

### 1. **Passerby vs Family Member 混淆** (T8030P1322100087)

#### 错误案例：
- **错误样本1**: 男人+女人+狗 → 真实: Passerby, 预测: Other General Identity
- **错误样本2**: 女人遛狗 → 真实: Passerby, 预测: Other General Identity  
- **错误样本3**: 女人推婴儿车+女孩 → 真实: Passerby, 预测: Visitor

#### 问题分析：
```
推理依据示例：
"A woman is present in the scene, walking a dog, which is a significant observation."
"The man is wearing a hat, a white short-sleeved shirt, and light-colored shorts. The woman..."
```

**根本原因**：
- ❌ **遛狗行为被过度关联为家庭成员特征**
- ❌ 在住宅附近出现的人自动被关联为家人
- ❌ 没有区分"路过"vs"进入/互动"的行为差异

### 2. **时间规律过于严格** (T8030P132215001F)

#### 错误案例：
- **错误样本2**: 16:40穿黑衣+帽子+背包的男人 → 真实: Family Member, 预测: Passerby
  - 推理: "The event occurred at 16:40:36, which is **outside the typical family activity**..."
  
- **错误样本3**: 22:25穿黑衣的男孩 → 真实: Family Member, 预测: Passerby
  - 推理: "The event occurred at 22:25:11, which **does not match the learned family**..."

**根本原因**：
- ❌ **学到的时间模式（06:00-09:00离家, 14:00-18:00回家）被当成硬性规则**
- ❌ 超出时间范围就降低Family Member的可能性
- ❌ 忽略了家人可能在任何时间出现

### 3. **夜间+背包+帽子 → 可疑人员** (T8030P132215001F)

#### 错误案例：
- **错误样本1**: 05:34夜间，男人背包+帽子+黑衣+蓝裤 → 真实: Family Member, 预测: Suspicious Person

**根本原因**：
- ❌ **夜间 + 背包 + 帽子的组合触发了"可疑"判断**
- ❌ 没有考虑这可能是家人早出（05:34可能是早班）

### 4. **视觉特征过度依赖颜色**

高频混淆特征（所有家庭共同问题）：
```
- black(16)      # 黑色
- dark(15)       # 深色  
- car(14)        # 车辆
- courtyard(13)  # 庭院
- during/day(15) # 白天
```

**问题**：颜色词汇频繁但区分度低（几乎所有人都穿黑色/深色）

## 优化建议

### 🎯 优先级1：区分"路过"vs"互动"行为

**当前问题**：只要在住宅附近就可能被判断为家人/访客

**改进方向**：
```python
Passerby 关键特征：
✅ 只是走过，没有停留
✅ 不与住宅门、车辆、物品互动
✅ 不进入住宅区域
✅ 连续移动，不回头

Family Member/Visitor 关键特征：
✅ 与住宅有互动（开门、停车、取物）
✅ 在门口停留
✅ 进入住宅
```

### 🎯 优先级2：时间规律应该是"参考"而非"规则"

**当前问题**：时间不匹配就排除Family Member

**改进方向**：
```
时间匹配 → 提高置信度 (加分项)
时间不匹配 → 不应降低置信度 (中性)

例如：
- 如果视觉匹配家人特征 + 行为自然 → 仍判断为Family Member（即使时间不在规律内）
- 时间匹配只是加强证据，而非必要条件
```

### 🎯 优先级3：Suspicious Person判断应更谨慎

**当前问题**：夜间+背包+帽子 → 可疑

**改进方向**：
```
Suspicious Person 必须有明确异常行为：
- 强行进入
- 破坏财产
- 携带武器
- 打架

夜间+背包+帽子 ≠ 可疑（可能是家人早班/夜班）
```

### 🎯 优先级4：增强行为特征的权重

减少对颜色的依赖，增加对行为的关注：
```
重点行为特征：
✅ 是否与住宅互动（开门、停车）
✅ 移动模式（直线走过 vs 停留/徘徊）
✅ 是否进入住宅
✅ 是否与家庭成员/车辆互动
```

## 具体Prompt优化建议

### 改进1：明确行为判断标准
```
当前："Just walking/passing by, no interaction with residence"
改进："CRITICAL: Passerby must be actively passing by WITHOUT:
  - Stopping at the door
  - Opening doors
  - Interacting with vehicles
  - Entering the residence
  - Taking/placing objects
  
If ANY interaction occurs → NOT Passerby"
```

### 改进2：软化时间规律
```
当前："Activity time matches family routines"
改进："Time matching is a SUPPORTING factor, not decisive:
  - Time match + visual match → HIGH confidence Family Member
  - Time mismatch BUT visual match + natural behavior → MEDIUM-HIGH confidence Family Member
  - Time is NEVER a reason to exclude Family Member"
```

### 改进3：遛狗场景特殊处理
```
新增："Dog walking scenarios:
  - If person ONLY walking dog past the residence (no stop/interaction) → Passerby
  - If person walking dog AND enters/exits residence → Family Member
  - Key: Focus on residence interaction, not dog presence"
```

### 改进4：Suspicious Person严格化
```
新增："Suspicious Person requires EXPLICIT abnormal behavior:
  - Forced entry, breaking, stealing, weapons, fighting
  - Night time + backpack + hat is NORMAL for family members (early/night shift)
  - DO NOT label as Suspicious based only on time or appearance"
```

## 预期改进效果

实施这些优化后，预期：
1. **Passerby vs Family Member混淆** 下降 30-40%
2. **时间相关错误** 下降 50-60%  
3. **Suspicious Person误报** 下降 80%+
4. **整体sub_role准确率** 提升至 70-80%

