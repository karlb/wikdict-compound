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
from wikdict_compound import split_compound

parts = split_compound(db_path='compound_dbs', lang='de', compound='Gartenschere')
```

This returns the list of words which form the compound in the correct order, along with a rating of the word importance, in this case `[('Garten', 1.4645167634735892), ('Schere', 1.1692122623775094)]`.

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
* de: 74.1%-96.8% success, tested over 2984 cases
* en: 64.0%-99.6% success, tested over 16061 cases
* es: 13.8%-31.8% success, tested over 1000 cases
* fi: 72.3%-89.2% success, tested over 65 cases
* fr: 13.1%-38.4% success, tested over 328 cases
* it: 16.2%-45.6% success, tested over 136 cases
* nl: 66.7%-100.0% success, tested over 3 cases
* pl: 25.5%-70.5% success, tested over 220 cases
* sv: 72.6%-96.7% success, tested over 5922 cases
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
