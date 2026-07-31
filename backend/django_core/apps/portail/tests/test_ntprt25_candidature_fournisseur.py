"""Tests NTPRT25 — auto-inscription (candidature) d'un fournisseur.

Le critère d'acceptation est une garantie NÉGATIVE : « un fournisseur en
attente n'apparaît dans AUCUNE liste de sourcing automatique tant qu'il n'est
pas validé ». Les tests l'exercent des deux côtés — la candidature créée est
invisible du sourcing, et elle y entre à la validation.

Les autres pièges couverts, tous liés au fait que l'endpoint est PUBLIC :

* la société vient de l'en-tête ``Host``, jamais du corps — sinon n'importe qui
  déposerait une candidature dans le référentiel du tenant de son choix ;
* le corps ne peut poser NI ``statut_validation`` NI ``statut`` NI ``company``
  (un candidat ne s'auto-valide pas) ;
* la validation/le rejet est réservé à l'ADMINISTRATEUR, et ``valider`` est
  obligatoire (aucun défaut : un corps vide ne fait entrer personne).

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt25_candidature_fournisseur -v2
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.stock.models import Fournisseur
from apps.stock.selectors import search_fournisseurs
from authentication.models import Company, CustomUser
from core.models import TenantTheme

URL = '/api/django/portail/fournisseurs/candidature/'
_HOTES = ['tenant-a.example', 'tenant-b.example', 'inconnu.example',
          'testserver']


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par appelant."""
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=f'role-{username}',
        defaults={'permissions': list(permissions)})
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)


@override_settings(ALLOWED_HOSTS=_HOTES)
class CandidaturePubliqueTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ntprt25-co-a', 'Tenant A')
        self.co_b = make_company('ntprt25-co-b', 'Tenant B')
        TenantTheme.objects.create(
            company=self.co_a, domaine='tenant-a.example')
        TenantTheme.objects.create(
            company=self.co_b, domaine='tenant-b.example')
        self.api = APIClient()

    def test_candidature_creee_en_attente_dans_le_bon_tenant(self):
        res = self.api.post(
            URL, {'nom': 'Solaris Distribution', 'email': 'a@example.invalid'},
            format='json', HTTP_HOST='tenant-a.example')

        self.assertEqual(res.status_code, 201, res.data)
        f = Fournisseur.objects.get(nom='Solaris Distribution')
        self.assertEqual(f.company_id, self.co_a.id)
        self.assertEqual(f.statut_validation,
                         Fournisseur.StatutValidation.EN_ATTENTE)
        # L'axe de BLOCAGE commercial (XPUR4) n'est pas détourné.
        self.assertEqual(f.statut, Fournisseur.Statut.ACTIF)

    def test_le_corps_ne_peut_pas_choisir_la_societe(self):
        """Le tenant vient du Host — un `company` posté est IGNORÉ."""
        res = self.api.post(
            URL, {'nom': 'Intrus SARL', 'company': self.co_b.id},
            format='json', HTTP_HOST='tenant-a.example')

        self.assertEqual(res.status_code, 201)
        f = Fournisseur.objects.get(nom='Intrus SARL')
        self.assertEqual(f.company_id, self.co_a.id)

    def test_le_corps_ne_peut_pas_s_auto_valider(self):
        res = self.api.post(
            URL,
            {'nom': 'Auto Valide SARL', 'statut_validation': 'valide',
             'statut': 'actif'},
            format='json', HTTP_HOST='tenant-a.example')

        self.assertEqual(res.status_code, 201)
        f = Fournisseur.objects.get(nom='Auto Valide SARL')
        self.assertEqual(f.statut_validation,
                         Fournisseur.StatutValidation.EN_ATTENTE)

    def test_hote_inconnu_404_sans_creation(self):
        res = self.api.post(
            URL, {'nom': 'Orphelin SARL'}, format='json',
            HTTP_HOST='inconnu.example')
        self.assertEqual(res.status_code, 404)
        self.assertFalse(Fournisseur.objects.filter(nom='Orphelin SARL')
                         .exists())

    def test_nom_obligatoire(self):
        res = self.api.post(
            URL, {'email': 'x@example.invalid'}, format='json',
            HTTP_HOST='tenant-a.example')
        self.assertEqual(res.status_code, 400)

    def test_double_envoi_ne_duplique_pas(self):
        payload = {'nom': 'Doublon SARL'}
        self.api.post(URL, payload, format='json',
                      HTTP_HOST='tenant-a.example')
        self.api.post(URL, payload, format='json',
                      HTTP_HOST='tenant-a.example')
        self.assertEqual(
            Fournisseur.objects.filter(company=self.co_a,
                                       nom='Doublon SARL').count(), 1)

    def test_la_reponse_ne_revele_rien_du_referentiel(self):
        res = self.api.post(
            URL, {'nom': 'Discret SARL'}, format='json',
            HTTP_HOST='tenant-a.example')
        self.assertEqual(set(res.data.keys()), {'detail'})


