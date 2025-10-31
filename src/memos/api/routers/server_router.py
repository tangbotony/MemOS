import os
import traceback

from typing import TYPE_CHECKING, Any
import re

from fastapi import APIRouter, HTTPException

from memos.api.config import APIConfig
from memos.api.product_models import (
    APIADDRequest,
    APIChatCompleteRequest,
    APISearchRequest,
    MemoryResponse,
    SearchResponse,
)
from memos.configs.embedder import EmbedderConfigFactory
from memos.configs.graph_db import GraphDBConfigFactory
from memos.configs.internet_retriever import InternetRetrieverConfigFactory
from memos.configs.llm import LLMConfigFactory
from memos.configs.mem_reader import MemReaderConfigFactory
from memos.configs.mem_scheduler import SchedulerConfigFactory
from memos.configs.reranker import RerankerConfigFactory
from memos.configs.vec_db import VectorDBConfigFactory
from memos.context.context import ContextThreadPoolExecutor
from memos.embedders.factory import EmbedderFactory
from memos.graph_dbs.factory import GraphStoreFactory
from memos.llms.factory import LLMFactory
from memos.log import get_logger
from memos.mem_cube.navie import NaiveMemCube
from memos.mem_os.product_server import MOSServer
from memos.mem_reader.factory import MemReaderFactory
from memos.mem_scheduler.orm_modules.base_model import BaseDBManager
from memos.mem_scheduler.scheduler_factory import SchedulerFactory
from memos.mem_scheduler.schemas.general_schemas import (
    SearchMode,
)
from memos.memories.textual.prefer_text_memory.config import (
    AdderConfigFactory,
    ExtractorConfigFactory,
    RetrieverConfigFactory,
)
from memos.memories.textual.prefer_text_memory.factory import (
    AdderFactory,
    ExtractorFactory,
    RetrieverFactory,
)
from memos.memories.textual.tree_text_memory.organize.manager import MemoryManager
from memos.memories.textual.tree_text_memory.retrieve.internet_retriever_factory import (
    InternetRetrieverFactory,
)
from memos.reranker.factory import RerankerFactory
from memos.templates.instruction_completion import instruct_completion


if TYPE_CHECKING:
    from memos.mem_scheduler.optimized_scheduler import OptimizedScheduler
from memos.types import MOSSearchResult, UserContext
from memos.vec_dbs.factory import VecDBFactory


logger = get_logger(__name__)

router = APIRouter(prefix="/product", tags=["Server API"])


def _build_graph_db_config(user_id: str = "default") -> dict[str, Any]:
    """Build graph database configuration."""
    graph_db_backend_map = {
        "neo4j-community": APIConfig.get_neo4j_community_config(user_id=user_id),
        "neo4j": APIConfig.get_neo4j_config(user_id=user_id),
        "nebular": APIConfig.get_nebular_config(user_id=user_id),
        "polardb": APIConfig.get_polardb_config(user_id=user_id),
    }

    graph_db_backend = os.getenv("NEO4J_BACKEND", "nebular").lower()
    return GraphDBConfigFactory.model_validate(
        {
            "backend": graph_db_backend,
            "config": graph_db_backend_map[graph_db_backend],
        }
    )


def _build_vec_db_config() -> dict[str, Any]:
    """Build vector database configuration."""
    return VectorDBConfigFactory.model_validate(
        {
            "backend": "milvus",
            "config": APIConfig.get_milvus_config(),
        }
    )


def _build_llm_config() -> dict[str, Any]:
    """Build LLM configuration."""
    return LLMConfigFactory.model_validate(
        {
            "backend": "openai",
            "config": APIConfig.get_openai_config(),
        }
    )


def _build_embedder_config() -> dict[str, Any]:
    """Build embedder configuration."""
    return EmbedderConfigFactory.model_validate(APIConfig.get_embedder_config())


