
update-readme:
		cog -r README.md

deploy-to-wikdict-web:
	rsync -avz --progress -e ssh compound_dbs/*.sqlite3 www.wikdict.com:wikdict-prod/data/compound_dbs/
