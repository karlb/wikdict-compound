#!/bin/bash
mkdir -p comparison_output

if [ $# -ne 2 ]; then
    echo "Usage: $0 <two-character-language-code> <number-of-compound-words>"
    echo "Example: $0 de 100"
    exit 1
fi

if [ -f "comparison_output/$1_$2.orig.txt" ]; then
    time ./split_word.py "$1" "$2" > "comparison_output/$1_$2.txt" && \
    # git diff --no-index --word-diff "comparison_output/$1_$2.orig.txt" "comparison_output/$1_$2.txt"
    difft "comparison_output/$1_$2.orig.txt" "comparison_output/$1_$2.txt" --color=always | less -R
else
    echo No orig file exists, using this run as original checkpoint
    ./split_word.py "$1" "$2" > "comparison_output/$1_$2.orig.txt"
fi
