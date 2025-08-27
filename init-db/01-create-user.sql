-- Create export service database and user
CREATE DATABASE IF NOT EXISTS export_service;
CREATE USER IF NOT EXISTS 'export_user'@'%' IDENTIFIED BY 'export_password';
GRANT ALL PRIVILEGES ON export_service.* TO 'export_user'@'%';
FLUSH PRIVILEGES;