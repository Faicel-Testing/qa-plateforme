import pytest
from urllib.parse import urljoin
from api.resources.api_resources import ApiResources


def _build_url(library_url: str, endpoint: str) -> str:
    """
    Helper pour construire une URL propre
    """
    return urljoin(library_url.rstrip("/") + "/", endpoint.lstrip("/"))

@pytest.mark.smoke
def test_get_then_delete_existing_book(http_session, library_url):
    """
    SMOKE TEST
    - Vérifie que l'API permet :
      1) de récupérer un livre
      2) de le supprimer avec succès
    """

    # -----------------------
    # 1) GET : récupérer les livres par auteur
    # -----------------------
    get_url = _build_url(library_url, ApiResources.GET_BOOK)
    params = {"AuthorName": "Rahul Shetty2"}

    get_resp = http_session.get(get_url, params=params)
    assert get_resp.status_code == 200

    books = get_resp.json()
    assert isinstance(books, list)
    assert len(books) > 0, "Aucun livre retourné par GetBook"

    # Choisir un livre existant
    book_to_delete = books[0]

    isbn = book_to_delete.get("isbn")
    aisle = book_to_delete.get("aisle")

    assert isbn is not None and aisle is not None, f"Livre invalide: {book_to_delete}"

    book_id = f"{isbn}{aisle}"

    # -----------------------
    # 2) DELETE : supprimer le livre
    # -----------------------
    del_url = _build_url(library_url, ApiResources.DELETE_BOOK)
    del_resp = http_session.post(del_url, json={"ID": book_id})

    if del_resp.status_code != 200:
        print("DEL URL  =", del_url)
        print("DEL ID   =", book_id)
        print("STATUS   =", del_resp.status_code)
        print("BODY     =", del_resp.text)

    assert del_resp.status_code == 200

    del_json = del_resp.json()
    assert del_json.get("msg") == "book is successfully deleted", (
        f"Réponse DeleteBook inattendue: {del_json}"
    )
