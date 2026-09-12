"""NTEXT35 — recherche globale sur les objets personnalisés.

Un ``CustomRecord`` apparaît dans ``GET reporting/search/?q=...``, GROUPÉ par
son objet (un groupe PAR objet personnalisé actif — dynamique, jamais un
modèle natif câblé en dur), filtré par la permission
``custom_object.<code>.voir`` — un rôle sans cette permission ne voit RIEN
de cet objet dans la recherche.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.customfields.models import CustomObjectDef, CustomRecord
from apps.roles.models import Role

User = get_user_model()

URL = '/api/django/reporting/search/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RechercheObjetCustomTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT35 Co')
        self.autre_company = Company.objects.create(nom='NTEXT35 Autre Co')
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='visiteurs', libelle='Visiteurs')
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'nom': 'Bennani Karim', 'badge': 'VIP'})
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'nom': 'Autre personne', 'badge': 'Standard'})
        # Isolation société : un enregistrement du même objet dans une AUTRE
        # société ne doit jamais remonter.
        objet_autre = CustomObjectDef.objects.create(
            company=self.autre_company, code='visiteurs', libelle='Visiteurs')
        CustomRecord.objects.create(
            company=self.autre_company, objet=objet_autre,
            data={'nom': 'Bennani Karim (autre société)'})

    def test_enregistrement_custom_trouve_et_groupe_par_objet(self):
        user = User.objects.create_user(
            username='ntext35_u', password='x', role_legacy='admin',
            company=self.company)
        res = _auth(user).get(f'{URL}?q=Bennani')
        self.assertEqual(res.status_code, 200, res.data)
        groupe = next(
            (g for g in res.data['groups'] if g['type'] == 'custom:visiteurs'),
            None)
        self.assertIsNotNone(groupe)
        self.assertEqual(groupe['label'], 'Visiteurs')
        self.assertEqual(len(groupe['results']), 1)
        self.assertIn('Bennani Karim', groupe['results'][0]['label'])

    def test_recherche_isolee_par_societe(self):
        user = User.objects.create_user(
            username='ntext35_u2', password='x', role_legacy='admin',
            company=self.company)
        res = _auth(user).get(f'{URL}?q=Bennani')
        groupe = next(
            g for g in res.data['groups'] if g['type'] == 'custom:visiteurs')
        labels = [r['label'] for r in groupe['results']]
        self.assertNotIn('Bennani Karim (autre société)', labels)

    def test_role_sans_permission_ne_voit_rien_de_lobjet(self):
        role_sans_acces = Role.objects.create(
            company=self.company, nom='SansAccesVisiteurs', permissions=[])
        user = User.objects.create_user(
            username='ntext35_sans', password='x', company=self.company,
            role=role_sans_acces)
        res = _auth(user).get(f'{URL}?q=Bennani')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNone(next(
            (g for g in res.data['groups'] if g['type'] == 'custom:visiteurs'),
            None))

    def test_role_avec_permission_voit_lobjet(self):
        role_avec_acces = Role.objects.create(
            company=self.company, nom='AvecAccesVisiteurs',
            permissions=['custom_object.visiteurs.voir'])
        user = User.objects.create_user(
            username='ntext35_avec', password='x', company=self.company,
            role=role_avec_acces)
        res = _auth(user).get(f'{URL}?q=Bennani')
        groupe = next(
            (g for g in res.data['groups'] if g['type'] == 'custom:visiteurs'),
            None)
        self.assertIsNotNone(groupe)

    def test_objet_inactif_absent_de_la_recherche(self):
        self.objet.actif = False
        self.objet.save(update_fields=['actif'])
        user = User.objects.create_user(
            username='ntext35_inactif', password='x', role_legacy='admin',
            company=self.company)
        res = _auth(user).get(f'{URL}?q=Bennani')
        self.assertIsNone(next(
            (g for g in res.data['groups'] if g['type'] == 'custom:visiteurs'),
            None))
