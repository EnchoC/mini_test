#!/usr/bin/python
# -*- coding:utf-8 -*-
import re
import csv
import json
import urllib
import logging
import Levenshtein
from test_line import Test
from tmall_analysis import DataAnaylsis
logging_format = '[%(asctime)s - %(filename)s - %(funcName)s] : %(message)s'
logging.basicConfig(level=logging.INFO, format=logging_format, datefmt='%Y-%m-%d %H:%M:%S')

class DealData(Test, DataAnaylsis) :

	def __init__(self, db_list, table_name) :
		Test.__init__(self, db_list, table_name)
		DataAnaylsis.__init__(self)
		self.load_file = 'text.json'
		self.finish_file = 'finish.csv'
		self.unicode_deal = re.compile('\s*U([0-9][a-z0-9]{3})\s*')
		self.ascii_deal = re.compile('\s*0X([A-Za-z0-9]{2})\s*')
		self.url_deal = re.compile('\s*((%[A-Z0-9]{2}){3})\s*')
		self.headers = ['id','pid','brand','product_name','monthly_sales','url','store','email','price','insert_time','update_time']

	def load_data(self) :
		read_data = []
		with open(self.load_file) as f:
		    lines = f.readlines()
		    for line in lines:
			    d = json.loads(line)
			    read_data.append(d)
		logging.info('load [%s] data is finish!' % self.load_file)
		return read_data

	def deal_data(self, read_data) :
		for line in read_data :
			for key, value in line.items() :
				## deal unicode
				value = re.sub(self.unicode_deal, lambda m : (r'\u' + m.group(1)).decode('unicode_escape'), value)
				## deal ascii
				value = re.sub(self.ascii_deal, lambda m : m.group(1).decode('hex'), value)
				## deal url code
				value = re.sub(self.url_deal, lambda m : m.group(1), value)
				value = value.encode('utf-8')
				value = urllib.unquote(value)
				line[key] = value
		logging.info('data has cleaned!')
		return read_data

	def transfer_data(self, read_data) :
		length = len(read_data)
		transfer_col = ['brand', 'product_name', 'store']
		for col in transfer_col :
			for head_line in range(length/2) :
				score_list = []
				for tail_line in range(length/2, length) :
					score = Levenshtein.jaro(read_data[head_line][col], read_data[tail_line][col])
					score_list.append(score)
				max_index = score_list.index(max(score_list))
				read_data[head_line][col] = read_data[max_index+(length/2)][col]
		return read_data[:length/2]

	def out_data(self, read_data) :
		with open(self.finish_file,'w') as f:
			f_scv = csv.DictWriter(f,self.headers)
			f_scv.writeheader()
			f_scv.writerows(read_data)
		logging.info('finish output')

	def run(self) :
		strat_data = self.load_data()
		after_data = self.deal_data(strat_data)
		last_data = self.transfer_data(after_data)
		result = list(self.test_fun(last_data))
		self.out_data(last_data)
		self.start(result)

if __name__ in '__main__' :
	table_name = 'file'
	db_list = {
		"host" : "localhost",
        "port" : 3306,
        "username" : "root",
        "password" : "027732",
        "dbname" : "test1",
        "charset" : "utf8",
    	}
	clean = DealData(db_list, table_name)
	clean.run()

