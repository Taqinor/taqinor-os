"""CAD159 — [TRANCHÉ 21/09/2026] champs du site TOUJOURS éditables, jamais
reposés.

Décision fondateur : la valeur venue du site reste visible avec sa provenance
et peut être écrasée en connaissance de cause (CAD150) ; en revanche la
QUESTION n'est jamais reposée quand le champ est rempli — elle revient
pré-remplie, « à confirmer ». Écartés : « éditable seulement si vide » et
« jamais éditable ».

Côté serveur, « la liste des questions à poser » est ``champs_a_poser`` du
panneau d'appel (``apps/crm/panneau_appel.py``, contrat ``panneau_appel``) ;
la valeur y revient dans ``prefill``. Contrat de la provenance :
``apps/crm/contract_samples/lead_provenance_site.json``.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import panneau_appel
from apps.crm.models import Lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_provenance_site.json').read_text(encoding='utf-8'))


class ReglePureTests(SimpleTestCase):

    def test_le_contrat_ne_couvre_que_les_champs_du_site(self):
        for exemple in ('exemple', 'exemple_ecrasee', 'exemple_sans_site'):
            for champ in CONTRAT[exemple]['provenance_site']:
                with self.subTest(exemple=exemple, champ=champ):
                    self.assertIn(champ, Lead.CHAMPS_SITE)


class JamaisReposeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD159 Solaire',
                                              slug='cad159-solaire')
        exemple = CONTRAT['exemple']
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', source=Lead.Source.SITE_WEB,
            ownership=exemple['ownership'], roof_age=exemple['roof_age'])

    def _champs_a_poser(self, lead):
        return [q['champ'] for q in panneau_appel.questions_a_poser(lead)]

    def test_un_champ_renseigne_par_le_site_n_est_pas_repose(self):
        a_poser = self._champs_a_poser(self.lead)
        prefill = panneau_appel.prefill_du_panneau(self.lead)
        for champ in CONTRAT['exemple']['provenance_site']:
            with self.subTest(champ=champ):
                self.assertNotIn(champ, a_poser)
                # … il revient PRÉ-REMPLI, pour être confirmé à l'oral.
                self.assertEqual(prefill[champ], CONTRAT['exemple'][champ])

    def test_le_meme_champ_vide_reste_une_question(self):
        vide = Lead.objects.create(company=self.company, nom='Walk-in')
        a_poser = self._champs_a_poser(vide)
        self.assertIn('ownership', a_poser)
        self.assertIn('roof_age', a_poser)