@override_settings(ALLOWED_HOSTS=_HOTES)
class SourcingEtValidationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt25-src', 'NTPRT25 Sourcing')
        self.candidat = Fournisseur.objects.create(
            company=self.company, nom='Candidat Sourcing SARL',
            statut_validation=Fournisseur.StatutValidation.EN_ATTENTE)
        self.historique = Fournisseur.objects.create(
            company=self.company, nom='Candidat Historique SARL')
        self.api = APIClient()

    def test_un_candidat_en_attente_est_hors_du_sourcing_automatique(self):
        noms = [f.nom for f in search_fournisseurs(self.company, 'Candidat')]
        self.assertIn('Candidat Historique SARL', noms)
        self.assertNotIn('Candidat Sourcing SARL', noms)

    def test_les_fournisseurs_existants_restent_valides_par_defaut(self):
        self.assertEqual(self.historique.statut_validation,
                         Fournisseur.StatutValidation.VALIDE)

    def test_un_admin_valide_et_le_candidat_entre_dans_le_sourcing(self):
        admin = make_user(self.company, 'ntprt25-admin', ['roles_gerer'])
        self.api.force_authenticate(user=admin)
        res = self.api.post(
            f'/api/django/stock/fournisseurs/{self.candidat.id}/'
            'decider-candidature/', {'valider': True}, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.statut_validation,
                         Fournisseur.StatutValidation.VALIDE)
        noms = [f.nom for f in search_fournisseurs(self.company, 'Candidat')]
        self.assertIn('Candidat Sourcing SARL', noms)

    def test_rejet_garde_le_candidat_hors_du_sourcing(self):
        admin = make_user(self.company, 'ntprt25-admin-r', ['roles_gerer'])
        self.api.force_authenticate(user=admin)
        self.api.post(
            f'/api/django/stock/fournisseurs/{self.candidat.id}/'
            'decider-candidature/', {'valider': False}, format='json')

        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.statut_validation,
                         Fournisseur.StatutValidation.REJETE)
        noms = [f.nom for f in search_fournisseurs(self.company, 'Candidat')]
        self.assertNotIn('Candidat Sourcing SARL', noms)

    def test_valider_est_obligatoire(self):
        """Un corps vide ne doit JAMAIS faire entrer un tiers par défaut."""
        admin = make_user(self.company, 'ntprt25-admin-v', ['roles_gerer'])
        self.api.force_authenticate(user=admin)
        res = self.api.post(
            f'/api/django/stock/fournisseurs/{self.candidat.id}/'
            'decider-candidature/', {}, format='json')

        self.assertEqual(res.status_code, 400)
        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.statut_validation,
                         Fournisseur.StatutValidation.EN_ATTENTE)

    def test_non_admin_refuse(self):
        """`stock_modifier` ne suffit pas : la décision est administrative."""
        modif = make_user(self.company, 'ntprt25-modif',
                          ['stock_voir', 'stock_modifier'])
        self.api.force_authenticate(user=modif)
        res = self.api.post(
            f'/api/django/stock/fournisseurs/{self.candidat.id}/'
            'decider-candidature/', {'valider': True}, format='json')

        self.assertEqual(res.status_code, 403)
        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.statut_validation,
                         Fournisseur.StatutValidation.EN_ATTENTE)

    def test_anonyme_refuse(self):
        res = APIClient().post(
            f'/api/django/stock/fournisseurs/{self.candidat.id}/'
            'decider-candidature/', {'valider': True}, format='json')
        self.assertIn(res.status_code, (401, 403))

    def test_un_fournisseur_deja_valide_n_est_pas_rejete_retroactivement(self):
        admin = make_user(self.company, 'ntprt25-admin-h', ['roles_gerer'])
        self.api.force_authenticate(user=admin)
        self.api.post(
            f'/api/django/stock/fournisseurs/{self.historique.id}/'
            'decider-candidature/', {'valider': False}, format='json')

        self.historique.refresh_from_db()
        self.assertEqual(self.historique.statut_validation,
                         Fournisseur.StatutValidation.VALIDE)
