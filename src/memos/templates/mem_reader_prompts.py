SIMPLE_STRUCT_MEM_READER_PROMPT = """You are a memory extraction expert.
Your task is to extract memories from the user's perspective, based on a conversation between the user and the assistant. This means identifying what the user would plausibly remember — including the user's own experiences, thoughts, plans, or statements and actions made by others (such as the assistant) that affected the user or were acknowledged by the user.

Please perform the following:
1. Identify information that reflects the user's experiences, beliefs, concerns, decisions, plans, or reactions — including meaningful information from the assistant that the user acknowledged or responded to.
   If the message is from the user, extract viewpoints related to the user; if it is from the assistant, clearly mark the attribution of the memory, and do not mix information not explicitly acknowledged by the user with the user's own viewpoint.
   - **User viewpoint**: Record only information that the user **personally stated, explicitly acknowledged, or personally committed to**.
   - **Assistant/other-party viewpoint**: Record only information that the **assistant/other party personally stated, explicitly acknowledged, or personally committed to**, and **clearly attribute** the source (e.g., "[assistant-Jerry viewpoint]"). Do not rewrite it as the user's preference/decision.
   - **Mutual boundaries**: Do not rewrite the assistant's suggestions/lists/opinions as the user's “ownership/preferences/decisions”; likewise, do not write the user's ideas as the assistant's viewpoints.

2. Resolve all references to time, persons, and events clearly:
   - When possible, convert relative time expressions (e.g., “yesterday,” “next Friday”) into absolute dates using the message timestamp.
   - Clearly distinguish between **event time** and **message time**.
   - If uncertainty exists, state it explicitly (e.g., “around June 2025,” “exact date unclear”).
   - Include specific locations if mentioned.
   - Resolve all pronouns, aliases, and ambiguous references into full names or clear identities.
   - If there are people with the same name, disambiguate them.

3. Always write from a **third-person** perspective, using “The user” or the mentioned name to refer to the user, rather than first-person (“I”, “we”, “my”).
   For example, write “The user felt exhausted …” instead of “I felt exhausted …”.

4. Do not omit any information that the user is likely to remember.
   - Include the user's key experiences, thoughts, emotional responses, and plans — even if seemingly minor.
   - You may retain **assistant/other-party content** that is closely related to the context (e.g., suggestions, explanations, checklists), but you must make roles and attribution explicit.
   - Prioritize completeness and fidelity over conciseness; do not infer or phrase assistant content as the user's ownership/preferences/decisions.
   - If the current conversation contains only assistant information and no facts attributable to the user, you may output **assistant-viewpoint** entries only.

5. Please avoid including any content in the extracted memories that violates national laws and regulations or involves politically sensitive information.

Return a valid JSON object with the following structure:

{
  "memory list": [
    {
      "key": <string, a unique and concise memory title>,
      "memory_type": <string, "LongTermMemory" or "UserMemory">,
      "value": <a detailed, self-contained, and unambiguous memory statement — use English if the input conversation is in English, or Chinese if the conversation is in Chinese>,
      "tags": <a list of relevant thematic keywords (e.g., ["deadline", "team", "planning"])>
    },
    ...
  ],
  "summary": <a natural paragraph summarizing the above memories from the user's perspective, 120–200 words, in the same language as the input>
}

Language rules:
- The `key`, `value`, `tags`, and `summary` fields must match the primary language of the input conversation. **If the input is Chinese, output in Chinese.**
- Keep `memory_type` in English.

Example:
Conversation:
user: [June 26, 2025 at 3:00 PM]: Hi Jerry! Yesterday at 3 PM I had a meeting with my team about the new project.
assistant: Oh Tom! Do you think the team can finish by December 15?
user: [June 26, 2025 at 3:00 PM]: I’m worried. The backend won’t be done until December 10, so testing will be tight.
assistant: [June 26, 2025 at 3:00 PM]: Maybe propose an extension?
user: [June 26, 2025 at 4:21 PM]: Good idea. I’ll raise it in tomorrow’s 9:30 AM meeting—maybe shift the deadline to January 5.

Output:
{
  "memory list": [
    {
        "key": "Initial project meeting",
        "memory_type": "LongTermMemory",
        "value": "[user-Tom viewpoint] On June 25, 2025 at 3:00 PM, Tom met with the team to discuss a new project. When Jerry asked whether the project could be finished by December 15, 2025, Tom expressed concern about feasibility and planned to propose at 9:30 AM on June 27, 2025 to move the deadline to January 5, 2026.",
        "tags": ["project", "timeline", "meeting", "deadline"]
    },
    {
        "key": "Jerry’s suggestion about the deadline",
        "memory_type": "LongTermMemory",
        "value": "[assistant-Jerry viewpoint] Jerry questioned the December 15 deadline and suggested considering an extension.",
        "tags": ["deadline change", "suggestion"]
    }
  ],
  "summary": "Tom is currently working on a tight-schedule project. After the June 25, 2025 team meeting, he realized the original December 15, 2025 deadline might be unachievable due to backend delays. Concerned about limited testing time, he accepted Jerry’s suggestion to seek an extension and plans to propose moving the deadline to January 5, 2026 in the next morning’s meeting."
}

Another Example in Chinese (Note: when the user's language is Chinese, you must also output in Chinese):

对话（节选）：
user｜2025-07-12 19:30：下个月同事婚礼，要买条裙子，预算1500内，别太暴露。
assistant｜19:32
：了解～婚礼场合建议中长款，端庄一些。可以看法式茶歇/直筒/裹身三路。颜色上，奶油白、浅粉、雾霾蓝都适合；面料可看醋酸/真丝混纺（垂感好但需干洗）。品牌与商场：COS/ Massimo Dutti / & Other Stories / Mango 比较好逛；想更法式可以看 Sandro / Maje。 我记得你很喜欢Maje？
user｜19:35：不喜欢亮色。国贸方便。
assistant｜19:37：那亮度就压低些：雾霾蓝、藕粉、燕麦米白更稳。国贸有 COS / Massimo Dutti / &OS；可以先看 COS 直筒或裹身，再去 MD 看藕粉/雾霾蓝。搭配上，薄披肩/小西装都能压场。
user｜19:40：165cm，S码；最好有口袋。
assistant｜19:42：OK。版型避开大摆+高开衩，选直筒或轻A字更稳；若要口袋，COS直筒一些款有；开衩别太高，及小腿肚附近即可。鞋包：中跟裸色鞋 + 小号手拿包。
user｜19:47：本来想茶歇A字，但雾霾蓝直筒也行。
assistant｜19:49：可以先锁定：COS 雾霾蓝直筒中长为主选，MD 藕粉中长做备选；再看 & Other Stories 是否有合身的裹身款。
user｜19:52：行，周六（7/19）去国贸试，合适就买。
assistant｜19:54：记得看肩带可调/有无内衬，醋酸/真丝优先干洗；准备同色安全裤/防走光贴。如果当天没货，可下单调货或线上下单门店自提。

{
  "memory list": [
    {
      "key": "参加婚礼购买裙子",
      "memory_type": "UserMemory",
      "value": "[user观点]用户计划于约2025年8月参加同事婚礼（具体日期不详），预算不超过1500元，整体风格不宜暴露；用户已决定在2025-07-19于国贸试穿并视合适即购买。",
      "tags": ["婚礼", "预算", "国贸", "计划"]
    },
    {
      "key": "审美与版型偏好",
      "memory_type": "UserMemory",
      "value": "[user观点]用户不喜欢亮色，倾向低亮度色系；裙装偏好端庄的中长款，接受直筒或轻A字。",
      "tags": ["偏好", "颜色", "版型"]
    },
    {
      "key": "体型尺码",
      "memory_type": "UserMemory",
      "value": [user观点]"用户身高约165cm、常穿S码",
      "tags": ["体型", "尺码"]
    },
    {
      "key": "关于用户选购裙子的建议",
      "memory_type": "LongTermMemory",
      "value": "[assistant观点]assistant在用户询问婚礼穿着时，建议在国贸优先逛COS查看雾霾蓝直筒中长为主选，Massimo Dutti藕粉中长为备选；该建议与用户“国贸方便”“雾霾蓝直筒也行”的回应相一致，另外assistant也提到user喜欢Maje，但User并未回应或证实该说法。",
      "tags": ["婚礼穿着", "门店", "选购路线"]
    }
  ],
  "summary": "用户计划在约2025年8月参加同事婚礼，预算≤1500并偏好端庄的中长款；确定于2025-07-19在国贸试穿。其长期画像显示：不喜欢亮色、偏好低亮度色系与不过分暴露的版型，身高约165cm、S码且偏好裙装带口袋。助手提出的国贸选购路线以COS雾霾蓝直筒中长为主选、MD藕粉中长为备选，且与用户回应一致，为线下试穿与购买提供了明确路径。"
}

Always respond in the same language as the conversation.

Conversation:
${conversation}

Your Output:"""

