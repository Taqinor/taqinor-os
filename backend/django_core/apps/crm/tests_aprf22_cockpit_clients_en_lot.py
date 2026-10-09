"""APRF22 — « Comptes dormants », « Portefeuille » et ``engagement-bulk``
calculés EN LOT : 3 puis 13 clients coûtent le même nombre de requêtes aux
trois endpoints, et rendent les mêmes listes/scores que le calcul unitaire
d'AVANT (recopié ici comme oracle, sur les sélecteurs ventes d'origine).

Test-du-test : rappeler un calcul par client (ancien
``compute_engagement_score`` en boucle) ⇒ +N requêtes, test_requetes_plates
échoue.
"""
import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import selectors
from apps.crm.engagement import compute_engagement_score
from apps.crm.models import Client, Lead, LeadActivity, PointContact
from apps.ventes.models import Devis, Facture, ShareLink

User = get_user_model()
BASE = '/api/django/crm/clients/'


def _ancien_score(client, now):
    """Oracle : le calcul UNITAIRE d'avant APRF22 (sélecteurs ventes)."""
    from apps.ventes.selectors import (
        devis_du_client_portail, devis_ouverts_ratio_client,
        factures_du_client_portail)
    company = client.company
    lead_ids = list(Lead.objects.filter(
        company=company, client=client).values_list('id', flat=True))
    score = 0
    st = devis_ouverts_ratio_client(company, client.id, limit=200)
    if st['total']:
        score += round(20 * st['ouverts'] / st['total'])
    if lead_ids:
        seuil = now - timezone.timedelta(days=90)
        n = PointContact.objects.filter(
            lead_id__in=lead_ids, date_contact__gte=seuil).count()
        score += min(20, n * 6)
        dates = []
        a = (LeadActivity.objects.filter(lead_id__in=lead_ids)
             .order_by('-created_at').values_list('created_at', flat=True)
             .first())
        c = (PointContact.objects.filter(lead_id__in=lead_ids)
             .order_by('-date_contact')
             .values_list('date_contact', flat=True).first())
        dates = [d for d in (a, c) if d]
        if dates:
            age = (now - max(dates)).days
            if age <= 0:
                score += 20
            elif age < 90:
                score += round(20 * (1 - age / 90))
    factures = factures_du_client_portail(company, client.id, limit=200)
    if factures:
        score += round(20 * sum(1 for f in factures if f.get('payee'))
                       / len(factures))
    devis = devis_du_client_portail(company, client.id, limit=200)
    if devis:
        score += round(20 * sum(1 for d in devis if d.get('accepte'))
                       / len(devis))
    return min(score, 100)


def _anciens_dormants(company, now, seuil):
    """Oracle : ``comptes_dormants`` d'avant APRF22 → {client_id: jours}."""
    from apps.ventes.selectors import (
        devis_du_client_portail, factures_du_client_portail)
    today = now.date()
    out = {}
    for client in Client.objects.filter(company=company):
        dl = devis_du_client_portail(company, client.id, limit=1)
        fl = factures_du_client_portail(company, client.id, limit=1)
        if not dl and not fl:
            continue
        dates = []
        if dl:
            dates.append(selectors._as_date(dl[0]['date_creation']))
        if fl:
            dates.append(selectors._as_date(fl[0]['date_emission']))
        lead_ids = list(Lead.objects.filter(
            company=company, client=client).values_list('id', flat=True))
        if lead_ids:
            dates.append(selectors._as_date(
                LeadActivity.objects.filter(lead_id__in=lead_ids)
                .order_by('-created_at')
                .values_list('created_at', flat=True).first()))
            dates.append(selectors._as_date(
                PointContact.objects.filter(lead_id__in=lead_ids)
                .order_by('-date_contact')
                .values_list('date_contact', flat=True).first()))
        dates = [d for d in dates if d is not None]
        jours = (today - max(dates)).days
        if jours >= seuil:
            out[client.pk] = jours
    return out


class CockpitClientsEnLotTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF22 Solaire', slug='aprf22-cockpit')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf22-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.now = timezone.now()
        self.n = 0

    def _clients(self, nombre):
        for _ in range(nombre):
            self.n += 1
            i = self.n
            client = Client.objects.create(
                company=self.company, nom=f'Client {i}')
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead {i}', owner=self.user,
                client=client)
            age = 200 if i % 2 else 10  # un sur deux dormant
            devis = Devis.objects.create(
                company=self.company, client=client, lead=lead,
                reference=f'DV-APRF22-{i}',
                statut=(Devis.Statut.ACCEPTE if i % 3 == 0
                        else Devis.Statut.ENVOYE))
            Devis.objects.filter(pk=devis.pk).update(
                date_creation=self.now - datetime.timedelta(days=age))
            if i % 2 == 0:
                ShareLink.objects.create(
                    company=self.company, devis=devis, view_count=2)
                Facture.objects.create(
                    company=self.company, client=client, devis=devis,
                    reference=f'FA-APRF22-{i}',
                    statut=(Facture.Statut.PAYEE if i % 4 == 0
                            else Facture.Statut.EMISE))
                PointContact.objects.create(
                    company=self.company, lead=lead, canal='telephone',
                    date_contact=self.now - datetime.timedelta(days=3))
                LeadActivity.objects.create(
                    company=self.company, lead=lead,
                    kind=LeadActivity.Kind.NOTE, body='note')

    def _appels(self):
        sorties = {}
        nb = {}
        for nom in ('dormants/', 'mon-portefeuille/', 'engagement-bulk/'):
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get(BASE + nom)
            self.assertEqual(resp.status_code, 200, resp.data)
            nb[nom] = len(ctx.captured_queries)
            sorties[nom] = resp.data
        return nb, sorties

    def test_requetes_plates(self):
        self._clients(3)
        self._appels()  # échauffement
        avant, _ = self._appels()
        self._clients(10)
        apres, _ = self._appels()
        self.assertEqual(apres, avant)

    def test_sorties_egales_au_calcul_unitaire(self):
        self._clients(13)
        clients = list(Client.objects.filter(company=self.company))
        attendu = {c.pk: _ancien_score(c, self.now) for c in clients}
        for c in clients:
            self.assertEqual(compute_engagement_score(c, now=self.now),
                             attendu[c.pk], c.nom)
        portefeuille = selectors.portefeuille_commercial(
            self.company, self.user, now=self.now)
        self.assertEqual({r['client_id']: r['score'] for r in portefeuille},
                         attendu)
        self.assertEqual([r['score'] for r in portefeuille],
                         sorted(attendu.values()))
        dormants = selectors.comptes_dormants(
            self.company, seuil_jours=90, now=self.now)
        self.assertEqual(
            {e['client'].pk: e['jours_inactivite'] for e in dormants},
            _anciens_dormants(self.company, self.now, 90))
        self.assertTrue(dormants)
