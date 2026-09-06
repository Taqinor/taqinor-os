"""MRY22 — « Perdu sans raison » n'existe plus, sur AUCUN des trois chemins.

Une ligne « perdu » sans motif ne sert à personne : elle sort le lead du
pipeline sans rien apprendre, et le KPI « perdus avec motif » (MRY21) ne peut
plus rien dire. Trois chemins mènent à « perdu » — la fiche, l'action en masse,
le refus de devis — et les trois devaient être fermés, sinon la règle se
contourne par le chemin resté ouvert.

Nuances tenues :
  * un motif DÉJÀ posé sur le lead suffit — on ne redemande pas un motif à qui
    ne fait que re-cocher la case ;
  * le refus de devis peut arriver SANS motif saisi : il retombe alors sur
    « Devis refusé » plutôt que d'écrire NULL. C'est le seul chemin où un
    défaut est légitime, parce qu'il énonce un fait vrai ;
  * `perdu=False` n'exige évidemment rien.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.events import devis_refused

from apps.crm.models import Client, Lead
from apps.crm.services import apply_bulk_action
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry22'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x', role_legacy='admin',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')


class FicheTests(_Base):
    slug = 'mry22-fiche'

    def test_patch_sans_motif_refuse(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('motif_perte', resp.data)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def test_patch_avec_motif_accepte(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True, 'motif_perte': 'Prix'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, 'Prix')

    def test_un_motif_deja_pose_suffit(self):
        """On ne redemande pas un motif à qui ne fait que re-cocher la case."""
        self.lead.motif_perte = 'Concurrent'
        self.lead.save(update_fields=['motif_perte'])
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_un_motif_vide_ne_compte_pas_pour_un_motif(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True, 'motif_perte': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_perdu_faux_nexige_rien(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class MasseTests(_Base):
    slug = 'mry22-masse'

    def test_bulk_sans_motif_refuse_en_400(self):
        resp = self.api.post('/api/django/crm/leads/bulk/', {
            'action': 'set_perdu', 'ids': [self.lead.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def test_bulk_avec_motif_accepte(self):
        resp = self.api.post('/api/django/crm/leads/bulk/', {
            'action': 'set_perdu', 'ids': [self.lead.pk],
            'motif': 'Hors zone',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, 'Hors zone')

    def test_le_service_leve_une_ValueError(self):
        """Perdre 40 leads d'un coup SANS raison est pire, pas plus
        acceptable, qu'en perdre un."""
        with self.assertRaises(ValueError):
            apply_bulk_action(
                company=self.company, user=self.acteur,
                lead_ids=[self.lead.pk], op='set_perdu', params={})


class RefusDeDevisTests(_Base):
    slug = 'mry22-refus'

    def _devis(self, reference):
        client = Client.objects.create(
            company=self.company, nom='Client', email=f'{reference}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=reference, client=client,
            lead=self.lead, statut='refuse', taux_tva=Decimal('20.00'))

    def test_refus_sans_motif_retombe_sur_devis_refuse(self):
        """Seul chemin où un défaut est légitime : il énonce un fait vrai,
        au lieu d'écrire NULL — ce qui rouvrirait la porte fermée ailleurs."""
        devis_refused.send(
            sender='test', devis=self._devis('DEV-MRY22-1'),
            user=self.acteur, motif_refus='', marquer_lead_perdu=True)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, 'Devis refusé')

    def test_refus_avec_motif_garde_le_motif_reel(self):
        devis_refused.send(
            sender='test', devis=self._devis('DEV-MRY22-2'),
            user=self.acteur, motif_refus='Délai trop long',
            marquer_lead_perdu=True)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.motif_perte, 'Délai trop long')

    def test_sans_marquer_lead_perdu_le_lead_reste_vivant(self):
        devis_refused.send(
            sender='test', devis=self._devis('DEV-MRY22-3'),
            user=self.acteur, motif_refus='')
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)


class ChainageArretTests(_Base):
    slug = 'mry22-chainage'

    def test_un_patch_avec_motif_arrete_les_cadences(self):
        """MRY9 + MRY22 : la perte est motivée ET les relances s'arrêtent."""
        from apps.crm.models import RelanceEtape
        from apps.crm.services import initialiser_plan_relance
        initialiser_plan_relance(self.lead, self.acteur, cadence='contact')
        self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True, 'motif_perte': 'Locataire'}, format='json')
        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.A_FAIRE).count(), 0)