def _build_mem_reader_config() -> dict[str, Any]:
    """Build memory reader configuration."""
    return MemReaderConfigFactory.model_validate(
        APIConfig.get_product_default_config()["mem_reader"]
    )


def _build_reranker_config() -> dict[str, Any]:
    """Build reranker configuration."""
    return RerankerConfigFactory.model_validate(APIConfig.get_reranker_config())


def _build_internet_retriever_config() -> dict[str, Any]:
    """Build internet retriever configuration."""
    return InternetRetrieverConfigFactory.model_validate(APIConfig.get_internet_config())


def _build_pref_extractor_config() -> dict[str, Any]:
    """Build extractor configuration."""
    return ExtractorConfigFactory.model_validate({"backend": "naive", "config": {}})


def _build_pref_adder_config() -> dict[str, Any]:
    """Build adder configuration."""
    return AdderConfigFactory.model_validate({"backend": "naive", "config": {}})


def _build_pref_retriever_config() -> dict[str, Any]:
    """Build retriever configuration."""
    return RetrieverConfigFactory.model_validate({"backend": "naive", "config": {}})


def _get_default_memory_size(cube_config) -> dict[str, int]:
    """Get default memory size configuration."""
    return getattr(cube_config.text_mem.config, "memory_size", None) or {
        "WorkingMemory": 20,
        "LongTermMemory": 1500,
        "UserMemory": 480,
    }


def init_server():
    """Initialize server components and configurations."""
    # Get default cube configuration
    default_cube_config = APIConfig.get_default_cube_config()

    # Build component configurations
    graph_db_config = _build_graph_db_config()
    llm_config = _build_llm_config()
    embedder_config = _build_embedder_config()
    mem_reader_config = _build_mem_reader_config()
    reranker_config = _build_reranker_config()
    internet_retriever_config = _build_internet_retriever_config()
    vector_db_config = _build_vec_db_config()
    pref_extractor_config = _build_pref_extractor_config()
    pref_adder_config = _build_pref_adder_config()
    pref_retriever_config = _build_pref_retriever_config()

    # Create component instances
    graph_db = GraphStoreFactory.from_config(graph_db_config)
    vector_db = VecDBFactory.from_config(vector_db_config)
    llm = LLMFactory.from_config(llm_config)
    embedder = EmbedderFactory.from_config(embedder_config)
    mem_reader = MemReaderFactory.from_config(mem_reader_config)
    reranker = RerankerFactory.from_config(reranker_config)
    internet_retriever = InternetRetrieverFactory.from_config(
        internet_retriever_config, embedder=embedder
    )
    pref_extractor = ExtractorFactory.from_config(
        config_factory=pref_extractor_config,
        llm_provider=llm,
        embedder=embedder,
        vector_db=vector_db,
    )
    pref_adder = AdderFactory.from_config(
        config_factory=pref_adder_config,
        llm_provider=llm,
        embedder=embedder,
        vector_db=vector_db,
    )
    pref_retriever = RetrieverFactory.from_config(
        config_factory=pref_retriever_config,
        llm_provider=llm,
        embedder=embedder,
        reranker=reranker,
        vector_db=vector_db,
    )

    # Initialize memory manager
    memory_manager = MemoryManager(
        graph_db,
        embedder,
        llm,
        memory_size=_get_default_memory_size(default_cube_config),
        is_reorganize=getattr(default_cube_config.text_mem.config, "reorganize", False),
    )
    mos_server = MOSServer(
        mem_reader=mem_reader,
        llm=llm,
        online_bot=False,
    )

    naive_mem_cube = NaiveMemCube(
        llm=llm,
        embedder=embedder,
        mem_reader=mem_reader,
        graph_db=graph_db,
        reranker=reranker,
        internet_retriever=internet_retriever,
        memory_manager=memory_manager,
        default_cube_config=default_cube_config,
        vector_db=vector_db,
        pref_extractor=pref_extractor,
        pref_adder=pref_adder,
        pref_retriever=pref_retriever,
    )

    # Initialize Scheduler
    scheduler_config_dict = APIConfig.get_scheduler_config()
    scheduler_config = SchedulerConfigFactory(
        backend="optimized_scheduler", config=scheduler_config_dict
    )
    mem_scheduler: OptimizedScheduler = SchedulerFactory.from_config(scheduler_config)
    mem_scheduler.initialize_modules(
        chat_llm=llm,
        process_llm=mem_reader.llm,
        db_engine=BaseDBManager.create_default_sqlite_engine(),
    )
    mem_scheduler.current_mem_cube = naive_mem_cube
    mem_scheduler.start()

    # Initialize SchedulerAPIModule
    api_module = mem_scheduler.api_module

    return (
        graph_db,
        mem_reader,
        llm,
        embedder,
        reranker,
        internet_retriever,
        memory_manager,
        default_cube_config,
        mos_server,
        mem_scheduler,
        naive_mem_cube,
        api_module,
        vector_db,
        pref_extractor,
        pref_adder,
        pref_retriever,
    )


