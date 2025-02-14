import datetime
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import regex
import requests
import xmltodict
from conftest import EXCLUDED_BOOKS
from utils import get_url

name_fmt = re.compile(
    r"^(?P<project>[a-z0-9\-\.]+?_)(?P<lang>[a-z\-]{2,10}?_|)"
    r"(?P<option>[a-z0-9\-\.\_]+)$"
)

filename_fmt = re.compile(
    r"^(?P<project>[a-z0-9\-\.]+?_)(?P<lang>[a-z\-]{2,10}?_|)"
    r"(?P<option>[a-z0-9\-\.\_]+_|)(?P<year>[\d]{4}|)\-(?P<month>[\d]{2})\.zim$"
)


def nb_grapheme_for(value: str) -> int:
    """Number of graphemes (visually perceived characters) in a given string"""
    return len(regex.findall(r"\X", value))


def has_only_allowed_chars(text: str) -> bool:
    def valid_char(char: int) -> bool:
        return (
            (char >= 48 and char <= 57)  # digits
            # or (char >= 65 and char <= 90)  # A-Z
            or (char >= 97 and char <= 122)  # a-z
            or char
            in (
                45,  # -
                46,  # .
                95,  # _
            )
        )

    return all(valid_char(ord(char)) for char in text)


@dataclass
class Book:
    uuid: UUID
    ident: str
    name: str
    title: str
    description: str
    author: str
    publisher: str
    langs_iso639_3: list[str]
    tags: list[str]
    flavour: str
    size: int
    url: str
    illustration_relpath: str
    version: str

    @property
    def category(self) -> str:
        try:
            return next(
                tag.split(":", 1)[1]
                for tag in self.tags
                if tag.startswith("_category:")
            )
        except StopIteration:
            return ""

    @property
    def filepath(self) -> Path:
        return Path(urllib.parse.urlparse(self.url).path)

    @property
    def filename(self) -> str:
        return Path(urllib.parse.urlparse(self.url).path).name

    @property
    def lang_codes(self) -> list[str]:
        return self.langs_iso639_3

    @property
    def lang_code(self) -> str:
        return self.langs_iso639_3[0]

    @property
    def has_illustration(self) -> bool:
        return len(self.illustration_relpath) > 0


def get_catalog() -> dict[str, Book]:
    books: dict[str, Book] = {}
    resp = requests.get(
        f"{get_url('/catalog/v2')}/entries", params={"count": "-1"}, timeout=30
    )
    resp.raise_for_status()
    catalog = xmltodict.parse(resp.content)
    if "feed" not in catalog:
        raise ValueError("Malformed OPDS response")
    if not int(catalog["feed"]["totalResults"]):
        raise OSError("Catalog has no entry; probably misbehaving")
    assert isinstance(catalog["feed"]["entry"], list)

    for entry in catalog["feed"]["entry"]:
        assert entry.get("name")
        if not entry.get("name"):
            print(f"Skipping entry without name: {entry}")
            continue

        links = {link["@type"]: link for link in entry["link"]}
        version = datetime.datetime.fromisoformat(
            re.sub(r"[A-Z]$", "", entry["updated"])
        ).strftime("%Y-%m-%d")
        flavour = entry.get("flavour") or ""
        publisher = entry.get("publisher", {}).get("name") or ""
        author = entry.get("author", {}).get("name") or ""
        ident = f"{publisher}:{entry['name']}:{flavour}"

        if ident in EXCLUDED_BOOKS:
            print(f"Skipping excluded book `{ident}`")
            continue

        if not links.get("image/png;width=48;height=48;scale=1"):
            print(f"Book has no illustration: {ident}")

        uuid = UUID(entry["id"])
        books[ident] = Book(
            uuid=uuid,
            ident=ident,
            name=entry["name"],
            title=entry["title"],
            author=author,
            publisher=publisher,
            description=entry["summary"],
            langs_iso639_3=list(set(entry["language"].split(","))) or ["eng"],
            tags=list(set(entry["tags"].split(";"))),
            flavour=flavour,
            size=int(links["application/x-zim"]["@length"]),
            url=re.sub(r".meta4$", "", links["application/x-zim"]["@href"]),
            illustration_relpath=links.get(
                "image/png;width=48;height=48;scale=1", {}
            ).get("@href", ""),
            version=version,
        )
    return books


catalog = get_catalog()

bookparam = pytest.mark.parametrize("book", catalog.values(), ids=catalog.keys())


def test_catalog_has_entries():
    assert catalog


@bookparam
def test_book_name(book: Book):
    assert has_only_allowed_chars(book.name)


@pytest.mark.name_pattern
@bookparam
def test_book_name_pattern(book: Book):
    assert name_fmt.match(book.name)


@bookparam
def test_book_filename(book: Book):
    fname = Path(book.filename)
    assert has_only_allowed_chars(fname.stem)
    assert book.filename == f"{fname.stem}.zim"


@pytest.mark.filename_pattern
@bookparam
def test_book_filename_pattern(book: Book):
    assert filename_fmt.match(book.filename)


# @pytest.mark.flavours
# @bookparam
# def test_book_flavour(book: Book):
#     assert book.flavour in ["mini", "nopic", "maxi", ""]


# @pytest.mark.flavour__maxi
# @bookparam
# def test_book_flavour_not__maxi(book: Book):
#     assert book.flavour != "_maxi"


# @pytest.mark.flavour__nopic
# @bookparam
# def test_book_flavour_not__nopic(book: Book):
#     assert book.flavour != "_nopic"


# @pytest.mark.flavour__mini
# @bookparam
# def test_book_flavour_not__mini(book: Book):
#     assert book.flavour != "_mini"


# @pytest.mark.all_flavour
# @bookparam
# def test_book_flavour_not_all(book: Book):
#     assert book.flavour != "all"


# @pytest.mark.title_len
# @bookparam
# def test_book_title_len(book: Book):
#     assert book.title
#     assert nb_grapheme_for(book.title) <= 30


# @pytest.mark.description_len
# @bookparam
# def test_book_description_len(book: Book):
#     assert book.description
#     assert nb_grapheme_for(book.description) <= 80


# @pytest.mark.author
# @bookparam
# def test_book_has_author(book: Book):
#     assert book.author


# @pytest.mark.publisher
# @bookparam
# def test_book_has_publisher(book: Book):
#     assert book.publisher


# @bookparam
# def test_publisher_spelling(book: Book):
#     assert book.publisher in ("Kiwix", "openZIM", "WikiProjectMed")


# @bookparam
# def test_book_has_valid_size(book: Book):
#     assert book.size


# @bookparam
# def test_book_has_illustration(book: Book):
#     assert book.has_illustration
