"""ADEV14 (C-ADEV-006) — ``override_credit`` / ``override_avertissement`` ne
sont honorés que pour un Administrateur ou un Responsable (``menu_tier``).

Matrice rôle × drapeau sur ``POST /ventes/devis/<id>/accepter/`` d'un devis
ENVOYÉ dont le client porte un avertissement de vente BLOQUANT, avec les rôles
CANONIQUES réels (``CANONICAL_SYSTEM_ROLES``, aucun mock de permission) :
* « Commercial » (palier normal, porte ``ventes_valider``) : 403 avec ou sans
  le drapeau, message « Un responsable ou un administrateur peut passer
  outre », devis toujours ``envoye`` ;
* « Commercial responsable » et « Administrateur » : 200 avec le drapeau.

Test-du-test : retirer la condition de palier de ``peut_passer_outre`` ⇒
``test_commercial_refuse_avec_override`` échoue (200).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev14_override_palier -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
ROLES = dict(CANONICAL_SYSTEM_ROLES)


class OverridePalierTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ADEV14 Co', slug='adev14-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bloqué', email='adev14@example.com',
            avertissement_vente='Validation direction requise',
            avertissement_bloquant=True)
        self.n = 0
        patcher = patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _user(self, nom_role, palier_attendu):
        role, _ = Role.objects.get_or_create(
            company=self.company, nom=nom_role,
            defaults={'permissions': list(ROLES[nom_role]),
                      'est_systeme': True})
        user = User.objects.create_user(
            username=f'adev14-{nom_role}'.replace(' ', '-').lower(),
            password='x', company=self.company, role=role)
        # Préconditions : le rôle canonique porte ``ventes_valider`` et son
        # palier est celui attendu (sinon le test ne prouverait rien).
        self.assertIn('ventes_valider', role.permissions)
        self.assertEqual(user.menu_tier, palier_attendu)
        return user

    def _devis(self, auteur):
        # Auteur = l'utilisateur qui accepte : les rôles commerciaux ont une
        # portée de visibilité restreinte (``visible_user_ids`` → devis
        # qu'ils ont créés) ; sans ``created_by`` le devis leur répond 404
        # avant même la garde d'avertissement que ce test exerce.
        self.n += 1
        return Devis.objects.create(
            company=self.company, reference=f'DEV-ADEV14-{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=auteur)

    def _accepter(self, user, devis, **drapeaux):
        api = APIClient()
        api.force_authenticate(user=user)
        return api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                        {'nom': 'Client', 'option': 'sans_batterie',
                         **drapeaux}, format='json')

    def test_commercial_refuse_avec_override(self):
        commercial = self._user('Commercial', 'normal')
        for drapeaux in ({}, {'override_avertissement': True}):
            with self.subTest(drapeaux=drapeaux):
                devis = self._devis(commercial)
                reponse = self._accepter(commercial, devis, **drapeaux)
                self.assertEqual(reponse.status_code, 403, reponse.content)
                self.assertTrue(reponse.data.get('sale_warning'))
                self.assertIn(
                    'Un responsable ou un administrateur peut passer outre',
                    reponse.data['detail'])
                # CLAUSE PERSISTANCE.
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_responsable_passe_outre(self):
        responsable = self._user('Commercial responsable', 'responsable')
        devis = self._devis(responsable)
        self.assertEqual(self._accepter(responsable, devis).status_code, 403)
        reponse = self._accepter(responsable, devis,
                                 override_avertissement=True)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_admin_passe_outre(self):
        admin = self._user('Administrateur', 'admin')
        devis = self._devis(admin)
        reponse = self._accepter(admin, devis, override_avertissement=True)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_peut_passer_outre_sans_utilisateur(self):
        from apps.ventes.domain.cycle_vie import peut_passer_outre
        self.assertFalse(peut_passer_outre(None))
