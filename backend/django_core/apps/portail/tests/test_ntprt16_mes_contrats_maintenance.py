"""Tests NTPRT16 — « Mes contrats » (maintenance), portail CLIENT.

Monte ``sav.selectors.contrats_maintenance_portail_client`` +
``sav.services.demander_action_portail_maintenance`` sur
``MesContratsMaintenancePortailViewSet`` (``apps.portail.views_client``).
Couvre :

* l'isolation (un contrat d'un autre client, ou d'une autre société, est
  introuvable) ;
* la demande de renouvellement/résiliation NE MODIFIE JAMAIS ``actif`` ni
  aucune date du contrat — elle journalise seulement une demande ;
* un type de demande invalide NOMME le champ fautif ;
* NTPRT6 — un membre d'équipe « lecture seule » ne peut pas déposer de
  demande.

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt16_mes_contrats_maintenance -v2
"""
import datetime
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.services import (
    accepter_invitation_portail, inviter_membre_portail,
    provisionner_compte_portail_client,
)
from apps.sav.models import ContratMaintenance
from authentication.models import Company

_seq = itertools.count(1)

URL_LISTE = '/api/django/portail/mes-contrats-maintenance/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT16-{n}',
        email=f'ntprt16-{company.id}-{n}@example.invalid')


def make_admin(company):
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_contrat(company, client, *, actif=True):
    return ContratMaintenance.objects.create(
        company=company, client=client,
        periodicite=ContratMaintenance.Periodicite.ANNUEL,
        date_debut=datetime.date(2026, 1, 1), actif=actif,
        visites_incluses_an=2, deplacements_inclus_an=1,
        pieces_couvertes_pct=50)


class MesContratsMaintenanceIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt16-co', 'NTPRT16 Société')
        self.client_crm, self.admin = make_admin(self.company)
        self.contrat = make_contrat(self.company, self.client_crm)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_liste_le_contrat_du_client(self):
        res = self.api.get(URL_LISTE)
        self.assertEqual(res.status_code, 200, res.data)
        ids = [c['id'] for c in res.data['results']]
        self.assertEqual(ids, [self.contrat.id])
        self.assertEqual(res.data['results'][0]['visites_incluses_an'], 2)

    def test_contrat_dun_autre_client_introuvable(self):
        autre_client = make_client_crm(self.company)
        autre_contrat = make_contrat(self.company, autre_client)
        res = self.api.get(f'{URL_LISTE}{autre_contrat.id}/')
        self.assertEqual(res.status_code, 404)

    def test_contrat_dune_autre_societe_invisible(self):
        autre = make_company('ntprt16-co-b', 'NTPRT16 Société B')
        autre_client, _ = make_admin(autre)
        make_contrat(autre, autre_client)
        res = self.api.get(URL_LISTE)
        ids = [c['id'] for c in res.data['results']]
        self.assertNotIn(self.contrat.id + 1000, ids)  # garde-fou trivial
        self.assertEqual(len(res.data['results']), 1)


class DemanderActionContratMaintenanceTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt16-dm', 'NTPRT16 Demande')
        self.client_crm, self.admin = make_admin(self.company)
        self.contrat = make_contrat(self.company, self.client_crm)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def _url(self):
        return f'{URL_LISTE}{self.contrat.id}/demander/'

    def test_demande_renouvellement_najamais_actif_ni_dates(self):
        res = self.api.post(
            self._url(), {'type_demande': 'renouvellement'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.contrat.refresh_from_db()
        self.assertTrue(self.contrat.actif)
        self.assertIsNone(self.contrat.date_renouvellement)

    def test_type_demande_invalide_nomme_le_champ(self):
        res = self.api.post(
            self._url(), {'type_demande': 'annulation-immediate'},
            format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('type_demande', res.data)

    def test_contrat_dautrui_introuvable_en_ecriture(self):
        autre_client = make_client_crm(self.company)
        autre_contrat = make_contrat(self.company, autre_client)
        res = self.api.post(
            f'{URL_LISTE}{autre_contrat.id}/demander/',
            {'type_demande': 'resiliation'}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_membre_lecture_ne_peut_pas_demander(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'lecteur@example.invalid',
            'lecture')
        lecteur = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-lecteur-1234')
        api = APIClient()
        api.force_authenticate(user=lecteur)
        res = api.post(
            self._url(), {'type_demande': 'renouvellement'}, format='json')
        self.assertEqual(res.status_code, 403)