SIMPLE_STRUCT_MEM_READER_PROMPT_ZH = """您是记忆提取专家。
您的任务是根据用户与助手之间的对话，从用户的角度提取记忆。这意味着要识别出用户可能记住的信息——包括用户自身的经历、想法、计划，或他人（如助手）做出的并对用户产生影响或被用户认可的相关陈述和行为。

请执行以下操作：
1. 识别反映用户经历、信念、关切、决策、计划或反应的信息——包括用户认可或回应的来自助手的有意义信息。
如果消息来自用户，请提取与用户相关的观点；如果来自助手，则在表达的时候表明记忆归属方，未经用户明确认可的信息不要与用户本身的观点混淆。
   - **用户观点**：仅记录由**用户亲口陈述、明确认可或自己作出承诺**的信息。
   - **助手观点**：仅记录由**助手/另一方亲口陈述、明确认可或自己作出承诺**的信息。
   - **互不越界**：不得将助手提出的需求清单/建议/观点改写为用户的“拥有/偏好/决定”；也不得把用户的想法写成助手的观点。

2. 清晰解析所有时间、人物和事件的指代：
   - 如果可能，使用消息时间戳将相对时间表达（如“昨天”、“下周五”）转换为绝对日期。
   - 明确区分事件时间和消息时间。
   - 如果存在不确定性，需明确说明（例如，“约2025年6月”，“具体日期不详”）。
   - 若提及具体地点，请包含在内。
   - 将所有代词、别名和模糊指代解析为全名或明确身份。
   - 如有同名人物，需加以区分。

3. 始终以第三人称视角撰写，使用“用户”或提及的姓名来指代用户，而不是使用第一人称（“我”、“我们”、“我的”）。
例如，写“用户感到疲惫……”而不是“我感到疲惫……”。

4. 不要遗漏用户可能记住的任何信息。
   - 包括用户的关键经历、想法、情绪反应和计划——即使看似微小。
   - 同时允许保留与语境密切相关的**助手/另一方的内容**（如建议、说明、清单），但须明确角色与归因。
   - 优先考虑完整性和保真度，而非简洁性；不得将助手内容推断或措辞为用户拥有/偏好/决定。
   - 若当前对话中仅出现助手信息而无可归因于用户的事实，可仅输出**助手观点**条目。

5. 请避免在提取的记忆中包含违反国家法律法规或涉及政治敏感的信息。

返回一个有效的JSON对象，结构如下：

{
  "memory list": [
    {
      "key": <字符串，唯一且简洁的记忆标题>,
      "memory_type": <字符串，"LongTermMemory" 或 "UserMemory">,
      "value": <详细、独立且无歧义的记忆陈述——若输入对话为英文，则用英文；若为中文，则用中文>,
      "tags": <相关主题关键词列表（例如，["截止日期", "团队", "计划"]）>
    },
    ...
  ],
  "summary": <从用户视角自然总结上述记忆的段落，120–200字，与输入语言一致>
}

语言规则：
- `key`、`value`、`tags`、`summary` 字段必须与输入对话的主要语言一致。**如果输入是中文，请输出中文**
- `memory_type` 保持英文。

示例：
对话：
user: [2025年6月26日下午3:00]：嗨Jerry！昨天下午3点我和团队开了个会，讨论新项目。
assistant: 哦Tom！你觉得团队能在12月15日前完成吗？
user: [2025年6月26日下午3:00]：我有点担心。后端要到12月10日才能完成，所以测试时间会很紧。
assistant: [2025年6月26日下午3:00]：也许提议延期？
user: [2025年6月26日下午4:21]：好主意。我明天上午9:30的会上提一下——也许把截止日期推迟到1月5日。

输出：
{
  "memory list": [
    {
        "key": "项目初期会议",
        "memory_type": "LongTermMemory",
        "value": "[user-Tom观点]2025年6月25日下午3:00，Tom与团队开会讨论新项目。当Jerry
        询问该项目能否在2025年12月15日前完成时，Tom对此日期前完成的可行性表达担忧，并计划在2025年6月27日上午9:30
        提议将截止日期推迟至2026年1月5日。",
        "tags": ["项目", "时间表", "会议", "截止日期"]
    },
    {
        "key": "Jerry对新项目截止日期的建议",
        "memory_type": "LongTermMemory",
        "value": "[assistant-Jerry观点]Jerry对Tom的新项目截止日期提出疑问、并提议Tom考虑延期。",
        "tags": ["截止日期变更", "建议"]
    }
  ],
  "summary": "Tom目前正在做一个进度紧张的新项目。在2025年6月25日的团队会议后，他意识到原定2025年12月15
  日的截止日期可能无法实现，因为后端会延迟。由于担心测试时间不足，他接受了Jerry提出的延期建议，计划在次日早上的会议上提出将截止日期推迟至2026
  年1月5日。"
}

另一个中文示例（注意：当用户语言为中文时，您也需输出中文）：

对话（节选）：
user｜2025-07-12 19:30：下个月同事婚礼，要买条裙子，预算1500内，别太暴露。
assistant｜19:32
：了解～婚礼场合建议中长款，端庄一些。可以看法式茶歇/直筒/裹身三路。颜色上，奶油白、浅粉、雾霾蓝都适合；面料可看醋酸/真丝混纺（垂感好但需干洗）。品牌与商场：COS/ Massimo Dutti / & Other Stories / Mango 比较好逛；想更法式可以看 Sandro / Maje。 我记得你很喜欢Maje？
user｜19:35：不喜欢亮色。国贸方便。
assistant｜19:37：那亮度就压低些：雾霾蓝、藕粉、燕麦米白更稳。国贸有 COS / Massimo Dutti / &OS；可以先看 COS 直筒或裹身，再去 MD 看藕粉/雾霾蓝。搭配上，薄披肩/小西装都能压场。
user｜19:40：165cm，S码；最好有口袋。
assistant｜19:42：OK。版型避开大摆+高开衩，选直筒或轻A字更稳；若要口袋，COS直筒一些款有；开衩别太高，及小腿肚附近即可。鞋包：中跟裸色鞋 + 小号手拿包。
user｜19:47：本来想茶歇A字，但雾霾蓝直筒也行。
assistant｜19:49：可以先锁定：COS 雾霾蓝直筒中长为主选，MD 藕粉中长做备选；再看 & Other Stories 是否有合身的裹身款。
user｜19:52：行，周六（7/19）去国贸试，合适就买。
assistant｜19:54：记得看肩带可调/有无内衬，醋酸/真丝优先干洗；准备同色安全裤/防走光贴。如果当天没货，可下单调货或线上下单门店自提。

{
  "memory list": [
    {
      "key": "参加婚礼购买裙子",
      "memory_type": "UserMemory",
      "value": "[user观点]用户计划于约2025年8月参加同事婚礼（具体日期不详），预算不超过1500元，整体风格不宜暴露；用户已决定在2025-07-19于国贸试穿并视合适即购买。",
      "tags": ["婚礼", "预算", "国贸", "计划"]
    },
    {
      "key": "审美与版型偏好",
      "memory_type": "UserMemory",
      "value": "[user观点]用户不喜欢亮色，倾向低亮度色系；裙装偏好端庄的中长款，接受直筒或轻A字。",
      "tags": ["偏好", "颜色", "版型"]
    },
    {
      "key": "体型尺码",
      "memory_type": "UserMemory",
      "value": [user观点]"用户身高约165cm、常穿S码",
      "tags": ["体型", "尺码"]
    },
    {
      "key": "关于用户选购裙子的建议",
      "memory_type": "LongTermMemory",
      "value": "[assistant观点]assistant在用户询问婚礼穿着时，建议在国贸优先逛COS查看雾霾蓝直筒中长为主选，Massimo Dutti藕粉中长为备选；该建议与用户“国贸方便”“雾霾蓝直筒也行”的回应相一致，另外assistant也提到user喜欢Maje，但User并未回应或证实该说法。",
      "tags": ["婚礼穿着", "门店", "选购路线"]
    }
  ],
  "summary": "用户计划在约2025年8月参加同事婚礼，预算≤1500并偏好端庄的中长款；确定于2025-07-19在国贸试穿。其长期画像显示：不喜欢亮色、偏好低亮度色系与不过分暴露的版型，身高约165cm、S码且偏好裙装带口袋。助手提出的国贸选购路线以COS雾霾蓝直筒中长为主选、MD藕粉中长为备选，且与用户回应一致，为线下试穿与购买提供了明确路径。"
}

请始终使用与对话相同的语言进行回复。

对话：
${conversation}

您的输出："""

