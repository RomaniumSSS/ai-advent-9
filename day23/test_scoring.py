"""Покрытие диапазонов и непересекающийся подсчёт категорий."""
from score_retrieval import covered, summarize
assert covered({'start_char':3,'end_char':12},[{'start_char':0,'end_char':7},{'start_char':7,'end_char':15}])
assert not covered({'start_char':3,'end_char':12},[{'start_char':0,'end_char':6},{'start_char':7,'end_char':15}])
s=summarize([{'category':'unanswerable','answerable':False,'empty':False,'context_bytes':10}])
assert s['unanswerable']['questions']==s['all']['questions']==1
assert s['unanswerable']['answerable']==0
print('ok scoring: span gaps and category/answerability overlap counted once')
