# -*- coding: utf-8 -*-
"""
本地配置文件（包含敏感信息，已被 .gitignore 忽略，请勿提交）

请在下方填入您的 API Key 后重启服务生效。
也可以在 Web 界面的"设置"中直接编辑配置源。
"""

import os


def _env_int(name, default, minimum=1, maximum=100):
    """Read a bounded integer environment setting without breaking startup."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _env_bool(name, default=False):
    """Read a boolean environment setting."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# ==================== OpenAI 兼容 API 配置（多配置源） ====================
OPENAI_CONFIG = [
    {
        "name": "OpenAI",
        "api_key": "",  # 填写您的 OpenAI API Key
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1"
    },
    {
        "name": "DeepSeek",
        "api_key": "",  # 填写您的 DeepSeek API Key
        "models": ["deepseek-chat", "deepseek-coder"],
        "base_url": "https://api.deepseek.com/v1"
    },
    {
        "name": "通义千问",
        "api_key": "sk-67a4cb1f90b34023a0340a7957fec3bd",
        "models": ["qwen3.8-max", "qwen3.7-plus", "qwen3.8-flash"],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    },
    {
        "name": "本地模型",
        "api_key": "local",
        "models": ["qwen2.5:latest"],
        "base_url": "http://localhost:11434/v1"
    },
    {
        "name": "openrouter",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "models": ["~openai/gpt-sol-latest", "~openai/gpt-terra-latest"],
        "base_url": "https://openrouter.ai/api/v1"
    }
]

# 默认使用的配置源（必须是 OPENAI_CONFIG 中的一个 name）
DEFAULT_CONFIG_NAME = "通义千问"

# ==================== ASR 选择 ====================
# 可选值：soniox、volcengine。实时录音默认使用 Soniox；文件识别失败
# 后会按 fallback_provider 回退。实时录音切换 provider 需重启后端。
ASR_CONFIG = {
    "provider": os.getenv("ASR_PROVIDER", "soniox").lower(),
    "fallback_provider": os.getenv("ASR_FALLBACK_PROVIDER", "volcengine").lower(),
}

# ==================== 聊天上下文配置 ====================
# 一轮 = 一条用户消息。默认只保留最近 15 轮用户问题，并限制历史内容
# 为 12000 token，避免把大量内容重复发送给模型；如需完整问答上下文，
# 可设置 CHAT_INCLUDE_ASSISTANT_HISTORY=1。
CHAT_CONTEXT_CONFIG = {
    "max_history_turns": _env_int("CHAT_MAX_HISTORY_TURNS", 15, 1, 100),
    # Serialized field name is retained for compatibility with saved sessions.
    "max_history_chars": _env_int("CHAT_MAX_HISTORY_TOKENS", _env_int("CHAT_MAX_HISTORY_CHARS", 12000, 1000, 200000), 1000, 200000),
    "include_assistant_history": _env_bool("CHAT_INCLUDE_ASSISTANT_HISTORY", False),
    "debug_context": _env_bool("CHAT_DEBUG_CONTEXT", True),
    "debug_context_full": _env_bool("CHAT_DEBUG_CONTEXT_FULL", False),
    "debug_preview_chars": _env_int("CHAT_DEBUG_PREVIEW_CHARS", 160, 40, 2000),
}

