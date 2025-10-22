"""
Simple test script for MemOS API MCP Server
Tests the three core interfaces: get_message, add_message, search_memory
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project path
project_root = Path(__file__).parent.parent.parent  # tests/api -> tests -> project_root
sys.path.insert(0, str(project_root / "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
from fastmcp import FastMCP



load_dotenv()


async def test_mcp_api_server():
    """Test MemOS API MCP Server"""
    
    # Check environment variables
    api_key = os.getenv("MEMOS_API_KEY")
    if not api_key:
        print("❌ Error: MEMOS_API_KEY environment variable not set")
        print("Please set: export MEMOS_API_KEY='your_api_key'")
        return
    
    print("=" * 80)
    print("MemOS API MCP Server Test")
    print("=" * 80)
    print()
    
    # Configure server parameters
    # Note: No need to pass MEMOS_API_KEY to server - each client call provides its own api_key
    server_params = StdioServerParameters(
        command="python",
        args=[str(project_root / "src" / "memos" / "api" / "mcp_api_serve.py")],
        env={
            "MEMOS_BASE_URL": os.getenv("MEMOS_BASE_URL", "https://memos.memtensor.cn/api/openmem/v1"),
        }
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()
                print("✅ Connected to MCP server\n")
                
                # List tools
                print("-" * 80)
                print("Available Tools")
                print("-" * 80)
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    print(f"  - {tool.name}")
                print()
                
                # Test parameters
                test_user_id = f"test_user_{hash(api_key) % 100000}"
                test_conversation_id = "test_conv_001"
                
                # Test 1: add_message
                print("-" * 80)
                print("Test 1: add_message")
                print("-" * 80)
                test_messages = [
                    {"role": "user", "content": "I want to travel during summer vacation, can you recommend something?"},
                    {"role": "assistant", "content": "Sure! Are you traveling alone, with family or with friends?"},
                    {"role": "user", "content": "I'm bringing my kid. My family always travels together."},
                ]
                
                result = await session.call_tool(
                    "add_message",
                    arguments={
                        "api_key": api_key,
                        "user_id": test_user_id,
                        "conversation_id": test_conversation_id,
                        "messages": test_messages
                    }
                )
                
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"Response code: {data.get('code')}")
                        print(f"Response message: {data.get('message')}")
                        if data.get('code') == 0:
                            print("✅ add_message test PASSED")
                        else:
                            print(f"⚠️  add_message returned code: {data.get('code')}")
                print()
                
                # Wait for processing
                await asyncio.sleep(2)
                
                # Test 2: get_message
                print("-" * 80)
                print("Test 2: get_message")
                print("-" * 80)
                
                result = await session.call_tool(
                    "get_message",
                    arguments={
                        "api_key": api_key,
                        "user_id": test_user_id,
                        "conversation_id": test_conversation_id
                    }
                )
                
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"Response code: {data.get('code')}")
                        if data.get('code') == 0:
                            msg_count = len(data.get('data', {}).get('message_detail_list', []))
                            print(f"Retrieved {msg_count} messages")
                            print("✅ get_message test PASSED")
                        else:
                            print(f"⚠️  get_message returned code: {data.get('code')}")
                print()
                
                # Test 3: search_memory
                print("-" * 80)
                print("Test 3: search_memory")
                print("-" * 80)
                
                result = await session.call_tool(
                    "search_memory",
                    arguments={
                        "api_key": api_key,
                        "query": "travel with family",
                        "user_id": test_user_id,
                        "conversation_id": test_conversation_id,
                        "memory_limit_number": 10
                    }
                )
                
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"Response code: {data.get('code')}")
                        if data.get('code') == 0:
                            mem_count = len(data.get('data', {}).get('memory_detail_list', []))
                            print(f"Found {mem_count} memories")
                            print("✅ search_memory test PASSED")
                        else:
                            print(f"⚠️  search_memory returned code: {data.get('code')}")
                print()
                
                # Summary
                print("=" * 80)
                print("All tests completed!")
                print("=" * 80)
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    print()
    try:
        asyncio.run(test_mcp_api_server())
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


