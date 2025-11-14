# FX-Quotes
Foreign exchange micro service in python/django.

Supports the following currencies:
- USD
- EUR
- KES
- NGN

## Setup and running
The project use uv to run commands and manage dependencies.
On the project root,
```
uv venv .venv
uv sync 
uv run manage.py migrate 
uv run manage.py loaddata app/fixture/currencies.json
uv rum manage.py runserver
```
If you want you can use docker 
```
docker-compose up --build
```
On another shell run to setup the database.
```
docker-compose exec web uv run manage.py migration
```
Next, load the supported currencies

```
docker-compose exec web uv run manage.py loaddata app/fixture/currencies.json
```


## Design approach and key decisions
## Known limitations
- No historical rate data
## Any assumptions you made
