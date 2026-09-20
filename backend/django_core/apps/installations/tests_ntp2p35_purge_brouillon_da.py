"""
NTP2P35 — Archivage planifié des brouillons de ``DemandeAchat`` abandonnés.

Couvre :
  * CRITÈRE D'ACCEPTATION : un brouillon vieux de 4 mois disparaît de la liste
    active par défaut ET reste consultable via le filtre « archivées » ;
  * jamais de suppression dure (la ligne existe toujours en base) ;
  * un brouillon ÉPINGLÉ n'est jamais archivé, quel que soit son âge ;
  * une demande SOUMISE/APPROUVÉE ancienne n'est jamais touchée ;
  * un brouillon récent n'est pas touché ;
  * idempotence : une seconde exécution n'archive plus rien ;
  * le seuil est lu par société sur ``stock.AchatsParametres`` quand il y est
    posé, sinon 90 jours (défaut) ;
  * isolation société : la tâche n'archive jamais le brouillon d'une autre
    société que la sienne.

Run :
    python manage.py test apps.installations.tests_ntp2p35_purge_brouillon_da -v2
"""
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat
from apps.installations.tasks import (
    PURGE_BROUILLON_JOURS_DEFAUT, _normaliser_seuil_purge,
    _seuil_purge_brouillon_jours, purger_demandes_achat_brouillon_task,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntp2p35-co-{n}', defaults={'nom': f'NTP2P35 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p35-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_demande(company, user, *, jours, statut=DemandeAchat.Statut.BROUILLON,
                 epinglee=False):
    """Crée une demande puis RECULE ``date_modification`` de ``jours``.

    ``date_modification`` est un ``auto_now`` : seule une écriture en masse
    (``update``) peut la poser à une valeur choisie — un ``save()`` la
    réécrirait à « maintenant »."""
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-P35-{next(_seq):04d}',
        objet='Réquisition de test', created_by=user, statut=statut,
        epinglee=epinglee)
    DemandeAchat.objects.filter(pk=da.pk).update(
        date_modification=timezone.now() - timedelta(days=jours))
    da.refresh_from_db()
    return da


class PurgeBrouillonDemandeAchatTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_brouillon_de_quatre_mois_archive_et_reste_consultable(self):
        """CRITÈRE D'ACCEPTATION NTP2P35."""
        vieux = make_demande(self.company, self.user, jours=120)

        purger_demandes_achat_brouillon_task()

        vieux.refresh_from_db()
        self.assertTrue(vieux.archivee)
        self.assertIsNotNone(vieux.date_archivage)
        # Jamais de suppression dure : la ligne est toujours là.
        self.assertTrue(DemandeAchat.objects.filter(pk=vieux.pk).exists())

        # Absente de la liste ACTIVE par défaut…
        resp = self.api.get(f'{BASE}/demandes-achat/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn(vieux.pk, [r['id'] for r in resp.data['results']])

        # …mais présente sous le filtre « archivées ».
        resp = self.api.get(f'{BASE}/demandes-achat/?archivees=1')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn(vieux.pk, [r['id'] for r in resp.data['results']])

        # Et son détail reste accessible (consultable, pas masquée).
        resp = self.api.get(f'{BASE}/demandes-achat/{vieux.pk}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['archivee'])

    def test_brouillon_epingle_jamais_archive(self):
        epingle = make_demande(
            self.company, self.user, jours=400, epinglee=True)

        purger_demandes_achat_brouillon_task()

        epingle.refresh_from_db()
        self.assertFalse(epingle.archivee)
        self.assertIsNone(epingle.date_archivage)
        resp = self.api.get(f'{BASE}/demandes-achat/')
        self.assertIn(epingle.pk, [r['id'] for r in resp.data['results']])

    def test_brouillon_recent_intact(self):
        recent = make_demande(self.company, self.user, jours=10)

        purger_demandes_achat_brouillon_task()

        recent.refresh_from_db()
        self.assertFalse(recent.archivee)

    def test_demande_soumise_ancienne_jamais_archivee(self):
        soumise = make_demande(
            self.company, self.user, jours=200,
            statut=DemandeAchat.Statut.SOUMISE)
        approuvee = make_demande(
            self.company, self.user, jours=200,
            statut=DemandeAchat.Statut.APPROUVEE)

        purger_demandes_achat_brouillon_task()

        soumise.refresh_from_db()
        approuvee.refresh_from_db()
        self.assertFalse(soumise.archivee)
        self.assertFalse(approuvee.archivee)

    def test_seconde_execution_idempotente(self):
        vieux = make_demande(self.company, self.user, jours=120)

        premier = purger_demandes_achat_brouillon_task()
        vieux.refresh_from_db()
        premiere_date = vieux.date_archivage
        second = purger_demandes_achat_brouillon_task()

        self.assertEqual(premier.get(self.company.id), 1)
        self.assertEqual(second.get(self.company.id), 0)
        vieux.refresh_from_db()
        self.assertEqual(vieux.date_archivage, premiere_date)

    def test_epingler_un_brouillon_via_api(self):
        """`epinglee` est le seul des trois champs que le terrain écrit."""
        da = make_demande(self.company, self.user, jours=120)

        resp = self.api.patch(
            f'{BASE}/demandes-achat/{da.pk}/',
            {'epinglee': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        purger_demandes_achat_brouillon_task()

        da.refresh_from_db()
        self.assertTrue(da.epinglee)
        self.assertFalse(da.archivee)

    def test_archivee_ignoree_du_corps_de_requete(self):
        da = make_demande(self.company, self.user, jours=10)

        resp = self.api.patch(
            f'{BASE}/demandes-achat/{da.pk}/',
            {'archivee': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        da.refresh_from_db()
        self.assertFalse(da.archivee)


class NormalisationSeuilPurgeTests(SimpleTestCase):
    """Unité pure : un réglage société absent/aberrant retombe sur le défaut."""

    def test_valeur_absente_retombe_sur_le_defaut(self):
        self.assertEqual(
            _normaliser_seuil_purge(None), PURGE_BROUILLON_JOURS_DEFAUT)

    def test_valeur_non_entiere_retombe_sur_le_defaut(self):
        self.assertEqual(
            _normaliser_seuil_purge('trente'), PURGE_BROUILLON_JOURS_DEFAUT)

    def test_valeur_nulle_ou_negative_retombe_sur_le_defaut(self):
        self.assertEqual(
            _normaliser_seuil_purge(0), PURGE_BROUILLON_JOURS_DEFAUT)
        self.assertEqual(
            _normaliser_seuil_purge(-5), PURGE_BROUILLON_JOURS_DEFAUT)

    def test_valeur_positive_respectee(self):
        self.assertEqual(_normaliser_seuil_purge(30), 30)
        self.assertEqual(_normaliser_seuil_purge('45'), 45)


class SeuilPurgeParSocieteTests(TestCase):
    """Le seuil est lu par société sur ``stock.AchatsParametres`` (lecture
    cross-app par ``apps.get_model``, jamais un import du modèle)."""

    def test_defaut_sans_reglage_societe(self):
        company = make_company()
        self.assertEqual(
            _seuil_purge_brouillon_jours(company),
            PURGE_BROUILLON_JOURS_DEFAUT)


class IsolationSocieteTests(TestCase):

    def test_tache_scopee_par_societe(self):
        company_a = make_company()
        company_b = make_company()
        user_a = make_user(company_a)
        user_b = make_user(company_b)
        vieux_a = make_demande(company_a, user_a, jours=150)
        vieux_b = make_demande(company_b, user_b, jours=150)

        result = purger_demandes_achat_brouillon_task()

        vieux_a.refresh_from_db()
        vieux_b.refresh_from_db()
        # Chaque société est traitée pour SES propres demandes uniquement.
        self.assertEqual(result.get(company_a.id), 1)
        self.assertEqual(result.get(company_b.id), 1)
        self.assertTrue(vieux_a.archivee)
        self.assertTrue(vieux_b.archivee)

        api_a = auth(user_a)
        resp = api_a.get(f'{BASE}/demandes-achat/?archivees=1')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn(vieux_b.pk, [r['id'] for r in resp.data['results']])
