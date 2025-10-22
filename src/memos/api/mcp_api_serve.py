"""
MemOS API MCP Server using FastMCP
Wraps three core interfaces: get_message, add_message, search_memory

Reference: https://docs-pre.openmem.net/dashboard/quick_start
"""

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

from memos.log import get_logger


load_dotenv()

logger = get_logger(__name__)


class MemOSAPIMCPServer:
    def __init__(self):
        self.mcp = FastMCP("MemOS API Server")
        self.base_url = os.getenv("MEMOS_BASE_URL", "https://memos.memtensor.cn/api/openmem/v1")
        self._setup_tools()

    def _get_headers(self, api_key: str) -> dict[str, str]:
        """Get HTTP headers with API key"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}"
        }

    def _setup_tools(self):
        """Setup MCP tools"""

        @self.mcp.tool()
        async def get_message(
            api_key: str,
            user_id: str,
            conversation_id: str | None = None
        ) -> dict[str, Any]:
            """
            Get user's message history.

            Retrieve the original conversation messages for a specified user and conversation.
            This returns the raw message history without any processing.

            Args:
                api_key (str): MemOS API Key (required) - each client provides their own key
                user_id (str): User ID (required)
                conversation_id (str, optional): Conversation ID. If not provided, returns all messages for the user

            Returns:
                dict: Response dictionary containing message list
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "message_detail_list": [
                                {
                                    "role": "user",
                                    "content": "...",
                                    "create_time": "2025-06-10 09:30:00",
                                    "update_time": "2025-06-10 09:30:00"
                                }
                            ]
                        }
                    }
            """
            try:
                url = f"{self.base_url}/get/message"
                data = {
                    "user_id": user_id,
                    "conversation_id": conversation_id
                }
                
                response = requests.post(
                    url=url,
                    headers=self._get_headers(api_key),
                    data=json.dumps(data),
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    f"Successfully retrieved messages, user_id={user_id}, "
                    f"count={len(result.get('data', {}).get('message_detail_list', []))}"
                )
                return result
                
            except Exception as e:
                logger.error(f"Failed to get messages: {e}")
                return {
                    "code": 500,
                    "message": f"Failed to get messages: {str(e)}",
                    "data": None
                }

        @self.mcp.tool()
        async def add_message(
            api_key: str,
            user_id: str,
            conversation_id: str,
            messages: list[dict[str, str]]
        ) -> dict[str, Any]:
            """
            Add messages to MemOS.

            Simply provide the raw conversation records to MemOS. MemOS will automatically
            abstract, process, and save them as memory. This is the core memory creation
            interface that transforms conversations into structured memories.

            Args:
                api_key (str): MemOS API Key (required) - each client provides their own key
                user_id (str): User ID (required)
                conversation_id (str): Conversation ID (required)
                messages (list[dict[str, str]]): Message list (required), each message contains role and content fields
                    Example: [
                        {"role": "user", "content": "I want to travel during summer vacation"},
                        {"role": "assistant", "content": "Sure! Are you traveling alone or with family?"}
                    ]

            Returns:
                dict: Response dictionary for add operation
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "success": true
                        }
                    }
            """
            try:
                url = f"{self.base_url}/add/message"
                data = {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "messages": messages
                }
                
                response = requests.post(
                    url=url,
                    headers=self._get_headers(api_key),
                    data=json.dumps(data),
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    f"Successfully added messages, user_id={user_id}, "
                    f"conversation_id={conversation_id}, count={len(messages)}"
                )
                return result
                
            except Exception as e:
                logger.error(f"Failed to add messages: {e}")
                return {
                    "code": 500,
                    "message": f"Failed to add messages: {str(e)}",
                    "data": None
                }

        @self.mcp.tool()
        async def search_memory(
            api_key: str,
            query: str,
            user_id: str,
            conversation_id: str,
            memory_limit_number: int = 6
        ) -> dict[str, Any]:
            """
            Search memory.

            Use the user's utterance to search memory, and MemOS will automatically retrieve
            the most relevant memories for the AI to reference. This enables memory-enhanced
            responses by finding contextually relevant information from past conversations.

            Args:
                api_key (str): MemOS API Key (required) - each client provides their own key
                query (str): Search query (required) - the user's current question or statement
                user_id (str): User ID (required)
                conversation_id (str): Conversation ID (required)
                memory_limit_number (int): Memory limit number, default 6. Maximum number of memories to return

            Returns:
                dict: Search result response dictionary
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "memory_detail_list": [
                                {
                                    "id": "...",
                                    "memory_key": "Summer Family Trip Plan",
                                    "memory_value": "[user perspective] The user plans...",
                                    "memory_type": "WorkingMemory",
                                    "conversation_id": "0610",
                                    "status": "activated",
                                    "tags": ["summer vacation", "family trip"],
                                    "relativity": 0.007873535
                                }
                            ],
                            "message_detail_list": null
                        }
                    }
            """
            try:
                url = f"{self.base_url}/search/memory"
                data = {
                    "query": query,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "memory_limit_number": memory_limit_number
                }
                
                response = requests.post(
                    url=url,
                    headers=self._get_headers(api_key),
                    data=json.dumps(data),
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    f"Successfully searched memory, query={query}, user_id={user_id}, "
                    f"results={len(result.get('data', {}).get('memory_detail_list', []))}"
                )
                return result
                
            except Exception as e:
                logger.error(f"Failed to search memory: {e}")
                return {
                    "code": 500,
                    "message": f"Failed to search memory: {str(e)}",
                    "data": None
                }

    def run(self, transport: str = "stdio", **kwargs):
        """Run MCP server with specified transport"""
        if transport == "stdio":
            # Run stdio mode (default for local usage)
            self.mcp.run(transport="stdio")
        elif transport == "http":
            # Run HTTP mode
            import asyncio
            host = kwargs.get("host", "localhost")
            port = kwargs.get("port", 8000)
            asyncio.run(self.mcp.run_http_async(host=host, port=port))
        elif transport == "sse":
            # Run SSE mode (deprecated but still supported)
            host = kwargs.get("host", "localhost")
            port = kwargs.get("port", 8000)
            self.mcp.run(transport="sse", host=host, port=port)
        else:
            raise ValueError(f"Unsupported transport: {transport}")


# Usage example
if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="MemOS API MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport method (default: stdio)",
    )
    parser.add_argument("--host", default="localhost", help="Host for HTTP/SSE transport")
    parser.add_argument("--port", type=int, default=8002, help="Port for HTTP/SSE transport")

    args = parser.parse_args()

    # Create and run MCP server
    server = MemOSAPIMCPServer()
    server.run(transport=args.transport, host=args.host, port=args.port)
