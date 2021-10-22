# EVE SDE Postgres updater

CLI utility for updating the EVE Online [static data export](https://developers.eveonline.com/resource/resources) postgres database.

This has been tested with the [Fuzzwork](https://www.fuzzwork.co.uk/dump/) postgres conversion but might work with other versions as well.

You should use a separate database for the sde and use for example [postgres_fdw](https://www.postgresql.org/docs/current/postgres-fdw.html) to use it with your main db.

## Usage

### Requirements

- Python 3
- [pipenv](https://github.com/pypa/pipenv#installation)
- [docker-compose](https://docs.docker.com/compose/install/) (if you want to use the included docker setup)

### Environment setup

    pipenv install

### Easy setup

    docker-compose up -d
    ./sde_updater.sh -e .env.local

### Custom settings

⚠️ NOTE: the script clears the entire database when restoring from the dump.  
⚠️ DO NOT USE THIS ON A DATABASE WHICH CONTENT YOU DO NOT WANT TO LOSE.

Make a copy of `.env.template` and save it as `.env`. Change settings as needed and run:

    ./sde_updater.sh

### Scheduling

The script keeps track of update history in `.update.log` and checks the latest entry against the "last-modified" header
of the Fuzzwork dumps. The databse is only updated if the dump is newer than your local version.

You can use `cron` or other scheduling tools to prediodically run this script to keep your database up to date.

### Docker network

By default, the included database container runs in a network named `eve-dev-net`.

You can change this by creating `.env` at the root of the project and setting 
`DOCKER_NETWORK_NAME` to the name of your desired network. 
