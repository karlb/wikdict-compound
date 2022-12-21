#!/usr/bin/env python3
import sys
import itertools
import sqlite3
import math
from wikdict_compound import make_db

if len(sys.argv) not in [2, 3] or len(sys.argv[1]) != 2:
    print(f"Usage: {sys.argv[0]} 2_LETTER_COUNTRY_CODE [LIMIT]")
    sys.exit(1)
lang = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

make_db(lang)

conn = sqlite3.connect(lang + "-compound.sqlite3")
conn.row_factory = sqlite3.Row
query_count = 0


class NoMatch(Exception):
    pass


def sol_score(solution):
    return math.prod(score for part, score in solution) / len(solution) ** 2


def print_query_plan(query, bindings={}):
    depth_of = {0: -1}
    result = conn.execute("EXPLAIN QUERY PLAN " + query, bindings).fetchall()
    for r in result:
        depth = depth_of[r["parent"]] + 1
        depth_of[r["id"]] = depth
        print("|  " * depth + r["detail"])


# TODO:
# - case
def split_word(word, ignore_word=None, first_part=True):
    word = word.lower()
    global query_count
    query = """
        SELECT *
        FROM (
            SELECT DISTINCT other_written, rel_score, affix_type, written_rep
            FROM compound_splitter
            WHERE (
                (
                    other_written <= :compound
                    AND other_written >= substr(:compound, 1, 2)
                    AND :compound LIKE other_written || '%'
                ) OR (
                    other_written = substr(:compound, 1, 1)
                )
            )
            --WHERE other_written <= :compound AND :compound LIKE other_written || '%'
            --WHERE other_written <= :compound AND other_written || 'z' > :compound
              AND other_written IS NOT lower(:ignore_word)
              AND (affix_type IS NULL OR :first_part = (affix_type = "prefix"))
            --LIMIT 20
        )
        ORDER BY length(other_written) * rel_score DESC
        LIMIT 2
    """
    bindings = dict(compound=word, ignore_word=ignore_word, first_part=first_part)
    # if query_count == 0:
    #     print_query_plan(query, bindings)
    query_count += 1
    result = conn.execute(query, bindings).fetchall()
    if not result:
        raise NoMatch()

    solutions = []
    best_score = max(r["rel_score"] for r in result)
    for r in result:
        # if r['rel_score'] < best_score / 4:
        #     break
        rest = word.replace(r["other_written"].lower(), "")
        if not rest:
            if r["affix_type"] in [None, "suffix"]:
                solutions.append([(to_base_form(r), r["rel_score"])])
            continue
        try:
            splitted_rest = split_word(rest, first_part=False)
        except NoMatch:
            continue
        solutions.append([(to_base_form(r), r["rel_score"])] + splitted_rest)

    if not solutions:
        raise NoMatch()

    solutions.sort(key=sol_score, reverse=True)
    # for s in solutions:
    #     print(s)
    # print('\t', word, solutions[0])
    return solutions[0]


def normalize(part):
    return part.replace("-", "")


def to_base_form(row):
    return row["written_rep"]


# +anläggningsingenjör
# +anmana
# print(split_word("ambassadörspost"))
# print(query_count, 'queries executed')
# exit()

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
        if "-s-" in parts:
            parts.remove("-s-")  # ignore genetiv-s
        normalized_test_parts = set(normalize(p) for p in parts)
        try:
            split = split_word(compound, ignore_word=compound)
            normalized_split_parts = set(normalize(p) for p, score in split) - {"s"}
            if split:
                counts["found"].append(split)
                match = normalized_test_parts == normalized_split_parts
                print(compound, parts, split, match)
                counts["passed" if match else "failed"].append([compound, parts, split])
            else:
                pass
        except NoMatch:
            continue

print(
    query_count,
    "queries executed (",
    query_count / len(counts["total"]),
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
