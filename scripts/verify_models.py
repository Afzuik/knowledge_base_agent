#!/usr/bin/env python3
"""Explicit, small real-service checks. Sends synthetic text; never prints credentials."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.infrastructure.models import build_providers
from app.infrastructure.models.transport import ModelError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/rag/latest-model-check.json')
    args = parser.parse_args()
    providers = build_providers(ROOT)
    results = {}
    checks = [
        ('llm', lambda: providers.llm.complete([{'role':'user','content':'这是连通性测试，请只回复 OK。'}], 64)),
        ('llm_stream', lambda: ''.join(providers.llm.stream([{'role':'user','content':'流式连通性测试，请只回复 OK。'}]))),
        ('embedding', lambda: providers.embedding.embed(['这是合成的接口测试文本。'])),
    ]
    if providers.reranker.enabled:
        checks.append(('reranker', lambda: providers.reranker.rank('预算是多少', ['演示预算120元。','天气晴朗。'], 2)))
    for name, check in checks:
        start = time.monotonic()
        try:
            value = check()
            result = {'ok': True, 'seconds': round(time.monotonic()-start, 2)}
            if name == 'embedding': result['dimension'] = len(value[0])
            elif name == 'reranker': result['order'] = value
            else: result['reply'] = value[:80]
        except Exception as exc:
            result = {'ok': False, 'error_type': type(exc).__name__,
                      'error': str(exc) if isinstance(exc, ModelError) else 'local validation failed'}
        results[name] = result
        print(name, json.dumps(result, ensure_ascii=False), flush=True)
    output = {'config': providers.settings.public(), 'checks': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    return 0 if all(r['ok'] for r in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