# ==================== Soniox 语音识别配置 ====================
# 日本区项目必须使用日本区 API Key 和日本区 endpoint。
# 实时识别使用 Soniox 官方 WebSocket 协议（兼容当前 Python 3.9 环境）。
SONIOX_TECH_TERMS = [
    # 编程语言、JVM 与 Java 生态
    "Java", "JVM", "JDK", "JRE", "Spring", "Spring Boot", "Spring Cloud",
    "MyBatis", "Hibernate", "JPA", "Maven", "Gradle", "JUnit", "Mockito",
    "Tomcat", "Netty", "Dubbo", "Nacos", "Sentinel", "Seata", "ZooKeeper",
    "bytecode", "class loader", "JIT", "garbage collection", "GC", "G1", "ZGC",
    "young generation", "old generation", "heap", "stack", "metaspace", "OOM",
    "memory leak", "thread pool", "coroutine", "synchronized", "volatile", "CAS",

    # 数据库、缓存与搜索
    "MySQL", "PostgreSQL", "Oracle", "SQL Server", "SQLite", "MongoDB", "Redis",
    "Elasticsearch", "Logstash", "Kibana", "InnoDB", "binlog", "redo log", "undo log",
    "MVCC", "B+ tree", "ACID", "transaction", "isolation level", "dirty read",
    "non-repeatable read", "phantom read", "deadlock", "primary key", "foreign key",
    "composite index", "covering index", "index pushdown", "slow query", "EXPLAIN",
    "sharding", "replication", "master-slave replication", "read-write splitting",
    "Redis Cluster", "Redis Sentinel", "RDB", "AOF", "LRU", "LFU", "Lua",
    "Bloom filter", "cache penetration", "cache breakdown", "cache avalanche",
    "distributed lock", "consistent hashing",

    # 消息队列与分布式系统
    "RabbitMQ", "Kafka", "RocketMQ", "message queue", "producer", "consumer", "topic",
    "partition", "offset", "ack", "exchange", "routing key", "dead letter queue",
    "persistence", "microservices", "distributed systems", "distributed transaction",
    "two-phase commit", "TCC", "eventual consistency", "CAP theorem", "BASE", "Paxos",
    "Raft", "snowflake ID", "high availability", "load balancing", "rate limiting",
    "circuit breaker", "idempotency", "service discovery", "configuration center",
    "API Gateway", "service mesh", "Istio",

    # 网络、接口与安全
    "TCP", "UDP", "HTTP", "HTTPS", "HTTP/2", "HTTP/3", "WebSocket", "gRPC", "DNS",
    "CDN", "TLS", "SSL", "RESTful API", "JSON", "XML", "Protobuf", "OAuth 2.0",
    "JWT", "CORS", "Nginx", "Apache", "reverse proxy", "keep-alive", "three-way handshake",
    "four-way handshake", "congestion control", "socket", "epoll", "select", "poll",

    # Linux、云原生与工程效率
    "Linux", "Docker", "Kubernetes", "K8s", "container", "Pod", "Deployment", "Service",
    "Ingress", "Helm", "Jenkins", "Git", "GitHub", "GitLab", "CI/CD", "DevOps",
    "Prometheus", "Grafana", "OpenTelemetry", "ELK", "SkyWalking", "virtual machine",
    "process", "thread", "context switch", "CPU", "I/O", "file descriptor",

    # 并发、数据结构与算法
    "concurrency", "parallelism", "mutex", "semaphore", "optimistic lock",
    "pessimistic lock", "race condition", "atomic operation", "data structure",
    "linked list", "array", "queue", "hash table", "binary tree",
    "red-black tree", "AVL tree", "priority queue", "heap sort", "quicksort",
    "merge sort", "binary search", "dynamic programming", "greedy algorithm",
    "backtracking", "BFS", "DFS", "LeetCode", "time complexity", "space complexity",
    "Big O",

    # 软件设计与测试开发
    "design pattern", "singleton", "factory pattern", "observer pattern", "proxy pattern",
    "strategy pattern", "SOLID", "object-oriented", "polymorphism", "inheritance",
    "encapsulation", "abstraction", "serialization", "deserialization", "unit testing",
    "integration testing", "interface testing", "performance testing", "stress testing",
    "load testing", "regression testing", "Selenium", "Appium", "Playwright", "Postman",
    "JMeter", "pytest", "TestNG", "mock", "code coverage", "assertion", "test case",
    "stack trace", "Agile", "Scrum",
]

SONIOX_CONFIG = {
    "api_key": os.getenv("SONIOX_API_KEY", "c9e85b46c6b3dc33b0101238f88517652725601fec034b42d5c0ba2fa599bc85"),
    "api_host": os.getenv("SONIOX_API_HOST", "https://api.jp.soniox.com:443"),
    "ws_url": os.getenv("SONIOX_WS_URL", "wss://stt-rt.jp.soniox.com/transcribe-websocket"),
    "model": os.getenv("SONIOX_MODEL", "stt-rt-v5"),
    "language": os.getenv("SONIOX_LANGUAGE", "zh"),
    "context": {
        "general": [
            {"key": "domain", "value": "Computer science and software engineering"},
            {"key": "topic", "value": "Chinese technical interview and programming discussion"},
            {"key": "language", "value": "Chinese speech containing English technical terms"},
        ],
        "terms": SONIOX_TECH_TERMS,
    },
}

# ==================== 字节跳动语音识别配置 ====================
# 注意：实时识别已改用火山引擎 v2/asr 协议（见下方 VOLCENGINE_CONFIG）。
# 此处为字节跳动开放平台 SAUC 协议凭据（app_key/access_key），
# 与火山引擎 appid/token 不同，需单独申请；留空时文件识别会自动降级到火山引擎。
BYTEDANCE_ASR_CONFIG = {
    "app_key": "",   # 您的 app_key
    "access_key": "",  # 您的 access_key
    "url": "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream",
    "segment_duration": 200,  # 每个音频包的时长（毫秒）
}

# ==================== 火山引擎配置（实时识别 + 文件识别备用） ====================
VOLCENGINE_CONFIG = {
    "appid": "2448163126",
    "token": "OYKhmgoizSmGsLJSdZ7WIMxZVbXTzfwH",
    "cluster": "volcengine_streaming_common",
    "ws_url": "wss://openspeech.bytedance.com/api/v2/asr",  # 实时流式识别 WebSocket 地址
    "segment_duration": 200,  # 每个音频包的时长（毫秒）
}

# ==================== 音频参数配置 ====================
AUDIO_CONFIG = {
    'rate': 16000,        # 采样率（Hz），火山引擎要求 16000
    'channels': 1,        # 声道数
    'chunk': 960,         # 每次读取的音频块大小
    'format': 8,          # pyaudio.paInt16
    'language': 'zh-CN',  # 识别语言（Soniox 使用 SONIOX_LANGUAGE）
    'max_duration_minutes': 5,  # 最大录音时长（分钟）
}

# ==================== 快捷键配置 ====================
HOTKEY_CONFIG = {
    "toggle": "ctrl+8",       # 全局快捷键（需要辅助功能权限）
    "local_toggle": "alt+e",  # 局部快捷键（前端页面中使用，无需权限）
}
