import sqlite3
from pathlib import Path
import hashlib
import sys


DEBUG_DB = False


with open(__file__, "rb") as f:
    md5sum = hashlib.md5(f.read()).hexdigest()


def make_db(lang: str, input_path, output_path) -> None:
    output_path = Path(output_path)
    output_path.mkdir(exist_ok=True)
    outfile = output_path / f"{lang}-compound.sqlite3"

    # Skip recreation if up to date, otherwise delete existing
    if outfile.exists():
        conn = sqlite3.connect(outfile)
        try:
            existing_md5sum = conn.execute("SELECT md5sum FROM version").fetchone()[0]
        except sqlite3.OperationalError:
            existing_md5sum = None
        if existing_md5sum == md5sum:
            print(
                f"Compound splitting db {outfile} is already up to date.",
                file=sys.stderr,
            )
            return
        else:
            conn.close()
            outfile.unlink(missing_ok=True)

    # For debugging, it is very helpful to store all intermediate results
    temp_table = "TEMPORARY TABLE" if not DEBUG_DB else "TABLE"
    temp_view = "TEMPORARY VIEW" if not DEBUG_DB else "TABLE"

    conn = sqlite3.connect(outfile, isolation_level="IMMEDIATE")

    # sqlite's lower can only handle ascii (no Ä->ä)
    conn.create_function("py_lower", 1, lambda x: x.lower(), deterministic=True)
    lower = "lower" if lang != "de" else "py_lower"

    conn.executescript(
        rf"""
        CREATE TABLE version AS SELECT "{md5sum}" AS md5sum;

        ATTACH DATABASE '{input_path}/{lang}.sqlite3' AS generic;

        CREATE {temp_table} form_with_entry AS
        SELECT *
        FROM generic.form
            JOIN entry USING (lexentry)
        WHERE
            -- Multi-word entries oftentimes don't have all words included
            -- in the form, resulting in misleading forms, so let's exclude
            -- those.
            written_rep NOT LIKE '% %'
        ;

        CREATE {temp_view} terms_from_forms AS
        SELECT other_written, written_rep, part_of_speech,
            (
                0.5 -- prefer base entries to inflected forms
            ) AS score_factor
        FROM form_with_entry
        ;

        CREATE {temp_view} terms_from_entries AS
        SELECT written_rep AS other_written, written_rep, part_of_speech, 1 AS score_factor
        FROM generic.entry
        ;

        CREATE {temp_table} terms AS
        SELECT *, null AS rule FROM terms_from_forms
        UNION ALL
        SELECT *, null AS rule FROM terms_from_entries
        ;
    """
    )

    def remove_end(
        end, where="true", score_factor=0.2, replacement="", from_table="terms"
    ):
        if from_table == "terms":
            where += " AND rule IS NULL"
        conn.execute(
            f"""
            INSERT INTO terms
            SELECT
                substr(other_written, 1, length(other_written) - :l)
                    || :replacement
                    AS other_written,
                written_rep,
                part_of_speech,
                :score_factor AS score_factor,
                'remove-' || :end AS rule
            FROM {from_table}
            WHERE substr(other_written, -:l, :l) = :end
              AND {where}
        """,
            dict(
                l=len(end), end=end, score_factor=score_factor, replacement=replacement
            ),
        )

    # Language specific data changes
    if lang == "de":
        conn.executescript(
            """
            -- "sein" has the form "ist" which would override the "-ist" suffix due to its high importance
            -- "in" is easily used instead of the "-in" suffix
            DELETE FROM terms WHERE written_rep IN ('sein', 'in');
        """
        )
        remove_end("logie", replacement="log", score_factor=0.5)
        remove_end("e")
    if lang == "sv":
        # "-a" is better handled by the -a rule below
        conn.execute("DELETE FROM terms WHERE written_rep = '-a'")
        remove_end(
            "a",
            where="pos = 'verb' AND mood = 'Infinitive' AND voice = 'ActiveVoice'",
            from_table="form_with_entry",
        )

    conn.executescript(
        f"""
        CREATE {temp_view} terms_view AS
        SELECT
            written_rep,
            other_written,
            part_of_speech,
            -- Affixes are not that important words in a normal
            -- dictionary, but for in compound words, they are very likely
            -- and should be prioritized.
            score_factor * CASE
                WHEN affix_type == 'suffix' THEN 3
                WHEN affix_type IN ('infix', 'prefix') THEN 2
                ELSE 1
            END AS score_factor,
            affix_type
        FROM (
            SELECT
                written_rep,
                {lower}(trim(other_written, '-')) AS other_written,
                part_of_speech,
                score_factor,
                CASE
                    WHEN substr(other_written, 1, 1) = '-' AND substr(other_written, -1, 1) = '-' THEN 'infix'
                    WHEN substr(other_written, 1, 1) = '-' THEN 'suffix'
                    WHEN substr(other_written, -1, 1) = '-' THEN 'prefix'
                END AS affix_type
            FROM terms
        );

        CREATE {temp_view} compound_splitter_ungrouped AS
        SELECT
            other_written,
            affix_type,
            coalesce(rel_score, 0.1) * score_factor AS rel_score,
            written_rep,
            part_of_speech
        FROM terms_view
            LEFT JOIN rel_importance ON (written_rep = written_rep_guess)
        WHERE other_written != '' -- Why are there forms without text?
          AND NOT (length(other_written) = 1 AND affix_type IS NULL)
          AND (
            part_of_speech NOT IN (
                'interjection', 'pronoun', 'indefinitePronoun', 'proverb', 'phraseologicalUnit', 'symbol',
                'article', 'idiom', 'properNoun')
            );

        CREATE TABLE compound_splitter AS
        SELECT 
            other_written AS other_written,
            affix_type,
            group_concat(DISTINCT part_of_speech) AS part_of_speech_list,
            max(rel_score) AS rel_score,
            first_value(written_rep) OVER (
                PARTITION BY other_written, affix_type
                ORDER BY rel_score DESC
            ) AS written_rep
        FROM compound_splitter_ungrouped
        GROUP BY 1, 2;
        
        CREATE INDEX compound_splitter_idx ON compound_splitter(other_written);
    """
    )
