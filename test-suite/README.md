test-suite
===

A collection of tests to ensure our SPOF that is the centralized [library.kiwix.org](https://library.kiwix.org/) catalog behaves as it should.

# Requirements

You must have a working python3 environments with a few dependencies.

```sh
pip install -r requirements.txt
```

# Usage

```sh
pytest -v
```

## Options

- You can change the target host by setting `LIBRARY_HOST` environment variable.
- You can select which schemes (http, https) to check using `SCHEMES` environment variable.
- You can disable Varnish-related tests using `-m "not varnish"` flag.

Examples:

```sh
# local kiwix-serve
SCHEMES=http LIBRARY_HOST="localhost:9000" pytest -v -m "not varnish"

# dev library
LIBRARY_HOST="dev.library.kiwix.org" pytest -v -m "not varnish"

# main online library
pytest -v
```

## Sample output

```sh
pytest -v
================================================================= test session starts =================================================================
platform darwin -- Python 3.8.6, pytest-7.1.2, pluggy-1.0.0 -- /Users/reg/src/envs/k8s/bin/python3.8
cachedir: .pytest_cache
rootdir: /Users/reg/src/k8s/test-suite, configfile: pytest.ini
collected 24 items

test_basic.py::test_reachable[https] PASSED                                                                                                     [  4%]
test_basic.py::test_reachable[http] PASSED                                                                                                      [  8%]
test_basic.py::test_opds_mimetypes[/catalog/root.xml-application/atom+xml; profile=opds-catalog; kind=acquisition; charset=utf-8] PASSED        [ 12%]
test_basic.py::test_opds_mimetypes[/catalog/v2/root.xml-application/atom+xml;profile=opds-catalog;kind=navigation] PASSED                       [ 16%]
test_basic.py::test_opds_mimetypes[/catalog/v2/searchdescription.xml-application/opensearchdescription+xml] PASSED                              [ 20%]
test_basic.py::test_opds_mimetypes[/catalog/v2/entries-application/atom+xml;profile=opds-catalog;kind=acquisition] PASSED                       [ 25%]
test_basic.py::test_opds_mimetypes[/catalog/v2/categories-application/atom+xml;profile=opds-catalog;kind=navigation] PASSED                     [ 29%]
test_basic.py::test_opds_mimetypes[/catalog/v2/languages-application/atom+xml;profile=opds-catalog;kind=navigation] PASSED                      [ 33%]
test_basic.py::test_opds_is_gzipped[/catalog/root.xml] PASSED                                                                                   [ 37%]
test_basic.py::test_opds_is_gzipped[/catalog/v2/root.xml] PASSED                                                                                [ 41%]
test_basic.py::test_opds_is_gzipped[/catalog/v2/searchdescription.xml] PASSED                                                                   [ 45%]
test_basic.py::test_opds_is_gzipped[/catalog/v2/entries] PASSED                                                                                 [ 50%]
test_basic.py::test_opds_is_gzipped[/catalog/v2/categories] PASSED                                                                              [ 54%]
test_basic.py::test_opds_is_gzipped[/catalog/v2/languages] PASSED                                                                               [ 58%]
test_basic.py::test_opds_is_cached[/catalog/root.xml] PASSED                                                                                    [ 62%]
test_basic.py::test_opds_is_cached[/catalog/v2/root.xml] PASSED                                                                                 [ 66%]
test_basic.py::test_opds_is_cached[/catalog/v2/searchdescription.xml] PASSED                                                                    [ 70%]
test_basic.py::test_opds_is_cached[/catalog/v2/entries] PASSED                                                                                  [ 75%]
test_basic.py::test_opds_is_cached[/catalog/v2/categories] PASSED                                                                               [ 79%]
test_basic.py::test_opds_is_cached[/catalog/v2/languages] PASSED                                                                                [ 83%]
test_basic.py::test_illus_mimetypes PASSED                                                                                                      [ 87%]
test_basic.py::test_illus_is_not_gzipped PASSED                                                                                                 [ 91%]
test_basic.py::test_illus_is_cached PASSED                                                                                                      [ 95%]
test_basic.py::test_random_is_not_cached PASSED                                                                                                 [100%]

================================================================= 24 passed in 11.77s =================================================================

```
