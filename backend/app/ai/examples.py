"""Bounded local retrieval of verified examples, separate from evaluation labels."""
import json
from pathlib import Path
import re


def retrieve_examples(path: Path | None,question: str,limit: int = 2) -> str:
    if path is None or not path.is_file() or path.stat().st_size>2*1024*1024:
        return ''
    tokens=set(re.findall(r'[a-z]+',question.casefold()))-{'show','the','a','are','there','please','me'}
    candidates=[]
    with path.open(encoding='utf-8') as handle:
        for index,line in enumerate(handle):
            if index>=500:
                break
            try:
                record=json.loads(line)
                if not isinstance(record,dict):
                    continue
                if not all(isinstance(record.get(key),str) for key in ('question','schema','sql')):
                    continue
                overlap=len(tokens & set(re.findall(r'[a-z]+',record['question'].casefold())))
                if overlap:
                    candidates.append((overlap,index,record))
            except (ValueError,TypeError):
                continue
    selected=sorted(candidates,key=lambda item:(-item[0],item[1]))[:limit]
    return '\n'.join(json.dumps({'question':record['question'][:500],'schema':record['schema'][:4000],'sql':record['sql'][:4000]}) for _,_,record in selected)
