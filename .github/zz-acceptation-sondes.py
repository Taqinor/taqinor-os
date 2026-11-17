"""TEMPORAIRE (zz-scratch-acceptation-1711) — juge les traces de sondes rejouées par le job `sondes` et écrit, par
groupe, un fichier d'étapes au format results.json (`/tmp/etapes-<G>.json`), fusionné ensuite dans l'enregistrement
du jour par `node frontend/e2e/acceptation/_enregistrement.js <G> --etapes-supplementaires`."""
import json
import os
import re
import sys

date = sys.argv[1]
RUN = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
GENERAL = ('runner GitHub ubuntu-latest, pile docker compose (conteneur django_core, .env = .env.example, '
           'migrate + seed_demo + seed_catalogue), run ' + RUN)
NA = {str(i): 'NA' for i in range(1, 11)}


def blocs(chemin):
    out, cur = {}, None
    if not os.path.exists(chemin):
        return out
    for ligne in open(chemin, encoding='utf-8', errors='replace').read().splitlines():
        m = re.match(r'== (C-[A-Z0-9-]+) \(sha', ligne)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif ligne.startswith('== bilan'):
            cur = None
        elif cur:
            out[cur].append(ligne)
    return out


def juger(lignes):
    texte = '\n'.join(lignes)
    m = re.search(r'^verdict : (\S+)', texte, re.M)
    verdict = m.group(1) if m else None
    obs = texte.split('observé : ', 1)[-1].split('\nverdict :', 1)[0] if 'observé : ' in texte else ''
    m2 = re.search(r'["\']repro["\']: (true|false|True|False)', obs)
    repro = {'true': True, 'false': False, 'True': True, 'False': False}.get(m2.group(1)) if m2 else None
    erreur = bool(re.search(r'ERREUR :|AUCUN RÉSULTAT|REFUSÉE|NameError|Traceback', texte)) or verdict is None
    base = 'base inchangée : oui' in texte
    cause = re.search(r'(\w*Error|ImproperlyConfigured)[^\n]*', texte)
    return {'verdict': verdict, 'erreur': erreur, 'repro': repro, 'base': base,
            'cause': cause.group(0)[:160] if cause else ''}


def juger_hote(chemin):
    texte = open(chemin, encoding='utf-8', errors='replace').read() if os.path.exists(chemin) else ''
    m = re.search(r'^repro: (True|False)', texte, re.M)
    code = re.search(r'^code : (\d+)', texte, re.M)
    return {'repro': {'True': True, 'False': False}.get(m.group(1)) if m else None,
            'code': code.group(1) if code else '?', 'traceback': 'Traceback' in texte}


def etape_sondes(tache, trace, sondes, attendu_repro=False, cmd='', extra=''):
    b = blocs(trace)
    ok, details = True, []
    for s in sondes:
        r = juger(b[s]) if s in b else None
        bon = bool(r) and not r['erreur'] and r['repro'] is attendu_repro and r['base']
        ok = ok and bon
        details.append(f"{s} : " + ('absente du rejeu' if not r else
                       f"verdict {r['verdict']}, repro {r['repro']}, erreur {'oui' if r['erreur'] else 'non'}"
                       + (f" ({r['cause']})" if r['cause'] else '')
                       + f", base inchangée {'oui' if r['base'] else 'non'}") + ('' if bon else ' [REFUS]'))
    return ok, details, {'id': '', 'taches': [tache], 'verdict': 'PASS' if ok else 'FAIL', 'base_verdict': None,
                         'trace': trace, 'oracles': dict(NA),
                         'notes': f"{GENERAL} ; clause jouée telle qu'écrite : {cmd} ; " + ' ; '.join(details) + extra}


T = f'docs/audits/acceptation/{{G}}/traces/{date}'
GROUPES = {}


def ajouter(groupe, ident, etape):
    etape['id'] = ident
    GROUPES.setdefault(groupe, []).append(etape)


