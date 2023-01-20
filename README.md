# wikdict-compound

[![PyPI](https://img.shields.io/pypi/v/wikdict-compound.svg)](https://pypi.org/project/wikdict-compound/)
[![Changelog](https://img.shields.io/github/v/release/karlb/wikdict-compound?include_prereleases&label=changelog)](https://github.com/karlb/wikdict-compound/releases)

This library splits compound words into the individual parts. It uses a large dictionary including inflected forms and keeps the amount of language specific rules to a minimum in order to support a variety of languages.
The dictionaries come from Wiktionary via [WikDict](https://www.wikdict.com/) and are licensed under [Creative Commons BY-SA](https://creativecommons.org/licenses/by-sa/3.0/).

## Installation

Install this library using `pip`:

    pip install wikdict-compound

## Usage

### Create Required Databases

To use wikdict-compound, you need a database with the required compound splitting dictionaries. These are created based on the WikDict dictionaries at <https://download.wikdict.com/dictionaries/sqlite/2/>. For each language you want to use
* Download the corresponding WikDict SQLite dictionary (e.g. `de.sqlite3` for German)
* Execute `make_db(lang, input_path, output_path)` where `input` path contains the WikDict dictionary and `output_path` is the directory where the generated compound splitting db should be placed.

### Split Compound Words

```
>>> from wikdict_compound import split_compound
>>> split_compound(db_path='compound_dbs', lang='de', compound='Bücherkiste')
Solution(parts=[
    Part(written_rep='Buch', score=63.57055093514545, match='bücher'),
    Part(written_rep='Kiste', score=33.89508861315521, match='kiste')
])
```

The returned solution object has a `parts` attribute, which contains the separate word parts in the correct order, along with the matched word part and a matching score (mostly interesting when comparing different splitting possibilites for the same word).

## Supported Languages and Splitting Quality

The results for each language are compared against compound word information from Wikidata.
For each language a success range is given, where the higher value includes all compounds where a splitting could be found while the lower value only counts those where the results are the same as on Wikidata.
Since some words have multiple valid splittings and the Wikidata entries are not perfect either, the true success rate should be somewhere within this range.

<!-- [[[cog
import cog
import subprocess
for lang in 'de en es fi fr it nl pl sv'.split():
    output = subprocess.check_output(
        f'./split_word.py {lang} | tail -1',
        shell=True,
        encoding='utf-8',
    )
    cog.out('* ' +output)
]]] -->
* de: 77.1%-95.6% success, tested over 2984 cases
* en: 67.7%-98.2% success, tested over 16061 cases
* es: 27.5%-75.6% success, tested over 1000 cases
* fi: 78.5%-96.9% success, tested over 65 cases
* fr: 15.2%-36.3% success, tested over 328 cases
* it: 18.4%-60.3% success, tested over 136 cases
* nl: 33.3%-100.0% success, tested over 3 cases
* pl: 30.9%-90.9% success, tested over 220 cases
* sv: 77.2%-97.7% success, tested over 5979 cases
<!-- [[[end]]] -->

## Development

To contribute to this library, first checkout the code. Then create a new virtual environment:

    cd wikdict-compound
    python -m venv .venv
    source .venv/bin/activate

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

<!--
To run the tests:

    pytest
-->

## Related Resources

The approach is similar to the one described in [Simple Compound Splitting for German](https://aclanthology.org/W17-1722) (Weller-Di Marco, MWE 2017). I can also recommend the paper as an overview of the problems and approaches to compound words splitting of German words.
