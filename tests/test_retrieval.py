import json

import pytest

from retrieval.chunking import chunk_text
from retrieval.file_parser import extract_text


def test_chunk_text_returns_chunks():
    text = "A " * 300
    chunks = chunk_text(text, chunk_size=100, overlap=20, max_chunks=10)

    assert chunks
    assert len(chunks) <= 10
    assert all(isinstance(chunk, str) for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_respects_max_chunks():
    text = "engineering " * 2000
    chunks = chunk_text(
        text,
        chunk_size=100,
        overlap=20,
        max_chunks=5,
    )

    assert len(chunks) <= 5


def test_extract_text_txt(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(
        "Brain 3.0 retrieval test.",
        encoding="utf-8",
    )

    result = extract_text(str(path), "sample.txt")

    assert result == "Brain 3.0 retrieval test."


def test_extract_text_json(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(
        json.dumps({"name": "Brain 3.0", "version": 10}),
        encoding="utf-8",
    )

    result = extract_text(str(path), "sample.json")

    assert "Brain 3.0" in result
    assert "version" in result


def test_extract_text_csv(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(
        "name,value\nBrain,3.0\n",
        encoding="utf-8",
    )

    result = extract_text(str(path), "sample.csv")

    assert "name | value" in result
    assert "Brain | 3.0" in result


def test_extract_text_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text(
            "/tmp/does-not-exist-brain30.txt",
            "missing.txt",
        )


def test_extract_text_unsupported_extension(tmp_path):
    path = tmp_path / "sample.exe"
    path.write_bytes(b"not supported")

    with pytest.raises(ValueError):
        extract_text(str(path), "sample.exe")