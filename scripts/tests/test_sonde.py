"""AMET93 — garde du lanceur de sondes `scripts/sonde.py`.

Ce que ce test verrouille (sans docker, sans Django, sans base) :
1. une sonde sans en-tete `SONDE = {constat, sha, attendu}` ou sans `def sonde(ctx)` est REFUSEE avant
   que quoi que ce soit parte vers le conteneur ;
2. le programme genere annule TOUJOURS la transaction (`set_rollback(True)`), met le mail en memoire,
   coupe Celery, bloque le HTTP sortant et arme `signal.alarm` — retirer l'un de ces garde-fous = rouge ;
3. le code de sortie exige « base inchangee » ET un verdict REPRO (ou STATIQUE) ;
4. le programme est execute pour de bon contre des modules Django/Celery factices : il imprime la ligne
   `@@RESULT` avec les comptes avant / apres, sans toucher a rien de reel.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts'))
import sonde  # noqa: E402

ENTETE = ('SONDE = {"constat": "C-TST-001", "sha": "abc123", "attendu": "le chiffre vaut 42"}\n'
          'def sonde(ctx):\n    print("ligne imprimee")\n    return {"valeur": 42}\n')


def _racine(fichiers):
    d = tempfile.mkdtemp(prefix='sonde_test_')
    dossier = os.path.join(d, 'docs', 'audits', 'sondes', 'TST')
    os.makedirs(dossier)
    for nom, texte in fichiers.items():
        with open(os.path.join(dossier, nom), 'w', encoding='utf-8') as f:
            f.write(texte)
    return d


class FauxShell:
    """Remplace `docker exec` : memorise le programme recu, repond par un resultat fixe."""

    def __init__(self, resultat=None, rc=0):
        self.appels = []
        self.resultat = resultat if resultat is not None else {
            'observe': 'valeur=42', 'verdict': 'REPRO', 'base_inchangee': True, 'comptes_avant': 3,
            'comptes_apres': 3, 'mails': 0, 'celery_bloques': 0}
        self.rc = rc

    def __call__(self, cmd, programme, timeout):
        self.appels.append((cmd, programme))
        return self.rc, 'bruit\n@@RESULT ' + json.dumps(self.resultat) + '\n', ''


def _lancer(racine, ref='TST/C-TST-001', faux=None, argv_extra=()):
    faux = faux or FauxShell()
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = sonde.main([ref, '--racine', racine, *argv_extra], executer=faux)
    return code, sortie.getvalue(), faux


class SondeTests(unittest.TestCase):
    def test_lanceur_refuse_une_sonde_sans_en_tete_et_annule_la_transaction(self):
        racine = _racine({'C-TST-001.py': 'def sonde(ctx):\n    return 1\n',
                          'C-TST-002.py': 'SONDE = {"constat": "C-TST-002", "sha": "a", "attendu": "x"}\n'})
        for ref in ('TST/C-TST-001', 'TST/C-TST-002'):
            code, sortie, faux = _lancer(racine, ref)
            self.assertNotEqual(code, 0, ref)
            self.assertEqual(faux.appels, [], 'rien ne doit partir vers le conteneur : ' + ref)
        racine = _racine({'C-TST-001.py': ENTETE})
        code, sortie, faux = _lancer(racine)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(faux.appels), 1)
        programme = faux.appels[0][1]
        self.assertIn('set_rollback(True)', programme)
        self.assertIn('transaction.atomic()', programme)
        compile(programme, 'programme', 'exec')

    def test_garde_fous_presents_dans_le_programme(self):
        _, _, faux = _lancer(_racine({'C-TST-001.py': ENTETE}))
        programme = faux.appels[0][1]
        for garde in ('django.core.mail.backends.locmem.EmailBackend', 'CELERY_TASK_ALWAYS_EAGER',
                      'apply_async', 'create_connection', 'signal.alarm', '@@RESULT'):
            self.assertIn(garde, programme)
        cmd = faux.appels[0][0]
        self.assertEqual(cmd[:4], ['docker', 'exec', '-i', 'erp-agentique-django_core-1'])
        self.assertEqual(cmd[-4:], ['python', '-u', 'manage.py', 'shell'])

    def test_code_de_sortie_exige_base_inchangee_et_repro(self):
        racine = _racine({'C-TST-001.py': ENTETE})
        base = {'observe': 'x', 'verdict': 'REPRO', 'base_inchangee': True}
        self.assertEqual(_lancer(racine, faux=FauxShell(dict(base)))[0], 0)
        self.assertEqual(_lancer(racine, faux=FauxShell(dict(base, base_inchangee=False)))[0], 1)
        sans_cle = {k: v for k, v in base.items() if k != 'base_inchangee'}
        self.assertEqual(_lancer(racine, faux=FauxShell(sans_cle))[0], 1)
        self.assertEqual(_lancer(racine, faux=FauxShell(dict(base, verdict='ÉCART')))[0], 1)
        self.assertEqual(_lancer(racine, faux=FauxShell(dict(base, verdict='STATIQUE')))[0], 0)
        code, sortie, _ = _lancer(racine, faux=FauxShell(dict(base, base_inchangee=False)))
        self.assertIn('base inchangée : non', sortie)

    def test_sortie_imprime_attendu_observe_verdict(self):
        code, sortie, _ = _lancer(_racine({'C-TST-001.py': ENTETE}))
        for morceau in ('attendu : le chiffre vaut 42', 'observé : valeur=42', 'verdict : REPRO',
                        'base inchangée : oui'):
            self.assertIn(morceau, sortie)

    def test_pas_de_ligne_resultat_est_un_echec(self):
        racine = _racine({'C-TST-001.py': ENTETE})

        def muet(cmd, programme, timeout):
            return 1, 'Traceback...', 'boom'
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = sonde.main(['TST/C-TST-001', '--racine', racine], executer=muet)
        self.assertEqual(code, 1)

    def test_dry_run_n_appelle_pas_docker_et_imprime_un_programme_compilable(self):
        racine = _racine({'C-TST-001.py': ENTETE})
        code, sortie, faux = _lancer(racine, argv_extra=['--dry-run'])
        self.assertEqual(code, 0)
        self.assertEqual(faux.appels, [])
        compile(sortie, 'dry-run', 'exec')

    def test_toutes_rejoue_le_groupe_en_serie_et_echoue_si_une_echoue(self):
        racine = _racine({'C-TST-001.py': ENTETE,
                          'C-TST-002.py': ENTETE.replace('C-TST-001', 'C-TST-002')})
        faux = FauxShell()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = sonde.main(['--toutes', 'TST', '--racine', racine], executer=faux)
        self.assertEqual(code, 0, sortie.getvalue())
        self.assertEqual(len(faux.appels), 2)
        self.assertIn('2/2', sortie.getvalue())
        mauvais = FauxShell({'observe': 'x', 'verdict': 'ÉCART', 'base_inchangee': True})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sonde.main(['--toutes', 'TST', '--racine', racine], executer=mauvais), 1)

    def test_les_sondes_du_depot_respectent_le_contrat(self):
        dossier = os.path.join(REPO_ROOT, 'docs', 'audits', 'sondes', 'AMET')
        noms = sorted(n for n in os.listdir(dossier) if n.startswith('C-AMET-') and n.endswith('.py'))
        self.assertGreaterEqual(len(noms), 12)
        for nom in noms:
            _, entete = sonde.charger(os.path.join(dossier, nom))
            self.assertEqual(entete['constat'], nom[:-3], nom)

    def test_conteneur_surcharge(self):
        _, _, faux = _lancer(_racine({'C-TST-001.py': ENTETE}), argv_extra=['--conteneur', 'autre'])
        self.assertEqual(faux.appels[0][0][3], 'autre')

    def test_programme_execute_contre_des_faux_modules_et_rend_la_base_inchangee(self):
        programme = sonde.programme(ENTETE, {'constat': 'C-TST-001', 'sha': 'a', 'attendu': 'x'}, 30)
        etat = {'rollback': None, 'comptes': [3, 3]}

        class Atomic:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        transaction = types.SimpleNamespace(atomic=lambda: Atomic(),
                                            set_rollback=lambda v: etat.__setitem__('rollback', v))
        modele = mock.Mock()
        modele._meta.managed, modele._meta.proxy = True, False
        modele._meta.label = 'tst.Modele'
        modele._default_manager.count.side_effect = lambda: etat['comptes'][0]
        django = types.ModuleType('django')
        django_conf = types.ModuleType('django.conf')
        django_conf.settings = types.SimpleNamespace()
        django_db = types.ModuleType('django.db')
        django_db.transaction = transaction
        django_apps = types.ModuleType('django.apps')
        django_apps.apps = types.SimpleNamespace(get_models=lambda: [modele])
        django_core = types.ModuleType('django.core')
        django_mail = types.ModuleType('django.core.mail')
        django_mail.outbox = []
        celery = types.ModuleType('celery')
        celery_app = types.ModuleType('celery.app')
        celery_task = types.ModuleType('celery.app.task')

        class Task:
            pass
        celery_task.Task = Task
        faux = {'django': django, 'django.conf': django_conf, 'django.db': django_db,
                'django.apps': django_apps, 'django.core': django_core, 'django.core.mail': django_mail,
                'celery': celery, 'celery.app': celery_app, 'celery.app.task': celery_task}
        sortie = io.StringIO()
        with mock.patch.dict(sys.modules, faux), mock.patch.object(socket, 'create_connection'), \
                contextlib.redirect_stdout(sortie):
            try:
                exec(compile(programme, 'programme', 'exec'), {'__name__': '__sonde__'})
            except SystemExit as e:
                code = e.code
        self.assertEqual(code, 0, sortie.getvalue())
        self.assertIs(etat['rollback'], True)
        self.assertEqual(django_conf.settings.EMAIL_BACKEND, 'django.core.mail.backends.locmem.EmailBackend')
        self.assertIs(django_conf.settings.CELERY_TASK_ALWAYS_EAGER, False)
        ligne = [x for x in sortie.getvalue().splitlines() if x.startswith('@@RESULT ')][0]
        res = json.loads(ligne[len('@@RESULT '):])
        self.assertEqual(res['verdict'], 'REPRO')
        self.assertIs(res['base_inchangee'], True)
        self.assertIn('ligne imprimee', res['observe'])
        self.assertIn('42', res['observe'])


if __name__ == '__main__':
    unittest.main()