# Initialize global components
(
    graph_db,
    mem_reader,
    llm,
    embedder,
    reranker,
    internet_retriever,
    memory_manager,
    default_cube_config,
    mos_server,
    mem_scheduler,
    naive_mem_cube,
    api_module,
    vector_db,
    pref_extractor,
    pref_adder,
    pref_retriever,
) = init_server()


def _format_memory_item(memory_data: Any) -> dict[str, Any]:
    """Format a single memory item for API response."""
    memory = memory_data.model_dump()
    memory_id = memory["id"]
    ref_id = f"[{memory_id.split('-')[0]}]"

    memory["ref_id"] = ref_id
    memory["metadata"]["embedding"] = []
    memory["metadata"]["sources"] = []
    memory["metadata"]["ref_id"] = ref_id
    memory["metadata"]["id"] = memory_id
    memory["metadata"]["memory"] = memory["memory"]

    return memory


def _post_process_pref_mem(
    memories_result: list[dict[str, Any]],
    pref_formatted_mem: list[dict[str, Any]],
    mem_cube_id: str,
    handle_pref_mem: bool,
):
    if handle_pref_mem:
        memories_result["pref_mem"].append(
            {
                "cube_id": mem_cube_id,
                "memories": pref_formatted_mem,
            }
        )
        pref_instruction: str = instruct_completion(pref_formatted_mem)
        memories_result["pref_string"] = pref_instruction

    return memories_result


@router.post("/search", summary="Search memories", response_model=SearchResponse)
def search_memories(search_req: APISearchRequest):
    """Search memories for a specific user."""
    # Create UserContext object - how to assign values
    user_context = UserContext(
        user_id=search_req.user_id,
        mem_cube_id=search_req.mem_cube_id,
        session_id=search_req.session_id or "default_session",
    )
    logger.info(f"Search user_id is: {user_context.mem_cube_id}")
    memories_result: MOSSearchResult = {
        "text_mem": [],
        "act_mem": [],
        "para_mem": [],
        "pref_mem": [],
        "pref_string": "",
    }

    search_mode = search_req.mode

    def _search_text():
        if search_mode == SearchMode.FAST:
            formatted_memories = fast_search_memories(
                search_req=search_req, user_context=user_context
            )
        elif search_mode == SearchMode.FINE:
            formatted_memories = fine_search_memories(
                search_req=search_req, user_context=user_context
            )
        elif search_mode == SearchMode.MIXTURE:
            formatted_memories = mix_search_memories(
                search_req=search_req, user_context=user_context
            )
        else:
            logger.error(f"Unsupported search mode: {search_mode}")
            raise HTTPException(status_code=400, detail=f"Unsupported search mode: {search_mode}")
        return formatted_memories

    def _search_pref():
        if os.getenv("ENABLE_PREFERENCE_MEMORY", "false").lower() != "true":
            return []
        results = naive_mem_cube.pref_mem.search(
            query=search_req.query,
            top_k=search_req.top_k,
            info={
                "user_id": search_req.user_id,
                "session_id": search_req.session_id,
                "chat_history": search_req.chat_history,
            },
        )
        return [_format_memory_item(data) for data in results]

    with ContextThreadPoolExecutor(max_workers=2) as executor:
        text_future = executor.submit(_search_text)
        pref_future = executor.submit(_search_pref)
        text_formatted_memories = text_future.result()
        pref_formatted_memories = pref_future.result()

    memories_result["text_mem"].append(
        {
            "cube_id": search_req.mem_cube_id,
            "memories": text_formatted_memories,
        }
    )

    memories_result = _post_process_pref_mem(
        memories_result, pref_formatted_memories, search_req.mem_cube_id, search_req.handle_pref_mem
    )

    return SearchResponse(
        message="Search completed successfully",
        data=memories_result,
    )


