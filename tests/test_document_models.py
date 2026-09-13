import pytest
from pydantic import ValidationError

from app.core.config import MAX_DOCUMENT_CONTENT_BYTES
from app.models.document import DocumentUpdate


def test_content_within_the_limit_is_accepted():
    DocumentUpdate(content="a" * MAX_DOCUMENT_CONTENT_BYTES)


def test_content_exactly_at_the_limit_is_accepted():
    # "exceeds" is a strict >, so the boundary value itself is still fine.
    doc = DocumentUpdate(content="a" * MAX_DOCUMENT_CONTENT_BYTES)
    assert len(doc.content.encode("utf-8")) == MAX_DOCUMENT_CONTENT_BYTES


def test_content_one_byte_over_the_limit_is_rejected():
    with pytest.raises(ValidationError, match="exceeds"):
        DocumentUpdate(content="a" * (MAX_DOCUMENT_CONTENT_BYTES + 1))


def test_content_size_uses_utf8_byte_length_not_character_count():
    # Multi-byte characters mean char count alone would under-count the
    # actual stored/transmitted size.
    multibyte_char = "€"  # 3 bytes in UTF-8
    char_count = MAX_DOCUMENT_CONTENT_BYTES  # would be within limit by char count alone
    with pytest.raises(ValidationError, match="exceeds"):
        DocumentUpdate(content=multibyte_char * char_count)


def test_missing_content_is_still_allowed_for_a_partial_update():
    doc = DocumentUpdate(title="New title")
    assert doc.content is None


def test_empty_string_content_is_allowed():
    doc = DocumentUpdate(content="")
    assert doc.content == ""
