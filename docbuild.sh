#!/bin/bash

if ! command -v asciidoctor &> /dev/null
then
    echo "asciidoctor could not be found, please install it"
    exit
fi

asciidoctor -D build index.adoc
cp -r images build/