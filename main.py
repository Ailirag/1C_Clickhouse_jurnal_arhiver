import sys
import os
import requests
import shutil
from datetime import datetime, timedelta
import configparser
import zipfile

current_path = os.getcwd()
path_to_settings = f'{current_path}{os.sep}settings.ini'
config_file = configparser.ConfigParser()


class Test(object):
    def __init__(self):
        self.status_code = 200
        self.text = '20220330000000.lgp'


class LOGS_TABLES:
    tables_str = 'system.asynchronous_metric_log, ' \
                 'system.metric_log,' \
                 'system.query_log,' \
                 'system.query_thread_log,' \
                 'system.trace_log'
    tables = tables_str.split(',')


def logging(text):
    with open(f'{os.getcwd() + os.sep}log.txt', 'a', encoding='utf8') as log_file:
        for log_text in text.split('\n'):
            log_file.write(f'{datetime.now()} :   {log_text}\n')


def date_serialization(file_name):
    mas_name = file_name.split('.')
    if len(mas_name) > 2 or len(mas_name) == 1:
        return datetime(3999, 12, 31)
    if mas_name[1][:3] == 'lgp' or mas_name[1][:3] == 'lgx':
        date_in_name = mas_name[0]
        loc_year = int(date_in_name[:4])
        loc_month = int(date_in_name[4:6])
        loc_day = int(date_in_name[6:8])
        loc_hour = int(date_in_name[8:10])
        loc_minutes = int(date_in_name[10:12])
        serialized = datetime(loc_year, loc_month, loc_day, loc_hour, loc_minutes)
        return serialized
    else:
        return datetime(3999, 12, 31)


if not os.path.exists(path_to_settings):
    logging('settings.ini not find and will be created.')
    config_file['DEFAULT']['clickhouse_url'] = ''
    config_file['DEFAULT']['clickhouse_user'] = ''
    config_file['DEFAULT']['clickhouse_pwd'] = ''
    config_file['DEFAULT']['count_of_days_in_clickhouse'] = ''
    config_file['DEFAULT']['path_to_v8Logs'] = ''
    config_file['DEFAULT']['backup_path'] = ''
    config_file['DEFAULT']['archive_prefix'] = ''

    with open(path_to_settings, 'w', encoding='utf8') as configfile:
        config_file.write(configfile)

    logging('settings.ini created. Please fill it and restart program.')
    sys.exit()
else:
    config_file.read(path_to_settings, encoding='utf8')
    clickhouse_url = config_file['DEFAULT']['clickhouse_url']
    clickhouse_user = config_file['DEFAULT']['clickhouse_user']
    clickhouse_pwd = config_file['DEFAULT']['clickhouse_pwd']
    count_of_days_in_clickhouse = config_file['DEFAULT']['count_of_days_in_clickhouse']
    path_to_v8Logs = config_file['DEFAULT']['path_to_v8Logs']
    backup_path = config_file['DEFAULT']['backup_path']
    archive_prefix = config_file['DEFAULT']['archive_prefix']

    if not clickhouse_url \
            or not clickhouse_user \
            or not path_to_v8Logs \
            or not backup_path:
        logging('All fields on settings.ini must be filled in. Please will it and restart program.')
        sys.exit()


def archiving_v8logs(file_name):
    try:
        logging(f'archiving date {file_name[:-4]}')
        name_archive = f'{path_to_v8Logs}{os.sep}{archive_prefix}{file_name[:-4]}.zip'
        name_backup = f'{backup_path}{os.sep}{archive_prefix}{file_name[:-4]}.zip'
        with zipfile.ZipFile(name_archive, 'w') as myzip:
            myzip.write(f'{path_to_v8Logs}{os.sep}{file_name[:-4]}.lgx', compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=7)
            myzip.write(f'{path_to_v8Logs}{os.sep}{file_name}', compress_type=zipfile.ZIP_DEFLATED, compresslevel=7)
        logging(f'Try to move in repo: {backup_path}')
        shutil.move(name_archive, name_backup)
        return True
    except Exception as e:
        error_exc = str(type(e)) + str(e)
        logging(f'Archiving failed with an error: {error_exc}')
        return False


def start_mutations_on_clickhouse(date_border):
    count_days = timedelta(days=int(count_of_days_in_clickhouse))
    cleaning_border = date_border - count_days

    if len(str(cleaning_border.month)) == 1:
        month = f'0{cleaning_border.month}'
    else:
        month = cleaning_border.month

    if len(str(cleaning_border.day)) == 1:
        day = f'0{cleaning_border.day}'
    else:
        day = cleaning_border.day

    cleaning_border_str = f'{cleaning_border.year}{month}{day}230000'
    headers = {'X-ClickHouse-User': f'{clickhouse_user}',
               'X-ClickHouse-Key': f'{clickhouse_pwd}'}
    sql = f"alter table v8logs.EventLogItems DELETE WHERE FileName < '{cleaning_border_str}.lgp'"
    result = requests.request('POST', f'{clickhouse_url}', headers=headers, data=sql)
    if result.status_code == 200:
        logging('Mutation on deleting data in clickhouse started.')

    date_event = f'{cleaning_border.year}-{month}-{day}'
    logging('Clearing log tables...')
    try:
        for table in LOGS_TABLES.tables:
            sql = f"alter table {table} delete where event_date < '{date_event}'"
            result = requests.request('POST', f'{clickhouse_url}', headers=headers, data=sql)
            if result.status_code != 200:
                logging(f'Mutation for table [{table}] not started. Response code = {result.status_code}')
        logging('Success')
    except Exception as e:
        error_exc = str(type(e)) + str(e)
        logging(f'Cleaning log tables failed with an error: {error_exc}')


if __name__ == '__main__':

    logging('Start iteration.\nGet request.')

    data = requests.request('GET',
                            f'{clickhouse_url}/?user={clickhouse_user}&password={clickhouse_pwd}&query=select+max(FileName)+from+v8logs.EventLogItems')

    # data = Test()

    status_code = data.status_code

    logging(f'Status code: {status_code}')

    if status_code == 200:
        date_border = date_serialization(data.text)
        logging(f'Border file: [{date_border}].\nTrying to archiving earlier files')
        # lgp lgx
        mas_delete = []
        for file_name in os.listdir(f'{path_to_v8Logs}'):
            if file_name[-3:] != 'lgp':
                continue
            date = date_serialization(file_name)
            if date < date_border:
                mas_delete.append(file_name)
        if mas_delete:
            for file_name in mas_delete:
                try:
                    successfully = archiving_v8logs(file_name)
                    if successfully:
                        os.remove(f'{path_to_v8Logs}{os.sep}{file_name}')
                        os.remove(f'{path_to_v8Logs}{os.sep}{file_name[:-3]}lgx')
                        logging('Success')
                except Exception as e:
                    error_exc = str(type(e)) + str(e)
                    logging(f'Error archiving/deleting file [{file_name}]   :   {error_exc}')
                    sys.exit()

            logging('All files successfully deleted.')
        else:
            logging('Files earlier than border not finded.')
        if count_of_days_in_clickhouse:
            start_mutations_on_clickhouse(date_border)
    else:
        logging('Abort. Status != 200')
        sys.exit(0)