# AMET109 — sonde.py rejoue la sonde 006 d'ACNC sans NameError et rend son repro (faux sur la branche).
tr = T.format(G='AMET') + '/AMET109-sonde-ACNC-006.txt'
_, _, e = etape_sondes('AMET109', tr, ['C-ACNC-006'], cmd='python scripts/sonde.py ACNC/C-ACNC-006',
                       extra=" ; les sondes des six tâches bloquées (ASUP66, ALEC50, AMSG105, ACNC77, AERR180, APUB75) "
                             "sont rejouées dans le même run (enregistrements de leurs groupes)")
ajouter('AMET', 'SONDES.AMET109-sonde-py', e)

# Les six tâches « sondes réparées » : `sonde.py --toutes <G>`, leurs sondes rendent un repro faux sans erreur.
for G, tache, sondes in (
        ('ASUP', 'ASUP66', ['C-ASUP-003', 'C-ASUP-022']),
        ('ALEC', 'ALEC50', ['C-ALEC-016', 'C-ALEC-020', 'C-ALEC-024', 'C-ALEC-025', 'C-ALEC-VER1-102']),
        ('AMSG', 'AMSG105', ['C-AMSG-003', 'C-AMSG-007', 'C-AMSG-009']),
        ('AERR', 'AERR180', ['C-AERR-001', 'C-AERR-044']),
        ('APUB', 'APUB75', ['C-APUB-004', 'C-APUB-007'])):
    _, _, e = etape_sondes(tache, T.format(G=G) + f'/{G}-sondes.txt', sondes, cmd=f'python scripts/sonde.py --toutes {G}')
    ajouter(G, f'SONDES.{tache}-sonde-py', e)

# ACNC77 — repro faux sur la branche, vrai sous le mutant (atomic de la vue retiré).
ok1, d1, e = etape_sondes('ACNC77', T.format(G='ACNC') + '/ACNC-sonde-006.txt', ['C-ACNC-006'],
                          cmd='python scripts/sonde.py ACNC/C-ACNC-006')
ok2, d2, _ = etape_sondes('ACNC77', T.format(G='ACNC') + '/ACNC-sonde-006-mutant.txt', ['C-ACNC-006'], attendu_repro=True)
e['verdict'] = 'PASS' if ok1 and ok2 else 'FAIL'
e['notes'] += (f" ; MUTANT (retrait de `transaction.atomic(...)` dans la vue, diff {T.format(G='ACNC')}/ACNC-mutant.diff) : "
               + ' ; '.join(d2) + (' => repro devient vrai' if ok2 else ' => REFUS : repro ne devient pas vrai'))
ajouter('ACNC', 'SONDES.ACNC77-sonde-py-mutant', e)

# ASUP69 — sonde hôte VER2-101 : repro faux (ICE d'origine imprimé), vrai sous le mutant d'avoir.html.
tr = T.format(G='ASUP') + '/ASUP69-sonde-VER2-101.txt'
trm = T.format(G='ASUP') + '/ASUP69-sonde-VER2-101-mutant.txt'
a, m = juger_hote(tr), juger_hote(trm)
bon = a['repro'] is False and not a['traceback'] and m['repro'] is True and not m['traceback']
ajouter('ASUP', 'SONDES.ASUP69-sonde-hote-mutant', {
    'id': '', 'taches': ['ASUP69'], 'verdict': 'PASS' if bon else 'FAIL', 'base_verdict': None, 'trace': tr,
    'oracles': dict(NA),
    'notes': (f"{GENERAL} ; python docs/audits/sondes/ASUP/C-ASUP-VER2-101.py (arbre monté par scripts/sonde.py) : "
              f"repro {a['repro']} (code {a['code']}) ; MUTANT avoir.html `{{% set acheteur = avoir.client %}}` "
              f"(diff {T.format(G='ASUP')}/ASUP69-mutant.diff, trace {trm}) : repro {m['repro']} (code {m['code']})"
              + ('' if bon else ' [REFUS]'))})

for G, etapes in GROUPES.items():
    chemin = f'/tmp/etapes-{G}.json'
    json.dump({'couvre': sorted({t for e in etapes for t in e['taches']}), 'etapes': etapes},
              open(chemin, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(G, [(e['id'], e['verdict']) for e in etapes])
