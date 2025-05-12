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
!     <title>Kiwix Library</title><base target="_top" /><script type="text/javascript">document.domain = "library.kiwix.org";</script>
      <link
        type="text/css"
        href="{{root}}/skin/kiwix.css?KIWIXCACHEID"
***************
*** 39,44 ****
--- 39,46 ----
      <script src="{{root}}/skin/isotope.pkgd.min.js?KIWIXCACHEID" defer></script>
      <script src="{{root}}/skin/iso6391To3.js?KIWIXCACHEID"></script>
      <script type="text/javascript" src="{{root}}/skin/index.js?KIWIXCACHEID" defer></script>
+     <link rel="stylesheet" type="text/css" href="https://donorbox.org/animate-popup-donate-button.css">
+     <script type="text/javascript" id="donorbox-donate-button-installer" src="https://donorbox.org/install-donate-button.js" data-target="_blank" data-href="https://donorbox.org/kiwix?default_interval=m" data-style="background: rgb(255, 153, 51); color: rgb(255, 255, 255); text-decoration: none; font-family: Verdana, sans-serif; display: flex; font-size: 16px; padding: 8px 22px 8px 18px; border-radius: 5px 5px 0px 0px; gap: 8px; width: fit-content; line-height: 24px; position: fixed; top: 50%; transform-origin: center center; z-index: 9999; overflow: hidden; right: 20px; transform: translate(50%, -50%) rotate(-90deg);" data-button-cta="Support" data-img-src="https://donorbox.org/images/white_logo.svg"></script>
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

echo "Replacing final file…"

mv $TEMPLATE_TMP_PATH $TEMPLATE_PATH

echo "Cleaning up"

cleanup

echo "done."
