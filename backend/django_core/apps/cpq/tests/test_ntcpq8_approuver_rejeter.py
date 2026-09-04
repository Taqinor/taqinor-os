"""NTCPQ8 — approuver-etape / rejeter-etape + chatter + déblocage envoi."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import RegleApprobationRemise, EtapeApprobationDevis
from apps.cpq import services
from apps.ventes.models import DevisActivity
from apps.ventes.services import mark_devis_sent
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class TestApprouverRejeter(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        RegleApprobationRemise.objects.create(
            company=self.company, remise_min_pct=Decimal('20'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=2)
        self.devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        services.lancer_approbation_devis(self.devis)

    def test_approuver_toutes_les_etapes_debloque_envoi(self):
        etape1, toutes1 = services.approuver_etape_devis(
            self.devis, user=self.user)
        self.assertFalse(toutes1)  # il reste l'étape 2
        etape2, toutes2 = services.approuver_etape_devis(
            self.devis, user=self.user)
        self.assertTrue(toutes2)
        mark_devis_sent(devis=self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')

    def test_rejeter_remet_en_brouillon_et_logue(self):
        # simulate the devis moved to envoye is prevented; force a non-brouillon
        # state to prove reject resets it.
        self.devis.statut = 'envoye'
        self.devis.save()
        etape = services.rejeter_etape_devis(
            self.devis, user=self.user, motif='Remise trop élevée')
        self.assertEqual(etape.statut, EtapeApprobationDevis.Statut.REJETE)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')
        # chatter : une entrée avec l'auteur et le motif.
        act = DevisActivity.objects.filter(
            devis=self.devis).order_by('-created_at').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.user_id, self.user.id)
        self.assertIn('Remise trop élevée', act.body)

    def test_endpoint_approuver_etape(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        # user needs responsable/admin role for the action
        staff = UserFactory(
            company=self.company, role_legacy='responsable')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(staff)}')
        resp = client.post(
            f'/api/django/ventes/devis/{self.devis.id}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['toutes_approuvees'])


class TestAud403SecondRegardNonAutoFranchissable(TestCase):
    """AUD403 — le second regard NTCPQ7/8 n'est plus auto-franchissable.

    Les deux ``@action`` déclaraient bien
    ``HasPermissionOrLegacy('cpq_approbation_approuver')``, mais
    ``DevisViewSet.get_permissions()`` ne consultait jamais ce
    ``permission_classes`` : les deux noms étaient groupés dans WRITE_ACTIONS,
    dont la branche renvoie inconditionnellement ``IsResponsableOrAdmin()``.
    Un rôle « Commercial » ordinaire — permissions d'écriture, mais PAS
    ``cpq_approbation_approuver`` — satisfaisait déjà ``is_responsable`` et
    approuvait/rejetait donc sa propre remise (200 avant le correctif).
    """

    def setUp(self):
        from apps.roles.models import Role
        self.company = CompanyFactory()
        RegleApprobationRemise.objects.create(
            company=self.company, remise_min_pct=Decimal('20'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=2)
        self.devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        services.lancer_approbation_devis(self.devis)

        # Rôle métier ORDINAIRE : de vraies permissions d'écriture (donc
        # ``is_responsable`` vrai), mais aucun droit d'approbation.
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['ventes_voir', 'ventes_creer', 'crm_voir'],
            est_systeme=False)
        # Le même rôle, PLUS le droit d'approuver.
        self.role_approbateur = Role.objects.create(
            company=self.company, nom='Commercial approbateur',
            permissions=['ventes_voir', 'ventes_creer', 'crm_voir',
                         'cpq_approbation_approuver'],
            est_systeme=False)

    def _client_for(self, role, username):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        user = UserFactory(
            username=username, company=self.company, role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def _url(self, suffixe):
        return f'/api/django/ventes/devis/{self.devis.id}/{suffixe}/'

    def test_commercial_sans_permission_ne_peut_pas_approuver(self):
        client = self._client_for(self.role_commercial, 'com-sans-appro')
        resp = client.post(self._url('approuver-etape'), {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        # Aucune étape n'a bougé.
        self.assertFalse(
            EtapeApprobationDevis.objects.filter(
                devis=self.devis,
                statut=EtapeApprobationDevis.Statut.APPROUVE).exists())

    def test_commercial_sans_permission_ne_peut_pas_rejeter(self):
        client = self._client_for(self.role_commercial, 'com-sans-rejet')
        resp = client.post(self._url('rejeter-etape'),
                           {'motif': 'trop cher'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.devis.refresh_from_db()
        self.assertFalse(
            EtapeApprobationDevis.objects.filter(
                devis=self.devis,
                statut=EtapeApprobationDevis.Statut.REJETE).exists())

    def test_role_porteur_de_la_permission_approuve_toujours(self):
        client = self._client_for(self.role_approbateur, 'com-appro')
        resp = client.post(self._url('approuver-etape'), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['toutes_approuvees'])

    def test_role_porteur_de_la_permission_rejette_toujours(self):
        client = self._client_for(self.role_approbateur, 'com-rejet')
        resp = client.post(self._url('rejeter-etape'),
                           {'motif': 'remise trop élevée'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_la_lecture_des_etapes_reste_ouverte_au_meme_perimetre(self):
        """``approbation`` (GET) déclare ``IsResponsableOrAdmin``, comme sa
        branche : honorer la déclaration ne la restreint ni ne l'ouvre."""
        client = self._client_for(self.role_commercial, 'com-lecture')
        resp = client.get(self._url('approbation'))
        self.assertEqual(resp.status_code, 200, resp.content)
