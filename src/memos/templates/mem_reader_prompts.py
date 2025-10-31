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
SECURITY_EVENT_PATTERN_PROMPT = r"""
Output ONLY the following **EXACT JSON structure**; array elements contain ONLY key, memory_type, value fields; value prefix MUST be English: "[Factual Memory]", "[Pattern Memory]", "[Inference Memory]"; **FORBID** Chinese labels, "约HH:MM", "(XX时)", "HH:MM" placeholders.

{
  "memory list": [
    {"key": "<string>", "memory_type": "UserMemory", "value": "[Factual Memory] ..."},
    {"key": "<string>", "memory_type": "LongTermMemory", "value": "[Pattern Memory] ..."},
    {"key": "<string>", "memory_type": "LongTermMemory", "value": "[Pattern Memory] ..."},
    {"key": "<string>", "memory_type": "LongTermMemory", "value": "[Inference Memory] ..."}
  ]
}

【INPUT】
- current_event: Single event, [HH:MM | Role | Scene] + description
- historical_events: Multiple lines "[YYYY-MM-DD HH:MM (XXh)] + description"

【OUTPUT COUNT (moderate control)】
- MUST output EXACTLY 1 [Factual Memory] (UserMemory), based on current_event, one sentence; time use "around HH:MM" (if minute unknown, "around HH o'clock"); if unknown, omit time.
- [Pattern Memory] (LongTermMemory) **2-5 items**: Extract patterns from different dimensions of historical events; output fewer if insufficient evidence.
- [Inference Memory] (LongTermMemory) **0-2 items**: Only output when sufficient evidence and reasonable inference.
- Total count **1-8 items** (1 factual + 2-5 patterns + 0-2 inferences), **don't pad if insufficient evidence**.

【ALLOWED KEYS (Extended)】
Must choose from following keys, each key at most once:
- family_commute: Family member entry/exit time patterns
- vehicle: Vehicle information (color, type, usage frequency)
- family_composition: Family structure (number, age groups, relationships)
- recurring_activities: Recurring activities (e.g., dog walking, package pickup, visitors)
- pet: Pet-related (species, activity patterns)
- interaction_patterns: People interaction patterns (who appears with whom)
- door_usage: Door usage habits (front/back/side door)
- door_state: Door state patterns (open/close periods)
- child_presence: Child-related activities
- delivery_pattern: Delivery/visitor patterns
- weather_correlation: Weather-related behavior changes
- visitor_frequency: Visitor frequency and types

【PERIOD-TYPE THRESHOLDS (moderately relaxed)】
Applies to: family_commute, door_usage, door_state, delivery_pattern
- Evidence: Same pattern **≥3 events, spans ≥2 days, from ≥2 different minute values**
- Aggregation: 60-120 minute windows → output 1-2 non-overlapping intervals (ascending, "HH:MM-HH:MM")
- Validity: Each segment **≥30 minutes**, start≠end; **strictly forbid** "00:00-00:00"/"09:00-09:00"
- Any not met → **don't output** this period-type pattern
- Example: If seeing 3 events "leave at 8:15 AM", "leave at 8:23 AM", "leave at 8:31 AM" spanning 2 days, output "[Pattern Memory] Family members typically leave home between 08:00-09:00 in the morning"

【ATTRIBUTE-TYPE THRESHOLDS (moderately relaxed)】
Applies to: vehicle, family_composition, recurring_activities, pet, interaction_patterns, child_presence, visitor_frequency
- Evidence: **≥3 events, spans ≥2 days**
- **FORBID** "HH:MM-HH:MM" in value
- Vehicle color/type: Must have **≥60% proportion**, **≥3 samples**, spans **≥2 days** to write color; otherwise only write type without color
- Example: If seeing 3 "silver SUV" appearances across 2 days, output "[Pattern Memory] Family owns a silver SUV that is frequently used"

【INFERENCE MEMORY (use cautiously)】
Only when **≥5 events, spans ≥3 days** and has clear logical chain; otherwise **don't** write [Inference Memory].
- Inference must be based on multiple confirmed pattern memories
- Inference content must be reasonable and verifiable
- Example: If seeing "leave at 8 AM" + "return at 6 PM" + "only on weekdays", can infer "[Inference Memory] Family members likely have fixed working hours, leaving early and returning late on weekdays"

【DEDUPLICATION & UPDATE】
- If history already has pattern for same key and current has no new evidence (no new time periods/attributes), **don't** output duplicate
- If current has significant convergence (more precise time periods) or expansion (new attributes), output updated version

【MULTI-DIMENSIONAL EXTRACTION PRINCIPLES】
Priority extraction dimensions (in order):
1. **Time patterns**: Entry/exit times, activity times (family_commute, door_usage)
2. **Physical features**: Vehicles, pets, people features (vehicle, pet, family_composition)
3. **Behavior patterns**: Recurring activities, interaction patterns (recurring_activities, interaction_patterns)
4. **Visitor patterns**: Delivery personnel, visitor frequency (delivery_pattern, visitor_frequency)
5. **Other patterns**: Weather correlation, door state, etc. (weather_correlation, door_state)

【PRE-GENERATION SELF-CHECK (any fails → don't output that item)】
- Any Chinese labels / "约HH:MM" / "(XXh)" / "HH:MM" placeholders present?
- Period-type: Is interval ≥30 minutes, start≠end, ≥2 different minute values, spans ≥2 days?
- Attribute-type: Mistakenly includes time period?
- Vehicle color: Meets 60% proportion + samples≥3 + spans≥2 days?
- Sufficient evidence? (period-type≥3 events, attribute-type≥3 events)
- Different keys not repeated? (each key at most once)

【OUTPUT EXAMPLE】
Assume input:
- current_event: [08:23 | Family Member | Normal Activity] A man opens the garage door and walks toward a silver SUV
- historical_events: 
  [2024-12-20 08:15 (08h)] A man walks toward a silver SUV and gets in
  [2024-12-21 08:31 (08h)] The same man drives away from the garage
  [2024-12-20 18:42 (18h)] Silver SUV parks back in garage
  [2024-12-21 18:35 (18h)] Man exits SUV and enters house
  [2024-12-20 09:15 (09h)] Delivery person delivers package to front door
  [2024-12-21 10:23 (10h)] Delivery person delivers package again

Expected output:
{
  "memory list": [
    {"key": "current_event", "memory_type": "UserMemory", "value": "[Factual Memory] Around 08:23, a man opened the garage door and walked toward a silver SUV"},
    {"key": "family_commute", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Family members typically leave home between 08:00-09:00 in the morning and return between 18:00-19:00 in the afternoon"},
    {"key": "vehicle", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Family owns a silver SUV that serves as the primary transportation"},
    {"key": "delivery_pattern", "memory_type": "LongTermMemory", "value": "[Pattern Memory] Delivery personnel typically deliver packages between 09:00-11:00 in the morning"}
  ]
}

【START NOW】
- current_event:
${current_event}

- historical_events:
${historical_events}
"""

