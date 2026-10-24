"""Reproducible synthetic feasibility comparison; not a learning-effect study."""
from pathlib import Path
import json
import sys
import time
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from test_personalization_v2 import bank, choose
from services.practice_recovery import select_resilient
from services.practice_selector import select_fixed

fixture = bank.__wrapped__()
data = next(fixture)
try:
    base = choose(data)
    levels, skills = base['aptga']['desired_quotas'], base['aptga']['skill_targets']
    items = [dict(question=q, skill=q.curriculum_node.canonical_code, fingerprint=str(q.id),
                  score=0, exposure_count=0, exposure_tier=0) for q in base['questions']]
    shifted = dict(skills)
    donor = next(k for k in shifted if shifted[k]>1)
    receiver = next(k for k in shifted if k!=donor and shifted[k]<5)
    shifted[donor]-=1
    shifted[receiver]+=1
    scenarios = [
        ('Ngân hàng vừa đủ, câu mới', items, skills),
        ('Toàn bộ câu vừa xuất hiện', [{**x,'exposure_count':1,'exposure_tier':3} for x in items],skills),
        ('Lệch phân bố một vị trí', items, shifted),
        ('Thiếu hẳn câu Đúng/Sai', [x for x in items if x['question'].question_type!='true_false'],skills),
        ('Các bản sao cùng nội dung', [{**x,'fingerprint':'same'} for x in items],skills),
    ]
    output = []
    for name,pool,target in scenarios:
        old,_,old_status = select_fixed([x for x in pool if x['exposure_tier']==0],levels,target)
        start=time.perf_counter()
        selected,shortages,status,audit = select_resilient(pool,levels,target)
        output.append(dict(scenario=name, baseline_count=len(old), baseline_status=old_status,
            v2_count=len(selected), v2_status=status, stage=audit['recovery_stage'],
            repeated_count=audit['repeated_count'], quota_changes=audit['quota_changes'],
            milliseconds=round((time.perf_counter()-start)*1000,2),
            unique_content=len({x['fingerprint'] for x in selected}),shortages=shortages))
    path=ROOT/'docs/reports/personalization-v2-synthetic.json'
    path.write_text(json.dumps(dict(kind='synthetic_feasibility_only',results=output),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True,indent=2))
finally:
    try: next(fixture)
    except StopIteration: pass
