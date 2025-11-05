import json
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


def _check_memory_duplication(new_memory: str, existing_memories: list, llm) -> tuple[bool, str]:
    """
    使用LLM判断新记忆是否与已有记忆重复
    
    Args:
        new_memory: 待添加的新记忆内容
        existing_memories: 已有的记忆列表
        llm: LLM实例
        
    Returns:
        (is_duplicate, reason): 是否重复及原因说明
    """
    if not existing_memories:
        return False, "无已有记忆"
    
    # 构建去重判断的Prompt
    existing_memories_text = "\n".join([
        f"{i+1}. {mem.memory}" 
        for i, mem in enumerate(existing_memories[:30])  # 增加比对数量，避免遗漏
    ])
    
    prompt = f"""你是一个记忆去重专家。请**严格判断**新记忆是否与已有记忆重复。

【判断原则 - 从严判定】
⚠️ 采用**保守策略**：当新旧记忆语义基本相同时，应判定为重复

【重复的判断标准（满足任一即为重复）】
1. **完全相同**：新记忆与某条已有记忆表达的意思完全一致（即使措辞略有不同）
   - 示例：
     - 新："男人和两个孩子经常在晚上与车互动" 
     - 旧："男人和两个孩子经常在晚上与汽车互动"
     - 判定：✅ 重复（"车" vs "汽车"只是表达差异，语义相同）

2. **实质包含**：新记忆的核心信息已经被某条已有记忆包含
   - 示例：
     - 新："家庭成员在晚上离开"
     - 旧："家庭成员在晚上22:00-00:00之间离开"
     - 判定：✅ 重复（旧记忆更详细，新记忆被包含）

3. **微小差异**：仅有单复数、冠词（a/the）、轻微措辞差异
   - 示例：
     - 新："A man interacts with cars"
     - 旧："A man interacts with a car"
     - 判定：✅ 重复（cars vs car 是微小差异）

【不重复的判断标准（需同时满足）】
✓ 新记忆包含**实质性的新信息**（不是微小差异），例如：
  - 新的时间范围（如：旧记忆只有晚上，新记忆增加了早上）
  - 新的对象/主体（如：旧记忆只有男人，新记忆增加了女人）
  - 新的行为模式（如：旧记忆是"离开"，新记忆是"返回"）
  - 新的详细属性（如：旧记忆是"蓝色车"，新记忆增加了"黑色车"）

【特别注意】
- Pattern Memory（规律记忆）：只有当时间范围或对象有**明显扩展**时才判定为不重复
- Inference Memory（推理记忆）：只有当推理结论有**本质变化**时才判定为不重复
- 表达方式的优化、措辞的调整、语序的变化 → 判定为重复
- 同义词替换（如 car/vehicle, cat/feline）→ 判定为重复

【新记忆】
{new_memory}

【已有记忆（编号方便引用）】
{existing_memories_text}

【输出格式】
请严格按照以下JSON格式输出（不要有其他文字）：
{{
  "is_duplicate": true/false,
  "reason": "判断原因（如果重复，说明与第几条记忆重复；如果不重复，说明新增了什么信息）"
}}

示例输出：
- 重复：{{"is_duplicate": true, "reason": "与第1条记忆语义完全相同，仅措辞略有差异"}}
- 不重复：{{"is_duplicate": false, "reason": "新增了早上时间段（06:00-10:00），旧记忆只有晚上"}}
"""
    
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.generate(messages)
        
        # 尝试解析JSON响应
        # 清理响应中的markdown代码块标记
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        result = json.loads(response_clean)
        is_duplicate = result.get("is_duplicate", False)
        reason = result.get("reason", "无说明")
        
        return is_duplicate, reason
    except Exception as e:
        logger.warning(f"去重检测失败: {e}，默认不重复")
        return False, f"检测失败: {e}"


