import sys
L=r'C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/l5/lots2'
PL=[('PLAN_AUDIT_CALEPINAGE','docs/plans/PLAN_AUDIT_CALEPINAGE.md'),('PLAN_AUDIT_DEVIS','docs/plans/PLAN_AUDIT_DEVIS.md'),('PLAN_AUDIT_MOTEUR','docs/plans/PLAN_AUDIT_MOTEUR.md'),('PLAN_AUDIT_LEAD','docs/plans/PLAN_AUDIT_LEAD.md'),('PLAN_AUDIT_CHANTIERS','docs/plans/PLAN_AUDIT_CHANTIERS.md'),('PLAN_AUDIT_STOCK','docs/plans/PLAN_AUDIT_STOCK.md'),('PLAN_AUDIT_SAV','docs/plans/PLAN_AUDIT_SAV.md'),('PLAN_AUDIT_PARAMETRES','docs/plans/PLAN_AUDIT_PARAMETRES.md'),('PLAN_AUDIT_DEPLOY','docs/plans/PLAN_AUDIT_DEPLOY.md'),('WEB_PLAN','docs/WEB_PLAN.md')]
sel=sys.argv[1:] or [n for n,_ in PL]
for nom,plan in PL:
    if nom not in sel: continue
    blk=open(f'{L}/INSERTION-{nom}.md',encoding='utf-8').read().rstrip('\n')+'\n\n'
    raw=open(plan,'rb').read(); bom=raw.startswith(b'\xef\xbb\xbf'); s=raw.decode('utf-8-sig')
    mk='\r\n## DONE LOG'; assert s.count(mk)==1 and 'complément du 2026-11-21 (vague 2)' not in s and 'calepinage du 2026-11-21 (vague 2)' not in s, plan
    i=s.index(mk)+2; s=s[:i]+blk.replace('\n','\r\n')+s[i:]
    open(plan,'wb').write((b'\xef\xbb\xbf' if bom else b'')+s.encode('utf-8')); print(plan,'ok')