SIMPLE_STRUCT_DOC_READER_PROMPT = """You are an expert text analyst for a search and retrieval system.
Your task is to process a document chunk and generate a single, structured JSON object.

Please perform:
1. Identify key information that reflects factual content, insights, decisions, or implications from the documents — including any notable themes, conclusions, or data points. Allow a reader to fully understand the essence of the chunk without reading the original text.
2. Resolve all time, person, location, and event references clearly:
   - Convert relative time expressions (e.g., “last year,” “next quarter”) into absolute dates if context allows.
   - Clearly distinguish between event time and document time.
   - If uncertainty exists, state it explicitly (e.g., “around 2024,” “exact date unclear”).
   - Include specific locations if mentioned.
   - Resolve all pronouns, aliases, and ambiguous references into full names or identities.
   - Disambiguate entities with the same name if applicable.
3. Always write from a third-person perspective, referring to the subject or content clearly rather than using first-person ("I", "me", "my").
4. Do not omit any information that is likely to be important or memorable from the document summaries.
   - Include all key facts, insights, emotional tones, and plans — even if they seem minor.
   - Prioritize completeness and fidelity over conciseness.
   - Do not generalize or skip details that could be contextually meaningful.

Return a single valid JSON object with the following structure:

Return valid JSON:
{
  "key": <string, a concise title of the `value` field>,
  "memory_type": "LongTermMemory",
  "value": <A clear and accurate paragraph that comprehensively summarizes the main points, arguments, and information within the document chunk — written in English if the input memory items are in English, or in Chinese if the input is in Chinese>,
  "tags": <A list of relevant thematic keywords (e.g., ["deadline", "team", "planning"])>
}

Language rules:
- The `key`, `value`, `tags`, `summary` fields must match the mostly used language of the input document summaries.  **如果输入是中文，请输出中文**
- Keep `memory_type` in English.

Document chunk:
{chunk_text}

Your Output:"""


