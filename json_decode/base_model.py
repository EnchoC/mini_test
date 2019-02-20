#!/usr/bin/env python
#coding=utf8
import json
import copy
from pprint import pprint 
import time
import socket
import MySQLdb
import MySQLdb.cursors
import logging
from datetime import datetime
RECORD_FORMAT = "%(levelname)s [%(asctime)s,%(msecs)03d][%(filename)s:%(lineno)d][%(process)d:%(threadName)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=RECORD_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')

class MyCursor(object):
    """
    set my cursor
    """
    __PASS = 0
    def __init__(self, base_model, cursor_class=MySQLdb.cursors.DictCursor):
        self._cursor_class = cursor_class
        self._base_model = base_model
        self.connect()
        self.retry_time = 3
    
    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def connect(self):
        self._cursor = self._base_model._db_conn.cursor(self._cursor_class)

    def close(self):
        if self._cursor is not None:
            self._cursor.close()
        self._cursor = None
    
    def _execute(self, *args, **kwargs):
        for x in xrange(self.retry_time):
            try:
                self._base_model._get_db() if self._cursor is None else self.__PASS
                self.connect()
                return self._cursor.execute(*args, **kwargs)
            except Exception as e:
                # TODO(Yingzhao): bulk insert deadlock problem
                logging.error("run excute error[retry : %s, e: %s]" % (x+1, e))
                raise
        return None

    def execute(self, *args, **kwargs):
        begin_time = datetime.now()
        res = self._execute(*args, **kwargs)
        runtime = (datetime.now() - begin_time).seconds
        logging.info("excute sql done[runtime: %d, args: %s, kwargs: %s, host_info: %s]",runtime, args, kwargs, self._cursor.connection.get_host_info())
        return res