def mix_search_memories(
    search_req: APISearchRequest,
    user_context: UserContext,
):
    """
    Mix search memories: fast search + async fine search
    """

    formatted_memories = mem_scheduler.mix_search_memories(
        search_req=search_req,
        user_context=user_context,
    )
    return formatted_memories


def fine_search_memories(
    search_req: APISearchRequest,
    user_context: UserContext,
):
    target_session_id = search_req.session_id
    if not target_session_id:
        target_session_id = "default_session"
    search_filter = {"session_id": search_req.session_id} if search_req.session_id else None

    # Create MemCube and perform search
    search_results = naive_mem_cube.text_mem.search(
        query=search_req.query,
        user_name=user_context.mem_cube_id,
        top_k=search_req.top_k,
        mode=SearchMode.FINE,
        manual_close_internet=not search_req.internet_search,
        moscube=search_req.moscube,
        search_filter=search_filter,
        info={
            "user_id": search_req.user_id,
            "session_id": target_session_id,
            "chat_history": search_req.chat_history,
        },
    )
    formatted_memories = [_format_memory_item(data) for data in search_results]

    return formatted_memories


def fast_search_memories(
    search_req: APISearchRequest,
    user_context: UserContext,
):
    target_session_id = search_req.session_id
    if not target_session_id:
        target_session_id = "default_session"
    search_filter = {"session_id": search_req.session_id} if search_req.session_id else None

    # Create MemCube and perform search
    search_results = naive_mem_cube.text_mem.search(
        query=search_req.query,
        user_name=user_context.mem_cube_id,
        top_k=search_req.top_k,
        mode=SearchMode.FAST,
        manual_close_internet=not search_req.internet_search,
        moscube=search_req.moscube,
        search_filter=search_filter,
        info={
            "user_id": search_req.user_id,
            "session_id": target_session_id,
            "chat_history": search_req.chat_history,
        },
    )
    formatted_memories = [_format_memory_item(data) for data in search_results]

    return formatted_memories


