#!/usr/bin/env python3
__author__ = 'Andriy Yatsynyak'
__version__ = '2.0'
__company__ = 'SOC Prime'


import argparse
import os
import locale
import datetime
import json
import logging
import logging.handlers
from copy import copy
import requests
import yaml


locale.setlocale(locale.LC_ALL, '')


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
USE_DATETIME = ''

LAST_DATETIME = datetime.datetime.utcnow().replace(microsecond=0)
FIRST_DATETIME = LAST_DATETIME - datetime.timedelta(days=30)


BASE_URL = 'https://api.tdm.socprime.com/v1/'
PREFIX_SEARCH = 'search-sigmas'
PREFIX_MAPPING = 'custom-field-mapping'


RES_FRM_FILE = 'txt'  # default
FRM_FILES = ['yaml', RES_FRM_FILE]
RES_DIR = os.path.join(BASE_DIR, 'output')


API_KEY = ''
MAPPING = False
CACHE_FILE_DATETIME = 'last_datetime.json'


FRM_DATETIME = '%Y-%m-%dT%H:%M:%S'
KEY_DATE_END = 'date_end'
KEY_DATE_START = 'date_start'


class Logger:
    def __init__(self, logger_name):
        logging.captureWarnings(True)
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        self.logPath = BASE_DIR

        if not os.path.exists(self.logPath):
            self.logPath = os.path.dirname(os.path.abspath(__file__))

        LOG_FILENAME = os.path.normpath(f'{self.logPath}/{logger_name}.log')

        fh = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=5242880, backupCount=10)
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s'))
        self.logger.addHandler(fh)

    def debug(self, msg):
        self.log(logging.DEBUG, msg)

    def info(self, msg):
        self.log(logging.INFO, msg)

    def warning(self, msg):
        self.log(logging.WARNING, msg)

    def error(self, msg):
        self.log(logging.ERROR,msg)

    def critical(self, msg):
        self.log(logging.CRITICAL, msg)

    def exception(self, msg):
        self.logger.exception(msg)

    def log(self, level, msg):
        msg = str(msg).replace('%', '')
        self.logger.log(level, f'{msg} %s', '')


def query_api(logger, **kwargs):
    headers = {
       'client_secret_id': API_KEY
    }
    headers.update(**kwargs)

    response = requests.get(f'{BASE_URL}{PREFIX_SEARCH}/', headers=headers)
    if not response.ok:
        logger.info(f'response data: {response.status_code}  {response.content} filter: {kwargs}')
        return False, response.content
    return True, response.json()


def get_mapping_api(logger):
    headers = {
       'client_secret_id': API_KEY
    }

    response = requests.get(f'{BASE_URL}{PREFIX_MAPPING}/', headers=headers)
    if not response.ok:
        logger.info(f'response data: {response.status_code}  {response.content}')
        return False, []
    return True, response.json()


def convert_name(s: str) -> str:
    return s.lower().strip().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace('.', '').replace('-', '_')


def save_info_in_file(siem_list: list):
    for siem in siem_list:
        siem_type = siem['siem_type']
        name = siem['case']['name']
        text = siem['sigma']['text']
        name_file = f'{convert_name(name)}_{convert_name(siem_type)}'

        path = os.path.join(RES_DIR, f'{name_file}.{RES_FRM_FILE}')
        if os.path.exists(path):
            if not os.path.isfile(path):
                print(f'error: this dir {path}')
                continue
            elif not os.access(path, os.W_OK):
                print(f"error: this file {path} and script "
                      f"{os.path.basename(__file__)} don't have rules of write")
                continue

        if RES_FRM_FILE == 'yaml':
            with open(path, 'w') as f:
                yaml.dump(text, f, default_flow_style=False)
        else:
            with open(path, 'w') as f:
                f.write(text)


def convert_str_into_datetime(s: str) -> datetime:
    return datetime.datetime.strptime(s, FRM_DATETIME)


def change_last_datetime(date_json):
    datetime_end = convert_str_into_datetime(date_json[KEY_DATE_END])
    date_json[KEY_DATE_END] = (datetime_end + datetime.timedelta(days=1)).strftime(FRM_DATETIME)
    date_json[KEY_DATE_START] = datetime_end.replace(second=0).strftime(FRM_DATETIME)
    return date_json


def save_last_datetime(date_json):
    with open(CACHE_FILE_DATETIME, 'w') as json_file:
        json.dump(date_json, json_file)


def is_date(logger, string: str) -> bool:
    try:
        datetime.datetime.strptime(string, FRM_DATETIME)
    except ValueError:
        logger.error(f'incorrect data format {string}, should be {FRM_DATETIME}')
        return False
    return True


def validate_json_frm(logger, data_json) -> bool:
    if any(k not in data_json for k in (KEY_DATE_END, KEY_DATE_START)):
        return False
    return all((is_date(logger, string) for string in data_json.values()))


def pre_validate_global_variable(logger):
    if not FRM_FILES:
        variable_msg = {
            'cache_file_datetime': CACHE_FILE_DATETIME,
            'frm_files': FRM_FILES
        }

        msg = """Error some variable empty or aren't correct:
                CACHE_FILE_DATETIME - {cache_file_datetime},
                FRM_FILES - {frm_files}
                """

        logger.error(msg.format(**variable_msg))
        exit(msg.format(**variable_msg))


