#!/usr/bin/env python
#coding=utf8
import urllib
import pandas as pd
import json
import logging
import re2 as re
import chardet
import sys
from base_model import *
reload(sys)
sys.setdefaultencoding('utf8')
RECORD_FORMAT = "%(levelname)s [%(asctime)s,%(msecs)03d][%(filename)s:%(lineno)d][%(process)d:%(threadName)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=RECORD_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')

def load_data(filename):
    f = open(filename, 'r')
    data = f.readlines()
    f.close()
    logging.info('loading data[%s] done'%filename)
    return data

def data_filter(data_tranfered):
    data_tranfered = pd.DataFrame(data_tranfered)
    data = data_tranfered.drop_duplicates(['pid'], keep='last')
    logging.info('filter data done, data length[%s]'%data.shape[0])
    return data

def data_transfer(data):
    data_list = []
    for line in data:
        uni_code = re.compile(r'(\\u[0-9a-z]{4})')
        url_code = re.compile(r'((\%[A-Z0-9]{2}){3})')
        ascii_code = re.compile(r'(0X([A-Za-z0-9]{2}))')
        uni_code_U = re.compile(r'(\U[0-9a-z]{4}\s)')
        line = re.sub(uni_code, lambda x: x.group().decode('unicode-escape'), line)
        line = re.sub(url_code, lambda x: urllib.unquote(str(x.group())), line)
        line = re.sub(ascii_code, lambda x: chr(int(x.group(), 16)) ,line)
        line = re.sub(uni_code_U, lambda x: ('\u' + x.group()[1:]).decode('unicode-escape'), line)
        if '♥' in line.replace(' ', ''):
            continue
        insert_data = json.loads(line.replace(' ', ''), encoding='utf-8')
        data_list.append(insert_data)
    logging.info('tranfer data done, data length[%s]'%len(data_list))
    return data_filter(data_list)

def get_table_msg():
    table_name = 'tmall_data'
    table_define = {
        'table_name' : table_name,
        'table_primary_key' : ['pid'],
        'table_uniques' : [
            {'uniques_pid':['pid']},
        ],
        'table_fields' : [
            ('`pid`', 'int(10) unsigned', 'NOT NULL'),
            ('`brand`', 'text', 'NOT NULL'),
            ('`product_name`', 'varchar(255)', 'NOT NULL'),
            ('`price`', 'float', 'NOT NULL'),
            ('`monthly_sales`', 'float', 'NOT NULL'),
            ('`url`', 'varchar(255)', 'NOT NULL'),
            ('`store`', 'varchar(255)', 'NOT NULL'),
            ('`email`', 'varchar(255)', 'NOT NULL'),
        ],
    }
    return table_name, table_define

def get_db_config():
    db_config = {
        "host" : "localhost",
        "port" : 3306,
        "username" : "root",
        "password" : "root",
        "dbname" : "work",
        "charset" : "utf8mb4",
    }
    return db_config

def db_operation(data):
    model = BaseModel(get_db_config())
    table_name, table_define = get_table_msg()
    sql = BaseModel.gen_create_table_sql(table_define)
    model._query_table(sql)
    data = data.to_dict('records')
    for row in data:
        row.pop('id')
        model._insert_table(table_name, row)
    logging.info('save to mysql done! data length[%s]'%len(data))

def run(filename):
    data = load_data(filename)
    data_tranfered = data_transfer(data)
    db_operation(data_tranfered)

if __name__ == '__main__':
    run('data.json')
