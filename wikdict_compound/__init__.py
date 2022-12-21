import sqlite3
from pathlib import Path


def make_db(lang):
    outfile = Path(lang + "-compound.sqlite3")
    outfile.unlink(missing_ok=True)
    conn = sqlite3.connect(outfile)
    conn.executescript(rf"""
        ATTACH DATABASE '{lang}.sqlite3' AS generic;

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
        GROUP BY 1, 2;
        
        CREATE INDEX compound_splitter_idx ON compound_splitter(other_written);
    """)

