"""NTGRC25 — registre des incidents de sécurité + escalade en violation.

Garanties : escalader un incident touchant des données personnelles crée une
``ViolationDonnees`` reliée par string-FK ; l'escalade est idempotente ; la
référence INC est race-safe (plus-haut-utilisé + 1, jamais count()+1) ; le
statut ne s'écrit pas au champ ; tout reste scopé société. Horloge FIGÉE.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import IncidentSecurite, ViolationDonnees
from apps.grc.services import (
    EscaladeImpossible, TransitionIncidentInterdite, changer_statut_incident,
    creer_incident, escalader_incident_en_violation,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 07:00:00+00:00'


class IncidentServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC25 SA', slug='ntgrc25')

    def _incident(self, **kw):
        params = {
            'titre': 'Poste infecté',
            'type': IncidentSecurite.TYPE_MALWARE,
            'severite': IncidentSecurite.SEVERITE_ELEVEE,
            'date_detection': timezone.now(),
        }
        params.update(kw)
        return creer_incident(self.company, **params)

    def test_la_reference_inc_est_posee(self):
        with frozen(INSTANT):
            incident = self._incident()
        self.assertTrue(incident.reference.startswith('INC-'))
        self.assertIn('202609', incident.reference)

    def test_la_reference_ne_recule_pas_si_une_ligne_manque(self):
        """Plus-haut-utilisé + 1, jamais count() + 1."""
        with frozen(INSTANT):
            premier = self._incident()
            second = self._incident()
            premier.delete()
            troisieme = self._incident()
        self.assertNotEqual(troisieme.reference, second.reference)
        self.assertGreater(troisieme.reference, second.reference)

    def test_escalader_cree_une_violation_reliee(self):
        with frozen(INSTANT):
            incident = self._incident()
            violation = escalader_incident_en_violation(
                incident,
                categories_donnees=['identite', 'contact'],
                nombre_personnes_estime=120)
        incident.refresh_from_db()
        self.assertEqual(incident.violation_donnees_ref, str(violation.pk))
        self.assertEqual(violation.company, self.company)
        self.assertEqual(violation.date_detection, incident.date_detection)
        self.assertEqual(violation.gravite, incident.severite)
        self.assertEqual(violation.nombre_personnes_estime, 120)

    def test_l_echeance_72h_de_la_violation_part_de_la_detection(self):
        with frozen(INSTANT):
            incident = self._incident()
            violation = escalader_incident_en_violation(incident)
        self.assertEqual(
            violation.date_echeance_72h.isoformat(),
            '2026-09-15T07:00:00+00:00')

    def test_escalader_deux_fois_est_refuse(self):
        with frozen(INSTANT):
            incident = self._incident()
            escalader_incident_en_violation(incident)
            with self.assertRaises(EscaladeImpossible):
                escalader_incident_en_violation(incident)
        self.assertEqual(ViolationDonnees.objects.count(), 1)

    def test_un_incident_clos_ne_se_rouvre_pas(self):
        with frozen(INSTANT):
            incident = self._incident()
            changer_statut_incident(incident, IncidentSecurite.STATUT_CLOS)
            with self.assertRaises(TransitionIncidentInterdite):
                changer_statut_incident(
                    incident, IncidentSecurite.STATUT_EN_COURS)

    def test_un_statut_inconnu_est_refuse(self):
        with frozen(INSTANT):
            incident = self._incident()
            with self.assertRaises(TransitionIncidentInterdite):
                changer_statut_incident(incident, 'archive')


class EndpointIncidentTests(TenantAPITestCase):
    BASE = '/api/django/grc/incidents-securite/'

    def _admin(self):
        return self.client_as(role='admin')

    def _creer(self, **kw):
        params = {
            'titre': 'Ordinateur volé',
            'type': 'perte_materiel',
            'date_detection': '2026-09-12T07:00:00Z',
        }
        params.update(kw)
        return self._admin().post(self.BASE, params, format='json')

    def test_creation_impose_la_societe_le_statut_et_la_reference(self):
        r = self._creer(statut='clos', reference='INC-BIDON')
        self.assertEqual(r.status_code, 201, r.content)
        incident = IncidentSecurite.objects.get(pk=r.data['id'])
        self.assertEqual(incident.company, self.company)
        self.assertEqual(incident.statut, IncidentSecurite.STATUT_OUVERT)
        self.assertTrue(incident.reference.startswith('INC-'))

    def test_un_titre_vide_nomme_le_champ(self):
        r = self._creer(titre='   ')
        self.assertEqual(r.status_code, 400)
        self.assertIn('titre', r.data)

    def test_action_escalader_violation(self):
        r = self._creer()
        incident_id = r.data['id']
        r2 = self._admin().post(
            f'{self.BASE}{incident_id}/escalader-violation/',
            {'categories_donnees': ['identite'],
             'nombre_personnes_estime': 5},
            format='json')
        self.assertEqual(r2.status_code, 201, r2.content)
        violation = ViolationDonnees.objects.get(
            pk=r2.data['violation']['id'])
        self.assertEqual(violation.company, self.company)
        self.assertEqual(
            r2.data['incident']['violation_donnees_ref'], str(violation.pk))

    def test_escalader_deux_fois_renvoie_409(self):
        r = self._creer()
        incident_id = r.data['id']
        self._admin().post(
            f'{self.BASE}{incident_id}/escalader-violation/', {},
            format='json')
        r2 = self._admin().post(
            f'{self.BASE}{incident_id}/escalader-violation/', {},
            format='json')
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(ViolationDonnees.objects.count(), 1)

    def test_changer_statut_nomme_le_champ_en_cas_de_refus(self):
        r = self._creer()
        incident_id = r.data['id']
        self._admin().post(
            f'{self.BASE}{incident_id}/changer-statut/', {'statut': 'clos'},
            format='json')
        r2 = self._admin().post(
            f'{self.BASE}{incident_id}/changer-statut/',
            {'statut': 'en_cours'}, format='json')
        self.assertEqual(r2.status_code, 400)
        self.assertIn('statut', r2.data)

    def test_liste_scopee_societe(self):
        IncidentSecurite.objects.create(
            company=self.other_company, titre='Etranger',
            date_detection=timezone.now())
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