class BaseModel(object):
    _charset = 'utf8mb4'
    _db_conn = None
    _time_fields = ['insert_time','update_time']
    __PASS = 0

    def __init__(self, db_config, db_conn_retry=3):
        self._db_conn_retry = db_conn_retry
        self._db_config = db_config
    
    def db_free(self):
        self._db_conn.close()
        self._db_conn = None

    def __get_db_conn(self):
        _timeout = 10
        db = self._db_config
        flag = False
        for x in xrange(self._db_conn_retry, -1, -1):
            try:
                host = socket.gethostbyname(db['host'])
                db_conn = MySQLdb.connect(host = host, user = db['username'], passwd = db['password'], db = db['dbname'], charset = db['charset'], port = db['port'], connect_timeout = _timeout)
                self._charset = db['charset']
                flag = True
            except Exception as e:
                logging.warning('connect mysql failed. host[%s], retry_remain[%d] e[%s]'%db['host'], x, e, exc_info=True)
            if flag:
                break
            time.sleep(3)
        if not flag:
            logging.warning('failed to connect mysql')
            return None, None
        return db_conn, db
    
    def get_db_cursor(self):
        return MyCursor(self)

    def _get_db(self):
        # TODO(Yingzhao): master/slave table
        # init the database
        if self._db_conn:
            return self._db_conn
        (self._db_conn, db) = self.__get_db_conn()
        db_cursor = self.get_db_cursor()
        if None == self._db_conn:
            raise RuntimeError, "RuntimeError get db connection failed class[%s] __init__(self)"%self.__class__
        if 'utf8mb4' == self._charset:
            db_cursor.execute("SET names utf8mb4 collate utf8mb4_unicode_ci;")
        db_cursor.execute("SET autocommit=1;")
        return self._db_conn
    
    def escape_string(self, v):
        return self._db_conn.escape_string(v.encode("utf8"))
    
    def _escape_string(self, v):
        return MySQLdb.escape_string(v.encode("utf8"))

    def __escape_string(self, v, escape=True):
        if isinstance(v, (str, unicode)):
            return self.escape_string(v) if escape else v
        elif isinstance(v, (dict, list)):
            return self.escape_string(str(v))
        else:
            return v

    def __gen_where(self, where_dict):
        pprint(where_dict)
        tmp = ' AND '.join(["`%s`='%s'"%(k, self.__escape_string(v)) for k,v in where_dict.items()])
        return 'WHERE %s'% tmp

    @classmethod
    def gen_create_table_sql(self, table_define):
        # gen sql by BaseModel.gen_create_table_sql(table_define)
        """
        # input & output demo
        table_define = {
            'table_name' : 'user_contact',
            'table_primary_key' : ['user_id', 'contact_id'],
            'table_indexs' : [
                {'query_by_phone':['phone']},
                {'query_by_phone_address':['phone','address']}
            ],
            'table_uniques' : [
                {'unique_username':['username']},
                {'unique_contact_id':['contact_id']}
            ],
            'table_options': [
                'AUTO_INCREMENT=50000000',
            ],
            'table_fields' : [
                ('`user_id`', 'int(10) unsigned', 'NOT NULL', 'AUTO_INCREMENT'),
                ('`username`', 'varchar(255)', 'NOT NULL'),
                ('`phone`', 'varchar(255)', 'NOT NULL'),
                ('`address`', 'varchar(255)', 'NOT NULL'),
                ('`contact_id`', 'varchar(255)', 'NOT NULL'),
                ('`avatar_data`', 'text', 'NOT NULL'),
                ('`avatar_resize_s`', 'mediumblob', 'NOT NULL'),
            ],
        }
        -----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS `user_contact` (
         `user_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
         `username` varchar(255) NOT NULL,
         `phone` varchar(255) NOT NULL,
         `address` varchar(255) NOT NULL,
         `contact_id` varchar(255) NOT NULL,
         `avatar_data` text NOT NULL,
         `avatar_resize_s` mediumblob NOT NULL,
         PRIMARY KEY (`user_id` ,`contact_id`),
         UNIQUE unique_username (`username`),
         UNIQUE unique_contact_id (`contact_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 
         AUTO_INCREMENT=50000000;
         
        """
        sql_fragment = []
        _table_define = copy.deepcopy(table_define)
        _table_define['table_fields'].extend([
            ('`insert_time`', 'int(10)', 'NOT NULL', "DEFAULT 0"),
            ('`update_time`', 'int(10)', 'NOT NULL', "DEFAULT 0")])
        sql_fragment.append("CREATE TABLE IF NOT EXISTS `%s` ("% _table_define['table_name'])
        sql_fragment.extend([' ' + ' '.join([key for key in field]) + ',' for field in _table_define['table_fields']])
        sql_fragment.append(" PRIMARY KEY (%s),"%' ,'.join(['`' + field + '`' for field in _table_define['table_primary_key']]))
        if 'table_indexes' in _table_define:
            for index in _table_define['table_indexes']:
                sql_fragment.append(" INDEX %s (%s),"%(index.keys()[0],' ,'.join(['`' + field + '`' for field in index.items()[0][1]])))
        if 'table_uniques' in _table_define:
            for index in _table_define['table_uniques']:
                sql_fragment.append(" UNIQUE %s (%s),"%(index.keys()[0],' ,'.join(['`' + field + '`' for field in index.items()[0][1]])))
        sql_fragment[-1] = sql_fragment[-1].rstrip(',')
        if 'utf8' == self._charset:
            sql_fragment.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8 ")
        elif 'utf8mb4' == self._charset:
            sql_fragment.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ")
        sql_fragment.append(' ' + ' '.join(_table_define['table_options']) + ';'if 'table_options' in _table_define else ';')
        return '\n'.join(sql_fragment) + '\n'

    def _gen_insert_sql(self, table_name, insert_param, show_keys, need_escape=True):
        insert_table_sql = 'INSERT INTO {table} ({keys}) VALUES ({values});'
        if [key for key in show_keys if key not in self._time_fields]:
            keys = ','.join(['`%s`' % self.__escape_string(x, need_escape) for x in show_keys])
            values = ','.join(["'%s'" % self.__escape_string(insert_param[x], escape_string) for x in show_keys])
        else:
            keys = ','.join(['`%s`' % self.__escape_string(x, need_escape) for x in insert_param.keys()])
            values = ','.join(["'%s'" % self.__escape_string(x, need_escape) for x in insert_param.values()])
        return insert_table_sql.format(table=table_name, keys=keys, values=values)
    
    def _gen_select_sql(self, table_name, select_param):
        # function: fields, where, force_index, order_by, limit, manual_sql
        """
        :fields: ['insert_time','update_time'] or ['*']
        :where: "CreateDate<'2017-1-1' AND ..." or {'CreateDate':'2017-1-1',...}
        :force_index: 'query_by_tplname'
        :order_by: 'email_time'
        :limit: (0,100)
        :manual_sql: "select * from Amazon where ...."
        """
        if select_param.get('manual_sql'):
            return select_param['manual_sql']
        select_table_sql = 'SELECT {fields} FROM {table}{force_index} {params};'
        params = []
        fields = ','.join([key for key in select_param['fields']])
        force_index = ' FORCE INDEX (`%s`)'% select_param['force_index'] if select_param.get('force_index') else ''
        if isinstance(select_param.get('where'), (str, unicode)):
            params.append('WHERE ' + select_param['where'])
        elif isinstance(select_param.get('where'), dict):
            params.append(self.__gen_where(select_param['where']))
        if select_param.get('order_by'):
            params.append('ORDER BY `%s`'%select_param['order_by'])
        if select_param.get('limit'):
            params.append('LIMIT %d, %d'%(select_param['limit']))
        return select_table_sql.format(fields=fields, table=table_name, force_index=force_index, params=' '.join(params))
    
    def _gen_update_sql(self, table_name, update_param, where_msg, need_escape=True):
        """
        :update_param: dict
        :where_msg: str or dict
        """
        update_table_sql = 'UPDATE {table} SET {update_field} {where};'
        update_field = ','.join(["`%s`='%s'" % (k, self.__escape_string(v, need_escape)) for k,v in update_param.items()])
        if isinstance(where_msg, (str, unicode)):
            return update_table_sql.format(table=table_name, update_field=update_field, where='WHERE ' + where_msg)
        elif isinstance(where_msg, dict):
            return update_table_sql.format(table=table_name, update_field=update_field, where=self.__gen_where(where_msg))

    def _gen_delete_sql(self, table_name, delete_param):
        delete_table_sql = 'DELETE FROM {table} {where};'
        if isinstance(delete_param, (str, unicode)):
            return delete_table_sql.format(table=table_name, where='WHERE ' + delete_param)
        elif isinstance(delete_param, dict):
            return delete_table_sql.format(table=table_name, where=self.__gen_where(delete_param))

    def _insert_table(self, table_name, insert_param, show_keys=[]):
        # insert one row to mysql
        self._get_db()
        timestamp = int(time.time())
        for key in self._time_fields:
            show_keys.append(key) if key not in show_keys else 0
            insert_param[key] = timestamp if key not in insert_param else insert_param[key]
        sql = self._gen_insert_sql(table_name, insert_param, show_keys)
        try:
            db_cursor = self.get_db_cursor()
            res = db_cursor.execute(sql)
            insertid = db_cursor.connection.insert_id()
        except Exception as e:
            logging.warning('insert sql failed! exception[%s], sql[%s]'%(e, sql), exc_info=True)
            return None
        return insertid
        
    def _insert_table_many(self, table_name, key_list, insert_list, cursor_class=MySQLdb.cursors.SSDictCursor):
        # insert rows to mysql
        """
        :table_name: str
        :key_list: list ['insert_time','update_time']
        :insert_list: must list, format  [{}.{},{}] or [(),(),()]
        """
        sql = "INSERT INTO `%s` (%s) VALUES(%s) ON DUPLICATE KEY UPDATE `update_time`=%s;"%(
                table_name,
                ','.join(['`%s`'%key for key in key_list]), 
                ','.join(['%s'] * len(key_list)),
                int(time.time()))
        try:
            (_db_conn, db) = self.__get_db_conn()
            _db_conn.query('SET net_write_timeout=86400')
            _cursor = _db_conn.cursor(cursor_class)
            _cursor.executemany(sql, insert_list)
            _db_conn.commit()
            logging.info('insert many finish[sql: %s, row: %d]', sql, len(insert_list))
        except Exception as e:
            logging.warning('insert many failed! exception[%s], sql[%s]'%(e, sql), exc_info=True)
            _db_conn.rollback()

    def _select_table(self, table_name, select_param, limit=None, order_by=None, fields=None, **kwargs):
        # not suitable for big data
        self._get_db()
        select_param.update(kwargs)
        select_param.update({'limit': limit}) if limit else self.__PASS
        select_param.update({'order_by': order_by}) if order_by else self.__PASS
        select_param['fields'] = fields if fields else '*'
        sql = self._gen_select_sql(table_name, select_param)
        logging.debug('the select sql[%s]'% sql)
        try:
            db_cursor = self.get_db_cursor()
            res = db_cursor.execute(sql)
            row = db_cursor.fetchallDict()
        except Exception as e:
            logging.warning('select mysql failed! exception[%s] sql[%s]'%(e, sql))
            return None
        return row
    
    def fetch_table(self, sql, cursor_class=MySQLdb.cursors.SSDictCursor):
        logging.debug('the fetch sql[%s]'% sql)
        try:
            (_db_conn, db) = self.__get_db_conn()
            [_db_conn.query(q) for q in ['SET net_read_timeout=86400', 'SET net_write_timeout=86400']]
            _cursor, cnt = _db_conn.cursor(cursor_class), 0
            _cursor.execute(sql)
            while True:
                row = _cursor.fetchone()
                if not row:
                    break
                yield row
                cnt += 1
            logging.info('fetch table finish[sql: %s, row: %d]', sql, cnt)
        except Exception as e:
            logging.warning('fetch mysql failed! exception[%s] sql[%s]'%(e, sql))

    def _update_table_by_key(self, table_name, update_param, where_msg, affected_row=False):
        self._get_db()
        update_param.update({'update_time': int(time.time())}) if 'update_time' not in update_param else self.__PASS
        sql = self._gen_update_sql(table_name, update_param, where_msg)
        logging.debug('the update sql[%s]'% sql)
        try:
            db_cursor = self.get_db_cursor()
            res = db_cursor.execute(sql)
        except Exception as e:
            logging.warning('update mysql failed! exception[%s] sql[%s]'%(e, sql))
            return False
        return res if affected_row else True

    def _delete_table_by_key(self, table_name, keys):
        # receive keys as dict or str
        self._get_db()
        sql = self._gen_delete_sql(table_name, keys)
        logging.debug('the delete sql[%s]'% sql)
        if not sql:
            return False
        try:
            db_cursor = self.get_db_cursor()
            res = db_cursor.execute(sql)
        except Exception as e:
            logging.warning('delete sql failed! exception[%s], sql[%s]'%(e, sql), exc_info=True)
            return False
        return True

    def _query_table(self, sql, is_insert=False, is_select=False):
        sql = sql.rstrip()
        logging.debug('the query sql[%s]'% sql)
        self._get_db()
        try:
            db_cursor = self.get_db_cursor()
            res = db_cursor.execute(sql)
            if is_select:
                res = db_cursor.fetchallDict()
                db_cursor.scroll(0, 'absolute') if len(res) else self.__PASS
            elif is_insert:
                res = db_cursor.connection.insert_id()
            return res
        except Exception as e:
            logging.warning('delete sql failed! exception[%s], sql[%s]'%(e, sql), exc_info=True)
            return None

