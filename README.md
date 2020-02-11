## Requirements

* Python 2.7
* Mysql 5.1+
* Redis
* pip
* virtualenv
* supervisor
* libmysqlclient-dev or similar

On ubuntu `sudo apt-get install mysql-server redis-server supervisor libjpeg-dev libmysqlclient-dev`, folowed by `pip install -r requirements/dev.txt` will do

## Configuration

`RBM2M_ENV` - App environment, one of Development, Production, Testing

`RBM2M_LOGIN` - management interface login

`RBM2M_PASSWORD` - management interface password
`SQLALCHEMY_DATABASE_URI` - MySQL connection settings, for example `mysql+mysqldb://rbm2m:rbm2m@127.0.0.1/rbm2m?charset=utf8mb4`

`REDIS_URL` - Redis connection settings, for example `redis://@localhost:6379/0`

`MEDIA_DIR` - Directory for images, must be writable. Default value: `APP_DIR/media`

`LOGS_DIR` - Directory for logs, must be writable. Default value: `APP_DIR/logs`

`MEDIA_BASEURL` - Public URL for `MEDIA_DIR`


## How to set up development environment

1. Create MySQL database and user, grant privileges

`mysql -u root`

```
CREATE DATABASE rbm2m;

CREATE USER 'rbm2m'@'localhost' IDENTIFIED BY 'rbm2m';

GRANT ALL PRIVILEGES ON rbm2m.* TO 'rbm2m'@'localhost';

FLUSH PRIVILEGES;

```

2. Set up environment variables

`export RBM2M_ENV=Development RBM2M_LOGIN=root RBM2M_PASSWORD=toor`

3. Create virtualenv and install dependencies

```
mkvirtualenv rbm2m

pip install --no-use-wheel -r requirements.txt
```

4. Create database and import genres

`make init`

