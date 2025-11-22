#!/bin/bash

# Anker 身份推理任务运行脚本
# 更新: 2024-11-20 支持渐进式评估

echo "======================================================================"
echo "🏠 Anker 家庭安防 - 渐进式身份推理与评估"
echo "======================================================================"
echo ""
echo "说明: "
echo "1. 系统将按照数据量从小到大处理家庭 (F3 -> F1 -> F2)"
echo "2. 采用渐进式学习: 每加入10%训练数据，在验证集上评估一次准确率"
echo "3. 最后对10月数据进行全量推理"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT" || exit 1

# 显示菜单
echo "请选择运行模式:"
echo ""
echo "  1. 🚀 快速验证模式 (test_inference_quick.py)"
echo "     - 少量样本 + 指标自检，秒级完成"
echo ""
echo "  2. 📦 最小数据家庭 (anker_identity_inference.py --mode quick)"
echo "     - 仅处理数据量最小的家庭 (F3)"
echo "     - 自动限流训练/测试样本"
echo ""
echo "  3. 🧪 完整渐进式评估 (anker_identity_inference.py --mode all)"
echo "     - 跑所有家庭，包含完整指标"
echo "     - 注意: 数据量大，耗时较长"
echo ""
echo "  0. 退出"
echo ""
read -p "请输入选项 (0-3): " choice

case $choice in
    1)
        echo ""
        echo "🚀 运行快速验证..."
        python examples/poc/test_inference_quick.py
        ;;
    
    2)
        echo ""
        echo "📦 运行最小数据家庭 (F3)..."
        python examples/poc/anker_identity_inference.py --mode quick
        ;;
    
    3)
        echo ""
        echo "🧪 开始完整渐进式评估..."
        echo "日志将保存在 examples/poc/inference_results/progressive_*/"
        python examples/poc/anker_identity_inference.py
        ;;
    
    0)
        exit 0
        ;;
    
    *)
        echo "无效选项"
        exit 1
        ;;
esac
