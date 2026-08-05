"""N101(b) — inscription self-service PARQUÉE + file d'approbation fondateur.

Invariant testé des deux côtés : l'endpoint public ne crée JAMAIS ni compte ni
société ; seule l'approbation du fondateur déclenche la création du tenant.
"""
from django.test import TestCase, override_settings
from django.core.cache import cache
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from ..models import DemandeInscription

URL_PUBLIQUE = '/api/django/auth/signup-demande/'

VALIDE = {
    'societe': 'Installateur Pilote',
    'nom': 'Amine Benali',
    'email': 'amine@installateur-pilote.ma',
    'telephone': '+212600000000',
}


class SignupDemandeParkedTests(TestCase):
    """Les DEUX états du drapeau sont testés (patron du formulaire contact)."""

    def setUp(self):
        self.api = APIClient()
        # L'endpoint est throttlé (5/h) et le compteur vit dans le cache
        # partagé : on le vide pour que les exécutions répétées restent fiables.
        cache.clear()

    @override_settings(TENANT_SIGNUP_ENABLED=False)
    def test_eteint_renvoie_404_et_n_enregistre_rien(self):
        resp = self.api.post(URL_PUBLIQUE, VALIDE, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(DemandeInscription.objects.count(), 0)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_allume_enregistre_la_demande(self):
        resp = self.api.post(URL_PUBLIQUE, VALIDE, format='json')
        self.assertEqual(resp.status_code, 201)
        demande = DemandeInscription.objects.get()
        self.assertEqual(demande.societe, 'Installateur Pilote')
        self.assertEqual(demande.statut, DemandeInscription.Statut.EN_ATTENTE)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_allume_ne_cree_jamais_de_compte_ni_de_societe(self):
        """Le cœur de la garde : une demande n'est pas une inscription."""
        self.api.post(URL_PUBLIQUE, VALIDE, format='json')
        self.assertEqual(Company.objects.count(), 0)
        self.assertEqual(CustomUser.objects.count(), 0)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_champs_obligatoires(self):
        resp = self.api.post(
            URL_PUBLIQUE, {'societe': 'X', 'nom': ''}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(DemandeInscription.objects.count(), 0)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_email_invalide_refuse(self):
        resp = self.api.post(
            URL_PUBLIQUE, {**VALIDE, 'email': 'pas-un-email'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(DemandeInscription.objects.count(), 0)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_pot_de_miel_absorbe_le_bot(self):
        """Champ piège rempli → 201 trompeur, mais rien n'est enregistré."""
        resp = self.api.post(
            URL_PUBLIQUE, {**VALIDE, 'site_web': 'http://spam.example'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(DemandeInscription.objects.count(), 0)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_double_clic_ne_duplique_pas(self):
        self.api.post(URL_PUBLIQUE, VALIDE, format='json')
        self.api.post(URL_PUBLIQUE, VALIDE, format='json')
        self.assertEqual(DemandeInscription.objects.count(), 1)


class FileApprobationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fondateur = CustomUser.objects.create_superuser(
            username='fondateur_signup', password='pw83706',
            email='fondateur.signup@exemple.ma')
        self.tenant = Company.objects.create(
            nom='Signup Existant', slug='signup-existant')
        self.admin_tenant = CustomUser.objects.create_user(
            username='admin_signup_existant', password='pw83706',
            company=self.tenant, role_legacy='admin')
        self.demande = DemandeInscription.objects.create(
            societe='Solaire Atlas', nom='Karim Idrissi',
            email='karim@solaire-atlas.ma')

    def _api(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def test_file_reservee_au_fondateur(self):
        resp = self._api(self.admin_tenant).get(
            '/api/django/adminops/demandes-inscription/')
        self.assertIn(resp.status_code, (401, 403))

    def test_file_listee_avec_compteur(self):
        resp = self._api(self.fondateur).get(
            '/api/django/adminops/demandes-inscription/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['en_attente'], 1)
        self.assertEqual(len(resp.data['results']), 1)

    def test_approbation_cree_le_tenant_via_le_flux_n100b(self):
        resp = self._api(self.fondateur).post(
            f'/api/django/adminops/demandes-inscription/{self.demande.pk}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'approuvee')

        company = Company.objects.get(slug='solaire-atlas')
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.company_creee_id, company.pk)
        self.assertEqual(self.demande.traite_par, self.fondateur)

        # Provisionnement complet hérité de N100(b).
        admin = CustomUser.objects.get(company=company)
        self.assertEqual(admin.email, 'karim@solaire-atlas.ma')
        self.assertTrue(admin.must_change_password)
        from apps.roles.models import Role
        self.assertTrue(
            Role.objects.filter(company=company, nom='Directeur').exists())

    def test_refus_ne_cree_rien(self):
        resp = self._api(self.fondateur).post(
            f'/api/django/adminops/demandes-inscription/{self.demande.pk}/refuser/',
            {'notes': 'Hors cible'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'refusee')
        self.assertFalse(Company.objects.filter(slug='solaire-atlas').exists())

    def test_demande_deja_traitee_refusee(self):
        api = self._api(self.fondateur)
        api.post(
            f'/api/django/adminops/demandes-inscription/{self.demande.pk}/refuser/')
        rejeu = api.post(
            f'/api/django/adminops/demandes-inscription/{self.demande.pk}/approuver/')
        self.assertEqual(rejeu.status_code, 400)

    def test_approbation_reservee_au_fondateur(self):
        resp = self._api(self.admin_tenant).post(
            f'/api/django/adminops/demandes-inscription/{self.demande.pk}/approuver/')
        self.assertIn(resp.status_code, (401, 403))
        self.assertFalse(Company.objects.filter(slug='solaire-atlas').exists())


class ConsolePayloadEnrichiTests(TestCase):
    """N101(a) — la charge utile console s'enrichit sans jamais casser."""

    def setUp(self):
        self.fondateur = CustomUser.objects.create_superuser(
            username='fondateur_payload', password='pw83706',
            email='fondateur.payload@exemple.ma')
        self.tenant = Company.objects.create(
            nom='Payload Co', slug='payload-co')

    def test_payload_porte_sante_et_licences(self):
        from datetime import date

        from ..models import FactureLicence
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 8, 1),
            montant_ttc=1200, statut=FactureLicence.Statut.EMISE)

        client = APIClient()
        client.force_authenticate(self.fondateur)
        resp = client.get('/api/django/auth/console/tenants/')
        self.assertEqual(resp.status_code, 200)
        ligne = next(t for t in resp.data if t['id'] == self.tenant.pk)
        self.assertIn('health_score', ligne)
        self.assertEqual(ligne['licences_impayees'], 1)
        self.assertEqual(float(ligne['licences_du_ttc']), 1200.0)
        # Les clés de la lane concurrente sont absentes plutôt qu'inventées.
        self.assertNotIn('plan_inexistant', ligne)
