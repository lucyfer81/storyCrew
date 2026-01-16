# LLM 交互日志格式说明

本文档描述了 StoryCrew 项目中增强的 LLM 交互日志功能。

## 功能概述

增强的 `LoggingInterceptor` 现在会记录每次 LLM 调用的完整信息：

1. **Request (发送给 LLM)**
   - 完整的 prompt 内容
   - 估算的 token 数量
   - 消息结构（如果有多个消息）

2. **Response (从 LLM 收到)**
   - 完整的 response 内容
   - 实际的 token 使用量（如果 API 提供）
   - 估算的 token 数量
   - 成本估算

## 日志格式

### 1. 请求日志

```
[LLM INTERCEPTOR] Request #N
[LLM INTERCEPTOR] Request URL: https://api.example.com/v1/chat/completions
[LLM INTERCEPTOR] Request Method: POST
[LLM REQUEST] 📤 Request contains M messages
[LLM REQUEST] Message 1 [system] (1,234 tokens est.):
[LLM REQUEST] You are a helpful assistant...
[LLM REQUEST] Message 2 [user] (5,678 tokens est.):
[LLM REQUEST] Please help me with...
```

### 2. 响应日志

```
[LLM TOKENS] 📊 Actual Token Usage (from API):
[LLM TOKENS]   Input (prompt):  6,912 tokens
[LLM TOKENS]   Output (completion): 1,234 tokens
[LLM TOKENS]   Total: 8,146 tokens
[LLM TOKENS]   Est. Cost: $0.0055
[LLM RESPONSE] 📥 Response Content (2,500 tokens est.):
[LLM RESPONSE] Here's the response from the LLM...
```

## Token 估算算法

由于无法直接访问 LLM 的 tokenizer，我们使用启发式算法估算 token 数量：

```python
# 中文字符：约 2 字符/token
# 英文字符：约 4 字符/token

chinese_chars = count(0x4e00 <= c <= 0x9fff)  # CJK Unicode 范围
other_chars = total_length - chinese_chars

estimated_tokens = (chinese_chars / 2) + (other_chars / 4)
```

**注意：**
- 这只是粗略估算
- 实际 token 数量取决于具体的 tokenizer
- 日志中会同时显示估算值（est.）和 API 返回的实际值（如果有）

## 日志级别

- **INFO**: 主要的请求/响应内容
- **WARNING**: 无法提取某些信息（如 request body）
- **DEBUG**: 额外的调试信息（如无法提取 token usage）

## 内容截断策略

为避免日志过大，长内容会被截断：

- **Request messages**: 最多显示 1000 字符
- **Request prompt**: 最多显示 2000 字符
- **Response content**: 最多显示 5000 字符
- 超过限制时会显示 `[truncated, total N chars]`

## 使用场景

### 1. 成本分析

通过日志中的 token 信息，可以：
- 追踪每个任务的 token 消耗
- 计算总体成本
- 优化 prompt 以减少 token 使用

### 2. 调试

完整的请求/响应日志帮助：
- 检查发送给 LLM 的 prompt 是否正确
- 验证 LLM 返回的内容格式
- 诊断 API 调用问题

### 3. 性能优化

通过分析日志可以：
- 识别哪些任务消耗最多 tokens
- 优化任务描述以减少重复内容
- 调整 max_tokens 参数

## 日志文件位置

日志文件默认保存在 `logs/` 目录：
- 开发环境：`logs/storycrew.log`
- 测试环境：`logs/test_*.log`

## 示例日志片段

```
================================================================================
[LLM INTERCEPTOR] Request #1
[LLM INTERCEPTOR] Request URL: https://api.openai.com/v1/chat/completions
[LLM INTERCEPTOR] Request Method: POST
[LLM INTERCEPTOR] Response Status: 200
[LLM REQUEST] 📤 Request contains 3 messages
[LLM REQUEST] Message 1 [system] (234 tokens est.):
[LLM REQUEST] You are a creative writer specializing in romance novels...
[LLM REQUEST] Message 2 [user] (5,678 tokens est.):
[LLM REQUEST] Please write chapter 1 with the following outline... [truncated, total 12000 chars]
[LLM REQUEST] Message 3 [assistant] (1,234 tokens est.):
[LLM REQUEST] [Previous conversation context]
[LLM TOKENS] 📊 Actual Token Usage (from API):
[LLM TOKENS]   Input (prompt):  7,146 tokens
[LLM TOKENS]   Output (completion): 2,345 tokens
[LLM TOKENS]   Total: 9,491 tokens
[LLM TOKENS]   Est. Cost: $0.0073
[LLM RESPONSE] 📥 Response Content (3,456 tokens est.):
[LLM RESPONSE] Chapter 1
[LLM RESPONSE] The morning sun streamed through the windows... [truncated, total 15000 chars]
================================================================================
```

## 配置

如需调整日志详细程度，可以修改 `LoggingInterceptor` 类中的截断限制：

```python
# crew.py - LoggingInterceptor.__call__()

# 当前限制：
# - Request message preview: 1000 chars
# - Request prompt preview: 2000 chars
# - Response content preview: 5000 chars
```

## 故障排除

### 问题：看不到 request 日志

**可能原因：**
- Request 对象不包含 `body` 或 `data` 属性
- Request body 不是 JSON 格式

**解决方法：**
- 检查日志中的 WARNING 信息
- 确认 LLM provider 是否支持 interceptor

### 问题：token 估算不准确

**说明：**
- 估算值与实际值可能有 ±20% 的误差
- 这对成本估算来说是可以接受的
- 如需精确值，依赖 API 返回的 `usage` 字段

### 问题：日志文件过大

**解决方法：**
- 使用日志轮转（log rotation）
- 调整日志级别（只记录 INFO 及以上）
- 减少截断限制（但会丢失详细信息）
