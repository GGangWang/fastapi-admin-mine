#!/bin/bash
# Sourced by the official MySQL entrypoint on first initialization.
set -e
log_database=${MYSQL_LOG_DATABASE:-res-nexus-log}
# Escape SQL identifiers and string literals under a known SQL mode.
escaped_database=${log_database//\`/\`\`}
escaped_user=${MYSQL_USER//\'/\'\'}
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
CREATE DATABASE IF NOT EXISTS \`$escaped_database\` CHARACTER SET utf8mb4;
GRANT ALL PRIVILEGES ON \`$escaped_database\`.* TO '$escaped_user'@'%';
SQL