@router.post("/add", summary="Add memories", response_model=MemoryResponse)
def add_memories(add_req: APIADDRequest):
    """Add memories for a specific user."""
    # Create UserContext object - how to assign values
    user_context = UserContext(
        user_id=add_req.user_id,
        mem_cube_id=add_req.mem_cube_id,
        session_id=add_req.session_id or "default_session",
    )
    target_session_id = add_req.session_id
    if not target_session_id:
        target_session_id = "default_session"

    def _process_text_mem() -> list[dict[str, str]]:
        # Determine the type based on source or default to chat
        mem_type = "chat"
        if add_req.source and "security" in add_req.source.lower():
            mem_type = "security"
        elif add_req.source and "anker" in add_req.source.lower():
            mem_type = "security"
        
        # For security type, retrieve historical similar events
        info_dict = {
            "user_id": add_req.user_id,
            "session_id": target_session_id,
        }
        
        # 用于存储检索到的历史记忆（用于返回给调用者）
        retrieved_historical_memories = []
        
        if mem_type == "security" and add_req.messages:
            # Get current event content
            current_event = add_req.messages[0].get("content", "")
            
            # Search for similar historical events
            try:
                similar_memories = naive_mem_cube.text_mem.search(
                    query=current_event,
                    user_name=user_context.mem_cube_id,
                    top_k=20,  # 多检索一些，后面会过滤
                )
                graph_data = naive_mem_cube.text_mem.graph_store.export_graph(user_name=user_context.mem_cube_id, include_embedding=False)
                print("--------------------------------")
                print("-------------graph_data-------------------")
                print(graph_data)
                print("---------------graph_data end-----------------")
                print("--------------------------------")
                # 过滤掉推理性内容，保留事实和规律记忆（包括可能不太相关的）
                filtered_memories = []
                
                for mem in similar_memories:
                    # 获取相似度分数
                    similarity = getattr(mem, 'similarity', None)
                    
                    # 检查是否为推理性内容
                    is_inference = (
                        "[推理记忆]" in mem.memory or 
                        "[Inference Memory]" in mem.memory or
                        "【推测】" in mem.memory or 
                        "[推测]" in mem.memory or 
                        "【推理】" in mem.memory or
                        "inference" in mem.metadata.tags
                    )
                    
                    # 只保留非推理性内容（事实记忆和规律记忆）
                    # 注意：不过滤相似度，让 LLM 自己判断是否相关
                    if not is_inference:
                        filtered_memories.append(mem)
                        # 保存用于返回
                        retrieved_historical_memories.append({
                            "memory": mem.memory,
                            "memory_id": mem.id,
                            "similarity": similarity
                        })
                        if len(filtered_memories) >= 8:  # 最多取8个，让 LLM 有更多选择
                            break
                
                # Format historical events for prompt (with timestamps and hour)
                historical_events = ""
                for mem in filtered_memories:
                    # 尝试从 metadata 中获取时间戳
                    timestamp_info = ""
                    if hasattr(mem, 'metadata') and hasattr(mem.metadata, 'sources'):
                        for source in mem.metadata.sources:
                            if isinstance(source, dict) and 'current_event' in source:
                                # 从 current_event 中提取时间戳（假设格式包含时间）
                                source_event = source['current_event']  # 修复：使用不同的变量名，避免覆盖外层的 current_event
                                # 尝试匹配日期时间格式 YYYY-MM-DD HH:MM
                                datetime_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2})', source_event)
                                if datetime_match:
                                    date = datetime_match.group(1)
                                    hour = datetime_match.group(2)
                                    minute = datetime_match.group(3)
                                    # 加上当天小时信息
                                    timestamp_info = f"[{date} {hour}:{minute} ({hour}h)] "
                                else:
                                    # 如果没有时间，至少提取日期
                                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', source_event)
                                    if date_match:
                                        timestamp_info = f"[{date_match.group(1)}] "
                                break
                    
                    # 如果没有找到时间戳，尝试从 created_at 获取
                    if not timestamp_info and hasattr(mem, 'metadata') and hasattr(mem.metadata, 'created_at'):
                        created_at = mem.metadata.created_at
                        if created_at:
                            # 取日期和小时分钟部分，并加上小时信息
                            created_str = str(created_at)[:16]
                            hour_match = re.search(r'(\d{2}):\d{2}$', created_str)
                            if hour_match:
                                hour = hour_match.group(1)
                                timestamp_info = f"[{created_str} ({hour}h)] "
                            else:
                                timestamp_info = f"[{created_str}] "
                    
                    historical_events += timestamp_info + mem.memory + "\n"
                
                # 调试：打印历史事件信息
                print(f"\n🔍 [Debug] 检索到 {len(filtered_memories)} 条历史记忆")
                print(f"🔍 [Debug] historical_events 长度: {len(historical_events)} 字符")
                if historical_events:
                    print(f"🔍 [Debug] historical_events 前 200 字符: {historical_events[:200]}")
                else:
                    print(f"🔍 [Debug] ⚠️ historical_events 为空!")
                
                if historical_events:
                    info_dict["historical_events"] = historical_events
                    logger.info(
                        f"Retrieved {len(filtered_memories)} non-inference historical events for pattern extraction "
                        f"(filtered from {len(similar_memories)} total)"
                    )
                else:
                    print(f"🔍 [Debug] ⚠️ 没有历史事件被添加到 info_dict")
            except Exception as e:
                logger.warning(f"Failed to retrieve historical events: {e}")
        
        memories_local = mem_reader.get_memory(
            [add_req.messages],
            type=mem_type,
            info=info_dict,
        )
        flattened_local = [mm for m in memories_local for mm in m]
        logger.info(f"Memory extraction completed for user {add_req.user_id} using type={mem_type}")
        mem_ids_local: list[str] = naive_mem_cube.text_mem.add(
            flattened_local,
            user_name=user_context.mem_cube_id,
        )
        logger.info(
            f"Added {len(mem_ids_local)} memories for user {add_req.user_id} "
            f"in session {add_req.session_id}: {mem_ids_local}"
        )
        
        # 构建返回结果，包含检索到的历史记忆
        result_memories = []
        for memory_id, memory in zip(mem_ids_local, flattened_local, strict=False):
            mem_dict = {
                "memory": memory.memory,
                "memory_id": memory_id,
                "memory_type": memory.metadata.memory_type,
            }
            # 如果有检索到的历史记忆，添加到第一个记忆项中
            if retrieved_historical_memories and len(result_memories) == 0:
                mem_dict["retrieved_historical_memories"] = retrieved_historical_memories
            result_memories.append(mem_dict)
        
        return result_memories

    def _process_pref_mem() -> list[dict[str, str]]:
        if os.getenv("ENABLE_PREFERENCE_MEMORY", "false").lower() != "true":
            return []
        pref_memories_local = naive_mem_cube.pref_mem.get_memory(
            [add_req.messages],
            type="chat",
            info={
                "user_id": add_req.user_id,
                "session_id": target_session_id,
            },
        )
        pref_ids_local: list[str] = naive_mem_cube.pref_mem.add(pref_memories_local)
        logger.info(
            f"Added {len(pref_ids_local)} preferences for user {add_req.user_id} "
            f"in session {add_req.session_id}: {pref_ids_local}"
        )
        return [
            {
                "memory": memory.memory,
                "memory_id": memory_id,
                "memory_type": memory.metadata.preference_type,
            }
            for memory_id, memory in zip(pref_ids_local, pref_memories_local, strict=False)
        ]

    with ContextThreadPoolExecutor(max_workers=2) as executor:
        text_future = executor.submit(_process_text_mem)
        pref_future = executor.submit(_process_pref_mem)
        text_response_data = text_future.result()
        pref_response_data = pref_future.result()

    return MemoryResponse(
        message="Memory added successfully",
        data=text_response_data + pref_response_data,
    )


@router.post("/chat/complete", summary="Chat with MemOS (Complete Response)")
def chat_complete(chat_req: APIChatCompleteRequest):
    """Chat with MemOS for a specific user. Returns complete response (non-streaming)."""
    try:
        # Collect all responses from the generator
        content, references = mos_server.chat(
            query=chat_req.query,
            user_id=chat_req.user_id,
            cube_id=chat_req.mem_cube_id,
            mem_cube=naive_mem_cube,
            history=chat_req.history,
            internet_search=chat_req.internet_search,
            moscube=chat_req.moscube,
            base_prompt=chat_req.base_prompt,
            top_k=chat_req.top_k,
            threshold=chat_req.threshold,
            session_id=chat_req.session_id,
        )

        # Return the complete response
        return {
            "message": "Chat completed successfully",
            "data": {"response": content, "references": references},
        }

    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(traceback.format_exc())) from err
    except Exception as err:
        logger.error(f"Failed to start chat: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(traceback.format_exc())) from err
