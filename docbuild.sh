#!/bin/bash

if ! command -v asciidoctor &> /dev/null
then
    echo "asciidoctor could not be found, please install it"
    exit
fi

python3 ./rmd_to_asciidoc.py src/rmd/*.rmd
asciidoctor -D github-pages index.adoc
asciidoctor -D github-pages hauptgerichte.adoc
asciidoctor -D github-pages basis_und_beilagen.adoc
asciidoctor -D github-pages nachspeisen_und_snacks.adoc
asciidoctor -D github-pages tagbook.adoc
mv recipes-metadata.json github-pages/
# cp -r images github-pages/
asciidoctor-pdf -D github-pages index.adoc
asciidoctor-pdf -D github-pages hauptgerichte.adoc
asciidoctor-pdf -D github-pages basis_und_beilagen.adoc
asciidoctor-pdf -D github-pages nachspeisen_und_snacks.adoc
asciidoctor-pdf -D github-pages tagbook.adoc
