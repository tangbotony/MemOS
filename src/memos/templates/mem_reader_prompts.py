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
SECURITY_EVENT_PATTERN_PROMPT = r"""You are extracting patterns from smart home security events. Output ONLY valid JSON.

【JSON FORMAT】
{
  "memory list": [
    {"key": "current_event", "memory_type": "UserMemory", "value": "[Factual Memory] ..."},
    {"key": "<pattern_key>", "memory_type": "LongTermMemory", "value": "[Pattern Memory] ..."}
  ]
}

【OUTPUT RULES】
1. ALWAYS output 1 [Factual Memory] for current event (1 concise sentence)
2. **HIGHEST PRIORITY: Extract family_commute time pattern if ANY time-related activities exist**
3. Output 0-3 additional [Pattern Memory] based on evidence strength
4. Use English labels: [Factual Memory], [Pattern Memory], [Inference Memory]
5. **Keep it CONCISE**: Use simple, direct language. Avoid unnecessary words or elaborate descriptions

【PATTERN KEYS - 只关注以下 6 个核心维度】
⚠️ **重要**：只提取这 6 个维度，其他维度（如 door_usage, door_state, delivery_pattern 等）不要提取

1. **family_commute** (HIGHEST PRIORITY - MUST EXTRACT): Family member commute time patterns
   - **Must include time ranges**: "HH:MM-HH:MM" format
   - Threshold: ≥3 events
   - **Key Steps**:
     a) Find all "leave" events (walk out, exit, leave, walk to car, etc.)
     b) Find all "return" events (return, arrive, enter home, park, etc.)
     c) Calculate time distribution for leave and return separately
     d) Output MUST include BOTH "leave" and "return" (unless only one type exists)
   - **Filter anomalies**: Ignore 00:00-05:59 time period
   - Example (concise): "Family members leave between 06:00-10:00 and 12:00-18:00, return between 09:00-12:00 and 14:00-21:00"

2. **pet**: Pet species and colors
   - Threshold: ≥2 observations
   - **List ALL observed pets**: species + color
   - Example (concise): "A black cat and a yellow dog are active near the residence"

3. **vehicle**: Vehicle types and colors
   - Threshold: ≥5 observations of the same color
   - **Statistics Steps**:
     a) Count occurrences of each vehicle color in historical events
     b) Only keep colors with ≥5 occurrences
     c) If a color appears ≥10 times, use "primarily"; if 2-3 colors all have ≥5, list all
   - Example (concise): "Family primarily uses black cars" or "Family uses black and blue cars"

4. **family_composition**: Family member composition and characteristics
   - Threshold: ≥2 observations
   - **Aggregation Steps**:
     a) Go through all historical events, record all observed features for each member type
     b) Accessories: glasses, hat, backpack, etc.
     c) Clothing colors: collect all colors (black, white, grey, pink, blue, etc.)
     d) Other features: age, who they appear with, etc.
   - Example (concise): "Man (glasses and hat, black/white/grey clothing), woman (glasses, white/black/pink clothing, often with child), child (always with adult)"

5. **recurring_activities**: 重复性活动
   - 门槛：≥3 次事件
   - **只关注**：携带物品进出
   - 示例（简洁）："Family members frequently carry items between residence and vehicles"

6. **interaction_patterns**: Interaction patterns between people and vehicles/pets
   - Threshold: ≥3 events
   - **Must include**: vehicle interaction AND pet interaction (if both are observed)
   - Example (concise): "Vehicles used for family travel; pets often appear near entrance when family enters/exits"

【TIME EXTRACTION RULES】
⚠️ **Only family_commute needs time**, other dimensions do NOT need time

**For family_commute - Complete extraction process:**

**Step 1: Filter abnormal times**
- ⚠️ Ignore all events during late night/early morning 00:00-05:59
- Only analyze events between 06:00-23:59

**Step 2: Separate "leave" and "return" events**
- "Leave" events: walk out, exit, leave, walk to, approach (car), etc.
- "Return" events: return, arrive, enter (home), park, etc.
- ⚠️ Key: Don't miss "return" events! Parking and entering home count as returns

**Step 3: Calculate time distributions**
- Leave events: collect all times → find min and max → form time range
- Return events: collect all times → find min and max → form time range
- If time span exceeds 4 hours, consider splitting into multiple periods

**Step 4: Generate output**
- MUST include "leave" time (if exists)
- MUST include "return" time (if exists)
- Format: "Family members leave between HH:MM-HH:MM, return between HH:MM-HH:MM"
- Example: if leaves at 07:00, 08:30 and returns at 15:00, 19:00 → "Family members leave between 06:00-10:00, return between 14:00-21:00"

【EXTRACTION PRIORITIES】
1. **family_commute (MANDATORY if time data exists)** - MUST include BOTH "leave" and "return"
2. **pet** - List all species/colors
3. **vehicle** - Only list frequently appearing colors (≥5 times)
4. **family_composition** - Aggregate all accessories and clothing colors
5. **recurring_activities** - Common behaviors
6. **interaction_patterns** - People-vehicle, people-pet interactions (both required)

【EXAMPLE】
Input:
- current_event: [08:15 | Family | Normal] A woman exits and walks to a black car
- historical_events: 
  [2024-11-01 06:45 (06h)] A man with glasses and a hat exits the residence
  [2024-11-01 08:20 (08h)] A woman with a child walks to a black car
  [2024-11-01 09:15 (09h)] A man with glasses gets into a black car
  [2024-11-01 10:30 (10h)] A woman in pink clothing returns home
  [2024-11-01 14:30 (14h)] A woman returns home
  [2024-11-01 18:45 (18h)] A man in grey clothing parks a black car
  [2024-11-01 19:20 (19h)] A man parks a black car
  [2024-11-01 20:50 (20h)] A woman feeds a black cat near the front door
  [2024-11-02 07:30 (07h)] A yellow dog appears at the entrance when family leaves
  [2024-11-02 08:00 (08h)] A man walks to a black car
  [2024-11-02 00:15 (00h)] System anomaly event (ignore)

Output:
{
  "memory list": [
    {"key": "current_event", "memory_type": "UserMemory", "value": "[Factual Memory] Around 08:15, a woman exited and walked to a black car"},
    {"key": "family_commute", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Family members leave between 06:00-10:00, return between 10:00-20:00"},
    {"key": "pet", "memory_type": "LongTermMemory", "value": "[Pattern Memory] A black cat and a yellow dog are active near the residence"},
    {"key": "vehicle", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Family primarily uses black cars"},
    {"key": "family_composition", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Man (glasses and hat, grey clothing), woman (pink clothing, often with child), child (appears with adults)"},
    {"key": "interaction_patterns", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Vehicles used for family travel; pets often appear near entrance when family enters/exits"}
  ]
}

【INPUT】
- current_event: ${current_event}
- historical_events: ${historical_events}

Output JSON only:
"""