SECURITY_EVENT_PATTERN_PROMPT_ZH = r"""
只输出下述**唯一 JSON 结构**；数组元素仅含 key、memory_type、value 三字段；value 前缀必须是中文："[实时记忆]"、"[规律记忆]"、"[推理记忆]"；**禁止**英文标签、"around HH:MM"、"(11h)"、"HH:MM"占位符。

{
  "memory list": [
    {"key": "<字符串>", "memory_type": "UserMemory", "value": "[实时记忆] ..."},
    {"key": "<字符串>", "memory_type": "LongTermMemory", "value": "[规律记忆] ..."},
    {"key": "<字符串>", "memory_type": "LongTermMemory", "value": "[规律记忆] ..."},
    {"key": "<字符串>", "memory_type": "LongTermMemory", "value": "[推理记忆] ..."}
  ]
}

【输入】
- current_event：单条，[HH:MM | 角色 | 场景] + 描述
- historical_events：多行 "[YYYY-MM-DD HH:MM (XX时)] + 描述"

【产出条数（适度控制）】
- 必须且**仅 1 条** [实时记忆]（UserMemory），基于 current_event，一句话；时间用"约HH:MM"（分钟未知可写"约HH点"）；未知就不写时间。
- [规律记忆]（LongTermMemory）**2-5 条**：从历史事件中提取不同维度的规律，每个维度一条；若证据不足则少产出。
- [推理记忆]（LongTermMemory）**0-2 条**：仅在有充分证据且推理合理时产出。
- 总条数 **1-8 条**（实时1条 + 规律2-5条 + 推理0-2条），**证据不足不凑数**。

【允许的 key（扩展版）】
必须从以下key中选择，每个key只产出一次：
- family_commute: 家庭成员出入时间规律
- vehicle: 车辆信息（颜色、类型、使用频率）
- family_composition: 家庭成员构成（人数、年龄段、关系）
- recurring_activities: 重复性活动（如遛狗、取快递、访客）
- pet: 宠物相关（种类、活动规律）
- interaction_patterns: 人员互动模式（谁与谁一起出现）
- door_usage: 门的使用习惯（前门/后门/侧门）
- door_state: 门的状态规律（开关时段）
- child_presence: 儿童相关活动
- delivery_pattern: 快递/访客规律
- weather_correlation: 天气相关行为变化
- visitor_frequency: 访客频率和类型

【时段型门槛（适度放宽）】
适用：family_commute、door_usage、door_state、delivery_pattern
- 证据：同一模式 **≥3 次事件、跨 ≥2 天、来自 ≥2 个不同分钟值**
- 聚合：60–120 分钟窗口 → 输出 1–2 个不重叠区间（升序，"HH:MM-HH:MM"）
- 合法性：每段 **≥30 分钟**、起止不同；**严禁** "00:00-00:00"/"09:00-09:00"
- 任一不满足 → **不产出**该时段型规律
- 示例：如果看到3次"早上8:15出门"、"早上8:23出门"、"早上8:31出门"，跨2天，可输出"[规律记忆] 家庭成员通常在早上08:00-09:00之间出门"

【属性型门槛（适度放宽）】
适用：vehicle, family_composition, recurring_activities, pet, interaction_patterns, child_presence, visitor_frequency
- 证据：**≥3 次事件、跨 ≥2 天**
- **禁止**在 value 中出现 "HH:MM-HH:MM"
- 车辆颜色/类型：占比 **≥60%**、样本 **≥3**、跨 **≥2 天**才写颜色；否则只写类型不写颜色
- 示例：如果看到3次"银色SUV"出现在2天内，可输出"[规律记忆] 家庭拥有一辆银色SUV，经常使用"

【推理记忆（谨慎使用）】
仅当 **≥5 次事件、跨 ≥3 天** 且有明确逻辑链时才写；否则**不要**写[推理记忆]。
- 推理必须基于多个已确认的规律记忆
- 推理内容必须合理且可验证
- 示例：如果看到"早上8点出门"+"晚上6点回家"+"工作日才有"，可推理"[推理记忆] 家庭成员可能有固定的工作时间，工作日早出晚归"

【去重与更新】
- 若历史已存在同 key 的规律且本次无新证据（无新时段/新属性），**不要**重复产出
- 若本次有显著收敛（时段更精确）或扩展（新属性），则产出更新版本

【多维度抽取原则】
优先抽取以下维度（按优先级）：
1. **时间规律**：出入时间、活动时间（family_commute, door_usage）
2. **物理特征**：车辆、宠物、人员特征（vehicle, pet, family_composition）
3. **行为模式**：重复活动、互动模式（recurring_activities, interaction_patterns）
4. **访客规律**：快递员、访客频率（delivery_pattern, visitor_frequency）
5. **其他规律**：天气关联、门状态等（weather_correlation, door_state）

【生成前自检（任一不通过→该条不产出）】
- 是否出现英文标签 / "around HH:MM" / "(XXh)" / "HH:MM"占位符？
- 时段型：区间是否≥30分钟、起止不同、≥2个不同分钟值且跨≥2天？
- 属性型：是否误带时间段？
- 车辆颜色：是否满足 60% 占比 + 样本≥3 + 跨≥2天？
- 证据是否充分？（时段型≥3次，属性型≥3次）
- 不同key是否重复？（每个key最多一条）

【输出示例】
假设输入：
- current_event: [08:23 | 家庭成员 | 正常活动] 一名男子打开车库门，走向银色SUV
- historical_events: 
  [2024-12-20 08:15 (08时)] 一名男子走向银色SUV并上车
  [2024-12-21 08:31 (08时)] 同一男子开车离开车库
  [2024-12-20 18:42 (18时)] 银色SUV停回车库
  [2024-12-21 18:35 (18时)] 男子从SUV下车进入房屋
  [2024-12-20 09:15 (09时)] 快递员送包裹到前门
  [2024-12-21 10:23 (10时)] 快递员再次送包裹

期望输出：
{
  "memory list": [
    {"key": "当前事件", "memory_type": "UserMemory", "value": "[实时记忆] 约08:23，一名男子打开车库门并走向银色SUV"},
    {"key": "family_commute", "memory_type": "LongTermMemory", "value": "[规律记忆] 家庭成员通常在早上08:00-09:00之间出门，下午18:00-19:00之间回家"},
    {"key": "vehicle", "memory_type": "LongTermMemory", "value": "[规律记忆] 家庭拥有一辆银色SUV，是主要出行工具"},
    {"key": "delivery_pattern", "memory_type": "LongTermMemory", "value": "[规律记忆] 快递员通常在上午09:00-11:00之间送货"}
  ]
}

【现在开始】
- current_event：
${current_event}

- historical_events：
${historical_events}
"""
