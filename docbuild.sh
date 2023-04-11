#!/bin/bash

if ! command -v asciidoctor &> /dev/null
then
    echo "asciidoctor could not be found, please install it"
    exit
fi

./rmd_to_asciidoc.py src/rmd/*.rmd
asciidoctor -D github-pages index.adoc
# cp -r images github-pages/
# asciidoctor-pdf -D github-pages index.adoc