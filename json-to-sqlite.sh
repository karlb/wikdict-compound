cp /home/karl/code/github/wikdict-gen/dictionaries/processed/sv.sqlite3 sv.sqlite3
sqlite-utils memory compouds-se.json "SELECT lexemeLabel, group_concat(compoundLabel, ' || ') AS parts FROM \"compouds-se\" WHERE lexemeLabel NOT LIKE '-%' GROUP BY lexemeLabel" > compouds-se-grouped.json
sqlite-utils drop-table sv.sqlite3 test_data
sqlite-utils insert sv.sqlite3 test_data compouds-se-grouped.json
