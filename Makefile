
update-readme:
		cog -r README.md

deploy-to-wikdict-web:
	rsync -avz --progress -e ssh compound_dbs www.wikdict.com:wikdict-prod/data/
