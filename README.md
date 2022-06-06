# 1C_Clickhouse_jurnal_arhiver
First you need to fill in the settings. The settings are stored in a dataset file using the library https://pypi.org/project/secure-settings/
reqired settings:
```
  clickhouse_url
  clickhouse_user
  clickhouse_pwd
  count_of_days_in_clickhouse
  path_to_v8logs
  backup_path
  archive_prefix
  database_name
```
use from_file option for simple filled https://pypi.org/project/secure-settings/

# Use
Add the program to the scheduler. Thats all.
