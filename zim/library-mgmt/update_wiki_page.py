#!/usr/bin/env python3

""" Update a Wiki with the content of a file

    pip3 install mwclient==0.10.1
    Usage: $0 wikiDomain wikiUser wikiUserPass pageName filePath editComment"""

import pathlib
import sys

import mwclient


def main(wiki_domain, username, password, page_name, fpath, edit_comment):
    fpath = pathlib.Path(fpath).expanduser().resolve()
    site = mwclient.Site(wiki_domain)
    site.login(username, password)
    page = site.pages[page_name]

    with open(fpath, encoding="utf-8") as fh:
        page.save(fh.read(), summary=edit_comment)
    print(f"{page_name} updated")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print(
            f"usage: {sys.argv[0]} wikiDomain wikiUser wikiUserPass "
            "pageName filePath editComment"
        )
        sys.exit(1)
    sys.exit(main(*sys.argv[1:]))
