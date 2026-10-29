"""Shared bounded HTTP transport. Never expose provider response bodies/headers in errors."""
import httpx


class ModelError(RuntimeError):
    pass


def client(settings):
    return httpx.Client(timeout=httpx.Timeout(settings.timeout, connect=15), trust_env=settings.trust_env)


def headers(endpoint):
    if not endpoint.configured:
        raise ModelError('模型配置缺失，请检查服务端配置。')
    return {'Authorization': 'Bearer ' + endpoint.api_key, 'Content-Type': 'application/json'}


def post(settings, endpoint, path, payload):
    try:
        with client(settings) as c:
            response = c.post(endpoint.base_url.rstrip('/') + path, headers=headers(endpoint), json=payload)
            if response.status_code >= 400:
                raise ModelError(f'模型服务返回 HTTP {response.status_code}。')
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelError('模型请求失败或返回无效数据。') from None
