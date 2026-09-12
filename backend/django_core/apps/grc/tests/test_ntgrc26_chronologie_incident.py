"""NTGRC26 — chronologie (« chatter ») d'un incident de sécurité.

Garanties : CHAQUE changement de statut et CHAQUE note manuelle apparaissent
dans la timeline ; l'auteur et la société sont TOUJOURS posés côté serveur ;
une transition faite par le SERVICE (donc par n'importe quel chemin de code)
est journalisée.

Choix d'architecture VERROUILLÉ ICI : la chronologie vit sur la primitive
PLATEFORME ``records.Activity`` (ARC8), pas sur un quatorzième modèle
``*Activity`` maison — ce dépôt en compte déjà treize à converger, et la garde
``scripts/check_platform.py`` refuse d'en accepter un de plus.

Horloge FIGÉE dans les assertions d'horodatage.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import IncidentSecurite
from apps.grc.services import (
    changer_statut_incident, chronologie_incident, creer_incident,
    noter_incident,
)
from apps.records.models import Activity
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

    def test_la_chronologie_vit_sur_la_primitive_plateforme(self):
        """Aucun modèle de chatter maison n'existe dans `grc`."""
        from apps.grc import models as grc_models

        self.assertFalse(hasattr(grc_models, 'IncidentActivity'))

    def test_une_transition_est_journalisee(self):
        with frozen(INSTANT):
            incident = self._incident()
            changer_statut_incident(
                incident, IncidentSecurite.STATUT_EN_COURS)
        ligne = chronologie_incident(incident).get()
        self.assertEqual(ligne.kind, Activity.Kind.MODIFICATION)
        self.assertEqual(ligne.company, self.company)
        self.assertEqual(ligne.field, 'statut')
        self.assertEqual(ligne.old_value, 'Ouvert')
        self.assertEqual(ligne.new_value, 'En cours de traitement')
        self.assertEqual(ligne.created_at.isoformat(),
                         '2026-09-12T06:00:00+00:00')

    def test_chaque_transition_ajoute_sa_ligne(self):
        with frozen(INSTANT):
            incident = self._incident()
            changer_statut_incident(
                incident, IncidentSecurite.STATUT_EN_COURS)
            changer_statut_incident(incident, IncidentSecurite.STATUT_RESOLU)
            changer_statut_incident(incident, IncidentSecurite.STATUT_CLOS)
        self.assertEqual(
            chronologie_incident(incident).filter(
                kind=Activity.Kind.MODIFICATION).count(), 3)

    def test_une_transition_refusee_n_ecrit_rien(self):
        with frozen(INSTANT):
            incident = self._incident()
            try:
                changer_statut_incident(incident, 'archive')
            except Exception:  # noqa: BLE001 — la garde est testée ailleurs
                pass
        self.assertEqual(chronologie_incident(incident).count(), 0)

    def test_une_note_manuelle_apparait(self):
        with frozen(INSTANT):
            incident = self._incident()
            note = noter_incident(incident, 'Poste réimagé')
        self.assertEqual(note.kind, Activity.Kind.NOTE)
        self.assertEqual(note.body, 'Poste réimagé')
        self.assertEqual(note.company, self.company)
        self.assertEqual(chronologie_incident(incident).count(), 1)

    def test_une_note_vide_est_refusee(self):
        with frozen(INSTANT):
            incident = self._incident()
            with self.assertRaises(ValueError):
                noter_incident(incident, '   ')
        self.assertEqual(chronologie_incident(incident).count(), 0)

    def test_la_chronologie_est_bornee_a_son_incident(self):
        with frozen(INSTANT):
            premier = self._incident()
            second = self._incident()
            noter_incident(premier, 'Note du premier')
        self.assertEqual(chronologie_incident(premier).count(), 1)
        self.assertEqual(chronologie_incident(second).count(), 0)


class EndpointChronologieTests(TenantAPITestCase):
    BASE = '/api/django/grc/incidents-securite/'

    def setUp(self):
        super().setUp()
        self.incident = creer_incident(
            self.company, titre='Incident', date_detection=timezone.now())

    def _admin(self):
        return self.client_as(role='admin')

    def test_noter_pose_l_auteur_et_la_societe_cote_serveur(self):
        admin = self.client_as(role='admin')
        r = admin.post(
            f'{self.BASE}{self.incident.pk}/noter/',
            {'detail': 'Appel au prestataire', 'auteur': 'quelquun-dautre',
             'company': self.other_company.pk},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ligne = Activity.objects.get(pk=r.data['id'])
        self.assertEqual(ligne.company, self.company)
        self.assertIsNotNone(ligne.created_by)
        self.assertNotEqual(r.data['user_username'], 'quelquun-dautre')
        self.assertEqual(ligne.body, 'Appel au prestataire')

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
        kinds = [ligne['kind'] for ligne in r.data['results']]
        self.assertIn(Activity.Kind.MODIFICATION, kinds)
        self.assertIn(Activity.Kind.NOTE, kinds)
        self.assertEqual(len(r.data['results']), 2)

    def test_l_url_generique_du_chatter_sert_la_meme_source(self):
        client = self._admin()
        client.post(f'{self.BASE}{self.incident.pk}/noter/',
                    {'detail': 'Une seule source'}, format='json')
        r = client.get(f'{self.BASE}{self.incident.pk}/chatter/historique/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['body'], 'Une seule source')

    def test_l_historique_d_une_autre_societe_est_introuvable(self):
        etranger = creer_incident(
            self.other_company, titre='Etranger',
            date_detection=timezone.now())
        r = self._admin().get(f'{self.BASE}{etranger.pk}/historique/')
        self.assertEqual(r.status_code, 404)
