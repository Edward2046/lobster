# Lobster 记忆系统使用指南

## 概述

Lobster 现在具备三层记忆能力：

1. **短期记忆**：自动注入最近 5 条对话到每次请求，让 Agent 能理解上下文
2. **长期记忆**：完整对话历史存储在 SQLite，Agent 可通过工具主动检索
3. **知识库**：用户明确要求记住的事实/偏好，持久化存储

## 自动功能

### 短期记忆（无需手动操作）
- 每次对话时，系统自动注入最近 5 条对话作为上下文
- Agent 能理解"刚才说的"、"上次提到的"等指代
- 示例：
  ```
  用户: 北京天气怎么样？
  Agent: [查询并回答]
  用户: 那东京呢？
  Agent: [理解"那"指的是天气，查询东京天气]
  ```

### 对话历史自动保存
- 所有对话自动保存到 `memory.db`
- 包含时间戳、角色（user/agent）、内容

## Agent 可用的记忆工具

### 1. search_memory(keyword, limit=10)
搜索历史对话中包含关键词的内容

**使用场景**：
- "我之前问过什么关于财经的问题？"
- "上周我们聊了什么？"

**示例**：
```python
search_memory("天气", limit=5)
# 返回包含"天气"的最近 5 条对话
```

### 2. remember_fact(key, value)
保存重要事实或用户偏好到长期记忆

**使用场景**：
- 用户说："记住我喜欢日本料理"
- 用户说："以后用英文回答我"

**示例**：
```python
remember_fact("用户偏好_语言", "英文")
remember_fact("用户喜好_美食", "日本料理、川菜")
```

### 3. recall_fact(key)
检索之前保存的事实

**示例**：
```python
recall_fact("用户偏好_语言")
# 返回: "用户偏好_语言: 英文"
```

### 4. list_all_facts(limit=20)
列出所有保存的事实

**使用场景**：
- "你记住了我的哪些偏好？"
- "给我看看你的长期记忆"

### 5. forget_fact(key)
删除指定的事实

**使用场景**：
- "忘掉我之前说的语言偏好"

## 使用示例

### 场景 1：上下文理解
```
用户: 帮我查一下特斯拉的财报时间
Agent: [调用 get_earnings_calendar 查询 TSLA]

用户: 苹果呢？
Agent: [理解"呢"指的是财报时间，查询 AAPL]
```

### 场景 2：主动检索历史
```
用户: 我上次问过什么股票的财报？
Agent: [调用 search_memory("财报") 查找历史]
```

### 场景 3：记住用户偏好
```
用户: 记住我每天早上 9 点想看财经简报
Agent: [调用 remember_fact("用户习惯_财经简报", "每天早上9点")]

（几天后）
用户: 我之前设置的财经简报时间是什么？
Agent: [调用 recall_fact("用户习惯_财经简报")]
```

## 数据存储

- **位置**：`/Users/libing/workplaza/lobster/memory.db`
- **格式**：SQLite 数据库
- **表结构**：
  - `conversations`：对话历史（id, session_id, role, content, timestamp）
  - `knowledge`：知识库（id, key, value, created_at, updated_at）

## 技术细节

### 短期记忆注入机制
```python
# 在 agent.py 和 server.py 中
context = memory.format_recent_context(limit=5)
question_with_context = f"{context}\n\n当前问题：{question}"
answer = agent.run(question_with_context)
```

### 线程安全
- SQLite 默认支持多线程读写
- 每次操作都是独立的连接，避免并发冲突

### 性能考虑
- 短期记忆只注入最近 5 条，避免 token 浪费
- 历史搜索有 limit 参数，防止返回过多结果
- 数据库有索引优化查询速度

## 未来扩展方向

1. **会话隔离**：支持 session_id，区分不同对话线程
2. **向量检索**：使用 embedding 做语义搜索，而不只是关键词匹配
3. **自动摘要**：定期将长对话压缩成摘要，节省上下文空间
4. **重要性评分**：自动识别重要对话，优先注入到上下文
5. **定期清理**：自动归档或删除过期对话
