"""Deterministic Markdown document creation, not LLM generation."""
import html
import re
from markdown_it import MarkdownIt

_parser = MarkdownIt('gfm-like')


def reference_labels(body):
    labels = []
    for token in _parser.parse(body):
        if token.type != 'inline': continue
        link_depth = 0
        for child in token.children or []:
            if child.type == 'link_open': link_depth += 1
            elif child.type == 'link_close': link_depth -= 1
            elif child.type == 'text' and link_depth == 0:
                for label in re.findall(r'\[(S\d+)\]',child.content):
                    if label not in labels: labels.append(label)
    return labels


def escape_heading(value):
    punctuation = set("\\`*_{}[]()#+.!|>~-")
    return ''.join(('\\' + c) if c in punctuation else c for c in html.escape(value,quote=False))


def filename_for(title):
    name = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', '_', title).strip(' .')[:100].rstrip(' .')
    if not name or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',name):
        name = '研究笔记' + ('-' + name if name else '')
    return name + '.md'


def markdown_for(note, citations, labels):
    lines = ['# ' + escape_heading(note['title']), '',
        '> 本笔记由回答保存并可编辑；引用为原回答保存的证据快照，编辑后请重新核对。', '',
        note['body_markdown'], '', '---', '', '## 参考资料', '']
    mapping = {c['label']:c for c in citations}
    if not labels: lines.append('本笔记正文未使用引用编号。')
    for label in labels:
        c = mapping[label]
        location = f"PDF 第 {c['page_start']} 页" if c['page_start'] is not None else '文本资料'
        if c['page_end'] is not None and c['page_end'] != c['page_start']:
            location += f"至第 {c['page_end']} 页"
        location += f"；字符 [{c['char_start']}, {c['char_end']})"
        fence = '`' * max(3, max([len(x)+1 for x in re.findall(r'`+',c['text'])] or [3]))
        lines.extend(['### ' + label + ' · ' + escape_heading(c['filename']), '',
            '- 位置：' + location, '- 引用原文（保存时快照）：', '', fence + 'text', c['text'], fence, ''])
    return '\n'.join(lines).rstrip() + '\n'
