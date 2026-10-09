#!/usr/bin/env python3
"""AMET93 — lanceur de sondes d'audit : `python scripts/sonde.py AMET/C-AMET-001` | `--toutes AMET`.

Une sonde vit dans `docs/audits/sondes/<G>/C-<G>-<NNN>.py` (METHODE §B.5) et porte :
    SONDE = {"constat": "C-AMET-001", "sha": "<sha de la session>", "attendu": "<observation attendue>"}
    def sonde(ctx): ...   # renvoie un dict (cle `repro` booleenne optionnelle) ou une chaine
Cle optionnelle `modeles` : liste de `app.Modele` dont on compte les lignes (defaut : tous les modeles).
Une chaine renvoyee commencant par « STATIQUE » = verdict STATIQUE (rien de rejoue). Sinon le verdict est
REPRO si la sonde s'execute sans erreur et que `repro` n'est pas faux, ECART sinon : sans cle `repro`, le
verdict certifie l'execution, la comparaison attendu / observe reste a lire.

Le lanceur envoie un programme AUTONOME (source de la sonde en ligne, jamais par chemin) a
`docker exec -i <conteneur> python -u manage.py shell` : transaction annulee (`set_rollback(True)`), mail
en memoire, Celery coupe, HTTP sortant bloque, `signal.alarm`, comptes avant / apres. Sortie 0 seulement
si verdict REPRO ou STATIQUE ET base inchangee. Jamais contre la prod.
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENEUR = 'erp-agentique-django_core-1'
MARQUE = '@@RESULT '

RUNNER = r'''
import io, json, signal, socket, sys, traceback, contextlib
from django.conf import settings
from django.db import transaction
from django.apps import apps
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
settings.CELERY_TASK_ALWAYS_EAGER = False
_CEL = []
def _noop(self, *a, **k):
    _CEL.append(getattr(self, 'name', '?'))
    return type('R', (), {'id': 'noop'})()
import celery.app.task as _ct
_ct.Task.apply_async = _noop
_ct.Task.delay = lambda self, *a, **k: _noop(self)
def _http(*a, **k):
    raise RuntimeError('HTTP sortant bloque par scripts/sonde.py')
socket.create_connection = _http
_SRC = __SRC__
_ENTETE = __ENTETE__
def _timeout(*a):
    raise TimeoutError('delai de la sonde depasse')
def _comptes():
    cibles = _ENTETE.get('modeles')
    out = {}
    for m in apps.get_models():
        if cibles and m._meta.label not in cibles and m.__name__ not in cibles:
            continue
        if not m._meta.managed or m._meta.proxy:
            continue
        try:
            out[m._meta.label] = m._default_manager.count()
        except Exception:
            pass
    return out
def _rejouer():
    ns = {'__name__': '__sonde__'}
    exec(compile(_SRC, 'sonde', 'exec'), ns)
    ctx = {'celery': _CEL, 'racine': '.', 'args': None}
    tampon = io.StringIO()
    erreur = None
    ret = None
    if hasattr(signal, 'alarm'):
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(__TIMEOUT__)
    try:
        with transaction.atomic():
            try:
                with contextlib.redirect_stdout(tampon):
                    ret = ns['sonde'](ctx)
            finally:
                transaction.set_rollback(True)
    except BaseException:
        erreur = traceback.format_exc()[-600:]
    finally:
        if hasattr(signal, 'alarm'):
            signal.alarm(0)
    return tampon.getvalue(), ret, erreur
_avant = _comptes()
_sortie, _ret, _err = _rejouer()
_apres = _comptes()
_texte = _sortie + ('' if _ret is None else (_ret if isinstance(_ret, str) else json.dumps(_ret, default=str, ensure_ascii=False)))
if _err:
    _texte += '\nERREUR : ' + _err
if _err or (isinstance(_ret, dict) and _ret.get('repro') is False):
    _verdict = 'ECART'
elif isinstance(_ret, str) and _ret.startswith('STATIQUE'):
    _verdict = 'STATIQUE'
else:
    _verdict = 'REPRO'
from django.core import mail
_res = {'observe': _texte.strip()[:6000], 'verdict': _verdict, 'base_inchangee': _avant == _apres,
        'comptes_avant': sum(_avant.values()), 'comptes_apres': sum(_apres.values()),
        'mails': len(getattr(mail, 'outbox', [])), 'celery_bloques': len(_CEL)}
print('__MARQUE__' + json.dumps(_res, ensure_ascii=True))
sys.exit(0 if _res['base_inchangee'] and _verdict in ('REPRO', 'STATIQUE') else 1)
'''


class ErreurSonde(Exception):
    pass


def charger(chemin):
    """Valide l'en-tete et le point d'entree SANS rien executer ; renvoie (source, SONDE)."""
    if not os.path.isfile(chemin):
        raise ErreurSonde('sonde introuvable : %s' % chemin)
    with open(chemin, encoding='utf-8') as f:
        source = f.read()
    try:
        arbre = ast.parse(source)
    except SyntaxError as e:
        raise ErreurSonde('sonde illisible (%s) : %s' % (e, chemin))
    entete = None
    for n in arbre.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SONDE' for t in n.targets):
            try:
                entete = ast.literal_eval(n.value)
            except ValueError:
                entete = None
    if not isinstance(entete, dict) or not all(isinstance(entete.get(k), str) and entete[k].strip()
                                               for k in ('constat', 'sha', 'attendu')):
        raise ErreurSonde('en-tete SONDE = {constat, sha, attendu} absent ou incomplet : %s' % chemin)
    if not any(isinstance(n, ast.FunctionDef) and n.name == 'sonde' and len(n.args.args) == 1
               for n in arbre.body):
        raise ErreurSonde('point d\'entree `def sonde(ctx)` absent : %s' % chemin)
    return source, entete


def programme(source, entete, timeout):
    return (RUNNER.replace('__SRC__', ascii(source)).replace('__ENTETE__', repr(entete))
            .replace('__TIMEOUT__', str(int(timeout))).replace('__MARQUE__', MARQUE))


def executer_docker(cmd, prog, timeout):
    r = subprocess.run(cmd, input=prog.encode('utf-8'), capture_output=True, timeout=timeout + 60)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def jouer(chemin, conteneur, timeout, executer, dry_run=False):
    """Rejoue UNE sonde ; renvoie (code, verdict). Imprime attendu / observe / verdict / base."""
    source, entete = charger(chemin)
    prog = programme(source, entete, timeout)
    if dry_run:
        print(prog)
        return 0, 'DRY'
    cmd = ['docker', 'exec', '-i', conteneur, 'python', '-u', 'manage.py', 'shell']
    rc, sortie, erreur = executer(cmd, prog, timeout)
    ligne = next((x for x in sortie.splitlines() if x.startswith(MARQUE)), None)
    print('== %s (sha %s)' % (entete['constat'], entete['sha']))
    print('attendu : %s' % entete['attendu'])
    if ligne is None:
        print('observé : AUCUN RÉSULTAT (code %s) %s' % (rc, (erreur or sortie).strip()[-400:]))
        print('verdict : ÉCART\nbase inchangée : inconnue')
        return 1, 'ÉCART'
    res = json.loads(ligne[len(MARQUE):])
    verdict = {'ECART': 'ÉCART'}.get(res.get('verdict'), res.get('verdict'))
    inchangee = res.get('base_inchangee') is True
    print('observé : %s' % res.get('observe', ''))
    print('verdict : %s' % verdict)
    print('base inchangée : %s (avant %s, après %s) ; mails %s ; tâches Celery bloquées %s' % (
        'oui' if inchangee else 'non', res.get('comptes_avant'), res.get('comptes_apres'),
        res.get('mails'), res.get('celery_bloques')))
    return (0 if inchangee and verdict in ('REPRO', 'STATIQUE') else 1), verdict


def main(argv=None, executer=executer_docker):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('sonde', nargs='?', help='ex. AMET/C-AMET-001')
    p.add_argument('--toutes', metavar='GROUPE', help='rejoue toutes les sondes du groupe, en série')
    p.add_argument('--conteneur', default=CONTENEUR)
    p.add_argument('--timeout', type=int, default=120)
    p.add_argument('--dry-run', action='store_true', help='imprime le programme généré, sans docker')
    p.add_argument('--racine', default=RACINE)
    a = p.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    base = os.path.join(a.racine, 'docs', 'audits', 'sondes')
    if bool(a.sonde) == bool(a.toutes):
        p.error('indiquer une sonde OU --toutes GROUPE')
    chemins = (sorted(glob.glob(os.path.join(base, a.toutes, 'C-*.py'))) if a.toutes
               else [os.path.join(base, a.sonde + '.py')])
    if not chemins:
        print('aucune sonde dans %s' % a.toutes)
        return 1
    bilan = []
    for chemin in chemins:
        try:
            code, verdict = jouer(chemin, a.conteneur, a.timeout, executer, a.dry_run)
        except ErreurSonde as e:
            print('REFUSÉE : %s' % e)
            code, verdict = 1, 'REFUSÉE'
        bilan.append((os.path.basename(chemin), code, verdict))
    if a.toutes:
        ok = sum(1 for _, c, _ in bilan if c == 0)
        print('\n== bilan %s : %d/%d OK' % (a.toutes, ok, len(bilan)))
        for nom, code, verdict in bilan:
            print('  %-16s %s' % (nom, verdict if code == 0 else verdict + ' (échec)'))
    return 0 if all(c == 0 for _, c, _ in bilan) else 1


if __name__ == '__main__':
    sys.exit(main())
