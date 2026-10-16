"""DevHelper: /help <вопрос>, один независимый запрос."""
from __future__ import annotations
import argparse
import json
from day31.config import add_arguments, build_assistant


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question',help='Например: /help Как устроен Git MCP?')
    parser.add_argument('--json',action='store_true',help='Полный ответ с trace и источниками')
    add_arguments(parser)
    args=parser.parse_args()
    try:
        app=build_assistant(args)
    except ValueError as error:
        parser.error(str(error))
    result=app.answer(args.question)
    if args.json:
        print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2))
    else:
        print(f'Режим: {result.model} / {result.provider}\nGit-root: {app.mcp.repo}\n')
        print(result.text)
        if result.git_context:
            context=result.git_context
            print(f'\nGit: {context["branch"] or "detached HEAD"} · {context["head"]}')
        for source in result.sources:
            if source['id'] in result.source_ids:
                print(f'Источник [{source["id"]}]: {source["path"]}:{source["start_line"]}–{source["end_line"]}')
        print(f'\nСтатус: {result.status} · trace {result.trace_id} · {result.elapsed_seconds:.2f} с')
    return 1 if result.status=='error' else 0


if __name__=='__main__':
    raise SystemExit(main())
