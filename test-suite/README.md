test-suite
===

A collection of tests to ensure our SPOFs behaves as they should.

- Centralized [library.kiwix.org](https://library.kiwix.org/) catalog
- Downloads load-balancer at [download.kiwix.org](https://download.kiwix.org/)

# Requirements

You must have a working python3 environments with a few dependencies.

```sh
pip install -r requirements.txt
```

# Usage

This tests suite targets 3 main use cases:

- testing library.kiwix.org which is our production catalog with a Varnish cache frontend
- testing dev.library.kiwix.org which is a dev environment catalog exposing kiwix-serve
- testing download.kiwix.org mirrorbain and its mirrors

Set the appropriate environment variables, flags and test file depending on your use case.

```sh
# tests production library and mirrors
pytest -v
```

## Options

- You can change the target host by setting `LIBRARY_HOST` environment variable.
- You can select which schemes (http, https) to check using `SCHEMES` environment variable.
- You can disable Varnish-related tests using `-m "not varnish"` flag.

Examples:

```sh
# local kiwix-serve
SCHEMES=http LIBRARY_HOST="localhost:9000" pytest -v -m "not varnish"  test_library.py

# dev library
LIBRARY_HOST="dev.library.kiwix.org" pytest -v -m "not varnish" test_library.py

# main online library
pytest -v test_library.py

# mirrors
pytest -v test_mirrors.py
```

## Sample output

```sh
pytest -v
=============================================================================================== test session starts ===============================================================================================
platform darwin -- Python 3.11.0, pytest-8.3.2, pluggy-1.5.0 -- /Library/Frameworks/Python.framework/Versions/3.11/bin/python3
cachedir: .pytest_cache
rootdir: /Users/reg/src/k8s/test-suite
configfile: pytest.ini
plugins: asyncio-0.24.0, cov-5.0.0, anyio-3.6.2
asyncio: mode=Mode.STRICT, default_loop_scope=None
collected 93 items

test_library.py::test_reachable[https] PASSED                                                                                                                                                               [  1%]
test_library.py::test_opds_mimetypes[/catalog/root.xml-application/atom+xml;profile=opds-catalog;kind=acquisition;charset=utf-8] PASSED                                                                     [  2%]
test_library.py::test_opds_mimetypes[/catalog/v2/root.xml-application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8] PASSED                                                                   [  3%]
test_library.py::test_opds_mimetypes[/catalog/v2/searchdescription.xml-application/opensearchdescription+xml] PASSED                                                                                        [  4%]
test_library.py::test_opds_mimetypes[/catalog/v2/entries-application/atom+xml;profile=opds-catalog;kind=acquisition;charset=utf-8] PASSED                                                                   [  5%]
test_library.py::test_opds_mimetypes[/catalog/v2/categories-application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8] PASSED                                                                 [  6%]
test_library.py::test_opds_mimetypes[/catalog/v2/languages-application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8] PASSED                                                                  [  7%]
test_library.py::test_opds_is_gzipped[/catalog/root.xml] PASSED                                                                                                                                             [  8%]
test_library.py::test_opds_is_gzipped[/catalog/v2/root.xml] PASSED                                                                                                                                          [  9%]
test_library.py::test_opds_is_gzipped[/catalog/v2/entries] PASSED                                                                                                                                           [ 10%]
test_library.py::test_opds_is_gzipped[/catalog/v2/categories] PASSED                                                                                                                                        [ 11%]
test_library.py::test_opds_is_gzipped[/catalog/v2/languages] PASSED                                                                                                                                         [ 12%]
test_library.py::test_opds_is_cached[/catalog/root.xml] PASSED                                                                                                                                              [ 13%]
test_library.py::test_opds_is_cached[/catalog/v2/root.xml] PASSED                                                                                                                                           [ 15%]
test_library.py::test_opds_is_cached[/catalog/v2/searchdescription.xml] PASSED                                                                                                                              [ 16%]
test_library.py::test_opds_is_cached[/catalog/v2/entries] PASSED                                                                                                                                            [ 17%]
test_library.py::test_opds_is_cached[/catalog/v2/categories] PASSED                                                                                                                                         [ 18%]
test_library.py::test_opds_is_cached[/catalog/v2/languages] PASSED                                                                                                                                          [ 19%]
test_library.py::test_illus_mimetypes PASSED                                                                                                                                                                [ 20%]
test_library.py::test_illus_is_not_gzipped PASSED                                                                                                                                                           [ 21%]
test_library.py::test_illus_is_cached PASSED                                                                                                                                                                [ 22%]
test_library.py::test_random_is_not_cached PASSED                                                                                                                                                           [ 23%]
test_library.py::test_viewer_settings_is_cached PASSED                                                                                                                                                      [ 24%]
test_mirrors.py::test_mirrors_list_reachable PASSED                                                                                                                                                         [ 25%]
test_mirrors.py::test_zim_exists PASSED                                                                                                                                                                     [ 26%]
test_mirrors.py::test_zim_permalink PASSED                                                                                                                                                                  [ 27%]
test_mirrors.py::test_zim_mirrors_list PASSED                                                                                                                                                               [ 29%]
test_mirrors.py::test_mirror_has_zim_file[mirror-sites-in.mblibrary.info] PASSED                                                                                                                            [ 30%]
test_mirrors.py::test_mirror_has_zim_file[ftp.fau.de] PASSED                                                                                                                                                [ 31%]
test_mirrors.py::test_mirror_has_zim_file[mirrors.dotsrc.org] PASSED                                                                                                                                        [ 32%]
test_mirrors.py::test_mirror_has_zim_file[mirror.download.kiwix.org] PASSED                                                                                                                                 [ 33%]
test_mirrors.py::test_mirror_has_zim_file[mirror-sites-fr.mblibrary.info] PASSED                                                                                                                            [ 34%]
test_mirrors.py::test_mirror_has_zim_file[www.mirrorservice.org] PASSED                                                                                                                                     [ 35%]
test_mirrors.py::test_mirror_has_zim_file[md.mirrors.hacktegic.com] PASSED                                                                                                                                  [ 36%]
test_mirrors.py::test_mirror_has_zim_file[ftp.nluug.nl] PASSED                                                                                                                                              [ 37%]
test_mirrors.py::test_mirror_has_zim_file[laotzu.ftp.acc.umu.se] PASSED                                                                                                                                     [ 38%]
test_mirrors.py::test_mirror_has_zim_file[mirror.isoc.org.il] PASSED                                                                                                                                        [ 39%]
test_mirrors.py::test_mirror_has_zim_file[mirror-sites-ca.mblibrary.info] PASSED                                                                                                                            [ 40%]
test_mirrors.py::test_mirror_has_zim_file[dumps.wikimedia.org] PASSED                                                                                                                                       [ 41%]
test_mirrors.py::test_mirror_has_zim_file[ftpmirror.your.org] PASSED                                                                                                                                        [ 43%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirror-sites-in.mblibrary.info] FAILED                                                                                                                     [ 44%]
test_mirrors.py::test_mirror_zim_has_contenttype[ftp.fau.de] PASSED                                                                                                                                         [ 45%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirrors.dotsrc.org] FAILED                                                                                                                                 [ 46%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirror.download.kiwix.org] PASSED                                                                                                                          [ 47%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirror-sites-fr.mblibrary.info] FAILED                                                                                                                     [ 48%]
test_mirrors.py::test_mirror_zim_has_contenttype[www.mirrorservice.org] PASSED                                                                                                                              [ 49%]
test_mirrors.py::test_mirror_zim_has_contenttype[md.mirrors.hacktegic.com] FAILED                                                                                                                           [ 50%]
test_mirrors.py::test_mirror_zim_has_contenttype[ftp.nluug.nl] PASSED                                                                                                                                       [ 51%]
test_mirrors.py::test_mirror_zim_has_contenttype[laotzu.ftp.acc.umu.se] PASSED                                                                                                                              [ 52%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirror.isoc.org.il] PASSED                                                                                                                                 [ 53%]
test_mirrors.py::test_mirror_zim_has_contenttype[mirror-sites-ca.mblibrary.info] FAILED                                                                                                                     [ 54%]
test_mirrors.py::test_mirror_zim_has_contenttype[dumps.wikimedia.org] PASSED                                                                                                                                [ 55%]
test_mirrors.py::test_mirror_zim_has_contenttype[ftpmirror.your.org] PASSED                                                                                                                                 [ 56%]
test_mirrors.py::test_mirror_zim_contenttype[mirror-sites-in.mblibrary.info] XFAIL (no content-type)                                                                                                        [ 58%]
test_mirrors.py::test_mirror_zim_contenttype[ftp.fau.de] PASSED                                                                                                                                             [ 59%]
test_mirrors.py::test_mirror_zim_contenttype[mirrors.dotsrc.org] FAILED                                                                                                                                     [ 60%]
test_mirrors.py::test_mirror_zim_contenttype[mirror.download.kiwix.org] PASSED                                                                                                                              [ 61%]
test_mirrors.py::test_mirror_zim_contenttype[mirror-sites-fr.mblibrary.info] XFAIL (no content-type)                                                                                                        [ 62%]
test_mirrors.py::test_mirror_zim_contenttype[www.mirrorservice.org] PASSED                                                                                                                                  [ 63%]
test_mirrors.py::test_mirror_zim_contenttype[md.mirrors.hacktegic.com] XFAIL (no content-type)                                                                                                              [ 64%]
test_mirrors.py::test_mirror_zim_contenttype[ftp.nluug.nl] FAILED                                                                                                                                           [ 65%]
test_mirrors.py::test_mirror_zim_contenttype[laotzu.ftp.acc.umu.se] PASSED                                                                                                                                  [ 66%]
test_mirrors.py::test_mirror_zim_contenttype[mirror.isoc.org.il] PASSED                                                                                                                                     [ 67%]
test_mirrors.py::test_mirror_zim_contenttype[mirror-sites-ca.mblibrary.info] XFAIL (no content-type)                                                                                                        [ 68%]
test_mirrors.py::test_mirror_zim_contenttype[dumps.wikimedia.org] PASSED                                                                                                                                    [ 69%]
test_mirrors.py::test_mirror_zim_contenttype[ftpmirror.your.org] PASSED                                                                                                                                     [ 70%]
test_mirrors.py::test_apk_exists PASSED                                                                                                                                                                     [ 72%]
test_mirrors.py::test_apk_permalink PASSED                                                                                                                                                                  [ 73%]
test_mirrors.py::test_apk_mirrors_list PASSED                                                                                                                                                               [ 74%]
test_mirrors.py::test_mirror_has_apk_file[mirror-sites-in.mblibrary.info] PASSED                                                                                                                            [ 75%]
test_mirrors.py::test_mirror_has_apk_file[ftp.fau.de] PASSED                                                                                                                                                [ 76%]
test_mirrors.py::test_mirror_has_apk_file[mirrors.dotsrc.org] PASSED                                                                                                                                        [ 77%]
test_mirrors.py::test_mirror_has_apk_file[mirror.download.kiwix.org] PASSED                                                                                                                                 [ 78%]
test_mirrors.py::test_mirror_has_apk_file[mirror-sites-fr.mblibrary.info] PASSED                                                                                                                            [ 79%]
test_mirrors.py::test_mirror_has_apk_file[md.mirrors.hacktegic.com] PASSED                                                                                                                                  [ 80%]
test_mirrors.py::test_mirror_has_apk_file[ftp.nluug.nl] PASSED                                                                                                                                              [ 81%]
test_mirrors.py::test_mirror_has_apk_file[mirror-sites-ca.mblibrary.info] PASSED                                                                                                                            [ 82%]
test_mirrors.py::test_mirror_apk_has_contenttype[mirror-sites-in.mblibrary.info] PASSED                                                                                                                     [ 83%]
test_mirrors.py::test_mirror_apk_has_contenttype[ftp.fau.de] PASSED                                                                                                                                         [ 84%]
test_mirrors.py::test_mirror_apk_has_contenttype[mirrors.dotsrc.org] PASSED                                                                                                                                 [ 86%]
test_mirrors.py::test_mirror_apk_has_contenttype[mirror.download.kiwix.org] PASSED                                                                                                                          [ 87%]
test_mirrors.py::test_mirror_apk_has_contenttype[mirror-sites-fr.mblibrary.info] PASSED                                                                                                                     [ 88%]
test_mirrors.py::test_mirror_apk_has_contenttype[md.mirrors.hacktegic.com] PASSED                                                                                                                           [ 89%]
test_mirrors.py::test_mirror_apk_has_contenttype[ftp.nluug.nl] PASSED                                                                                                                                       [ 90%]
test_mirrors.py::test_mirror_apk_has_contenttype[mirror-sites-ca.mblibrary.info] PASSED                                                                                                                     [ 91%]
test_mirrors.py::test_mirror_apk_contenttype[mirror-sites-in.mblibrary.info] PASSED                                                                                                                         [ 92%]
test_mirrors.py::test_mirror_apk_contenttype[ftp.fau.de] PASSED                                                                                                                                             [ 93%]
test_mirrors.py::test_mirror_apk_contenttype[mirrors.dotsrc.org] PASSED                                                                                                                                     [ 94%]
test_mirrors.py::test_mirror_apk_contenttype[mirror.download.kiwix.org] PASSED                                                                                                                              [ 95%]
test_mirrors.py::test_mirror_apk_contenttype[mirror-sites-fr.mblibrary.info] PASSED                                                                                                                         [ 96%]
test_mirrors.py::test_mirror_apk_contenttype[md.mirrors.hacktegic.com] PASSED                                                                                                                               [ 97%]
test_mirrors.py::test_mirror_apk_contenttype[ftp.nluug.nl] PASSED                                                                                                                                           [ 98%]
test_mirrors.py::test_mirror_apk_contenttype[mirror-sites-ca.mblibrary.info] PASSED
```
