"""待实现：RAG 生成策略、上下文组装、提示词与流式输出。

生成答案和展示引用共用同一次检索结果；来源不足时明确说明。
实际模型请求由 infrastructure.models.llm 提供；会话保存由 application.chat 负责。
暂不单独创建 prompts.py，提示词实际实现并需要拆分时再添加。
"""
