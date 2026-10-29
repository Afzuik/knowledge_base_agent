"""Local deterministic text extraction. No database, model API or task lifecycle."""
from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader


class ParseError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PageText:
    text: str
    page: int | None


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[PageText]
    page_count: int


def parse_document(content: bytes, kind: str, max_chars=2_000_000, max_pages=200):
    if kind in ('md', 'txt'):
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ParseError('invalid_encoding', '文本不是有效 UTF-8，请转换编码后重新上传。') from exc
        controls = sum(ord(c) < 32 and c not in '\n\r\t' for c in text)
        if '\x00' in text or controls > max(2, len(text) // 100):
            raise ParseError('invalid_text', '文件包含二进制或异常控制字符，不是可支持的文本。')
        if len(text) > max_chars:
            raise ParseError('text_limit', '提取的文本超过字符数限制。')
        pages = [PageText(text, None)]; count = 0
    elif kind == 'pdf':
        if not content.startswith(b'%PDF-'):
            raise ParseError('invalid_pdf', '文件不是有效 PDF。')
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise ParseError('encrypted_pdf', '暂不支持加密 PDF，请先解密。')
            count = len(reader.pages)
            if count > max_pages:
                raise ParseError('page_limit', 'PDF 页数超过限制。')
            pages = []; total = 0
            for i, page in enumerate(reader.pages, 1):
                stream = page.get_contents()
                if stream is not None and len(stream.get_data()) > 10 * 1024 * 1024:
                    raise ParseError('pdf_stream_limit', 'PDF 单页内容过大，暂不支持。')
                text = page.extract_text() or ''
                total += len(text)
                if total > max_chars:
                    raise ParseError('text_limit', '提取的文本超过字符数限制。')
                pages.append(PageText(text, i))
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError('invalid_pdf', 'PDF 解析失败，文件可能已损坏。') from exc
    else:
        raise ParseError('unsupported_type', '不支持此文件格式。')
    if not any(p.text.strip() for p in pages):
        raise ParseError('no_text', '未提取到有效文本；扫描 PDF 需要 OCR，本版尚不支持。')
    return ParsedDocument(pages, count)
