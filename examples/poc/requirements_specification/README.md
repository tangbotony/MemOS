## 测试数据说明

### 测试文件
- `MemOS 测试.pdf`（见附件）

### 数据位置
- 路径：`./test_data/1-10/`

### 文件说明
- `General_Identity_formatted.json`：家庭成员通用身份的描述
- `Staff_formatted.json`：快递员身份的描述

### 家庭数据
- 命名规则：文件夹 `1-10` 分别对应 10 个家庭
- 每个家庭文件夹内均包含上述两个 JSON 文件

### 命名规范
- 家庭目录：`1`–`10`（数字字符串，对应 10 个家庭）
- 文件名：`General_Identity_formatted.json`、`Staff_formatted.json`
- JSON 键：下划线小写（如 `timestamp`, `event_description`, `key_scene`, `role_type`）
- 枚举/分类值：英文 Title Case（如 `Normal Activity`, `General Identity`, `Staff`）

### 字段说明
- `timestamp`：事件时间，格式 `YYYY-MM-DD HH:MM:SS`
- `event_description`：事件描述（英文）
- `key_scene`：关键场景分类
- `role_type`：身份类型（示例：`General Identity`、`Staff`）
