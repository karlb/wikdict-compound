#!/usr/bin/env python3
import itertools
import sqlite3
import math

#conn = sqlite3.connect("/home/karl/code/github/wikdict-gen/dictionaries/processed/sv.sqlite3")
conn = sqlite3.connect("sv-compound.sqlite3")
conn.row_factory = sqlite3.Row

conn.executescript(r"""
    ATTACH DATABASE 'sv.sqlite3' AS generic;

    --DROP TABLE IF EXISTS compound_splitter;
    CREATE TABLE IF NOT EXISTS compound_splitter AS
    SELECT 
        other_written,
        affix_type,
        max(rel_score) AS rel_score,
        first_value(written_rep) OVER (PARTITION BY other_written, affix_type ORDER BY rel_score DESC) AS written_rep
    FROM (
        SELECT
            lower(trim(other_written, '-')) AS other_written,
            CASE
                WHEN substr(other_written, 1, 1) = '-' AND substr(other_written, -1, 1) = '-' THEN 'infix'
                WHEN substr(other_written, 1, 1) = '-' THEN 'suffix'
                WHEN substr(other_written, -1, 1) = '-' THEN 'prefix'
            END AS affix_type,
            rel_score * score_factor AS rel_score,
            written_rep
        FROM (
                SELECT other_written, written_rep,
                    CASE "case"
                        WHEN 'GenitiveCase' THEN 1
                        ELSE 0.5
                    END AS score_factor
                FROM generic.form
                    JOIN entry USING (lexentry)
                WHERE
                    lexentry NOT LIKE '%\_\_Pronomen\_\_%' ESCAPE '\'
                    -- Multi-word entries oftentimes don't have all words included
                    -- in the form, resulting in misleading forms, so let's exclude
                    -- those.
                    AND written_rep NOT LIKE '% %'
                UNION ALL
                SELECT written_rep, written_rep, 1 AS score_factor
                FROM generic.entry
            )
            JOIN rel_importance ON (written_rep = written_rep_guess)
        WHERE other_written != '' -- Why are there forms without text?
          AND NOT (length(other_written) = 1 AND affix_type IS NULL)
    )
    GROUP BY 1, 2
    ;
    
    CREATE INDEX IF NOT EXISTS compound_splitter_idx ON compound_splitter(other_written);
""")

query_count = 0


class NoMatch(Exception):
    pass

def sol_score(solution):
    return math.prod(score for part, score in solution) / len(solution)**2

def print_query_plan(query, bindings={}):
    depth_of = {0: -1}
    result = conn.execute("EXPLAIN QUERY PLAN " + query, bindings).fetchall()
    for r in result:
        depth = depth_of[r['parent']] + 1
        depth_of[r['id']] = depth
        print('|  ' * depth + r['detail'])

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
    best_score = max(r['rel_score'] for r in result)
    for r in result:
        # if r['rel_score'] < best_score / 4:
        #     break
        rest = word.replace(r['other_written'].lower(), '')
        if not rest:
            if r['affix_type'] in [None, 'suffix']:
                solutions.append([(to_base_form(r), r['rel_score'])])
            continue
        try:
            splitted_rest = split_word(rest, first_part=False)
        except NoMatch:
            continue
        solutions.append([(to_base_form(r), r['rel_score'])] + splitted_rest)

    if not solutions:
        raise NoMatch()

    solutions.sort(key=sol_score, reverse=True)
    # for s in solutions:
    #     print(s)
    # print('\t', word, solutions[0])
    return solutions[0]


def normalize(part):
    return part.replace('-', '')

def to_base_form(row):
    return row['written_rep']

# +anläggningsingenjör
# +anmana
# print(split_word("ambassadörspost"))
# print(query_count, 'queries executed')
# exit()

counts: dict[str, list] = dict(total=[], found=[], passed=[], failed=[])
with open('tests/wikidata/wikidata_sv.tsv') as f:
    grouped_by_compound = itertools.groupby(
            (line.rstrip('\n').split('\t') for line in f.readlines()),
            key=lambda line: line[0]
    )
    for compound, (lines_for_compound) in grouped_by_compound:
        if len(counts['total']) == 200:
            break
        if compound.endswith('bo'):
            continue
        parts = [part for comp, part in lines_for_compound]
        if len(parts) == 1:
            continue
        counts['total'].append(compound)
        if '-s-' in parts:
            parts.remove('-s-')  # ignore genetiv-s
        normalized_test_parts = set(normalize(p) for p in parts)
        try:
            split = split_word(compound, ignore_word=compound)
            normalized_split_parts = set(normalize(p) for p, score in split) - {'s'}
            if split:
                counts['found'].append(split)
                match = normalized_test_parts == normalized_split_parts
                print(compound, parts, split, match)
                counts['passed' if match else 'failed'].append([compound, parts, split])
            else:
                pass
        except NoMatch:
            continue

print(query_count, 'queries executed (', query_count / len(counts['total']),'per compound).')
print('Counts:')
for key, val in counts.items():
    print('\t', key, len(val))
