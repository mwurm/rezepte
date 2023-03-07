#!/bin/bash

if ! command -v asciidoctor &> /dev/null
then
    echo "asciidoctor could not be found, please install it"
    exit
fi

asciidoctor -D build rezepte.adoc
cp -r images build/