def post_validate_global_variable(logger):
    if not (BASE_URL and API_KEY and CACHE_FILE_DATETIME and FRM_DATETIME and RES_DIR):
        variable_msg = {
            'base_url': BASE_URL,
            'api_key': 'XXXXXXXXXXXXX',
            'cache_file_datetime': CACHE_FILE_DATETIME,
            'frm_datetime': FRM_DATETIME,
            'res_dir': RES_DIR,
            'res_frm_file': RES_FRM_FILE
        }

        msg = """Error some variable empty or aren't correct:
        URL - {base_url}
        API_KEY - {api_key}
        CACHE_FILE_DATETIME - {cache_file_datetime}
        FRM_DATETIME_FILTER - {frm_datetime}
        RES_DIR  - {res_dir}
        RES_FRM_FILE - {res_frm_file}
        """

        logger.error(msg.format(**variable_msg))
        variable_msg['api_key'] = API_KEY
        exit(msg.format(**variable_msg))

    msg_err = 'error:'
    if not os.path.isdir(RES_DIR):
        try:
            os.mkdir(RES_DIR)
        except OSError as e:
            logger.error(f'{msg_err} to try create dir for path: {RES_DIR} error: {e}')
            exit(f'{msg_err} to try create dir for path: {RES_DIR}')
    elif not os.access(RES_DIR, os.W_OK):
        logger.error(f'{msg_err} this dir not have writeable rule: {RES_DIR}')
        exit(f'{msg_err} this dir not have writeable rule: {RES_DIR}')

    if USE_DATETIME and not is_date(logger, USE_DATETIME):
        logger.error(f'{msg_err} not correct variable {USE_DATETIME} for this format {FRM_DATETIME}')
        exit(f'{msg_err} not correct variable {USE_DATETIME} for this format {FRM_DATETIME}')


def run_query_apis(logger):
    mapping_list = []
    logger = logger
    logger.info(f'current last time: {LAST_DATETIME}')

    if MAPPING:
        status_mapping, mapping_list = get_mapping_api(logger)
        logger.info(f'information mapping list {mapping_list}')
        status_mapping or exit('error: to try get sigma mapping')

    while True:
        if not os.path.isfile(CACHE_FILE_DATETIME) or os.path.isfile(CACHE_FILE_DATETIME) \
                and not os.stat(CACHE_FILE_DATETIME).st_size:

            date_filter = dict.fromkeys((KEY_DATE_END, KEY_DATE_START),
                                        USE_DATETIME or FIRST_DATETIME.strftime(FRM_DATETIME))
            date_filter = change_last_datetime(date_filter)
        else:
            with open(CACHE_FILE_DATETIME) as json_file:
                date_filter = json.load(json_file)

            if not validate_json_frm(logger, date_filter):
                logger.error(f'not validate format file {CACHE_FILE_DATETIME} json-frm: {date_filter}')
                raise Exception(f'not validate file {CACHE_FILE_DATETIME}, need remove this file {CACHE_FILE_DATETIME}')

        logger.info(f'show date filter: {date_filter}')
        if MAPPING and mapping_list:
            kwargs = copy(date_filter)
            for mapping_name in mapping_list:
                kwargs['mapping_name'] = mapping_name
                status, data_json = query_api(logger, **kwargs)
                status and save_info_in_file(data_json)
        else:
            status, data_json = query_api(logger, **date_filter)
            status and save_info_in_file(data_json)

        datetime_obj = convert_str_into_datetime(date_filter[KEY_DATE_END])
        if datetime_obj >= LAST_DATETIME:
            date_filter[KEY_DATE_END] = LAST_DATETIME.strftime(FRM_DATETIME)
            date_filter[KEY_DATE_START] = (LAST_DATETIME.replace(second=0) -
                                           datetime.timedelta(minutes=5)).strftime(FRM_DATETIME)
            save_last_datetime(date_filter)
            logger.info(f'finish script: {datetime_obj} >= {LAST_DATETIME}')
            return
        date_filter = change_last_datetime(date_filter)
        save_last_datetime(date_filter)


def valid_str_date(s: str) -> str or None:
    now_date = LAST_DATETIME.replace(second=0)
    try:
        input_date = datetime.datetime.strptime(s, '%Y-%m-%d')
        if now_date <= input_date:
            raise AttributeError
        return input_date.strftime(FRM_DATETIME)
    except ValueError:
        msg = f"Not a valid date: '{s}'"
        raise argparse.ArgumentTypeError(msg)
    except AttributeError:
        msg = f"Not a valid date, this future date: '{s}'"
        raise argparse.ArgumentTypeError(msg)


if __name__ == '__main__':
    logger = Logger('run_script')
    pre_validate_global_variable(logger)

    parser = argparse.ArgumentParser(
        description=f'List commands for "{os.path.basename(__file__)}" script.')
    parser.add_argument('-d', '--path-dir',
                        type=str,
                        help='full path to directory')
    parser.add_argument('-k', '--api-key',
                        type=str,
                        help='secret api key')
    parser.add_argument('-f', '--format-file',
                        default='txt',
                        choices=list(FRM_FILES),
                        help='save format file:')
    parser.add_argument('-s',
                        '--startdate',
                        help='the start date - format: YYYY-MM-DD',
                        required=False,
                        type=valid_str_date)
    parser.add_argument('-m',
                        '--mapping-field',
                        action='store_true',
                        default=False,
                        help='get sigma mapping field rules')

    args = parser.parse_args()
    RES_DIR = args.path_dir or RES_DIR
    RES_FRM_FILE = args.format_file or RES_FRM_FILE
    API_KEY = args.api_key or API_KEY
    MAPPING = args.mapping_field or MAPPING

    if args.startdate:
        USE_DATETIME = args.startdate
        if os.path.exists(CACHE_FILE_DATETIME):
            try:
                os.remove(CACHE_FILE_DATETIME)
            except:
                logger.error(f"can't remove file {CACHE_FILE_DATETIME}")
                exit(f"error: can't remove file {CACHE_FILE_DATETIME}")

    post_validate_global_variable(logger)
    run_query_apis(logger)

