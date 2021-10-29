# EVE SDE Postgres updater

CLI utility for updating the EVE Online [static data export](https://developers.eveonline.com/resource/resources) postgres database.

This has been tested with the [Fuzzwork](https://www.fuzzwork.co.uk/dump/) postgres conversion but might work with other versions as well.

You should use a separate database for the sde and use for example [postgres_fdw](https://www.postgresql.org/docs/current/postgres-fdw.html) to use it with your main db.

## Table of Contents
- [Usage](#usage)
- [Prebuilt images](#prebuilt-images)
- [Examples](#examples)

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

## Prebuilt images

Images with the dump included are also available at [DockerHub](https://hub.docker.com/repository/docker/mjuopperi/eve_sde).

## Examples

### Postgres FWD

https://www.postgresql.org/docs/current/postgres-fdw.html

Setup docker so that your own db and the sde image are on the same network:

```yml
version: '3.9'
services :
  db:
    image: postgres:13-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: <username>
      POSTGRES_PASSWORD: <password>
      POSTGRES_DB: <db name>

  eve_sde_db:
    image: mjuopperi/eve_sde:2021-10-13_15-31-schema

networks:
  default:
    name: eve-dev-net
```

Connect to your own database and setup `postgres_fwd`:

```sql
-- Install the postgres_fdw extension
create extension postgres_fdw;
-- Create foreign server. "eve_sde_db" host is using docker networking.
create server sde_db foreign data wrapper postgres_fdw options (host 'eve_sde_db', port '5432', dbname 'sde');
-- Setup remote user
create user mapping for dev server sde_db options (user 'dev', password 'dev');

-- Create local schema
create schema evesde;
-- Import evesde schema to your database
import foreign schema evesde from server sde_db into evesde;
```

Select data like it was in your database:

```sql
select item_type."typeName", material_type."typeName", material.quantity
from "evesde"."invTypes" item_type
join "evesde"."invTypeMaterials" material on item_type."typeID" = material."typeID"
join "evesde"."invTypes" material_type on material_type."typeID" = material."materialTypeID"
where item_type."typeName" = 'Spodumain';
```

