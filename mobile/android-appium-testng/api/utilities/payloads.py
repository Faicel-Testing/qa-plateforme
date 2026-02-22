import uuid

def add_book_payload(author: str = "Rahul Shetty2") -> dict:
    """
    Génère un payload valide et unique pour AddBook.
    ISBN/Aisle uniques évitent les collisions.
    """
    unique = uuid.uuid4().hex[:6]
    isbn = f"QA{unique}"
    aisle = str(int(unique, 16))[:4]  # petit nombre dérivé

    return {
        "name": "Learn Appium Automation with Java",
        "isbn": isbn,
        "aisle": aisle,
        "author": author
    }
