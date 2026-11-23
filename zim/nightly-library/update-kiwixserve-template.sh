#!/bin/bash
set -e

TEMPLATE_PATH=/data/index-template.html
TEMPLATE_TMP_PATH="${TEMPLATE_PATH}.tmp"
TEMPLATE_SRC_PATH="${TEMPLATE_PATH}.src"
TEMPLATE_URL="https://github.com/kiwix/libkiwix/raw/refs/tags/${LIBKIWIX_VERSION}/static/templates/index.html"
KIWIX_PATCH=$(cat <<EOF
*** index.html	2024-10-29 12:16:01
--- index-kiwix.html	2024-10-29 12:18:18
***************
*** 4,10 ****
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <link type="root" href="{{root}}">
!     <title>Welcome to Kiwix Server</title>
      <link
        type="text/css"
        href="{{root}}/skin/kiwix.css?KIWIXCACHEID"
--- 4,10 ----
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <link type="root" href="{{root}}">
!     <title>[NIGHTLY] Nightly preview of Kiwix library</title><base target="_top" /><script type="text/javascript">document.domain = "nightly.library.kiwix.org";</script>
      <link
        type="text/css"
        href="{{root}}/skin/kiwix.css?KIWIXCACHEID"
***************
*** 39,44 ****
--- 39,45 ----
      <script src="{{root}}/skin/isotope.pkgd.min.js?KIWIXCACHEID" defer></script>
      <script src="{{root}}/skin/iso6391To3.js?KIWIXCACHEID"></script>
      <script type="text/javascript" src="{{root}}/skin/index.js?KIWIXCACHEID" defer></script>
+     <style type="text/css">html { border-top: 6px solid #ff3d00; } body { padding-bottom: 44px !important; } body::after { content: "\26A0  NIGHTLY BUILD \2014  preview of the Kiwix library, content may be unstable or incomplete. For the stable library, visit library.kiwix.org"; position: fixed; left: 0; right: 0; bottom: 0; z-index: 9999; padding: 10px 16px; background: repeating-linear-gradient(-45deg, #ff3d00 0 14px, #e63600 14px 28px); color: #fff; font: bold 15px/24px Verdana, sans-serif; text-align: center; letter-spacing: 0.5px; box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.3); pointer-events: none; }</style>
    </head>
    <body>
      <noscript>
EOF
)

cleanup() {
	rm -f $TEMPLATE_TMP_PATH $TEMPLATE_SRC_PATH
}

echo "Cleaning up…"

cleanup

echo "Downloading source template from libkiwix version ${LIBKIWIX_VERSION}…"

curl -o $TEMPLATE_SRC_PATH -L $TEMPLATE_URL

echo "Applying Kiwix Patch…"

echo "$KIWIX_PATCH" | patch --input=- --output=$TEMPLATE_TMP_PATH -p1 $TEMPLATE_SRC_PATH

echo "Replacing KIWIXCACHEID with ${LIBKIWIX_VERSION}"

sed -i "s/KIWIXCACHEID/$LIBKIWIX_VERSION/g" $TEMPLATE_TMP_PATH

echo "Replacing final file…"

mv $TEMPLATE_TMP_PATH $TEMPLATE_PATH

echo "Cleaning up"

cleanup

echo "done."