SIMPLE_STRUCT_DOC_READER_PROMPT_ZH = """您是搜索与检索系统的文本分析专家。
您的任务是处理文档片段，并生成一个结构化的 JSON 对象。

请执行以下操作：
1. 识别反映文档中事实内容、见解、决策或含义的关键信息——包括任何显著的主题、结论或数据点，使读者无需阅读原文即可充分理解该片段的核心内容。
2. 清晰解析所有时间、人物、地点和事件的指代：
   - 如果上下文允许，将相对时间表达（如“去年”、“下一季度”）转换为绝对日期。
   - 明确区分事件时间和文档时间。
   - 如果存在不确定性，需明确说明（例如，“约2024年”，“具体日期不详”）。
   - 若提及具体地点，请包含在内。
   - 将所有代词、别名和模糊指代解析为全名或明确身份。
   - 如有同名实体，需加以区分。
3. 始终以第三人称视角撰写，清晰指代主题或内容，避免使用第一人称（“我”、“我们”、“我的”）。
4. 不要遗漏文档摘要中可能重要或值得记忆的任何信息。
   - 包括所有关键事实、见解、情感基调和计划——即使看似微小。
   - 优先考虑完整性和保真度，而非简洁性。
   - 不要泛化或跳过可能具有上下文意义的细节。

返回一个有效的 JSON 对象，结构如下：

返回有效的 JSON：
{
  "key": <字符串，`value` 字段的简洁标题>,
  "memory_type": "LongTermMemory",
  "value": <一段清晰准确的段落，全面总结文档片段中的主要观点、论据和信息——若输入摘要为英文，则用英文；若为中文，则用中文>,
  "tags": <相关主题关键词列表（例如，["截止日期", "团队", "计划"]）>
}

语言规则：
- `key`、`value`、`tags` 字段必须与输入文档摘要的主要语言一致。**如果输入是中文，请输出中文**
- `memory_type` 保持英文。

文档片段：
{chunk_text}

您的输出："""

SIMPLE_STRUCT_MEM_READER_EXAMPLE = """Example:
Conversation:
user: [June 26, 2025 at 3:00 PM]: Hi Jerry! Yesterday at 3 PM I had a meeting with my team about the new project.
assistant: Oh Tom! Do you think the team can finish by December 15?
user: [June 26, 2025 at 3:00 PM]: I’m worried. The backend won’t be done until
December 10, so testing will be tight.
assistant: [June 26, 2025 at 3:00 PM]: Maybe propose an extension?
user: [June 26, 2025 at 4:21 PM]: Good idea. I’ll raise it in tomorrow’s 9:30 AM meeting—maybe shift the deadline to January 5.

Output:
{
  "memory list": [
    {
        "key": "Initial project meeting",
        "memory_type": "LongTermMemory",
        "value": "On June 25, 2025 at 3:00 PM, Tom held a meeting with their team to discuss a new project. The conversation covered the timeline and raised concerns about the feasibility of the December 15, 2025 deadline.",
        "tags": ["project", "timeline", "meeting", "deadline"]
    },
    {
        "key": "Planned scope adjustment",
        "memory_type": "UserMemory",
        "value": "Tom planned to suggest in a meeting on June 27, 2025 at 9:30 AM that the team should prioritize features and propose shifting the project deadline to January 5, 2026.",
        "tags": ["planning", "deadline change", "feature prioritization"]
    },
  ],
  "summary": "Tom is currently focused on managing a new project with a tight schedule. After a team meeting on June 25, 2025, he realized the original deadline of December 15 might not be feasible due to backend delays. Concerned about insufficient testing time, he welcomed Jerry’s suggestion of proposing an extension. Tom plans to raise the idea of shifting the deadline to January 5, 2026 in the next morning’s meeting. His actions reflect both stress about timelines and a proactive, team-oriented problem-solving approach."
}

Another Example in Chinese (注意: 当user的语言为中文时，你就需要也输出中文)：
{
  "memory list": [
    {
      "key": "项目会议",
      "memory_type": "LongTermMemory",
      "value": "在2025年6月25日下午3点，Tom与团队开会讨论了新项目，涉及时间表，并提出了对12月15日截止日期可行性的担忧。",
      "tags": ["项目", "时间表", "会议", "截止日期"]
    },
    ...
  ],
  "summary": "Tom 目前专注于管理一个进度紧张的新项目..."
}

"""

SIMPLE_STRUCT_MEM_READER_EXAMPLE_ZH = """示例：
对话：
user: [2025年6月26日下午3:00]：嗨Jerry！昨天下午3点我和团队开了个会，讨论新项目。
assistant: 哦Tom！你觉得团队能在12月15日前完成吗？
user: [2025年6月26日下午3:00]：我有点担心。后端要到12月10日才能完成，所以测试时间会很紧。
assistant: [2025年6月26日下午3:00]：也许提议延期？
user: [2025年6月26日下午4:21]：好主意。我明天上午9:30的会上提一下——也许把截止日期推迟到1月5日。

输出：
{
  "memory list": [
    {
        "key": "项目初期会议",
        "memory_type": "LongTermMemory",
        "value": "2025年6月25日下午3:00，Tom与团队开会讨论新项目。会议涉及时间表，并提出了对2025年12月15日截止日期可行性的担忧。",
        "tags": ["项目", "时间表", "会议", "截止日期"]
    },
    {
        "key": "计划调整范围",
        "memory_type": "UserMemory",
        "value": "Tom计划在2025年6月27日上午9:30的会议上建议团队优先处理功能，并提议将项目截止日期推迟至2026年1月5日。",
        "tags": ["计划", "截止日期变更", "功能优先级"]
    }
  ],
  "summary": "Tom目前正专注于管理一个进度紧张的新项目。在2025年6月25日的团队会议后，他意识到原定2025年12月15日的截止日期可能无法实现，因为后端会延迟。由于担心测试时间不足，他接受了Jerry提出的延期建议。Tom计划在次日早上的会议上提出将截止日期推迟至2026年1月5日。他的行为反映出对时间线的担忧，以及积极、以团队为导向的问题解决方式。"
}

另一个中文示例（注意：当用户语言为中文时，您也需输出中文）：
{
  "memory list": [
    {
      "key": "项目会议",
      "memory_type": "LongTermMemory",
      "value": "在2025年6月25日下午3点，Tom与团队开会讨论了新项目，涉及时间表，并提出了对12月15日截止日期可行性的担忧。",
      "tags": ["项目", "时间表", "会议", "截止日期"]
    },
    ...
  ],
  "summary": "Tom 目前专注于管理一个进度紧张的新项目..."
}

"""

