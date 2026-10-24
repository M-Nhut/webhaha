"""Read-only source audit; writes renderer cache and a local JSON report only."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.latex_parser import parse_latex
from services.latex_renderer import render_latex_block_result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=Path('tmp/tex-figure-audit.json'))
    args=parser.parse_args()
    with patch('services.latex_parser.render_latex_block_result',return_value={'verified':False}):
        questions=parse_latex(args.source)
    rows=[]
    for index,question in enumerate(questions,1):
        for asset in question.get('formulas',{}).values():
            if asset.get('source_format')!='LaTeXBlock': continue
            if asset.get('table'):
                result={'verified':True,'method':'structured_table_v1'}
            else:
                result=render_latex_block_result(asset['source_text'],asset.get('source_preamble',''))
            rows.append({'question':index,**result})
    result={'question_count':len(questions),'figure_count':len(rows),
            'verified_count':sum(row['verified'] for row in rows),'figures':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='figures'}))


if __name__=='__main__':main()
