"""NTGRC26 — chronologie (« chatter ») d'un incident de sécurité.

Garanties : CHAQUE changement de statut et CHAQUE note manuelle apparaissent
dans la timeline ; l'acteur et la société sont TOUJOURS posés côté serveur ;
une transition faite par le service (donc par n'importe quel chemin de code)
est journalisée. Horloge FIGÉE dans les assertions d'horodatage.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import IncidentActivity, IncidentSecurite
from apps.grc.services import (
    changer_statut_incident, creer_incident, noter_incident,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 06:00:00+00:00'


class ChronologieServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC26 SA', slug='ntgrc26')

    def _incident(self):
        return creer_incident(
            self.company, titre='Incident', date_detection=timezone.now())

    def test_une_transition_est_journalisee(self):
        with frozen(INSTANT):
            incident = self._incident()
            changer_statut_incident(
                incident, IncidentSecurite.STATUT_EN_COURS, acteur='dpo')
        ligne = IncidentActivity.objects.get(incident=incident)
        self.assertEqual(ligne.type, IncidentActivity.TYPE_LOG)
        self.assertEqual(ligne.auteur, 'dpo')
        self.assertEqual(ligne.company, self.company)
        self.assertIn('Ouvert', ligne.detail)
        self.assertIn('En cours de traitement', ligne.detail)
        self.assertEqual(ligne.timestamp.isoformat(),
                         '2026-09-12T06:00:00+00:00')

    def test_chaque_transition_ajoute_sa_ligne(self):
        with frozen(INSTANT):
            incident = self._incident()
            changer_statut_incident(
                incident, IncidentSecurite.STATUT_EN_COURS)
            changer_statut_incident(incident, IncidentSecurite.STATUT_RESOLU)
            changer_statut_incident(incident, IncidentSecurite.STATUT_CLOS)
        self.assertEqual(IncidentActivity.objects.filter(
            incident=incident, type=IncidentActivity.TYPE_LOG).count(), 3)

    def test_une_transition_refusee_n_ecrit_rien(self):
        with frozen(INSTANT):
            incident = self._incident()
            try:
                changer_statut_incident(incident, 'archive')
            except Exception:  # noqa: BLE001 — la garde est testée ailleurs
                pass
        self.assertEqual(IncidentActivity.objects.count(), 0)

    def test_une_note_manuelle_apparait(self):
        with frozen(INSTANT):
            incident = self._incident()
            note = noter_incident(incident, 'Poste réimagé', acteur='si')
        self.assertEqual(note.type, IncidentActivity.TYPE_NOTE)
        self.assertEqual(note.detail, 'Poste réimagé')
        self.assertEqual(note.auteur, 'si')
        self.assertEqual(note.company, self.company)

    def test_une_note_vide_est_refusee(self):
        with frozen(INSTANT):
            incident = self._incident()
            with self.assertRaises(ValueError):
                noter_incident(incident, '   ')
        self.assertEqual(IncidentActivity.objects.count(), 0)


class EndpointChronologieTests(TenantAPITestCase):
    BASE = '/api/django/grc/incidents-securite/'

    def setUp(self):
        super().setUp()
        self.incident = creer_incident(
            self.company, titre='Incident', date_detection=timezone.now())

    def _admin(self):
        return self.client_as(role='admin')

    def test_noter_pose_l_acteur_cote_serveur(self):
        client = self._admin()
        r = client.post(
            f'{self.BASE}{self.incident.pk}/noter/',
            {'detail': 'Appel au prestataire', 'auteur': 'quelquun-dautre',
             'company': self.other_company.pk},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ligne = IncidentActivity.objects.get(pk=r.data['id'])
        self.assertEqual(ligne.company, self.company)
        self.assertNotEqual(ligne.auteur, 'quelquun-dautre')
        self.assertEqual(ligne.detail, 'Appel au prestataire')

    def test_noter_vide_nomme_le_champ(self):
        r = self._admin().post(
            f'{self.BASE}{self.incident.pk}/noter/', {'detail': '  '},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('detail', r.data)

    def test_historique_montre_transitions_et_notes(self):
        client = self._admin()
        client.post(f'{self.BASE}{self.incident.pk}/changer-statut/',
                    {'statut': 'en_cours'}, format='json')
        client.post(f'{self.BASE}{self.incident.pk}/noter/',
                    {'detail': 'Analyse en cours'}, format='json')
        r = client.get(f'{self.BASE}{self.incident.pk}/historique/')
        self.assertEqual(r.status_code, 200, r.content)
        types = [ligne['type'] for ligne in r.data['results']]
        self.assertIn('log', types)
        self.assertIn('note', types)
        self.assertEqual(len(r.data['results']), 2)

    def test_l_historique_d_une_autre_societe_est_introuvable(self):
        etranger = creer_incident(
            self.other_company, titre='Etranger',
            date_detection=timezone.now())
        r = self._admin().get(f'{self.BASE}{etranger.pk}/historique/')
        self.assertEqual(r.status_code, 404)