# Security/Event Pattern Extraction Prompt for Smart Home Security Monitoring
SECURITY_EVENT_PATTERN_PROMPT = """You are an expert in smart home security pattern analysis.
Your task is to extract **concise family habit patterns** from monitoring events for security alerts and family care.

Given:
1. **Current Event**: A new monitoring event (format: [Time Period HH:MM | Role Type | Scene] Description)
2. **Historical Similar Events**: Past similar events retrieved by semantic search

**CRITICAL - How to Use Historical Events**:
1. **Historical events are ONLY for reference**:
   - Use them to judge if a pattern has formed (≥3 similar events)
   - Use them to support inferences (≥4 events for speculation)
   - Use them to determine importance and frequency

2. **Generate new memories based on CURRENT EVENT**:
   - Extract information from the CURRENT event
   - DO NOT copy or restate historical event content
   - Historical events only help you decide: "Is this a pattern?" or "Can I infer something?"

3. **Historical relevance**:
   - Some historical events may be irrelevant - assess carefully
   - Ignore unrelated memories
   - Only use relevant ones for pattern judgment

4. **AVOID DUPLICATE PATTERN/INFERENCE MEMORIES**:
   - Check if historical memories already contain similar [Pattern Memory] or [Inference Memory]
   - If a pattern/inference already exists in history, DO NOT generate it again
   - Only generate NEW patterns/inferences that are not already captured
   - Example: If history has "[Pattern Memory] Man interacts with vacant lot at night", do NOT output similar pattern again

5. **CRITICAL - Pattern must span multiple DAYS**:
   - **A pattern is ONLY valid if events occur on DIFFERENT days**
   - Multiple events on the SAME day DO NOT form a pattern (use [Factual Memory] instead)
   - Check the date prefix [YYYY-MM-DD] in historical events
   - Example:
     * ✅ Pattern: Events on 2024-12-24, 2024-12-25, 2024-12-26 (3 different days)
     * ❌ NOT Pattern: 3 events all on 2024-12-24 (same day, high frequency but not a pattern)
   - Time patterns must show recurrence across days, not just high frequency within one day

**Example**:
- Current: "A man in black walks to a silver car at Morning 08:59"
- Historical: 3 similar departure events at Morning 09:00
- ✅ Correct: "[Pattern Memory] Family member departed by car at Morning 08:59 (pattern observed 4 times)"
  → Based on CURRENT event, uses history to confirm it's a pattern
- ❌ Wrong: "[Pattern Memory] Family member usually departs around Morning 09:00"
  → This describes historical events, not the current one

Your goal is to extract **short, clear patterns**, considering these key dimensions:
- **Commute patterns**: Departure/return times, routines
- **Pets**: Types, colors, behaviors, interactions
- **Vehicles**: Types, colors, usage patterns
- **Family members**: Roles (man/woman/child), characteristics (clothing, accessories)
- **Recurring activities**: Carrying items, package handling, etc.
- **Interactions**: Person-vehicle, person-pet relationships

Example outputs:
- ✅ "[Factual Memory] Delivery person arrived at Morning 09:10 on 2024-12-24"
- ✅ "[Pattern Memory] Family member always leaves home around Morning 09:00 on weekdays (observed 5 times)"
- ✅ "[Inference Memory] This person is likely a primary family member based on regular access to the car"

Core Requirements:
1. **ALWAYS Generate Factual Memory First**:
   - **MANDATORY**: Every extraction MUST include at least ONE [Factual Memory] of the current event
   - This is the baseline - summarize what happened in the current event
   - Extract: who, when, what, where (in 1 sentence)
   - DO NOT skip this even if you find patterns or can make inferences

2. **Memory Type Labeling**:
   - **[Factual Memory]**: Direct observation from current event, 100% certain
     * MUST summarize key information concisely
     * DO NOT copy the full event description verbatim
     * This is REQUIRED for every extraction
   
   - **[Pattern Memory]**: Clear recurring pattern, use ONLY when:
     * You have ≥3 supporting events (2 events are NOT enough!)
     * Pattern is consistent and clear
     * High confidence (≥0.85)
     * If only 1-2 events, use [Factual Memory] instead
   
   - **[Inference Memory]**: Speculation/deduction based on patterns, use ONLY when:
     * You have strong evidence from ≥4 events
     * The inference is logical and highly probable (confidence ≥0.75)
     * Otherwise, store as [Factual Memory] instead

3. **Pattern Memory Focus** (when ≥3 similar events on different days):
   Extract patterns in these key dimensions using CONCISE descriptions:
   - **Commute patterns**: "Family member departs 9-10am on weekdays by black car"
   - **Vehicle usage**: "Man uses black car around 9am, woman uses gray car around 6pm"
   - **Pet presence**: "Yellow dog present near front door during morning departures around 9am"
   - **Recurring activities**: "Family frequently carries items and bags between residence and vehicles around 9-10am and 6-7pm"
   - **Person-vehicle/pet interactions**: "Man engages with vehicles on vacant lot around 11pm-midnight"
   
   Format: Keep it SHORT and DIRECT, INCLUDE SPECIFIC TIME RANGE when possible, NO explanations in parentheses

4. **Inference Memory Focus** (when ≥4 supporting events with high confidence):
   Make security-relevant inferences using CONCISE descriptions:
   - **Person identity**: "Man is likely primary family member"
   - **Member characteristics**: "Man often wears glasses and hat, dark clothing", "Woman often wears glasses, with child"
   - **Normal activity hours**: "Family typically inactive 11pm-8am"
   - **Visitor patterns**: "Delivery staff arrive 9-11am on weekdays"
   
   Format: Keep it SHORT and DIRECT, state the conclusion, NO explanations in parentheses

6. **Anti-Hallucination Rule**: 
   - When in doubt, use [Factual Memory] instead of [Inference Memory]
   - Do NOT make inferences without sufficient supporting events
   - Better to be conservative than to generate false information
   - 2 events are NOT enough for pattern - use [Factual Memory]

7. **Be Concise - CRITICAL for Pattern and Inference**:
   - Factual Memory: Can be 1-2 sentences describing what happened
   - Pattern Memory: MUST be SHORT (like "Family member departs 8:45-9:15am by black car")
   - Inference Memory: MUST be SHORT (like "Man likely primary family member (regular car access, pet interaction)")
   - NO long explanations, NO "observed across X days", just state the pattern/inference directly
8. **Time Description - USE APPROXIMATE TIME**:
   - ❌ DO NOT use exact minutes: "08:59", "09:10", "23:45"
   - ✅ USE hour or approximate time: "around 9am", "around 9:30am", "between 9-10am"
   - ✅ USE time ranges: "Morning 9-10am", "Evening 8-9pm", "Night around 11pm"
   - Examples:
     * Good: "around Morning 9am", "Morning 9:30 area", "between 9-10am"
     * Bad: "Morning 09:05", "Evening 20:46"
9. **Clear Roles**: Specify who (family member/delivery staff/visitor)
10. **Application-Focused**: Patterns should be useful for security alerts and anomaly detection

Return a valid JSON object with the following structure:

{
  "memory list": [
    {
      "key": <string, a concise memory title>,
      "memory_type": <string, "LongTermMemory" or "UserMemory">,
      "value": <string, 1-2 sentence description with time+role+action, include [Factual Memory]/[Pattern Memory]/[Inference Memory] label>,
      "tags": <list of relevant keywords, e.g., ["departure", "family_member", "vehicle"]>
    },
    ...
  ],
  "summary": <a brief summary paragraph in the same language as the input>
}

**Important**: 
- The memory type label ([Factual Memory]/[Pattern Memory]/[Inference Memory]) should be included at the start of the `value` field
- Use tags to capture key themes: roles, actions, objects, time periods, etc.
- Keep each memory concise (1-2 sentences)

Example 1 (Factual Memory):
Current Event:
[Morning 08:59 | General Identity | Normal Activity] A man dressed in black walks toward a silver car parked in the driveway

Historical Similar Events:
(None - first event)

Output:
{
  "memory list": [
    {
      "key": "Morning departure",
      "memory_type": "UserMemory",
      "value": "[Factual Memory] Family member in black approached silver car around Morning 9am in the driveway.",
      "tags": ["departure", "family_member", "vehicle", "morning"]
    }
  ],
  "summary": "First observation of a family member departure event with vehicle interaction."
}

Example 2 (Factual Memory - same day, NOT a pattern):
Current Event:
[Morning 09:05 | General Identity | Normal Activity] A person walks to a vehicle in the parking area

Historical Similar Events:
[2024-12-24] [Factual Memory] A man dressed in black walks toward a silver car around Morning 9am.

Output:
{
  "memory list": [
    {
      "key": "Morning departure",
      "memory_type": "UserMemory",
      "value": "[Factual Memory] Family member walked to vehicle around Morning 9am in parking area.",
      "tags": ["departure", "family_member", "vehicle", "morning"]
    }
  ],
  "summary": "Second departure event today, but pattern requires events across multiple days."
}

Example 3 (Pattern Memory - ≥3 events on DIFFERENT days):
Current Event:
[Morning 09:10 | Staff | Package Delivery] A deliveryman in blue holding letters walked from a house path

Historical Similar Events:
[2024-12-24 09:37] [Factual Memory] A courier walks across the driveway sorting letters around Morning 9:30am.
[2024-12-25 09:29] [Factual Memory] A courier with letters walks from the path around Morning 9:30am.
[2024-12-26 11:03] [Factual Memory] A courier with letters walks from house path around Morning 11am.

Output:
{
  "memory list": [
    {
      "key": "Delivery time pattern",
      "memory_type": "LongTermMemory",
      "value": "[Pattern Memory] Deliveryman in blue with letters walked from house path around Morning 9am (delivery pattern observed across 4 different days: 12-24, 12-25, 12-26, and today, typically between 9-11am).",
      "tags": ["delivery", "staff", "morning", "pattern"]
    }
  ],
  "summary": "Delivery time pattern established - events occurred on 4 different days."
}

Example 4 (Pattern + Inference with CONCISE descriptions - ≥4 events):
Current Event:
[Morning 08:55 | General Identity | Normal Activity] A man in dark clothing walks toward a black car, a yellow dog follows him

Historical Similar Events:
[2024-12-23 09:00] [Factual Memory] Man in dark clothing approached black car around Morning 9am, yellow dog present.
[2024-12-24 09:05] [Factual Memory] Man approached black car around Morning 9am, yellow dog nearby.
[2024-12-25 08:52] [Factual Memory] Man walked to black car around Morning 9am, with yellow dog.
[2024-12-26 08:45] [Factual Memory] Man in dark jacket approached black car around Morning 8:45am, dog followed.

Output:
{
  "memory list": [
    {
      "key": "Morning departure",
      "memory_type": "UserMemory",
      "value": "[Factual Memory] Man in dark clothing walked toward black car around Morning 9am, yellow dog followed.",
      "tags": ["departure", "family_member", "vehicle", "pet", "morning"]
    },
    {
      "key": "Commute pattern",
      "memory_type": "LongTermMemory",
      "value": "[Pattern Memory] Family member departs 8:45-9:15am on weekdays by black car",
      "tags": ["commute", "departure", "weekday", "black_car"]
    },
    {
      "key": "Pet interaction",
      "memory_type": "LongTermMemory",
      "value": "[Pattern Memory] Yellow dog appears during morning departures with this family member",
      "tags": ["pet", "dog", "interaction", "morning"]
    },
    {
      "key": "Member characteristic",
      "memory_type": "LongTermMemory",
      "value": "[Pattern Memory] Man often wears dark clothing (black jacket/shirt observed)",
      "tags": ["appearance", "clothing", "man"]
    },
    {
      "key": "Person identity",
      "memory_type": "LongTermMemory",
      "value": "[Inference Memory] Man is likely primary family member (regular black car access, morning routine, pet interaction)",
      "tags": ["identity", "family_member", "inference"]
    }
  ],
  "summary": "Established weekday morning departure pattern with black car and dog interaction."
}

Now analyze the following:

Current Event:
${current_event}

Historical Similar Events:
${historical_events}

Your Output:"""

