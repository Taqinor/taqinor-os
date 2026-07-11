"""VX199 — les actions sensibles (validation de devis, émission de facture,
fusion/conversion de lead) sont gardées par une permission ERP FINE, pas par le
grossier ``IsResponsableOrAdmin``.

Bug systémique corrigé : ``IsResponsableOrAdmin`` passe dès que
``user.is_responsable`` est vrai, or (depuis ERR4) ``is_responsable`` = « le rôle
accorde AU MOINS UNE permission d'écriture ». Un rôle « Commercial » qui ne peut
qu'écrire des leads (``crm_creer``) et créer des devis (``ventes_creer``) passait
donc l'acceptation de devis, l'émission de facture et la fusion de leads — alors
que le frontend cache pourtant le bouton. Le correctif remplace la garde grossière
par ``HasPermissionOrLegacy('<domaine>_<action>')`` sur ces actions sensibles :
  - devis ``accepter`` / ``refuser`` → ``ventes_valider``
  - facture ``emettre``            → ``ventes_valider``
  - lead ``merge`` / ``convertir-client`` → ``crm_modifier``

DoD : un compte « lecture + une écriture » (sans la permission fine) reçoit 403 en
appelant DIRECTEMENT l'API ; un compte porteur de la permission fine n'est PAS
bloqué au niveau permission (jamais 403) ; les comptes hérités sans rôle fin
(``role_legacy='responsable'``) gardent exactement leur comportement.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client as CrmClient, Lead
from apps.ventes.models import Devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VX199GuardBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VX199 Co', slug='vx199-co')
        # Rôle « lecture + une écriture » : porte des permissions d'écriture
        # (crm_creer, ventes_creer) donc is_responsable == True, MAIS ni
        # ventes_valider ni crm_modifier. C'est exactement le compte que la
        # garde grossière laissait passer par erreur.
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial VX199',
            permissions=['crm_voir', 'crm_creer', 'ventes_voir',
                         'ventes_creer'],
            est_systeme=False)
        self.commercial = User.objects.create_user(
            username='vx199_com', password='x', role=self.commercial_role,
            company=self.company)
        # Rôle qui DÉTIENT la permission fine de validation ventes.
        self.valideur_role = Role.objects.create(
            company=self.company, nom='Valideur VX199',
            permissions=['ventes_voir', 'ventes_valider', 'crm_voir',
                         'crm_modifier'],
            est_systeme=False)
        self.valideur = User.objects.create_user(
            username='vx199_val', password='x', role=self.valideur_role,
            company=self.company)
        # Compte HÉRITÉ sans rôle fin : comportement legacy préservé.
        self.legacy_resp = User.objects.create_user(
            username='vx199_legacy', password='x',
            role_legacy='responsable', company=self.company)

        self.client_obj = CrmClient.objects.create(
            company=self.company, nom='Client', prenom='VX',
            email='vx199@example.com', telephone='+212600000199')


class TestDevisValidationGuard(VX199GuardBase):
    def _devis(self, num=1, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def test_read_write_role_gets_403_on_accepter(self):
        devis = self._devis(num=1)
        r = _auth(self.commercial).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'X', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_read_write_role_gets_403_on_refuser(self):
        devis = self._devis(num=2)
        r = _auth(self.commercial).post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'x'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_valideur_role_not_blocked_on_accepter(self):
        devis = self._devis(num=3)
        r = _auth(self.valideur).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Bennani', 'date': '2026-06-10'}, format='json')
        # La permission fine passe : jamais 403 (200 ici — acceptation OK).
        self.assertNotEqual(r.status_code, 403, r.data)

    def test_legacy_responsable_still_accepts(self):
        devis = self._devis(num=4)
        r = _auth(self.legacy_resp).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Legacy', 'date': '2026-06-10'}, format='json')
        self.assertNotEqual(r.status_code, 403, r.data)


# NB : l'émission de facture (`emettre`) N'EST PAS re-gardée par VX199 — sa
# permission reste gouvernée par le workflow de revue XFAC18 (flag société +
# rôle) déjà en place ; VX199 ne touche QUE devis accepter/refuser + lead
# merge/convertir, pour ne pas entrer en conflit avec XFAC18.


class TestLeadSensitiveActionsGuard(VX199GuardBase):
    def test_read_write_role_gets_403_on_merge(self):
        survivor = Lead.objects.create(company=self.company, nom='Alaoui')
        dup = Lead.objects.create(company=self.company, nom='Alaoui2')
        r = _auth(self.commercial).post(
            f'/api/django/crm/leads/{survivor.id}/merge/',
            {'others': [dup.id]}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_read_write_role_gets_403_on_convertir_client(self):
        lead = Lead.objects.create(company=self.company, nom='Bennani')
        r = _auth(self.commercial).post(
            f'/api/django/crm/leads/{lead.id}/convertir-client/',
            {'mode': 'nouveau'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_crm_modifier_role_not_blocked_on_merge(self):
        survivor = Lead.objects.create(company=self.company, nom='Cherkaoui')
        dup = Lead.objects.create(company=self.company, nom='Cherkaoui2')
        r = _auth(self.valideur).post(
            f'/api/django/crm/leads/{survivor.id}/merge/',
            {'others': [dup.id]}, format='json')
        self.assertNotEqual(r.status_code, 403, r.data)
