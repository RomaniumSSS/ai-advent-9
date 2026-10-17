"""Офлайн-регрессии сценарных smoke-проверок, без запуска браузера/сети."""
import json
from pathlib import Path
import unittest
from run_demo import check_response


def response(text, ticket='T101', source='FAQ-EMAIL', mode='mock'):
    return {'answer':text,'source_ids':[source], 'context':{'ticket':{'id':ticket}},
            'trace':{'mode':mode,'run_id':'offline','mcp':[{'method':'tools/call'}],
                     'retrieval_ids':[source],'response_kind':'model_answer'}}


class RecorderChecks(unittest.TestCase):
    def test_actual_inflection(self):
        check_response(response('Ваша почта не подтверждена. Перейдите по ссылке подтверждения. [FAQ-EMAIL]'), 'T101','FAQ-EMAIL','mock')

    def test_mock_cases_and_required_facts(self):
        check_response(response('Подтвердите почту по ссылке. [FAQ-EMAIL]'),'T101','FAQ-EMAIL','mock')
        check_response(response('Срок приглашения истёк. Попросите новое приглашение. [FAQ-INVITE]','T102','FAQ-INVITE'),'T102','FAQ-INVITE','mock')
        for text in ['Почта существует. [FAQ-EMAIL]','Подтверждение готово. [FAQ-EMAIL]']:
            with self.assertRaises(AssertionError):check_response(response(text),'T101','FAQ-EMAIL','mock')
        with self.assertRaises(AssertionError):
            check_response(response('Приглашение активно. [FAQ-INVITE]','T102','FAQ-INVITE'),'T102','FAQ-INVITE','mock')

    def test_saved_successful_dry04(self):
        files=list((Path(__file__).resolve().parents[1]/'results/live-dry-04').glob('response-*.json'))
        self.assertTrue(files, 'Нет сохранённого evidence dry04')
        successful=0
        for path in files:
            value=json.loads(path.read_text())
            if value['status'] != 200: continue
            data=value['data'];ticket=data['context']['ticket']['id']
            source={'T101':'FAQ-EMAIL','T102':'FAQ-INVITE','T103':None}[ticket]
            check_response(data,ticket,source,'live');successful+=1
        self.assertGreater(successful,0)


if __name__=='__main__':unittest.main(verbosity=2)
