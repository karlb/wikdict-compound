import sqlite3
from pathlib import Path
import statistics

supported_langs = "de en fi nl sv".split()
query_count = 0


DEBUG_QUERY_LOG = False


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
            group_concat(DISTINCT part_of_speech) AS part_of_speech_list,
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
                coalesce(rel_score, 0.1)
                    * score_factor
                    -- Affixes are not that important words in a normal
                    -- dictionary, but for in compound words, they are very likely
                    -- and should be prioritized.
                    * CASE
                        WHEN substr(other_written, 1, 1) = '-' OR substr(other_written, -1, 1) = '-'
                        THEN 2
                        ELSE 1
                    END
                    AS rel_score,
                written_rep,
                part_of_speech
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
                LEFT JOIN rel_importance ON (written_rep = written_rep_guess)
            WHERE other_written != '' -- Why are there forms without text?
              AND NOT (length(other_written) = 1 AND affix_type IS NULL)
              AND (
                part_of_speech NOT IN (
                    'interjection', 'pronoun', 'proverb', 'phraseologicalUnit', 'symbol',
                    'article', 'idiom', 'properNoun')
                )
        )
        GROUP BY 1, 2;
        
        CREATE INDEX compound_splitter_idx ON compound_splitter(other_written);
    """
    )

    # Language specific data changes
    if lang == "de":
        conn.executescript(
            """
            -- "sein" has the form "ist" which would override the "-ist" suffix due to its high importance
            DELETE FROM compound_splitter WHERE written_rep = 'sein';
        """
        )


class NoMatch(Exception):
    pass


def sol_score(solution):
    return (
        statistics.geometric_mean(score for part, score, match in solution)
        / len(solution) ** 2
    )


def get_potential_matches(compound, r, lang):
    match = r["other_written"].lower()
    yield match
    pos_list = r["part_of_speech_list"].split(",")

    if lang == "sv":
        if "verb" in pos_list:
            if match.endswith("a"):
                yield match[:-1]

    elif lang == "de":
        if "noun" in pos_list:
            if not match.endswith("s") and compound.startswith(match + "s"):
                yield match + "s"


def find_matches_in_db(db_path, lang, compound: str, ignore_word=None, first_part=True):
    conn = sqlite3.connect(Path(db_path) / f"{lang}-compound.sqlite3")
    conn.row_factory = sqlite3.Row
    global query_count
    query = """
        SELECT *
        FROM (
            SELECT DISTINCT
                other_written,
                length(other_written) * rel_score AS rel_score,
                affix_type,
                written_rep,
                part_of_speech_list
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
        ORDER BY rel_score DESC
        LIMIT 3
    """
    bindings = dict(compound=compound, ignore_word=ignore_word, first_part=first_part)
    # if query_count == 0:
    #     print_query_plan(conn, query, bindings)
    result = conn.execute(query, bindings).fetchall()

    query_count += 1
    if DEBUG_QUERY_LOG:
        with open("query.log", "a") as f:
            f.write(compound + "\n")
            for r in result:
                f.write(str(dict(r)) + "\n")

    return result


def split_compound_interal(
    db_path,
    lang: str,
    compound: str,
    ignore_word=None,
    first_part=True,
    all_results=False,
    rec_depth=0,
):
    if rec_depth > 10:
        raise Exception(f"Too deep recursion when trying to resolve {compound!r}")

    result = find_matches_in_db(db_path, lang, compound, ignore_word, first_part)
    if not result:
        raise NoMatch()

    solutions = []
    best_score = max(r["rel_score"] for r in result)
    for r in result:
        if r["rel_score"] < best_score / 4:
            break
        for match in get_potential_matches(compound, r, lang):
            rest = compound.replace(match, "", 1)
            if not rest:
                if r["affix_type"] in [None, "suffix"]:
                    solutions.append([(r["written_rep"], r["rel_score"], match)])
                continue
            try:
                splitted_rest = split_compound_interal(
                    db_path, lang, rest, first_part=False, rec_depth=rec_depth + 1
                )
            except NoMatch:
                continue
            solutions.append(
                [(r["written_rep"], r["rel_score"], match)] + splitted_rest
            )

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


def split_compound(
    db_path,
    lang: str,
    compound: str,
    ignore_word=None,
    all_results=False,
):
    compound = compound.lower()
    return split_compound_interal(
        db_path, lang, compound, ignore_word, first_part=True, all_results=all_results
    )


def print_query_plan(conn, query, bindings={}):
    depth_of = {0: -1}
    result = conn.execute("EXPLAIN QUERY PLAN " + query, bindings).fetchall()
    for r in result:
        depth = depth_of[r["parent"]] + 1
        depth_of[r["id"]] = depth
        print("|  " * depth + r["detail"])
