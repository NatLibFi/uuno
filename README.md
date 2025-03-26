# Uuno

Uuno is a simple URN resolver used by The National Library of Finland.

It requires the following software:
- Python
- PostgreSQL
- Flask
- Psycopg2

## Installation

More detailed installation instructions are not yet available, but these are the basic steps:

- Install Python.
- Install PostgreSQL:
  - Create a database using the database schema given in the file `uuno.schema`.
  - Edit the file `src/config_normal.py`:
    - `app_host` and `app_port` specify where you want to run your Flask server.
    - Edit `db_config` to match your database configuration.
  - It is probably a good idea to insert some (test) data into the database.
- Install Flask and psycopg2 from PyPI.

You can start the resolver by typing:

```sh
./resolver.py normal
```

## Functionality

For a given URN, the resolver is able to resolve it or provide metadata about it.

### Resolving

To resolve a URN, point your web browser to:

```
http://<your-host>/<path-to-your-resolver>/<URN>
```

For example:

```
http://127.0.0.1:5000/urn:nbn:fi-fe2024052134041
```

If the given URN is in the database, the URN resolver should return an HTTP code 303 (See Other).

### Metadata

To get metadata for a URN, point your web browser to:

```
http://<your-host>/<path-to-your-resolver>/rest/v1/metadata/<URN>
```

For example:

```
http://127.0.0.1:5000/rest/v1/metadata/urn:nbn:fi-fe2024052134041
```

might return something like this:

```json
{
    "urn": "urn:nbn:fi-fe2024052134041",
    "metadata": {
        "dc.creator": [
            "Vihervalli, Ulriika"
        ],
        "dc.title": [
            "Uniform Resource Name in National Libraries: a URN:NBN landscape report"
        ]
    },
    "locations": [
        {
            "url": "https://www.doria.fi/handle/10024/189022",
            "source": "the Doria Repository"
        }
    ]
}
```
