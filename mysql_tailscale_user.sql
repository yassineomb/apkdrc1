DROP USER IF EXISTS 'anr_app'@'100.122.199.48';

CREATE USER 'anr_app'@'100.122.199.48' IDENTIFIED BY '7x#K9$mP!vR2$zLg';

GRANT SELECT, INSERT, UPDATE
ON anr_renseignement_db.fiches
TO 'anr_app'@'127.0.0.1';

FLUSH PRIVILEGES;