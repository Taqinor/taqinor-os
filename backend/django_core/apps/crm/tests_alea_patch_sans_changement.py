"""ALEA29 — un PATCH lead sans changement réel n'avance ni
``date_modification`` ni ``updated_by`` (C-ALEA-017, sonde V3 LFICHE-4e).

Aucun mock : ``perform_update`` et ``_save_borne_aux_champs`` réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

User = get_user_model()


class PatchSansChangementTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA29', slug='taqinor-alea29')
        self.u1 = User.objects.create_user(
            username='alea29-u1', password='x', company=self.company,
            role_legacy='admin')
        self.u2 = User.objects.create_user(
            username='alea29-u2', password='x', company=self.company,
            role_legacy='admin')
        self.lead = Lead.objects.create(
            company=self.company, nom='Stable', prenom='Lead',
            telephone='+212661290001', ville='Casablanca')
        self.t0 = timezone.now() - datetime.timedelta(days=2)
        Lead.objects.filter(pk=self.lead.pk).update(
            date_modification=self.t0, updated_by=self.u1)
        self.api = APIClient()
        self.api.force_authenticate(self.u2)
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _etat(self):
        self.lead.refresh_from_db()
        return self.lead.date_modification, self.lead.updated_by_id

    def _assert_get_identique(self, avant):
        apres = self.api.get(self.url).json()
        self.assertEqual(apres['date_modification'],
                         avant['date_modification'])
        self.assertEqual(apres.get('updated_by_nom'),
                         avant.get('updated_by_nom'))

    def test_corps_vide_n_avance_pas(self):
        avant = self.api.get(self.url).json()
        r = self.api.patch(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._etat(), (self.t0, self.u1.pk))
        self._assert_get_identique(avant)

    def test_valeur_identique_n_avance_pas(self):
        avant = self.api.get(self.url).json()
        r = self.api.patch(self.url, {'ville': 'Casablanca'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._etat(), (self.t0, self.u1.pk))
        self._assert_get_identique(avant)

    def test_vrai_changement_avance(self):
        r = self.api.patch(self.url, {'ville': 'Rabat'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        date, par = self._etat()
        self.assertGreater(date, self.t0)
        self.assertEqual(par, self.u2.pk)
        self.assertEqual(self.lead.ville, 'Rabat')


class PatchMarqueSaisiesHumainesTests(TestCase):
    """ERR-LEAD-SAISIES-HUMAINES-FORMULAIRE — l'écriture bornée (CRX25) garde le
    marqueur `saisies_humaines` posé par le sérialiseur, sans élargir la borne."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor SH', slug='taqinor-sh')
        self.user = User.objects.create_user(
            username='sh-u1', password='x', company=self.company,
            role_legacy='admin')
        self.lead = Lead.objects.create(
            company=self.company, nom='Marque', prenom='Lead',
            telephone='+212661290002', whatsapp='0661290002',
            ville='Casablanca')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def test_regle_automatique_respecte_marqueur_et_dedup(self):
        # ACVI32 — la porte des automatisations écrit comme le PATCH.
        from apps.crm.fiche_ecritures import appliquer_champ_automatique
        from apps.crm.services import find_duplicates_by_contact
        from apps.records.models import Activity
        from apps.records.provenance import MESSAGE_REFUS

        Lead.objects.filter(pk=self.lead.pk).update(email='a@exemple.ma')
        r = self.api.patch(self.url, {'email': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.lead.refresh_from_db()
        self.assertIn('email', self.lead.saisies_humaines)

        appliquer_champ_automatique(self.lead, 'email', 'x@exemple.ma')
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.email)
        self.assertTrue(Activity.objects.filter(
            company=self.company, field='email', body=MESSAGE_REFUS).exists())

        b = Lead.objects.create(company=self.company, nom='B')
        appliquer_champ_automatique(b, 'telephone', '0612340025')
        b.refresh_from_db()
        self.assertEqual(b.phone_normalise, '612340025')
        self.assertEqual(
            [d.pk for d in find_duplicates_by_contact(
                self.company, phone='0612340025')], [b.pk])

    def test_post_marque_les_champs_saisis(self):
        # ACVI25 — la date tapée au POST survit au démarrage de la cadence.
        import datetime

        from django.utils import timezone

        date = timezone.localdate() + datetime.timedelta(days=10)
        r = self.api.post('/api/django/crm/leads/', {
            'nom': 'X', 'telephone': '0612345678',
            'relance_date': date.isoformat()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        lead = Lead.objects.get(pk=r.data['id'])
        self.assertEqual(lead.relance_date, date)
        self.assertLessEqual(
            {'nom', 'telephone', 'relance_date'}, set(lead.saisies_humaines))
        self.assertFalse({'owner', 'company'} & set(lead.saisies_humaines))

    def test_patch_vide_whatsapp_persiste_le_marqueur(self):
        r = self.api.patch(self.url, {'whatsapp': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.lead.refresh_from_db()
        self.assertIn('whatsapp', self.lead.saisies_humaines)
        from apps.records.provenance import ecrire_si_libre
        self.assertFalse(
            ecrire_si_libre(self.lead, 'whatsapp', '212600019019',
                            journal=False))

    def test_borne_crx25_inchangee_champ_non_envoye_intact(self):
        # La ville change en base entre-temps ; le PATCH {whatsapp} ne doit
        # PAS la réécrire (borne CRX25 conservée).
        Lead.objects.filter(pk=self.lead.pk).update(ville='Rabat')
        r = self.api.patch(self.url, {'whatsapp': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.ville, 'Rabat')
        self.assertEqual(self.lead.saisies_humaines, ['whatsapp'])
