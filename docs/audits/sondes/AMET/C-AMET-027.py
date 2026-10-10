"""Sonde statique de la session audit-méthode du 09/10/2026 : lit docs/plans et la mémoire partagée, ne touche pas la base.
Racine du dépôt = ctx['racine'] ; sans docs/plans à cet endroit → STATIQUE."""
SONDE = {
    'constat': 'C-AMET-027',
    'sha': 'f3716e3f0',
    'attendu': 'décisions répondues avec dépendants « Si (a) » encore ouverts (9/10)',
}


def sonde(ctx):
    import glob
    import os
    import re
    racine = ctx.get('racine') or '.'
    if not os.path.isdir(os.path.join(racine, 'docs', 'plans')):
        return 'STATIQUE : docs/plans absent sous %s (conteneur sans dépôt) ; rejouer depuis une copie du dépôt' % racine
    os.chdir(racine)
    ans = {}
    for f in glob.glob('docs/claude-memory/*decision*.md'):
        for line in open(f, encoding='utf-8'):
            for m in re.finditer(r'\*\*(?:[^*]*?)\b((?:D-[A-Z]+-[A-Z]?\d+)|(?:A[A-Z]{3}\d{1,3}))\b', line):
                ans.setdefault(m.group(1), os.path.basename(f))
    print('answered ids in memory:', len(ans))
    task_re = re.compile(r'^\s*- \[(?P<st>(?:[^\[\]]|\[[^\[\]]*\])*)\]\s+\**(?P<id>[A-Z]{3,5}\d{1,4})\**')
    cond = re.compile(r'\b[Ss]i \(?[ab]\)|\([ab]\)\s*:|option \(?[ab]\)', re.U)
    refdec = re.compile(r'(?:décision|decision|tranch\w*|arbitrage)[^.;]{0,60}?\b((?:D-[A-Z]+-[A-Z]?\d+)|(?:A[A-Z]{3}\d{1,3}))\b', re.I)
    rows = []
    for f in sorted(glob.glob('docs/plans/PLAN_*.md')) + ['docs/WEB_PLAN.md']:
        sec = ''
        for n, line in enumerate(open(f, encoding='utf-8'), 1):
            if line.startswith('#'):
                sec = line.strip()
                continue
            m = task_re.match(line)
            if not m or m.group('st').strip().lower().startswith('x'):
                continue
            head = line[:line.rfind('Files:')] if 'Files:' in line else line
            c = cond.findall(head)
            refs = set(refdec.findall(head))
            gated = 'GATED' in sec.upper() or 'GATED' in head[:300]
            if c:
                rows.append((m.group('id'), os.path.basename(f), n, len(c), sorted(refs),
                             [r for r in refs if r in ans], gated, sec[:40]))
    print('open tasks with conditional (a)/(b) text:', len(rows))
    withans = [r for r in rows if r[5]]
    print('of which reference an ANSWERED decision:', len(withans))
    for r in withans:
        print('  ', r[0], r[1], 'L%d' % r[2], 'refs=', r[4], 'answered=', r[5], 'gated=', r[6])
    return {'repro': bool(withans), 'dependants_ouverts_avec_decision_repondue': len(withans)}
