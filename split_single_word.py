#!/usr/bin/env python3
import sys
import itertools
import sqlite3
import wikdict_compound
from wikdict_compound import make_db, split_compound

if len(sys.argv) not in [3] or len(sys.argv[1]) != 2:
    print(f"Usage: {sys.argv[0]} 2_LETTER_COUNTRY_CODE WORD")
    sys.exit(1)
lang = sys.argv[1]
compound = sys.argv[2]

db_path = "compound_dbs"
make_db(lang, input_path="wikdict", output_path=db_path)


results = split_compound(
    db_path,
    lang,
    compound,
    ignore_word=compound,
    all_results=True,
    write_graph_to_file="graph.dot",
)
print()
for r in results:
    print("·".join(p.written_rep for p in r.parts))
    for p in r.parts:
        print("\t", p)
