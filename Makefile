
update-readme:
	cog -r README.md

deploy-to-wikdict-web:
	rsync -tvz --progress -e ssh compound_dbs/*.sqlite3 piku.karl.berlin:/home/piku/.piku/data/wikdict/compound_dbs/
