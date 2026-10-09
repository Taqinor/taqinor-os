# SONDE = {'constat': 'C-AMET-027', 'sha': 'f3716e3f0', 'attendu': "décisions répondues avec dépendants « Si (a) » encore ouverts (9/10)"}
# Sonde de la session audit-méthode du 09/10/2026 (R3), jouée dans le conteneur local en transaction annulée,
# backend mail en mémoire, Celery coupé. Rejouable par scripts/sonde.py (AMET93) ; jamais contre la prod.
import re, glob, os, collections
os.chdir(r"C:/dev/taqinor-os/.claude/worktrees/audit-script-enhancement-3f7e3a")
# answered decision ids in memory files
ans = {}
for f in glob.glob("docs/claude-memory/*decision*.md"):
    for line in open(f, encoding="utf-8"):
        for m in re.finditer(r"\*\*(?:[^*]*?)\b((?:D-[A-Z]+-[A-Z]?\d+)|(?:A[A-Z]{3}\d{1,3}))\b", line):
            ans.setdefault(m.group(1), os.path.basename(f))
print("answered ids in memory:", len(ans))
task_re = re.compile(r"^\s*- \[(?P<st>(?:[^\[\]]|\[[^\[\]]*\])*)\]\s+\**(?P<id>[A-Z]{3,5}\d{1,4})\**")
cond = re.compile(r"\b[Ss]i \(?[ab]\)|\([ab]\)\s*:|option \(?[ab]\)", re.U)
refdec = re.compile(r"(?:décision|decision|tranch\w*|arbitrage)[^.;]{0,60}?\b((?:D-[A-Z]+-[A-Z]?\d+)|(?:A[A-Z]{3}\d{1,3}))\b", re.I)
rows=[]
for f in sorted(glob.glob("docs/plans/PLAN_*.md"))+["docs/WEB_PLAN.md"]:
    sec=""
    for n,line in enumerate(open(f, encoding="utf-8"),1):
        if line.startswith("#"): sec=line.strip(); continue
        m = task_re.match(line)
        if not m: continue
        st = m.group("st").strip()
        if st.lower().startswith("x"): continue
        head = line[:line.rfind("Files:")] if "Files:" in line else line
        c = cond.findall(head)
        refs = set(refdec.findall(head))
        gated = "GATED" in sec.upper() or "GATED" in head[:300]
        if c:
            rows.append((m.group("id"), os.path.basename(f), n, len(c), sorted(refs), [r for r in refs if r in ans], gated, sec[:40]))
print("open tasks with conditional (a)/(b) text:", len(rows))
withans = [r for r in rows if r[5]]
print("…of which reference an ANSWERED decision:", len(withans))
for r in withans: print("  ", r[0], r[1], "L%d"%r[2], "refs=", r[4], "answered=", r[5], "gated=", r[6])
print("…reference no decision id:", sum(1 for r in rows if not r[4]))
for r in rows:
    if not r[4]: print("  noref:", r[0], r[1], r[7])
