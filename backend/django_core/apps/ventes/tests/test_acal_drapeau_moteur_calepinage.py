"""ACAL331 (D-ACAL-17, C-ACAL-145) — ``USE_MOTEUR_CALEPINAGE`` est un
réglage activable par l'ENVIRONNEMENT (défaut OFF), et la commande de dry-run
« compte moteur vs compte du devis » ne modifie RIEN.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_drapeau_moteur_calepinage"
"""
import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import moteur_calepinage_actif
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)

RACINE_DJANGO = Path(__file__).resolve().parents[3]
LAYOUT = {'scenario': 'reseau', 'panelWatt': 550,
          'result': {'panels': 12, 'kwc': 6.6}}


class ReglageDuDrapeau(SimpleTestCase):

    def test_le_reglage_existe_dans_settings_et_vaut_off_par_defaut(self):
        self.assertTrue(hasattr(settings, 'USE_MOTEUR_CALEPINAGE'))
        if os.environ.get('USE_MOTEUR_CALEPINAGE', '0') != '1':
            self.assertFalse(settings.USE_MOTEUR_CALEPINAGE)
            self.assertFalse(moteur_calepinage_actif())
        base = (RACINE_DJANGO / 'erp_agentique' / 'settings'
                / 'base.py').read_text(encoding='utf-8')
        self.assertIn("os.environ.get('USE_MOTEUR_CALEPINAGE', '0') == '1'",
                      base)

    def test_l_environnement_leve_le_drapeau(self):
        code = ('import django; django.setup(); '
                'from apps.ventes.domain.geometrie import '
                'moteur_calepinage_actif as m; print(m())')
        env = dict(os.environ, USE_MOTEUR_CALEPINAGE='1')
        sortie = subprocess.run(
            [sys.executable, '-c', code], cwd=str(RACINE_DJANGO), env=env,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(sortie.returncode, 0, sortie.stderr[-2000:])
        self.assertEqual(sortie.stdout.strip().splitlines()[-1], 'True')


class CommandeDryRun(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference, statut='brouillon'):
        devis = make_devis(self.company, self.user, self.client_obj,
                           [('Panneau mono 550W', '10', '1100')],
                           reference=reference)
        Devis.objects.filter(pk=devis.pk).update(statut=statut,
                                                 roof_layout=LAYOUT)
        Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            titre=reference, roof_layout=LAYOUT)
        return devis

    def _lancer(self, *args):
        sortie = StringIO()
        call_command('comparer_compte_moteur_calepinage', '--json', *args,
                     stdout=sortie)
        return json.loads(sortie.getvalue())

    def test_la_commande_liste_ecart_stocke_vs_moteur_sans_ecrire(self):
        devis = self._devis('DEV-A331-01')
        avant = (LigneDevis.objects.filter(devis=devis).count(),
                 list(LigneDevis.objects.filter(devis=devis)
                      .values_list('quantite', flat=True)))
        resultat = self._lancer('--company', self.company.slug)
        self.assertTrue(resultat['lecture_seule'])
        ligne, = [li for li in resultat['devis']
                  if li['devis'] == 'DEV-A331-01']
        self.assertEqual(ligne['compte_stocke'], 10)
        self.assertTrue(ligne['recalculable'])
        self.assertIn('compte_moteur', ligne)
        self.assertIn('ecart', ligne)
        apres = (LigneDevis.objects.filter(devis=devis).count(),
                 list(LigneDevis.objects.filter(devis=devis)
                      .values_list('quantite', flat=True)))
        self.assertEqual(avant, apres)

    def test_la_commande_refuse_un_devis_envoye(self):
        self._devis('DEV-A331-02', statut='envoye')
        # Sans --devis : un envoyé n'est même pas listé.
        self.assertEqual(
            [li for li in self._lancer()['devis']
             if li['devis'] == 'DEV-A331-02'], [])
        # Désigné explicitement : refusé, jamais recalculé.
        ligne, = self._lancer('--devis', 'DEV-A331-02')['devis']
        self.assertFalse(ligne['recalculable'])
        self.assertIsNone(ligne['compte_moteur'])
        self.assertIn('jamais recalculé', ligne['motif'])
