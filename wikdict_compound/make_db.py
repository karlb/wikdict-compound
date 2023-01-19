import sqlite3
from pathlib import Path


def make_db(lang: str, input_path, output_path) -> None:
    output_path = Path(output_path)
    output_path.mkdir(exist_ok=True)
    outfile = output_path / f"{lang}-compound.sqlite3"
    outfile.unlink(missing_ok=True)
    conn = sqlite3.connect(outfile)
    conn.executescript(
        rf"""
        ATTACH DATABASE '{input_path}/{lang}.sqlite3' AS generic;

        CREATE TEMPORARY VIEW form_with_entry AS
        SELECT *
        FROM generic.form
            JOIN entry USING (lexentry)
        WHERE
            -- Multi-word entries oftentimes don't have all words included
            -- in the form, resulting in misleading forms, so let's exclude
            -- those.
            written_rep NOT LIKE '% %'
        ;

        CREATE TEMPORARY VIEW terms_from_forms AS
        SELECT other_written, written_rep, part_of_speech,
            CASE "case"
                WHEN 'GenitiveCase' THEN 1
                ELSE 0.5
            END AS score_factor
        FROM form_with_entry
        ;

        CREATE TEMPORARY VIEW terms_from_entries AS
        SELECT written_rep, written_rep, part_of_speech, 1 AS score_factor
        FROM generic.entry
        ;

        CREATE TEMPORARY TABLE terms AS
        SELECT * FROM terms_from_forms
        UNION ALL
        SELECT * FROM terms_from_entries
        ;
    """
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
    if lang == "sv":
        conn.executescript(
            """
            -- "-a" is better handled by the -a rule below
            DELETE FROM terms WHERE written_rep = '-a';

            -- Remove -a from verb infinitives
            INSERT INTO terms
            SELECT
                substr(other_written, 1, length(other_written) - 1) AS other_written,
                written_rep,
                part_of_speech,
                0.2 AS score_factor
            FROM form_with_entry
            WHERE pos = 'verb'
                AND mood = 'Infinitive'
                AND voice = 'ActiveVoice'
                AND substr(other_written, -1, 1) = 'a'
        """
        )

    conn.executescript(
        """
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
            FROM terms
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
