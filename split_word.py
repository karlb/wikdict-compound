#!/usr/bin/env python3
import sys
import itertools
import sqlite3
import wikdict_compound
from wikdict_compound import make_db, split_compound, NoMatch

if len(sys.argv) not in [2, 3] or len(sys.argv[1]) != 2:
    print(f"Usage: {sys.argv[0]} 2_LETTER_COUNTRY_CODE [LIMIT]")
    sys.exit(1)
lang = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

db_path = "compound_dbs"
make_db(lang, input_path="wikdict", output_path=db_path)


def normalize(part):
    return part.lower().replace("-", "")


counts: dict[str, list] = dict(total=[], found=[], passed=[], failed=[])
with open(f"tests/wikidata/wikidata_{lang}.tsv") as f:
    grouped_by_compound = itertools.groupby(
        (line.rstrip("\n").split("\t") for line in f.readlines()),
        key=lambda line: line[0],
    )
    for compound, (lines_for_compound) in grouped_by_compound:
        if limit and len(counts["total"]) == limit:
            break
        if compound.endswith("bo"):
            continue
        parts = [part for comp, part in lines_for_compound]
        if len(parts) == 1:
            continue
        counts["total"].append(compound)
        normalized_test_parts = set(normalize(p) for p in parts)
        if lang in ("de", "sv"):
            normalized_test_parts -= {"s"}

        solution = split_compound(db_path, lang, compound, ignore_word=compound)
        if solution:
            normalized_split_parts = set(
                normalize(p.written_rep) for p in solution.parts
            )
            if lang in ("de", "sv"):
                normalized_split_parts -= {"s"}
            counts["found"].append(solution)
            correct = normalized_test_parts == normalized_split_parts
            print(
                compound,
                parts,
                [(p.written_rep, p.score) for p in solution.parts],
                correct,
            )
            counts["passed" if correct else "failed"].append(
                [compound, parts, solution]
            )
        else:
            pass

print(
    wikdict_compound.query_count,
    "queries executed (" + str(wikdict_compound.query_count / len(counts["total"])),
    "per compound).",
)
print("Counts:")
for key, val in counts.items():
    print("\t", key, len(val))

min_success = len(counts["passed"]) / len(counts["total"])
max_success = len(counts["found"]) / len(counts["total"])
print(
    f"{lang}: {min_success:.1%}-{max_success:.1%} success, tested over {len(counts['total'])} cases"
)