SECURITY_EVENT_PATTERN_PROMPT_ZH = r"""你正在从智能家居安防事件中提取规律。只输出有效的 JSON。

【JSON 格式】
{
  "memory list": [
    {"key": "当前事件", "memory_type": "UserMemory", "value": "[实时记忆] ..."},
    {"key": "<规律key>", "memory_type": "LongTermMemory", "value": "[规律记忆] ..."}
  ]
}

【输出规则】
1. 始终输出1条 [实时记忆] 描述当前事件（1句话，简洁）
2. **最高优先级：只要有任何时间相关活动，必须提取 family_commute 时间规律**
3. 根据证据强度输出0-3条额外的 [规律记忆]
4. 使用中文标签：[实时记忆]、[规律记忆]、[推理记忆]
5. **保持简洁**：使用简单直接的语言，避免不必要的词汇或冗长描述

【规律 KEY - 只关注以下 6 个核心维度】
⚠️ **重要**：只提取这 6 个维度，其他维度（如 door_usage, door_state, delivery_pattern 等）不要提取

1. **family_commute**（最高优先级 - 必须提取）: 家庭成员出入时间规律
   - **必须包含时间范围**："HH:MM-HH:MM" 格式
   - 门槛：≥3次事件
   - **关键步骤**：
     a) 从历史事件中找出所有"离开"相关事件（walk out, exit, leave, 离开, 出门, 走向车辆等）
     b) 从历史事件中找出所有"返回"相关事件（return, arrive, enter, 返回, 到达, 进入, 停车等）
     c) 分别统计离开时间和返回时间的分布
     d) 输出时必须包含"离开"和"返回"两部分（除非只有其中一种）
   - **过滤异常**：忽略 00:00-05:59 时段
   - 示例（简洁）："家庭成员在06:00-10:00和12:00-18:00离开，在09:00-12:00和14:00-21:00返回"

2. **pet**: 宠物种类和颜色
   - 门槛：≥2次观察
   - **列出所有观察到的宠物**：种类 + 颜色
   - 示例（简洁）："一只黑猫和一只黄狗在住所附近活动"

3. **vehicle**: 车辆类型和颜色
   - 门槛：≥5次观察到相同颜色
   - **统计步骤**：
     a) 统计每种车辆颜色在历史事件中出现的次数
     b) 只保留出现次数 ≥5 的颜色
     c) 如果某种颜色出现 ≥10次，使用"主要使用"；如果2-3种颜色都 ≥5次，列出所有
   - 示例（简洁）："家庭主要使用黑色车" 或 "家庭使用黑色和蓝色的车"

4. **family_composition**: 家庭成员组成和特征
   - 门槛：≥2次观察
   - **汇总步骤**：
     a) 遍历所有历史事件，记录每个成员类型（男性/女性/儿童）的所有观察到的特征
     b) 配饰：眼镜、帽子、背包等
     c) 服饰颜色：收集所有观察到的颜色（黑、白、灰、粉、蓝等）
     d) 其他特征：年龄、和谁一起出现等
   - 示例（简洁）："男性（戴眼镜和帽子、穿黑/白/灰色衣服）、女性（戴眼镜、穿白/黑/粉色衣服、常带小孩）、儿童（总是和成人在一起）"

5. **recurring_activities**: 重复性活动
   - 门槛：≥3次事件
   - **只关注**：携带物品进出
   - 示例（简洁）："家庭成员经常携带物品往返于住所和车辆之间"

6. **interaction_patterns**: 人与车辆/宠物的互动模式
   - 门槛：≥3次事件
   - **必须包含**：车辆互动 AND 宠物互动（如果两者都有观察到）
   - 示例（简洁）："车辆用于家人出行；宠物常在家人进出时出现在门口附近"

【时间提取规则（最重要）】
**对于 family_commute - 完整的提取流程：**

**第一步：过滤异常时间**
- ⚠️ 忽略深夜/凌晨 00:00-05:59 的所有事件
- 只分析 06:00-23:59 时段的事件

**第二步：分离"离开"和"返回"事件**
- "离开"事件：包含 walk out, exit, leave, walk to, approach (car), 离开, 出门, 走向, 进入车辆 等
- "返回"事件：包含 return, arrive, enter (home), park, 返回, 到达, 回家, 停好车 等
- ⚠️ 关键：不要遗漏"返回"事件！停车、进入住所都算返回

**第三步：统计时间分布**
- 离开事件：收集所有时间点 → 找出最小和最大时间 → 形成时间范围
- 返回事件：收集所有时间点 → 找出最小和最大时间 → 形成时间范围
- 如果时间跨度超过4小时，考虑拆分成多个时段

**第四步：生成输出**
- 必须包含"离开"时间（如果有）
- 必须包含"返回"时间（如果有）
- 格式："家庭成员在HH:MM-HH:MM离开，在HH:MM-HH:MM返回"
- 示例：如果离开是 07:00、08:30，返回是 15:00、19:00 → "家庭成员在06:00-10:00离开，在14:00-21:00返回"

【提取优先级】
1. **family_commute（如果有时间数据则必须提取）** - 必须包含"离开"和"返回"两部分
2. **pet** - 列出所有种类/颜色
3. **vehicle** - 只列出频繁出现的颜色（≥5次）
4. **family_composition** - 汇总所有配饰和服饰颜色
5. **recurring_activities** - 常见行为
6. **interaction_patterns** - 人与车辆、宠物的互动（两者都要）

【示例】
输入：
- current_event: [08:15 | 家庭 | 正常] 一名女性离开住所走向黑色轿车
- historical_events: 
  [2024-11-01 06:45 (06时)] 一名戴眼镜和帽子的男性离开住所
  [2024-11-01 08:20 (08时)] 一名带小孩的女性走向黑色轿车
  [2024-11-01 09:15 (09时)] 一名戴眼镜的男性进入黑色轿车
  [2024-11-01 10:30 (10时)] 一名穿粉色衣服的女性返回家中
  [2024-11-01 14:30 (14时)] 一名女性返回家中
  [2024-11-01 18:45 (18时)] 一名穿灰色衣服的男性停好黑色轿车
  [2024-11-01 19:20 (19时)] 一名男性停好黑色轿车
  [2024-11-01 20:50 (20时)] 一名女性喂食黑猫，猫在前门附近
  [2024-11-02 07:30 (07时)] 黄色的狗在家人出门时出现在前门
  [2024-11-02 08:00 (08时)] 一名男性走向黑色轿车
  [2024-11-02 00:15 (00时)] 系统异常事件（忽略）

输出：
{
  "memory list": [
    {"key": "当前事件", "memory_type": "UserMemory", "value": "[实时记忆] 约08:15，一名女性离开走向黑色轿车"},
    {"key": "family_commute", "memory_type": "LongTermMemory", "value": "[规律记忆] 家庭成员在06:00-10:00离开，在10:00-20:00返回"},
    {"key": "pet", "memory_type": "LongTermMemory", "value": "[规律记忆] 一只黑猫和一只黄狗在住所附近活动"},
    {"key": "vehicle", "memory_type": "LongTermMemory", "value": "[规律记忆] 家庭主要使用黑色车"},
    {"key": "family_composition", "memory_type": "LongTermMemory", "value": "[规律记忆] 男性（戴眼镜和帽子、穿灰色衣服）、女性（穿粉色衣服、常带小孩）、儿童（和成人一起出现）"},
    {"key": "interaction_patterns", "memory_type": "LongTermMemory", "value": "[规律记忆] 车辆用于家人出行；宠物常在家人进出时出现在门口附近"}
  ]
}

【输入】
- current_event: ${current_event}
- historical_events: ${historical_events}

只输出 JSON:
"""