if __name__ == '__main__':
    table_define = {
        'table_name' : 'user',
        'table_primary_key' : ['user_id', 'contact_id'],
        'table_indexs' : [
            {'query_by_phone':['phone']},
            {'query_by_phone_address':['phone','address']}
        ],
        'table_uniques' : [
            {'unique_username':['username']},
            {'unique_contact_id':['contact_id']}
        ],
        'table_options': [
            'AUTO_INCREMENT=50000000',
        ],
        'table_fields' : [
            ('`user_id`', 'int(10) unsigned', 'NOT NULL', 'AUTO_INCREMENT'),
            ('`username`', 'varchar(255)', 'NOT NULL'),
            ('`phone`', 'varchar(255)', 'NOT NULL'),
            ('`address`', 'varchar(255)', 'NOT NULL'),
            ('`contact_id`', 'varchar(255)', 'NOT NULL'),
            ('`avatar_data`', 'text', 'NOT NULL'),
            ('`avatar_resize_s`', 'mediumblob', 'NOT NULL'),
        ],
    }
    sql = BaseModel.gen_create_table_sql(table_define)
    db_config = {
	"host" : "localhost",
        "port" : 3306,
        "username" : "root",
        "password" : "root",
        "dbname" : "work",
        "charset" : "utf8",
    }
    insert_data = {
        'username':'yingzhao',
        'phone':15011667792,
        'address':'Eidson.inc',
        'contact_id': '106',
        'avatar_data':[1,2,3,4],
        'avatar_resize_s':{'one':'a','two':'b'},
    }
    model = BaseModel(db_config)
    print sql
    # query table test
    print model._query_table(sql)
    # insert table test
    '''
    model._insert_table('user_contact', insert_data)
    '''
    # delete table test
    '''
    model._delete_table_by_key('user_contact', insert_data)
    '''
    # update table test
    '''
    update_param = {
        'address':'Apple',
        'avatar_data': ['update','text',1],
        'avatar_resize_s':{'baby':100,'happy':'user_contact'}
    }
    where_msg = {
        'username':'Mjk4NTUyMjE2Mjg1ODE1MzA0Ng==',
    }
    #model._update_table_by_key('user_contact', update_param, "username='LTcxNTIwOTU2NDk4NTU4NTE1MDc='")
    model._update_table_by_key('user_contact', update_param, where_msg)
    '''
    # select table test
    '''
    import random
    import base64
    for i in xrange(0,20):
        num = hash(str(abs(random.randint(1,10000))))
        insert_data = {
            'username':base64.b64encode(str(num)),
            'phone':15603053802,
            'address':'Eidson.inc',
            'contact_id': num,
            'avatar_data':[1,2,3,4],
            'avatar_resize_s':{'one':num+1,'two':'b'},
        }
        model._insert_table('user_contact', insert_data)
    select_param = {
        'fields':['username', 'contact_id', 'phone'],
        'order_by': 'insert_time',
        'limit': (0,10),
    }
    data = model._select_table('user_contact', select_param)
    pprint(data)
    '''
    # fetch table test
    '''
    sql = "select * from `Wayfair` where `sender_id`='service@wayfair.com' limit 0,10000"
    data = model.fetch_table(sql)
    cnt = 0
    for x in data:
        pprint(x)
        if cnt > 100:
            break
    '''
    # insert many test
    '''
    import random
    import base64
    insert_param, key_list = [], []
    for i in xrange(0,20):
        num = hash(str(abs(random.randint(10000,20000))))
        insert_data = {
            'username':base64.b64encode(str(num)),
            'phone':10086,
            'address':'easilydo',
            'contact_id': num,
            'avatar_data':str([1,2,3,'bug']),
            'avatar_resize_s': str({'insert':num+1,'many':'b'}),
        }
        insert_param.append(insert_data.values())
        if not key_list:
            key_list = insert_data.keys() 
    model._insert_table_many('user_contact', key_list, insert_param)
    '''


