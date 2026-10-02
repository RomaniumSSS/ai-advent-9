"""Запрет эталонов во входе preparation и защита loopback."""
from common import loopback
from prepare_remote import query_cases

def rejected(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('accepted invalid input')

def main():
    assert query_cases({'cases':[{'id':'Q1','question':'Вопрос?'}]})[0]['id']=='Q1'
    rejected(lambda:query_cases([{'id':'Q1','question':'Q','expected_facts':[]}]))
    rejected(lambda:query_cases([{'id':'Q1','question':'Q'},{'id':'Q1','question':'Q'}]))
    rejected(lambda:loopback('http://example.com:11434'))
    rejected(lambda:loopback('http://127.0.0.1:11434/path'))
    rejected(lambda:loopback('http://user@127.0.0.1:11434'))
    assert loopback('http://127.0.0.1:11434/')=='http://127.0.0.1:11434'
    print('ok prepare: query-only schema, unique IDs, loopback')

if __name__=='__main__':main()
