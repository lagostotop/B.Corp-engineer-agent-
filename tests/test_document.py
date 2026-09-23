from unittest.mock import MagicMock,patch

from database.documents import (
    create_document,
    list_documents,
    get_document,
    delete_document,
)


def test_create_document():
    response=MagicMock()
    response.data=[{"id":"doc-1","user_id":"user-1"}]

    with patch("database.documents.db") as mock_db:
        mock_db.return_value.table.return_value.insert.return_value.execute.return_value=response

        result=create_document(
            user_id="user-1",
            chat_id="chat-1",
            content="Test document",
            embedding=[0.1]*1536,
            metadata={"filename":"test.txt"},
        )

    assert result["id"]=="doc-1"


def test_create_document_rejects_wrong_embedding_size():
    with patch("database.documents.db") as mock_db:
        try:
            create_document(
                user_id="user-1",
                chat_id="chat-1",
                content="Test",
                embedding=[0.1]*10,
            )
            assert False
        except ValueError as exc:
            assert "1536" in str(exc)

        mock_db.assert_not_called()


def test_list_documents():
    response=MagicMock()
    response.data=[
        {"id":"doc-1","user_id":"user-1"},
        {"id":"doc-2","user_id":"user-1"},
    ]

    with patch("database.documents.db") as mock_db:
        query=mock_db.return_value.table.return_value
        query.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value=response

        result=list_documents("user-1")

    assert len(result)==2
    assert result[0]["user_id"]=="user-1"


def test_get_document():
    response=MagicMock()
    response.data={"id":"doc-1","user_id":"user-1"}

    with patch("database.documents.db") as mock_db:
        query=mock_db.return_value.table.return_value
        query.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value=response

        result=get_document("doc-1","user-1")

    assert result["id"]=="doc-1"


def test_delete_document():
    response=MagicMock()
    response.data=[{"id":"doc-1"}]

    with patch("database.documents.db") as mock_db:
        query=mock_db.return_value.table.return_value
        query.delete.return_value.eq.return_value.eq.return_value.execute.return_value=response

        result=delete_document("doc-1","user-1")

    assert result is True