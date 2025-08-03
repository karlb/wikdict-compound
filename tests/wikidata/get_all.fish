#!/usr/bin/env fish
for lang in de en es fi fr it nl pl sv da
	echo $lang
	./get_from_wikidata.py $lang || fail
end
