"""Décision fondateur (Reda, 08/10/2026) — un lead qui SORT de « Signé » par
une action utilisateur dés-accepte son devis.

Le bug d'origine : glisser un lead « Signé » vers une autre colonne ne
changeait que ``Lead.stage`` ; le devis restait « accepté », et le ramener en
« Signé » rouvrait le SigneDialog dont l'acceptation tombait en 409 (« Ce
devis est déjà accepté. ») — pas de célébration.

Ce que ces tests prouvent, de bout en bout par l'API :

* sortie de « Signé » (PATCH unitaire) → devis « envoyé », tampons effacés,
  chantier auto-créé annulé, commission revenue « Approuvé », notes de
  chatter, événement ``devis_acceptation_annulee`` émis, preuve de signature
  conservée ;
* une facture émise BLOQUE : 409 nommant la facture, rien d'écrit ;
* ré-acceptation : plus de 409, le lead revient « Signé », UN seul chantier,
  actif ;
* en masse (``set_stage`` → Froid) : le lead bloqué est sauté avec la raison,
  l'autre passe ;
* multi-tenant : un autre tenant ne voit ni ne dés-accepte rien ;
* un lead « Signé » SANS devis accepté sort exactement comme avant.

Clés d'étape : ``apps.crm.stages`` (miroir de STAGES.py, règle #2).

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_sortie_signe_desaccepte -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

import apps.crm.stages as stages
from apps.crm.models import (
    Apporteur, Client, DealEnregistre, Lead, LeadActivity,
)
from apps.installations.models import Installation
from apps.ventes.models import (
    Devis, DevisActivity, DevisSignature, Facture,
)
from authentication.models import Company
from core.events import devis_acceptation_annulee

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SortieSigneBase(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sortie-signe-co', defaults={'nom': 'Sortie Signé Co'})
        self.user = User.objects.create_user(
            username='sortie_signe_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Signé',
            email='signe@example.com', telephone='+212600000077')
        self._num = 0

    def _lead_et_devis(self, company=None, client_obj=None):
        company = company or self.company
        self._num += 1
        lead = Lead.objects.create(
            company=company, nom=f'Lead {self._num}',
            stage=stages.FOLLOW_UP)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{MONTH}-{8800 + self._num}',
            client=client_obj or self.client_obj, lead=lead,
            statut=Devis.Statut.ENVOYE, date_envoi=timezone.now(),
            taux_tva=Decimal('20'))
        return lead, devis

    def _accepter(self, devis, api=None):
        r = (api or self.api).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Client'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        devis.refresh_from_db()
        return r

    def _patch_stage(self, lead, cible, api=None):
        return (api or self.api).patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': cible, 'confirme_recul': True}, format='json')


class TestSortieSigneUnitaire(SortieSigneBase):
    def test_sortie_desaccepte_et_defait_l_aval(self):
        lead, devis = self._lead_et_devis()
        apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur', taux_commission_pct=5)
        deal = DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=lead,
            statut=DealEnregistre.Statut.APPROUVE)
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        # NTCRM22 pose À_PAYER + montant à l'acceptation ; on le fige ici
        # (le calcul lui-même est couvert par test_qjr_commission_apporteur).
        DealEnregistre.objects.filter(pk=deal.pk).update(
            statut=DealEnregistre.Statut.A_PAYER,
            montant_commission_du=Decimal('100'))
        chantier = Installation.objects.get(devis=devis)
        self.assertFalse(chantier.annule)
        signatures = DevisSignature.objects.filter(devis=devis).count()

        recus = []

        def _capte(sender, devis, **kwargs):
            recus.append((devis.pk, kwargs.get('option_acceptee')))
        devis_acceptation_annulee.connect(_capte, dispatch_uid='t_capte')
        try:
            r = self._patch_stage(lead, stages.FOLLOW_UP)
        finally:
            devis_acceptation_annulee.disconnect(dispatch_uid='t_capte')
        self.assertEqual(r.status_code, 200, r.data)

        lead.refresh_from_db()
        devis.refresh_from_db()
        chantier.refresh_from_db()
        deal.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNone(devis.date_acceptation)
        self.assertEqual(devis.accepte_par_nom, '')
        self.assertEqual(devis.option_acceptee, '')
        self.assertTrue(chantier.annule)
        self.assertEqual(deal.statut, DealEnregistre.Statut.APPROUVE)
        self.assertIsNone(deal.montant_commission_du)
        self.assertEqual([pk for pk, _ in recus], [devis.pk])
        # La preuve de signature n'est jamais supprimée.
        self.assertEqual(
            DevisSignature.objects.filter(devis=devis).count(), signatures)
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, body__contains='Acceptation annulée').exists())
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__contains=f'Acceptation du devis {devis.reference} annulée',
        ).exists())

    def test_facture_emise_bloque_409_rien_ecrit(self):
        lead, devis = self._lead_et_devis()
        self._accepter(devis)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8801',
            devis=devis, client=self.client_obj,
            statut=Facture.Statut.EMISE, type_facture='acompte',
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), created_by=self.user)
        r = self._patch_stage(lead, stages.FOLLOW_UP)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(facture.reference, r.data['detail'])
        self.assertIn('Impossible de sortir ce lead', r.data['detail'])
        lead.refresh_from_db()
        devis.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNotNone(devis.date_acceptation)
        self.assertFalse(Installation.objects.get(devis=devis).annule)
        self.assertFalse(DevisActivity.objects.filter(
            devis=devis, body__contains='Acceptation annulée').exists())

    def test_chantier_planifie_bloque(self):
        lead, devis = self._lead_et_devis()
        self._accepter(devis)
        chantier = Installation.objects.get(devis=devis)
        Installation.objects.filter(pk=chantier.pk).update(
            statut=Installation.Statut.PLANIFIE)
        r = self._patch_stage(lead, stages.COLD)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(chantier.reference, r.data['detail'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_reacceptation_apres_sortie_sans_409_un_seul_chantier(self):
        lead, devis = self._lead_et_devis()
        self._accepter(devis)
        r = self._patch_stage(lead, stages.FOLLOW_UP)
        self.assertEqual(r.status_code, 200, r.data)
        # Le SigneDialog rappelle « accepter » : plus de 409.
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(lead.stage, stages.SIGNED)
        chantiers = Installation.objects.filter(devis=devis)
        self.assertEqual(chantiers.count(), 1)
        self.assertFalse(chantiers.get().annule)

    def test_lead_signe_sans_devis_accepte_inchange(self):
        lead = Lead.objects.create(
            company=self.company, nom='Signé à la main', stage=stages.SIGNED)
        r = self._patch_stage(lead, stages.COLD)
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)


class TestSortieSigneMasse(SortieSigneBase):
    def test_set_stage_masse_saute_le_lead_bloque(self):
        lead_ok, devis_ok = self._lead_et_devis()
        lead_ko, devis_ko = self._lead_et_devis()
        self._accepter(devis_ok)
        self._accepter(devis_ko)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8802',
            devis=devis_ko, client=self.client_obj,
            statut=Facture.Statut.EMISE, type_facture='acompte',
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), created_by=self.user)
        r = self.api.post('/api/django/crm/leads/bulk/', {
            'action': 'set_stage', 'ids': [lead_ok.id, lead_ko.id],
            'stage': stages.COLD}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['updated'], 1)
        sautes = {s['id']: s['reason'] for s in r.data['skipped']}
        self.assertIn(lead_ko.id, sautes)
        self.assertIn('FAC-', sautes[lead_ko.id])
        lead_ok.refresh_from_db()
        lead_ko.refresh_from_db()
        devis_ok.refresh_from_db()
        devis_ko.refresh_from_db()
        self.assertEqual(lead_ok.stage, stages.COLD)
        self.assertEqual(devis_ok.statut, Devis.Statut.ENVOYE)
        self.assertTrue(Installation.objects.get(devis=devis_ok).annule)
        self.assertEqual(lead_ko.stage, stages.SIGNED)
        self.assertEqual(devis_ko.statut, Devis.Statut.ACCEPTE)
        self.assertFalse(Installation.objects.get(devis=devis_ko).annule)


class TestSortieSigneMultiTenant(SortieSigneBase):
    def test_autre_tenant_ne_desaccepte_rien(self):
        lead, devis = self._lead_et_devis()
        self._accepter(devis)
        autre, _ = Company.objects.get_or_create(
            slug='sortie-signe-autre', defaults={'nom': 'Autre'})
        intrus = User.objects.create_user(
            username='sortie_signe_intrus', password='x',
            role_legacy='responsable', company=autre)
        r = self._patch_stage(lead, stages.COLD, api=auth(intrus))
        self.assertEqual(r.status_code, 404)
        devis.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(lead.stage, stages.SIGNED)
        from apps.ventes.selectors import devis_acceptes_actifs
        self.assertEqual(devis_acceptes_actifs(autre, lead_id=lead.pk), [])
        self.assertEqual(
            [d.pk for d in devis_acceptes_actifs(
                self.company, lead_id=lead.pk)], [devis.pk])
