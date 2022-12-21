#!/usr/bin/env python3
import sys
import urllib.request
import urllib.parse
import re

if len(sys.argv) != 2 or len(sys.argv[1]) != 2:
    print(f'Usage: {sys.argv[0]} 2_LETTER_COUNTRY_CODE')
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
}    
ORDER BY ?lexemeLabel
"""
)

string_with_lang_re = re.compile(r'"(.*?)"@[\w-]+[\t\n]')

url_args = {"query": query}
req = urllib.request.Request(
    "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(url_args),
    headers={"Accept": "text/tab-separated-values"}
)
with urllib.request.urlopen(req) as response:
    with open(f"wikidata_{lang}.tsv", "w") as f:
        f.write(response.readline().decode('utf-8').replace('?', ''))  # header
        for line in response.readlines():
            fields = string_with_lang_re.findall(line.decode("utf-8"))
            f.write("\t".join(fields) + "\n")
