"""Validate citation labels against the exact evidence used for generation."""
import re


def finalize(text, evidence):
    # Normalize only unambiguous citation markers, never free-standing source names.
    text = re.sub(r'[（(【]\s*(S\d+)\s*[）)】]', r'[\1]', text)
    mapping = {c['label']:c for c in evidence}
    seen = []; invalid = []
    def replace(match):
        label = match.group(1)
        if label not in mapping:
            invalid.append(label); return '[无效引用]'
        if label not in seen: seen.append(label)
        return match.group(0)
    cleaned = re.sub(r'\[(S\d+)\]', replace, text)
    fields = ['label','source_id','filename','text','page_start','page_end','char_start','char_end','index_revision']
    citations = [{**{k:mapping[label][k] for k in fields},'chunk_id':mapping[label]['id']} for label in seen]
    warnings = []
    if invalid: warnings.append('模型生成了不存在的引用编号，已取消这些引用链接。')
    if not citations: warnings.append('本回答没有有效引用；可能是资料不足的说明，请核对，不能视为已验证结论。')
    return cleaned, citations, warnings
