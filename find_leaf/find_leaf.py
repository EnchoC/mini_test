# -*- coding: utf-8 -*-
import time
## target 构成 target_format = '%s_%s' % (channel_id, page_id)
s = [
    {'channel_id' : 2001, 'page_id' : 10, 'target' : ['2001_11', 'response', '2001_12']},
    {'channel_id' : 2001, 'page_id' : 11, 'target' : ['response']},
    {'channel_id' : 2001, 'page_id' : 12, 'target' : ['3001_1', 'response']},
    {'channel_id' : 3001, 'page_id' : 1, 'target' : ['response']},
    {'channel_id' : 3001, 'page_id' : 2, 'target' : ['response']},
    {'channel_id' : 3001, 'page_id' : 3, 'target' : ['response']},
    {'channel_id' : 3001, 'page_id' : 4, 'target' : ['response']},
    ]

def get_node(target):
    channel_id, page_id = target.split('_')
    channel_id = int(channel_id)
    page_id = int(page_id)
    for line in s :
       if line['channel_id'] == channel_id and line['page_id'] == page_id :
           return line
           
def get_child_node(head_node):
    child_node_list = []
    if len(head_node['target']) == 1:
        return None
    elif len(head_node['target']) > 1:
        for child in head_node['target']:
            if child != 'response':
                child_node_list.append(get_node(child))
        return child_node_list

## 跪求帮我实现这个函数
def get_leaf_node(channel_id, page_id) :
    leaf_node_list = []
    head_node = '%s_%s' % (channel_id, page_id)
    node = get_node(head_node)
    cur_list = [node]
    next_list = []
    while cur_list:
        cur_node = cur_list.pop()
        child_node_list = get_child_node(cur_node)
        if child_node_list == None:
            leaf_node_list.append(cur_node)
        else:
            next_list.extend(child_node_list)
        if len(cur_list) == 0:
            cur_list = next_list
            next_list = []
    return leaf_node_list
        
        
## 输入
start = time.time()
channel_id = 2001
page_id = 10
result = get_leaf_node(channel_id, page_id)
print(result)
print time.time() - start
## 输出结果
## [{'channel_id' : 2001, 'page_id' : 11}, {'channel_id' : 3001, 'page_id' : 1}]
