import json
from urllib.parse import urlsplit
import httpx
from .transport import client, headers, post, ModelError


class LLM:
    def __init__(self, settings):
        self.settings = settings
        self.endpoint = settings.llm

    def payload(self, messages, max_tokens, stream):
        result = dict(model=self.endpoint.model, messages=messages, temperature=0.2, max_tokens=max_tokens, stream=stream)
        if self.settings.enable_thinking is not None:
            if urlsplit(self.endpoint.base_url).hostname == 'api.deepseek.com':
                result['thinking'] = {'type': 'enabled' if self.settings.enable_thinking else 'disabled'}
            else:
                result['enable_thinking'] = self.settings.enable_thinking
        return result

    def complete(self, messages, max_tokens=256):
        data = post(self.settings, self.endpoint, '/chat/completions', self.payload(messages, max_tokens, False))
        try:
            answer = data['choices'][0]['message']['content']
            if not isinstance(answer,str) or not answer.strip(): raise ValueError()
            return answer
        except (KeyError, TypeError, ValueError, IndexError):
            raise ModelError('模型没有返回有效文本。') from None

    def stream(self, messages):
        try:
            with client(self.settings) as c:
                with c.stream('POST', self.endpoint.base_url.rstrip('/') + '/chat/completions', headers=headers(self.endpoint),
                    json=self.payload(messages, 2048, True)) as response:
                    if response.status_code >= 400: raise ModelError(f'生成服务返回 HTTP {response.status_code}。')
                    finished = False
                    for line in response.iter_lines():
                        if not line.startswith('data:'): continue
                        raw = line[5:].strip()
                        if raw == '[DONE]':
                            if not finished: raise ModelError('生成流未确认正常完成。')
                            return
                        data = json.loads(raw)
                        if 'error' in data: raise ModelError('生成服务返回流式错误。')
                        for choice in data.get('choices',[]):
                            content = choice.get('delta',{}).get('content')
                            if content: yield content
                            reason = choice.get('finish_reason')
                            if reason:
                                if reason != 'stop': raise ModelError('回答被截断或未正常结束。')
                                finished = True
                    if not finished: raise ModelError('生成流意外中断。')
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise ModelError('生成请求失败或流式数据无效。') from None
