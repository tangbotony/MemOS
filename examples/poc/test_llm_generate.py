#!/usr/bin/env python3
"""测试LLM generate功能"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from memos.api.routers.server_router import llm
from memos.log import get_logger

logger = get_logger(__name__)


def test_simple_query():
    """测试1: 简单查询"""
    print("\n" + "="*60)
    print("测试1: 简单查询")
    print("="*60)
    
    query = "Hello, please tell me a short joke."
    
    try:
        print(f"\n📝 Query: {query}")
        response = llm.generate(query)
        print(f"\n✅ Response: {response}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_security_event_query():
    """测试2: 安防事件推理查询"""
    print("\n" + "="*60)
    print("测试2: 安防事件推理查询")
    print("="*60)
    
    query = """Analyze this security event and infer the person's identity:

Time: 2022-09-27 08:30 (Morning)
Description: A woman wearing black clothing and glasses was seen leaving the house with confident movements.

Based on the description, infer:
1. role_type: General Identity, Staff, or Suspicious Person
2. sub_role_type: Family Member, Visitor, Passerby, Delivery Person, Service Worker, Unspecified, or Potential Intruder
3. confidence: High, Medium, or Low
4. reasoning: Brief explanation

Format:
role_type: [answer]
sub_role_type: [answer]  
confidence: [answer]
reasoning: [answer]"""
    
    try:
        print(f"\n📝 Query: {query[:200]}...")
        response = llm.generate(query)
        print(f"\n✅ Response:\n{response}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_system_prompt():
    """测试3: 带system prompt的查询"""
    print("\n" + "="*60)
    print("测试3: 带system prompt的查询")
    print("="*60)
    
    # 检查llm.generate是否支持system_prompt参数
    import inspect
    sig = inspect.signature(llm.generate)
    print(f"\nllm.generate 参数: {sig}")
    
    query = "Analyze this: A person in uniform delivered a package at 2 PM."
    
    try:
        print(f"\n📝 Query: {query}")
        response = llm.generate(query)
        print(f"\n✅ Response: {response}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_info():
    """测试4: 查看LLM配置信息"""
    print("\n" + "="*60)
    print("测试4: LLM配置信息")
    print("="*60)
    
    try:
        print(f"\n📊 LLM类型: {type(llm)}")
        print(f"📊 LLM类名: {llm.__class__.__name__}")
        
        # 检查是否有config属性
        if hasattr(llm, 'config'):
            config = llm.config
            print(f"📊 模型: {getattr(config, 'model_schema', 'N/A')}")
            print(f"📊 Base URL: {getattr(config, 'base_url', 'N/A')}")
        
        # 列出所有方法
        methods = [m for m in dir(llm) if not m.startswith('_')]
        print(f"\n📊 可用方法: {', '.join(methods[:10])}")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("🧪 LLM Generate 功能测试")
    print("="*60)
    
    results = []
    
    # 测试4: 先查看配置
    results.append(("LLM配置信息", test_llm_info()))
    
    # 测试1: 简单查询
    results.append(("简单查询", test_simple_query()))
    
    # 测试2: 安防事件查询
    results.append(("安防事件推理", test_security_event_query()))
    
    # 测试3: 系统提示
    results.append(("带System Prompt", test_with_system_prompt()))
    
    # 总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    print(f"\n总计: {passed}/{total} 通过")


if __name__ == "__main__":
    main()

