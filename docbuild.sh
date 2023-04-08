#!/bin/bash

if ! command -v asciidoctor &> /dev/null
then
    echo "asciidoctor could not be found, please install it"
    exit
fi

asciidoctor -D github-pages index.adoc
# cp -r images github-pages/