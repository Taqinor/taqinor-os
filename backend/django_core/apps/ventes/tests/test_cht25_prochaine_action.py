"""CHT25 — historique daté du dossier 82-21 + prochaine action explicite.

Couvre :
  * ``('ventes', 'RegulatoryDossier')`` est désormais suivi par le Journal
    d'activité générique (``apps.audit.signals.TRACKED_MODELS``) — une
    transition de statut (dépôt, complément demandé, approbation…) laisse
    enfin une ligne ``AuditLog`` datée, comme le reste des pièces
    réglementaires déjà tracées ;
  * le calendrier réglementaire (``calendrier_view.calendrier_reglementaire``)
    intègre la ``prochaine_action_date`` explicite du dossier dans ses
    alertes, en PLUS des règles déduites (dépôt en instruction, validité
    d'accord) — jamais un remplacement ;
  * le tri global reste par urgence (date d'échéance croissante) une fois la
    nouvelle échéance ajoutée au lot.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_cht25_prochaine_action -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.audit.signals import TRACKED_MODELS
from apps.crm.models import Client
from apps.ventes.models import Devis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_dossier(company, user, ref, **kw):
    client = Client.objects.create(
        company=company, nom='Naciri', prenom='Imane',
        email=f'i_{ref}@example.com', telephone='+212655555555')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)
    return RegulatoryDossier.objects.create(
        company=company, devis=devis, regime_8221='accord_raccordement',
        **kw)


class RegulatoryDossierEstTraceParLeJournalTests(TestCase):
    def setUp(self):
        self.company = make_company('cht25-acme')
        self.user = make_user(self.company, 'cht25_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.dossier = make_dossier(
            self.company, self.user, 'DEV-CHT25-1', statut='en_constitution')
        self.url = (f'/api/django/ventes/dossiers-reglementaires/'
                    f'{self.dossier.id}/')

    def test_le_modele_est_declare_suivi(self):
        self.assertIn(('ventes', 'RegulatoryDossier'), TRACKED_MODELS)

    def test_transition_de_statut_ecrit_une_ligne_auditlog(self):
        resp = self.api.patch(
            self.url, {'statut': 'depose'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.STATUS,
            content_type__model='regulatorydossier',
            object_id=str(self.dossier.id)).latest('id')
        self.assertIn('En constitution', ligne.detail)
        self.assertIn('Déposé', ligne.detail)


class CalendrierProchaineActionTests(TestCase):
    def setUp(self):
        self.company = make_company('cht25-cal')
        self.user = make_user(self.company, 'cht25_cal_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/calendrier-reglementaire/'
        self.today = timezone.now().date()

    def test_prochaine_action_explicite_apparait_dans_le_calendrier(self):
        d = make_dossier(
            self.company, self.user, 'DEV-CHT25-CAL1',
            statut='complement_demande',
            prochaine_action='Relancer le distributeur',
            prochaine_action_date=self.today + timedelta(days=5))
        resp = self.api.get(self.url, {'seuil': 30})
        self.assertEqual(resp.status_code, 200, resp.content)
        entrees = [e for e in resp.data['echeances']
                   if e['type'] == 'prochaine_action']
        self.assertEqual(len(entrees), 1)
        entree = entrees[0]
        self.assertEqual(entree['dossier_id'], d.id)
        self.assertEqual(entree['libelle'], 'Relancer le distributeur')
        self.assertEqual(entree['statut_alerte'], 'imminent')

    def test_prochaine_action_absente_ne_cree_aucune_ligne(self):
        make_dossier(
            self.company, self.user, 'DEV-CHT25-CAL2', statut='depose')
        resp = self.api.get(self.url)
        types = {e['type'] for e in resp.data['echeances']}
        self.assertNotIn('prochaine_action', types)

    def test_tri_par_urgence_avec_prochaine_action_melangee(self):
        # Une échéance déduite (dépôt en instruction) ET une prochaine action
        # explicite, sur deux dossiers différents : le tri global reste par
        # date d'échéance croissante (la plus urgente en premier).
        make_dossier(
            self.company, self.user, 'DEV-CHT25-CAL3', statut='depose',
            date_depot=self.today + timedelta(days=20))
        make_dossier(
            self.company, self.user, 'DEV-CHT25-CAL4',
            statut='en_instruction',
            prochaine_action='Envoyer le complément',
            prochaine_action_date=self.today + timedelta(days=2))
        resp = self.api.get(self.url, {'seuil': 30})
        dates = [e['date_echeance'] for e in resp.data['echeances']]
        self.assertEqual(dates, sorted(dates))
        # La prochaine action (dans 2 jours) précède le dépôt (dans 20 jours).
        self.assertEqual(
            resp.data['echeances'][0]['type'], 'prochaine_action')