def _extract_time_info(memory_content: str, memory_key: str, mem_cube, mem_cube_id: str, llm) -> tuple[bool, str]:
    """
    从历史事实记忆中提取并总结时间信息
    
    Args:
        memory_content: 记忆内容
        memory_key: 记忆的key（如family_commute, delivery_pattern等）
        mem_cube: MemCube实例，用于检索历史记忆
        mem_cube_id: 用户的mem_cube_id
        llm: LLM实例
        
    Returns:
        (needs_time, extracted_time): 是否需要时间及提取的时间信息
    """
    # 判断是否为需要时间的记忆类型
    time_required_keys = [
        "family_commute", "door_usage", "door_state", "delivery_pattern"
    ]
    
    if memory_key not in time_required_keys:
        return False, ""
    
    # 检查是否已经包含时间范围（HH:MM-HH:MM格式）
    time_pattern = r'\d{2}:\d{2}-\d{2}:\d{2}'
    if re.search(time_pattern, memory_content):
        return False, ""  # 已经有时间信息
    
    # 检索相关的历史事实记忆
    try:
        # 使用记忆内容作为查询，检索相关的历史记忆
        related_memories = mem_cube.text_mem.search(
            query=memory_content,
            user_name=mem_cube_id,
            top_k=30,  # 多检索一些事实记忆
        )
        
        # 过滤出事实记忆（Factual Memory）并提取时间戳
        factual_memories_with_time = []
        for mem in related_memories:
            # 检查是否为事实记忆
            is_factual = (
                "[实时记忆]" in mem.memory or 
                "[Factual Memory]" in mem.memory
            )
            
            if is_factual:
                # 尝试从 metadata 中提取时间戳
                timestamp = None
                if hasattr(mem, 'metadata'):
                    # 尝试多种方式获取时间戳
                    if hasattr(mem.metadata, 'sources') and mem.metadata.sources:
                        for source in mem.metadata.sources:
                            if isinstance(source, dict):
                                # 尝试从 current_event 或其他字段提取时间
                                current_event = source.get('current_event', '')
                                if current_event and '[' in current_event:
                                    # 假设格式：[HH:MM | ... ] 或 [YYYY-MM-DD HH:MM]
                                    time_match = re.search(r'\[(\d{2}:\d{2})', current_event)
                                    if time_match:
                                        timestamp = time_match.group(1)
                                        break
                                # 或者直接从 metadata 字段获取
                                if 'timestamp' in source:
                                    ts = source['timestamp']
                                    # 提取时间部分（HH:MM）
                                    time_match = re.search(r'(\d{2}:\d{2})', str(ts))
                                    if time_match:
                                        timestamp = time_match.group(1)
                                        break
                
                if timestamp:
                    factual_memories_with_time.append({
                        "content": mem.memory,
                        "timestamp": timestamp
                    })
        
        if not factual_memories_with_time:
            logger.info(f"未找到带时间戳的相关事实记忆，Key: {memory_key}")
            return False, ""
        
        # 使用 LLM 从这些带时间戳的事实记忆中总结时间规律
        memories_text = "\n".join([
            f"[{m['timestamp']}] {m['content']}" 
            for m in factual_memories_with_time[:20]  # 提供更多候选，让 LLM 筛选
        ])
        
        prompt = f"""你是一个时间规律提取专家。请从历史事实记忆中**谨慎地**提取时间规律。

【重要提醒】
⚠️ 检索出来的历史记忆可能不完全相关，你需要：
1. **首先判断每条历史记忆是否与规律记忆真正相关**
2. **只使用相关的事件来提取时间**
3. **确保提取的时间具有高置信度**（至少3-5条相关事件支持）
4. **如果相关事件少于3条，或者时间分散不成规律，请返回 has_time: false**

【规律记忆类型】
{memory_key}

【规律记忆内容】
{memory_content}

【检索到的历史事实记忆（带时间戳，可能不全部相关）】
{memories_text}

【提取步骤】
步骤1: 筛选相关事件
- 仔细阅读规律记忆的描述（如"家庭成员离开"、"返回"等）
- 从历史记忆中找出**真正相关**的事件（内容语义匹配）
- 忽略不相关的事件（例如：规律是"离开"，但事件是"喂宠物"）

步骤2: 判断是否足够
- 相关事件 ≥ 3条：继续
- 相关事件 < 3条：返回 has_time: false

步骤3: 提取时间规律
- 分析相关事件的时间戳
- 如果是"离开和返回"类型，需要分别处理离开时间和返回时间
- 找出时间范围（最早到最晚，可适当扩展）
- 确保时间范围合理（如 06:00-10:00，而不是 06:45-06:50）

步骤4: 评估置信度
- high: ≥5条相关事件，时间集中在2-4小时窗口内
- medium: 3-4条相关事件，时间相对集中
- low: 时间太分散或事件太少
- 如果是 low，请返回 has_time: false

【输出格式】
请严格按照以下JSON格式输出：
{{
  "has_time": true/false,
  "time_range": "HH:MM-HH:MM",
  "confidence": "high/medium",
  "relevant_count": <相关事件数量>,
  "explanation": "从X条检索记忆中筛选出Y条相关事件，时间范围为..."
}}

【示例】
假设规律记忆是："家庭成员经常在早上离开住所"
- 相关事件：[07:30] 男性离开, [08:15] 女性离开, [08:45] 男性开车离开
- 不相关事件：[16:30] 喂猫, [20:00] 车停在车库
- 提取结果：time_range: "07:00-09:00", confidence: "high", relevant_count: 3
"""
        
        # 打印 prompt 到日志（用于调试）
        print(f"\n{'='*80}")
        print(f"【时间提取 LLM Prompt】")
        print(f"{'='*80}")
        print(f"记忆类型: {memory_key}")
        print(f"规律内容: {memory_content[:150]}...")
        print(f"检索到 {len(factual_memories_with_time)} 条带时间戳的事实记忆")
        print(f"\nPrompt (前1500字符):")
        print(prompt[:1500])
        if len(prompt) > 1500:
            print(f"... (剩余 {len(prompt) - 1500} 个字符)")
        print(f"{'='*80}\n")
        
        logger.info(
            f"开始时间提取 - Key: {memory_key}, "
            f"检索到 {len(factual_memories_with_time)} 条带时间戳的事实记忆"
        )
        
        messages = [{"role": "user", "content": prompt}]
        response = llm.generate(messages)
        
        # 清理响应
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        result = json.loads(response_clean)
        has_time = result.get("has_time", False)
        time_range = result.get("time_range", "")
        confidence = result.get("confidence", "low")
        relevant_count = result.get("relevant_count", 0)
        explanation = result.get("explanation", "")
        
        # 打印 LLM 响应（用于调试）
        print(f"\n{'='*80}")
        print(f"【时间提取 LLM Response】")
        print(f"{'='*80}")
        print(f"Has Time: {has_time}")
        print(f"Time Range: {time_range}")
        print(f"Confidence: {confidence}")
        print(f"Relevant Count: {relevant_count}")
        print(f"Explanation: {explanation}")
        print(f"{'='*80}\n")
        
        logger.info(
            f"时间提取结果 - Key: {memory_key}, HasTime: {has_time}, "
            f"TimeRange: {time_range}, Confidence: {confidence}, "
            f"检索 {len(factual_memories_with_time)} 条 -> 相关 {relevant_count} 条, "
            f"Explanation: {explanation}"
        )
        
        # 只有在置信度为 high 或 medium 时才返回时间
        if has_time and confidence in ["high", "medium"] and relevant_count >= 3:
            return True, time_range
        else:
            logger.info(f"时间提取置信度不足或相关事件太少，不添加时间信息")
            return False, ""
        
    except Exception as e:
        logger.warning(f"时间提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, ""


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
                        if len(filtered_memories) >= 20:  # 最多取8个，让 LLM 有更多选择
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
                
                if historical_events:
                    info_dict["historical_events"] = historical_events
                    logger.info(
                        f"Retrieved {len(filtered_memories)} non-inference historical events for pattern extraction "
                        f"(filtered from {len(similar_memories)} total)"
                    )
            except Exception as e:
                logger.warning(f"Failed to retrieve historical events: {e}")
        
        memories_local = mem_reader.get_memory(
            [add_req.messages],
            type=mem_type,
            info=info_dict,
        )
        flattened_local = [mm for m in memories_local for mm in m]
        logger.info(f"Memory extraction completed for user {add_req.user_id} using type={mem_type}")
        
        # 🔍 对非Factual Memory进行去重检测和时间提取
        filtered_memories = []
        duplicate_memories = []  # 记录重复的记忆
        total_memories = len(flattened_local)
        duplicate_count = 0
        
        for memory_item in flattened_local:
            memory_content = memory_item.memory
            
            # 判断记忆类型
            is_factual = "[实时记忆]" in memory_content or "[Factual Memory]" in memory_content
            is_pattern = "[规律记忆]" in memory_content or "[Pattern Memory]" in memory_content
            is_inference = "[推理记忆]" in memory_content or "[Inference Memory]" in memory_content
            
            # 如果是Factual Memory，直接添加
            if is_factual:
                logger.info(f"✅ Factual Memory，直接添加: {memory_content[:100]}...")
                filtered_memories.append(memory_item)
                continue
            
            # 对Pattern Memory和Inference Memory进行处理
            if is_pattern or is_inference:
                memory_type_label = "Pattern Memory" if is_pattern else "Inference Memory"
                logger.info(f"🔍 检测到 {memory_type_label}，开始处理...")
                
                # 1. 去重检测
                is_duplicate = False
                try:
                    logger.info(f"🔍 检测 {memory_type_label} 去重...")
                    
                    # 检索该用户所有非Factual的记忆（增加 top_k 避免遗漏重复）
                    all_memories = naive_mem_cube.text_mem.search(
                        query=memory_content,
                        user_name=user_context.mem_cube_id,
                        top_k=50,  # 增加检索数量，确保不遗漏重复记忆
                    )
                    
                    # 过滤出非Factual Memory
                    non_factual_memories = [
                        mem for mem in all_memories
                        if not ("[实时记忆]" in mem.memory or "[Factual Memory]" in mem.memory)
                    ]
                    
                    logger.info(f"   检索到 {len(non_factual_memories)} 条非Factual记忆")
                    
                    if non_factual_memories:
                        is_duplicate, dup_reason = _check_memory_duplication(
                            memory_content, non_factual_memories, llm
                        )
                        
                        if is_duplicate:
                            logger.info(f"   判定: 重复 - {dup_reason}")
                            duplicate_count += 1
                            duplicate_memories.append({
                                'content': memory_content,
                                'reason': dup_reason
                            })
                            continue  # 跳过这条重复记忆
                        else:
                            logger.info(f"   判定: 不重复 - {dup_reason}")
                    else:
                        # 没有历史记忆，直接添加
                        logger.info(f"   判定: 不重复（无历史记忆）")
                except Exception as e:
                    error_msg = f"⚠️  去重检测异常: {e}，默认添加该记忆"
                    logger.warning(error_msg)
                
                # 2. 时间信息提取
                try:
                    # 获取记忆的key（从metadata中获取）
                    memory_key = getattr(memory_item.metadata, 'key', '')
                    
                    if memory_key:
                        needs_time, time_range = _extract_time_info(
                            memory_content, memory_key, naive_mem_cube, user_context.mem_cube_id, llm
                        )
                        
                        if needs_time and time_range:
                            # 更新记忆内容，添加时间信息
                            # 在记忆类型标签后添加时间信息
                            if "[Pattern Memory]" in memory_content:
                                updated_content = memory_content.replace(
                                    "[Pattern Memory]",
                                    f"[Pattern Memory] (Time: {time_range})"
                                )
                            elif "[规律记忆]" in memory_content:
                                updated_content = memory_content.replace(
                                    "[规律记忆]",
                                    f"[规律记忆] (时间: {time_range})"
                                )
                            elif "[Inference Memory]" in memory_content:
                                updated_content = memory_content.replace(
                                    "[Inference Memory]",
                                    f"[Inference Memory] (Time: {time_range})"
                                )
                            elif "[推理记忆]" in memory_content:
                                updated_content = memory_content.replace(
                                    "[推理记忆]",
                                    f"[推理记忆] (时间: {time_range})"
                                )
                            else:
                                updated_content = memory_content
                            
                            memory_item.memory = updated_content
                            logger.info(f"   时间提取: {memory_key} -> {time_range}")
                            print(f"   ⏰ 添加时间: {time_range}")
                except Exception as e:
                    time_error_msg = f"⚠️  时间提取失败: {e}，使用原始内容"
                    logger.warning(time_error_msg)
                    print(f"   {time_error_msg}")
                
                # 添加到过滤后的列表
                filtered_memories.append(memory_item)
            else:
                # 其他类型的记忆直接添加
                filtered_memories.append(memory_item)
        
        # 使用过滤和更新后的记忆列表
        flattened_local = filtered_memories
        added_count = len(filtered_memories)
        
        # 打印去重统计
        print(f"\n{'='*60}")
        print(f"📊 【去重统计】")
        print(f"{'='*60}")
        print(f"  本次提取记忆总数: {total_memories}")
        print(f"  判定为重复: {duplicate_count} 条")
        print(f"  最终加入: {added_count} 条")
        print(f"{'='*60}\n")
        
        logger.info(
            f"去重统计 - 总数: {total_memories}, 重复: {duplicate_count}, 加入: {added_count}"
        )
        
        mem_ids_local: list[str] = naive_mem_cube.text_mem.add(
            flattened_local,
            user_name=user_context.mem_cube_id,
        )
        logger.info(
            f"Added {len(mem_ids_local)} memories for user {add_req.user_id} "
            f"in session {add_req.session_id}: {mem_ids_local}"
        )
        
        # 打印每条添加到数据库的记忆
        print(f"\n{'='*60}")
        print(f"✅ 【成功添加 {len(mem_ids_local)} 条记忆到数据库】")
        print(f"{'='*60}")
        
        for idx, (memory_id, memory) in enumerate(zip(mem_ids_local, flattened_local), 1):
            memory_content = memory.memory
            
            # 判断记忆类型（用于图标）
            if "[实时记忆]" in memory_content or "[Factual Memory]" in memory_content:
                mem_icon = "📌"
                mem_label = "实时记忆"
            elif "[规律记忆]" in memory_content or "[Pattern Memory]" in memory_content:
                mem_icon = "🔄"
                mem_label = "规律记忆"
            elif "[推理记忆]" in memory_content or "[Inference Memory]" in memory_content:
                mem_icon = "🤔"
                mem_label = "推理记忆"
            else:
                mem_icon = "📝"
                mem_label = memory.metadata.memory_type
            
            print(f"\n{mem_icon} 记忆 {idx}: {mem_label}")
            print(f"  ID: {memory_id}")
            print(f"  内容: {memory_content}")
        
        print(f"\n{'='*60}")
        
        # 打印重复的记忆（如果有）
        if duplicate_memories:
            print(f"\n{'='*60}")
            print(f"❌ 【重复的记忆（未加入）】共 {len(duplicate_memories)} 条")
            print(f"{'='*60}")
            for idx, dup_mem in enumerate(duplicate_memories, 1):
                # 判断记忆类型
                dup_content = dup_mem['content']
                if "[规律记忆]" in dup_content or "[Pattern Memory]" in dup_content:
                    mem_icon = "🔄"
                    mem_label = "规律记忆"
                elif "[推理记忆]" in dup_content or "[Inference Memory]" in dup_content:
                    mem_icon = "🤔"
                    mem_label = "推理记忆"
                else:
                    mem_icon = "📝"
                    mem_label = "其他记忆"
                
                print(f"\n❌ {mem_icon} [重复 {idx}]: {mem_label}")
                print(f"  内容: {dup_content}")
                print(f"  原因: {dup_mem['reason']}")
            print(f"\n{'='*60}")
        
        print()
        
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
