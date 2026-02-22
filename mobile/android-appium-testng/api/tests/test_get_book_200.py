import pytest
from api.resources.api_resources import ApiResources


@pytest.mark.smoke
def test_get_books_by_author_returns_200_and_json(http_session, library_url):
    url = library_url + ApiResources.GET_BOOK
    params = {"AuthorName": "Rahul Shetty2"}

    response = http_session.get(url, params=params)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json;charset=UTF-8"

    books = response.json()
    assert isinstance(books, list)
    assert len(books) > 0


def test_get_books_contains_isbn_a1b_if_present(http_session, library_url):
    url = library_url + ApiResources.GET_BOOK
    params = {"AuthorName": "Rahul Shetty2"}

    response = http_session.get(url, params=params)
    assert response.status_code == 200

    books = response.json()
    actual_book = next((b for b in books if b.get("isbn") == "A1b"), None)

    if actual_book:
        print("Livre trouvé :", actual_book)
