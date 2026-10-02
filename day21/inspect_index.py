"""Read-only paired-index verification; aggregate output, no corpus text or API."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import statistics
from unittest.mock import patch
import index_pipeline as pipeline


def inspect(root):
    root=Path(root).resolve();current=root/'current.json'
    if not current.exists():return {'status':'notready','reason':'current_pointer_absent','network_calls':0}
    if current.is_symlink():raise ValueError('symlink_pointer')
    pointer=json.loads(current.read_text());generation=pointer.get('generation')
    if not isinstance(generation,str) or not re.fullmatch(r'[0-9a-f]{24}',generation):raise ValueError('invalid_generation_name')
    directory=root/generation
    if directory.is_symlink() or not directory.is_dir():raise ValueError('invalid_generation_directory')
    for name in ['state.json','expected-chunks.json','fixed.db','structure.db']:
        if (directory/name).is_symlink() or not (directory/name).is_file():raise ValueError('missing_or_symlink_artifact')
    state=json.loads((directory/'state.json').read_text())
    if state.get('status')!='complete':return {'status':'notready','reason':'generation_incomplete','generation':generation,'network_calls':0}
    if pipeline.file_hash(directory/'expected-chunks.json')!=pointer['expected_chunks_sha256']:raise ValueError('expected_manifest_hash')
    expected=json.loads((directory/'expected-chunks.json').read_text());identity=expected['identity'];config=identity['config']
    if (state['identity']!=identity or pointer['corpus_sha256']!=identity['corpus_sha256']
            or pointer['identity_sha256']!=pipeline.digest(identity) or generation!=pipeline.digest(identity)[:24]):raise ValueError('identity_mismatch')
    if config['pipeline_sha256']!=pipeline.file_hash(pipeline.__file__):raise ValueError('pipeline_code_identity')
    if config['model']['model']!=pipeline.MODEL or config['tokenizer']['model']!=pipeline.TOKENIZER_MODEL:raise ValueError('model_identity')
    if config['max_tokens']!=400 or config['overlap']!=60:raise ValueError('chunk_config_identity')
    result={'status':'ready','generation':generation,'corpus_sha256':identity['corpus_sha256'],'model':config['model'],
            'tokenizer':config['tokenizer'],'config':{k:config[k] for k in ['max_tokens','overlap','transition_threshold']},'strategies':{},'network_calls':0,'corpus_text_printed':False}
    original_connect=sqlite3.connect
    def readonly_connect(path):return original_connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    for strategy in ['fixed','structure']:
        path=directory/(strategy+'.db');chunks=expected['strategies'][strategy]
        # Existing verifier is reused with a scoped read-only connection factory; pipeline remains frozen.
        with patch.object(pipeline.sqlite3,'connect',readonly_connect):pipeline.verify_index(path,identity|{'strategy':strategy},chunks)
        with closing(original_connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
            count=conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
        sizes=sorted(c['token_count'] for c in chunks);documents={c['document_id']:c['source'] for c in chunks}
        if not sizes or max(sizes)>400:raise ValueError('token_size')
        result['strategies'][strategy]={'chunks':count,'documents':len(documents),'source_document_counts':{source:sum(v==source for v in documents.values()) for source in sorted(set(documents.values()))},
            'source_records':len({m['source_key'] for c in chunks for m in (c.get('document_members') or c.get('members') or [])}),
            'tokens':{'min':min(sizes),'median':statistics.median(sizes),'p95':sizes[max(0,__import__('math').ceil(len(sizes)*.95)-1)],'max':max(sizes)},
            'vector_dimensions':pipeline.DIMENSIONS,'file_bytes':path.stat().st_size}
    if {c['document_id'] for c in expected['strategies']['fixed']}!={c['document_id'] for c in expected['strategies']['structure']}:raise ValueError('paired_document_coverage')
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--root',type=Path,required=True);args=cli.parse_args()
    try:print(json.dumps(inspect(args.root),ensure_ascii=False))
    except Exception as error:print(json.dumps({'status':'invalid','error_type':type(error).__name__}));raise SystemExit(1)

if __name__=='__main__':main()
