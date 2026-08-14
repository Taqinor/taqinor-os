"""NTMKT17 — Progressive profiling : champs déjà connus masqués sur le
formulaire public d'intake pour un visiteur RECONNU (email/téléphone déjà
connu du navigateur, réutilisé via ``?identifiant=``).

Couvre : visiteur inconnu = formulaire complet (inchangé), identifiant sans
lead correspondant = formulaire complet (no-op), visiteur reconnu = seuls les
champs pas encore renseignés sont rendus, isolation multi-société.
"""
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead
from apps.marketing.models import FormulaireIntake


class ProgressiveProfilingTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt17', nom='NTMKT17')
        self.formulaire = FormulaireIntake.objects.create(
            company=self.co, nom='Pompage agricole', slug='pompage-ntmkt17',
            champs=[{'code': 'nom'}, {'code': 'email'}, {'code': 'ville'}])

    def _url(self, identifiant=None):
        url = reverse(
            'mkt-formulaire-intake-public',
            kwargs={'slug': 'pompage-ntmkt17'})
        if identifiant:
            url += f'?identifiant={identifiant}'
        return url

    def test_visiteur_inconnu_voit_le_formulaire_complet(self):
        res = self.client.get(self._url())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['champs']), 3)

    def test_identifiant_sans_lead_correspondant_voit_le_formulaire_complet(self):
        res = self.client.get(self._url('inconnu@exemple.ma'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['champs']), 3)

    def test_visiteur_connu_ne_revoit_pas_les_champs_deja_connus(self):
        Lead.objects.create(
            company=self.co, nom='Ahmed', email='ahmed@exemple.ma')
        res = self.client.get(self._url('ahmed@exemple.ma'))
        self.assertEqual(res.status_code, 200)
        codes = [c['code'] for c in res.json()['champs']]
        # nom + email déjà connus, ville jamais renseignée -> ne reste que ville.
        self.assertEqual(codes, ['ville'])

    def test_visiteur_connu_par_telephone(self):
        Lead.objects.create(
            company=self.co, nom='Fatima', telephone='0612345678',
            ville='Agadir')
        res = self.client.get(self._url('0612345678'))
        self.assertEqual(res.status_code, 200)
        codes = [c['code'] for c in res.json()['champs']]
        # nom + ville connus -> ne reste que email.
        self.assertEqual(codes, ['email'])

    def test_no_op_sans_doublon_detecte_pour_une_autre_societe(self):
        autre = Company.objects.create(slug='ntmkt17b', nom='NTMKT17b')
        Lead.objects.create(
            company=autre, nom='Ahmed', email='ahmed@exemple.ma', ville='X')
        # Le lead existe mais dans une AUTRE société : jamais adressable.
        res = self.client.get(self._url('ahmed@exemple.ma'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['champs']), 3)
