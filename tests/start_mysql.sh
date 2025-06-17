docker run --rm --name mysql \
-e MYSQL_USER=test_user \
-e MYSQL_PASSWORD=password \
-e MYSQL_ROOT_PASSWORD=password \
-e MYSQL_DATABASE=test_database \
-p 3306:3306 mysql:9