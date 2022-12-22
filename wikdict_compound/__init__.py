import sqlite3
from pathlib import Path
import statistics

supported_langs = "de en fi nl sv".split()
query_count = 0


def make_db(lang, input_path, output_path):
    output_path = Path(output_path)
    output_path.mkdir(exist_ok=True)
    outfile = output_path / f"{lang}-compound.sqlite3"
    outfile.unlink(missing_ok=True)
    conn = sqlite3.connect(outfile)
    conn.executescript(
        rf"""
        ATTACH DATABASE '{input_path}/{lang}.sqlite3' AS generic;

        CREATE TABLE compound_splitter AS
        SELECT 
            other_written,
            affix_type,
            max(rel_score) AS rel_score,
            first_value(written_rep) OVER (
                PARTITION BY other_written, affix_type
                ORDER BY rel_score DESC
            ) AS written_rep
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
                    SELECT other_written, written_rep, part_of_speech,
                        CASE "case"
                            WHEN 'GenitiveCase' THEN 1
                            ELSE 0.5
                        END AS score_factor
                    FROM generic.form
                        JOIN entry USING (lexentry)
                    WHERE
                        -- Multi-word entries oftentimes don't have all words included
                        -- in the form, resulting in misleading forms, so let's exclude
                        -- those.
                        written_rep NOT LIKE '% %'
                    UNION ALL
                    SELECT written_rep, written_rep, part_of_speech, 1 AS score_factor
                    FROM generic.entry
                )
                JOIN rel_importance ON (written_rep = written_rep_guess)
            WHERE other_written != '' -- Why are there forms without text?
              AND NOT (length(other_written) = 1 AND affix_type IS NULL)
              AND (
                part_of_speech IS NULL
                OR part_of_speech NOT IN (
                    'interjection', 'pronoun', 'proverb', 'phraseologicalUnit', 'symbol',
                    'article', 'idiom', '')
                )
        )
        GROUP BY 1, 2;
        
        CREATE INDEX compound_splitter_idx ON compound_splitter(other_written);
    """
    )


class NoMatch(Exception):
    pass


def sol_score(solution):
    return (
        statistics.geometric_mean(score for part, score, match in solution)
        / len(solution) ** 2
    )


def split_compound(
    db_path, lang, compound, ignore_word=None, first_part=True, all_results=False
):
    conn = sqlite3.connect(Path(db_path) / f"{lang}-compound.sqlite3")
    conn.row_factory = sqlite3.Row
    compound = compound.lower()
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
        LIMIT 3
    """
    bindings = dict(compound=compound, ignore_word=ignore_word, first_part=first_part)
    # if query_count == 0:
    #     print_query_plan(conn, query, bindings)
    query_count += 1
    result = conn.execute(query, bindings).fetchall()
    if not result:
        raise NoMatch()

    solutions = []
    best_score = max(r["rel_score"] for r in result)
    for r in result:
        # if r['rel_score'] < best_score / 4:
        #     break
        match = r["other_written"].lower()
        rest = compound.replace(match, "", 1)
        if not rest:
            if r["affix_type"] in [None, "suffix"]:
                solutions.append([(r["written_rep"], r["rel_score"], match)])
            continue
        try:
            splitted_rest = split_compound(db_path, lang, rest, first_part=False)
        except NoMatch:
            continue
        solutions.append([(r["written_rep"], r["rel_score"], match)] + splitted_rest)

    if not solutions:
        raise NoMatch()

    solutions.sort(key=sol_score, reverse=True)
    # for s in solutions:
    #     print(s)
    # print('\t', compound, solutions[0])
    if all_results:
        return solutions
    else:
        return solutions[0]


def print_query_plan(conn, query, bindings={}):
    depth_of = {0: -1}
    result = conn.execute("EXPLAIN QUERY PLAN " + query, bindings).fetchall()
    for r in result:
        depth = depth_of[r["parent"]] + 1
        depth_of[r["id"]] = depth
        print("|  " * depth + r["detail"])
