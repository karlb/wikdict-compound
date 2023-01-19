#!/usr/bin/env python3
import sys
import urllib.request
import urllib.parse
import re
from itertools import groupby

if len(sys.argv) != 2 or len(sys.argv[1]) != 2:
    print(f"Usage: {sys.argv[0]} 2_LETTER_COUNTRY_CODE")
    sys.exit(1)
lang = sys.argv[1]

query = (
    """
SELECT
  # ?lexeme
  ?lexemeLabel
  ?compoundLabel
WHERE {
  ?lexeme dct:language [wdt:P218 '"""
    + lang
    + """'] .
  ?lexeme wdt:P5238 ?compound .
  ?lexeme wikibase:lemma ?lexemeLabel .
  ?compound wikibase:lemma ?compoundLabel .
  # multi-word lexemes are not useful for testing compound splitting
  FILTER (!contains(?lexemeLabel, ' '))
}    
ORDER BY ?lexemeLabel
"""
)

string_with_lang_re = re.compile(r'"(.*?)"@[\w-]+[\t\n]')

url_args = {"query": query}
req = urllib.request.Request(
    "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(url_args),
    headers={"Accept": "text/tab-separated-values"},
)
with urllib.request.urlopen(req) as response:
    with open(f"wikidata_{lang}.tsv", "w") as f:
        f.write(response.readline().decode("utf-8").replace("?", ""))  # header
        for line in response.readlines():
            fields = string_with_lang_re.findall(line.decode("utf-8"))
            if len(fields) != 2:
                continue
            f.write("\t".join(fields) + "\n")


def normalize(word, lang):
    word = word.lower()
    if lang == "de":
        for match, replacement in [
            ("ä", "a"),
            ("ö", "o"),
            ("ü", "u"),
            ("ß", "ss"),
        ]:
            word = word.replace(match, replacement)
    return word


def find_part(compound, parts, lang):
    for try_compound, try_parts in [
        (compound, ((p, p) for p in parts)),
        (compound, ((p, p[:-1]) for p in parts)),
        (compound[1:], ((p, p) for p in parts)),
        # (compound[1:], ((p, p[1:]) for p in parts)),
        (compound, ((p, p[2:]) for p in parts)),
        # (compound, ((p, p[3:]) for p in parts)),
        (compound[2:], ((p, p) for p in parts)),
        (compound, ((p, p[:-2]) for p in parts)),
        (compound, ((p, p[1:]) for p in parts)),
    ]:
        for (orig_p, p) in try_parts:
            p = normalize(p, lang)
            if not p:
                continue
            # print("===", repr(try_compound), p, try_compound.startswith(p))
            if try_compound.startswith(p):
                return orig_p, try_compound.replace(p, "", 1)

    return None, None


# Group by compound and order parts
with (
    open(f"wikidata_{lang}.tsv") as in_file,
    open(f"wikidata_grouped_{lang}.tsv", "w") as out_file,
):
    in_file.readline()  # skip header
    split_lines = (line.rstrip().split("\t") for line in in_file.readlines())
    for compound, lines in groupby(split_lines, key=lambda fields: fields[0]):
        remaining_compound = normalize(compound, lang).strip("-")
        # Some entries are duplicated in our input data. We deduplicate them
        # and assume that no word contains the same part twice.
        parts = set(fields[1] for fields in lines)
        remaining_parts = list(
            sorted(
                (p.strip("-") for p in parts),
                key=lambda p: len(p),
                reverse=True,
            )
        )
        ordered_parts: list[str] = []
        while remaining_parts:
            found_part, remaining_compound = find_part(
                remaining_compound, remaining_parts, lang
            )
            if not found_part:
                break
            remaining_parts.remove(found_part)
            ordered_parts.append(found_part)
            # print(found_part, remaining_compound, remaining_parts)

        if remaining_parts:
            # We couldn't figure it out, keep parts unordered
            ordered_parts = list(parts)
            # print(f"Could not order {parts} in {compound}.")

        out_file.write("\t".join([compound] + ordered_parts) + "\n")