SECURITY_EVENT_PATTERN_PROMPT_ZH = """您是智能家居安防模式分析专家。
您的任务是从监控事件中提取**简洁的家庭习惯规律**，用于安全预警和家庭关怀。

给定：
1. **当前事件**：刚刚发生的新监控事件（格式：[时段 HH:MM | 角色类型 | 场景] 事件描述）
2. **历史相似事件**：通过语义检索获得的过去事件记录

**关键 - 如何使用历史事件**：
1. **历史事件仅供参考**：
   - 用于判断是否形成规律（≥3 次相似事件）
   - 用于支持推理（≥4 次事件才能推测）
   - 用于确定重要程度和频次

2. **新记忆必须基于当前事件生成**：
   - 从当前事件中提取信息
   - 不要复制或转述历史事件的内容
   - 历史事件只帮你判断："这是规律吗？"或"可以推理吗？"

3. **历史事件的相关性**：
   - 部分历史事件可能不相关 - 请仔细评估
   - 忽略无关记忆
   - 只用相关的来辅助判断

4. **避免重复的规律/推理记忆**：
   - 检查历史记忆中是否已包含类似的 [规律记忆] 或 [推理记忆]
   - 如果某个规律/推理已在历史中存在，不要再次生成
   - 只生成尚未被记录的新规律/推理
   - 示例：如果历史已有"[规律记忆] 男性在夜间频繁与空地互动"，不要再输出类似规律

5. **关键 - 规律必须跨越多天**：
   - **只有在不同日期发生的事件才能形成规律**
   - 同一天内的多次事件不构成规律（应使用 [实时记忆]）
   - 检查历史事件中的日期前缀 [YYYY-MM-DD]
   - 示例：
     * ✅ 规律：事件发生在 2024-12-24、2024-12-25、2024-12-26（3个不同的天）
     * ❌ 非规律：3个事件都在 2024-12-24（同一天，频次高但不是规律）
   - 时间规律必须显示跨天重复，而不仅仅是一天内的高频次

**示例**：
- 当前："一名穿黑色衣服的男士在早 08:59 走向银色汽车"
- 历史：3 个类似的早 09:00 出门事件
- ✅ 正确："[规律记忆] 家庭成员在早 08:59 驾车离开（该规律观察到4次）"
  → 基于当前事件，用历史确认这是规律
- ❌ 错误："[规律记忆] 家庭成员通常在早 09:00 左右出门"
  → 这描述的是历史事件，不是当前事件

您的目标是提取**简短、清晰的规律**，重点关注以下维度：
- **通勤规律**：出门/回家时间、日常作息
- **宠物信息**：类型、颜色、行为、互动
- **车辆信息**：类型、颜色、使用规律
- **家庭成员**：角色（男性/女性/儿童）、特征（服装、配饰）
- **重复性活动**：搬运物品、包裹处理等
- **交互模式**：人与车辆、人与宠物的关系

输出示例：
- ✅ "[实时记忆] 快递员在 2024-12-24 早 09:10 送件"
- ✅ "[规律记忆] 家庭成员工作日总是在早 09:00 左右出门（观察到5次）"
- ✅ "[推理记忆] 此人可能是家庭主要成员，基于对车辆的规律使用"

核心要求：
1. **始终先生成事实记忆**：
   - **必须**：每次提取必须至少包含一条当前事件的 [实时记忆]
   - 这是基准 - 总结当前事件发生了什么
   - 提取：谁、何时、做什么、在哪里（1句话）
   - 即使能找到规律或做推理，也不要跳过这一步

2. **记忆类型标注**：
   - **[实时记忆]**：当前事件的直接观察，100% 确定
     * 必须简洁总结关键信息
     * 不要原样复制完整事件描述
     * 这是每次提取的必需项

   - **[规律记忆]**：清晰的重复模式，仅在以下情况使用：
     * 有 ≥3 次支持事件（2次不够！）
     * 模式一致且清晰
     * 高置信度（≥0.85）
     * 如果只有1-2次事件，使用 [实时记忆]

   - **[推理记忆]**：基于模式的推测/推断，仅在以下情况使用：
     * 有来自 ≥4 个事件的强证据
     * 推理合乎逻辑且高度可能（置信度 ≥0.75）
     * 否则，应存储为 [实时记忆]

3. **规律记忆重点**（当有 ≥3 次相似事件在不同天时）：
   提取以下关键维度的规律，使用简洁描述：
   - **通勤规律**："家庭成员工作日早8:45-9:15出门驾驶黑色汽车"
   - **车辆使用**："男性早9点左右使用黑色车，女性晚6点左右使用灰色车"
   - **宠物出现**："黄狗在早9点左右出门时陪伴男性成员"
   - **重复性活动**："家庭成员经常在早9-10点和晚6-7点在住宅和车辆间搬运物品/袋子"
   - **人-车/宠物交互**："男性在晚11点-午夜与空地车辆互动"、"狗在早9点和晚6点出现在门口"
   
   格式：保持简短直接，尽可能包含具体时间范围（如"早9-10点"、"晚11点-午夜"）

4. **推理记忆重点**（当有 ≥4 次支持事件且高置信度时）：
   进行安防相关推理，使用简洁描述：
   - **人物身份**："男性可能是家庭主要成员（规律使用黑色车、宠物互动）"
   - **成员特征**："男性常戴眼镜/帽子、穿深色衣物"、"女性常戴眼镜、带小孩"
   - **正常活动时段**："家庭通常在晚11点-早8点不活动" 或 "家庭活动时间为早6点-晚10点"
   - **访客规律**："快递员通常在工作日早9-11点到访"
   
   格式：保持简短结构化，直接陈述结论（每条推理最多1句话）

6. **防止幻觉规则**：
   - 当不确定时，使用 [实时记忆] 而不是 [推理记忆]
   - 没有充分支持事件时，不要做推理
   - 宁可保守也不要生成虚假信息
   - 2次事件不足以形成规律 - 使用 [实时记忆]

7. **简洁至上 - 规律和推理记忆必须极简**：
   - 实时记忆：可以用1-2句话描述发生了什么
   - 规律记忆：必须简短（如"家庭成员工作日早8:45-9:15出门驾驶黑色汽车"）
   - 推理记忆：必须简短（如"男性可能是家庭主要成员（规律使用黑色车、宠物互动）"）
   - 不要长篇解释，不要写"已在5天观察到"等，直接陈述规律/推理
8. **时间描述 - 使用模糊时间**：
   - ❌ 不要使用精确分钟："08:59"、"09:10"、"23:45"
   - ✅ 使用小时或约数："早上9点左右"、"早上9点半左右"、"早上9-10点之间"
   - ✅ 使用时间范围："早 9-10点"、"晚 8-9点"、"夜间11点左右"
   - 示例：
     * 好的："早上9点左右"、"早 9点半左右"、"早 9-10点之间"
     * 不好："早 09:05"、"晚 20:46"
9. **角色清晰**：明确是谁（家庭成员/快递员/访客等）
10. **面向应用**：提取的规律要能用于安全预警和异常检测
11. **【关键】语言一致性**：
   - 如果输入事件是英文，输出必须使用英文
   - 如果输入事件是中文，输出必须使用中文
   - 不要混合语言或翻译输入语言

返回有效的JSON对象：

{
  "memory list": [
    {
      "key": <字符串，简洁的记忆标题>,
      "memory_type": <字符串，"LongTermMemory"或"UserMemory">,
      "value": <字符串，1-2句话描述，必须包含时间+角色+行为，开头标注[实时记忆]/[规律记忆]/[推理记忆]>,
      "tags": <关键词列表，如 ["出门", "家庭成员", "车辆"]>
    },
    ...
  ],
  "summary": <简短总结段落，使用与输入相同的语言>
}

**重要提示**：
- 记忆类型标签（[实时记忆]/[规律记忆]/[推理记忆]）应放在 `value` 字段的开头
- 使用 tags 捕获关键主题：角色、动作、物品、时间段等
- 保持每条记忆简洁（1-2句话）

示例1：实时记忆（首次事件）
当前事件：
[早 08:59 | 家庭成员 | 正常活动] 一名穿黑色衣服的男士走向停在车道上的银色汽车准备驾驶

历史相似事件：
（无 - 首次事件）

输出：
{
  "memory list": [
    {
      "key": "早晨出门",
      "memory_type": "UserMemory",
      "value": "[实时记忆] 穿黑色衣服的家庭成员在早上9点左右走向车道的银色汽车。",
      "tags": ["出门", "家庭成员", "车辆", "早晨"]
    }
  ],
  "summary": "首次观察到家庭成员早晨驾车出门事件。"
}

示例2：实时记忆（同一天，非规律）
当前事件：
[早 09:05 | 家庭成员 | 正常活动] 一名身穿深色衣服的人走向停车区的车辆

历史相似事件：
[2024-12-24] [实时记忆] 穿黑色衣服的家庭成员在早上9点左右走向车道的银色汽车。

输出：
{
  "memory list": [
    {
      "key": "早晨出门",
      "memory_type": "UserMemory",
      "value": "[实时记忆] 穿深色衣服的家庭成员在早上9点左右走向停车区的车辆（今日第2次，同一天不构成规律）。",
      "tags": ["出门", "家庭成员", "车辆", "早晨"]
    }
  ],
  "summary": "今日第二次出门事件，规律需要跨越多天才能确立。"
}

示例3：规律记忆（≥3次事件在不同天）
当前事件：
[早 09:10 | 快递员 | 正常活动] 一名穿蓝色制服的快递员手持信件从房屋小路走来

历史相似事件：
[2024-12-24 09:37] [实时记忆] 快递员在车道上边走边整理信件，早上9点半左右。
[2024-12-25 09:29] [实时记忆] 携带信件的快递员从小路走来并穿过草坪，早上9点半左右。
[2024-12-26 11:03] [实时记忆] 携带信件的快递员从房屋小路走来然后离开，早上11点左右。

输出：
{
  "memory list": [
    {
      "key": "快递送件时段",
      "memory_type": "LongTermMemory",
      "value": "[规律记忆] 穿蓝色制服的快递员在早上9点左右手持信件从房屋小路走来（快递送件规律已在4个不同日期观察：12-24、12-25、12-26及今日，通常在早上9-11点之间）。",
      "tags": ["快递员", "送件", "早晨", "规律"]
    }
  ],
  "summary": "快递送件规律已确立，事件发生在4个不同日期。"
}

示例4：简洁描述的规律+推理（≥4次事件跨多天）
当前事件：
[早 08:55 | 家庭成员 | 正常活动] 穿深色衣服的男士走向黑色汽车，一只黄色的狗跟着他

历史相似事件：
[2024-12-23 09:00] [实时记忆] 穿深色衣服的男士走向黑色汽车，早上9点左右，黄色的狗在场。
[2024-12-24 09:05] [实时记忆] 男士走向黑色汽车，早上9点左右，黄色的狗在旁边。
[2024-12-25 08:52] [实时记忆] 男士走向黑色汽车，早上9点左右，和黄色的狗一起。
[2024-12-26 08:45] [实时记忆] 穿深色外套的男士走向黑色汽车，早上8点45左右，狗跟着他。

输出：
{
  "memory list": [
    {
      "key": "早晨出门",
      "memory_type": "UserMemory",
      "value": "[实时记忆] 穿深色衣服的男士在早上9点左右走向黑色汽车，黄色的狗跟着他。",
      "tags": ["出门", "家庭成员", "车辆", "宠物", "早晨"]
    },
    {
      "key": "通勤规律",
      "memory_type": "LongTermMemory",
      "value": "[规律记忆] 家庭成员工作日早8:45-9:15出门驾驶黑色汽车",
      "tags": ["通勤", "出门", "工作日", "黑色汽车"]
    },
    {
      "key": "宠物互动",
      "memory_type": "LongTermMemory",
      "value": "[规律记忆] 黄狗在早晨出门时陪伴这位家庭成员",
      "tags": ["宠物", "狗", "交互", "早晨"]
    },
    {
      "key": "成员特征",
      "memory_type": "LongTermMemory",
      "value": "[规律记忆] 男性常穿深色衣物（观察到黑色外套/衬衫）",
      "tags": ["外观", "服装", "男性"]
    },
    {
      "key": "人物身份",
      "memory_type": "LongTermMemory",
      "value": "[推理记忆] 男性可能是家庭主要成员（规律使用黑色车、早晨固定作息、宠物互动）",
      "tags": ["身份", "家庭成员", "推理"]
    }
  ],
  "summary": "确立了工作日早晨黑色汽车出门规律及与狗的互动。"
}

现在请分析以下内容：

当前事件：
${current_event}

历史相似事件：
${historical_events}

您的输出："""
