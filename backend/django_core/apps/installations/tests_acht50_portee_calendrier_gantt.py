"""ACHT50 (C-ACHT-049) — `interventions/calendrier/` et `chantiers/gantt/`
partent du queryset du viewset (portée de visibilité Feature F) : un
Technicien de portée équipe n'y voit que ce que sa liste lui montre.

Rejoue CTEN-1 : calendrier 200 i1 i2 · gantt avec le chantier hors portée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht50_portee_calendrier_gantt"
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, Intervention
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS,
)

User = get_user_model()
BASE = '/api/django/installations'


class PorteeCalendrierGanttTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT50', slug='acht50-co')
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.t1 = User.objects.create_user(
            username='t1-acht50', password='x', company=self.company,
            role=role_tech)
        self.t2 = User.objects.create_user(
            username='t2-acht50', password='x', company=self.company,
            role=role_tech)
        self.admin = User.objects.create_user(
            username='admin-acht50', password='x', company=self.company,
            role=role_admin)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT50',
            technicien_responsable=self.admin, created_by=self.admin)
        jour = datetime.date.today() + datetime.timedelta(days=2)
        self.i1 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t1, date_prevue=jour)
        self.i2 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t2, date_prevue=jour)
        self.fenetre = {
            'date_from': str(jour - datetime.timedelta(days=1)),
            'date_to': str(jour + datetime.timedelta(days=1))}

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _ids_calendrier(self, user):
        r = self._api(user).get(f'{BASE}/interventions/calendrier/',
                                self.fenetre)
        self.assertEqual(r.status_code, 200, r.data)
        ids = set()
        for groupe in r.data:
            for iv in groupe['interventions']:
                ids.add(iv['id'])
        return ids

    def test_technicien_voit_sa_portee(self):
        self.assertEqual(self._ids_calendrier(self.t1), {self.i1.id})
        r = self._api(self.t1).get(f'{BASE}/chantiers/gantt/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn(self.chantier.id, [row['id'] for row in r.data])

    def test_admin_voit_tout(self):
        self.assertEqual(self._ids_calendrier(self.admin),
                         {self.i1.id, self.i2.id})
        r = self._api(self.admin).get(f'{BASE}/chantiers/gantt/')
        self.assertIn(self.chantier.id, [row['id'] for row in r.data])


CONTRAT_LISTE = (Path(__file__).resolve().parent / 'contract_samples'
                 / 'assistant_chantiers.json')


class ListeAssistantTests(TestCase):
    """Copilote vague 2 (CHTA3) — ``GET chantiers/assistant/`` part du
    queryset du viewset (même portée que la liste), sert les clés EXACTES de
    ``assistant_chantiers.json`` et ses blocages SANS le besoin matériel.
    Même jeu de données que :class:`PorteeCalendrierGanttTests`."""

    setUp = PorteeCalendrierGanttTests.setUp
    _api = PorteeCalendrierGanttTests._api

    def _liste(self, user, **params):
        r = self._api(user).get(f'{BASE}/chantiers/assistant/', params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_portee_de_la_liste(self):
        self.assertIn(self.chantier.id,
                      [li['id'] for li in self._liste(self.admin)['lignes']])
        self.assertNotIn(self.chantier.id,
                         [li['id'] for li in self._liste(self.t1)['lignes']])

    def test_bloques_cles_du_contrat_sans_materiel(self):
        echantillon = json.loads(CONTRAT_LISTE.read_text(encoding='utf-8'))
        data = self._liste(self.admin, vue='bloques')
        self.assertEqual(set(data), set(echantillon['exemple']))
        self.assertEqual((data['vue'], data['total'], data['limite']), ('bloques', 1, 10))
        ligne = data['lignes'][0]
        self.assertEqual(set(ligne), set(echantillon['exemple']['lignes'][0]))
        self.assertEqual(ligne['blocages'], ['sans_date'])
        self.assertEqual(ligne['a_faire'], 'planifier_pose')
        self.assertEqual(ligne['pose_intervention']['id'], self.i1.id)
        self.assertEqual(ligne['lien'], f'/chantiers?id={self.chantier.id}')
        self.assertEqual(data['note'], echantillon['exemple']['note'])
        self.assertNotIn('prix', json.dumps(data))

    def test_date_et_pose_plus_bloque_puis_semaine(self):
        Installation.objects.filter(pk=self.chantier.pk).update(
            date_pose_prevue=self.i1.date_prevue)
        self.assertEqual(self._liste(self.admin, vue='bloques')['total'], 0)
        data = self._liste(self.admin, vue='poses_semaine',
                           debut=self.i1.date_prevue.isoformat())
        self.assertEqual([li['id'] for li in data['lignes']], [self.chantier.id])
        self.assertEqual(data['lignes'][0]['a_faire'], 'poser')
        autre_semaine = self.i1.date_prevue + datetime.timedelta(days=14)
        self.assertEqual(self._liste(self.admin, vue='poses_semaine',
                                     debut=autre_semaine.isoformat())['total'], 0)

    def test_annule_exclu_q_et_lead(self):
        Installation.objects.create(company=self.company, reference='CH-ACHT50-ANNULE',
                                    annule=True, created_by=self.admin)
        refs = [li['reference'] for li in self._liste(self.admin)['lignes']]
        self.assertEqual(refs, ['CH-ACHT50'])
        self.assertEqual(self._liste(self.admin, q='inexistant')['total'], 0)
        self.assertEqual(self._liste(self.admin, q='acht50')['total'], 1)

    def test_parametre_hors_liste_400_nomme(self):
        r = self._api(self.admin).get(f'{BASE}/chantiers/assistant/', {'vue': 'tout'})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual((r.data['field'], r.data['code']), ('vue', 'vue_inconnue'))
        r = self._api(self.admin).get(f'{BASE}/chantiers/assistant/', {'limite': '26'})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['field'], 'limite')


class BriefChantiersTests(TestCase):
    """Copilote vague 2 (CHTA7) — ``selectors_assistant.brief_chantiers`` :
    forme du bloc ``chantiers`` du matin (contrat du digest crm), lignes =
    lignes de la liste, portée de l'utilisateur, ``None`` sans lecture du
    module. Même jeu de données que :class:`PorteeCalendrierGanttTests`."""

    setUp = PorteeCalendrierGanttTests.setUp

    def test_forme_du_contrat_et_portee(self):
        from apps.installations.selectors_assistant import brief_chantiers
        digest = json.loads((Path(__file__).resolve().parents[1] / 'crm' / 'contract_samples'
                             / 'assistant_digest_matin.json').read_text(encoding='utf-8'))
        attendu = digest['vague2']['exemple_copilote']['chantiers']
        ligne_liste = json.loads(CONTRAT_LISTE.read_text(encoding='utf-8'))['exemple']['lignes'][0]
        jour = self.i1.date_prevue
        bloc = brief_chantiers(self.admin, jour)
        self.assertEqual(set(bloc), set(attendu))
        self.assertEqual(set(bloc['bloques']), set(attendu['bloques']))
        self.assertEqual(bloc['bloques']['total'], 1)
        self.assertEqual(set(bloc['bloques']['lignes'][0]), set(ligne_liste))
        self.assertEqual(bloc['bloques']['lignes'][0]['blocages'], ['sans_date'])
        self.assertEqual(bloc['poses_semaine']['total'], 1)
        self.assertEqual(bloc['lien'], '/chantiers')
        self.assertEqual(brief_chantiers(self.t1, jour)['bloques']['total'], 0)

    def test_sans_lecture_du_module_none(self):
        from apps.installations.selectors_assistant import brief_chantiers
        crm = User.objects.create_user(
            username='crm-brief-chta7', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='CRM brief',
                                     permissions=['crm_voir']))
        self.assertIsNone(brief_chantiers(crm, datetime.date.today()))

    def test_cinq_lignes_au_plus_compteur_sur_tout(self):
        from apps.installations.selectors_assistant import LIGNES_BRIEF, brief_chantiers
        for n in range(LIGNES_BRIEF + 2):
            Installation.objects.create(company=self.company, reference=f'CH-BRIEF-{n}',
                                        created_by=self.admin)
        bloc = brief_chantiers(self.admin, datetime.date.today())
        self.assertEqual(bloc['bloques']['total'], LIGNES_BRIEF + 3)
        self.assertEqual(len(bloc['bloques']['lignes']), LIGNES_BRIEF)
