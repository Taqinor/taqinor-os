"""WIR281/XSAL6 — exposition REST des plans de commission.

Le modèle `PlanCommission` et le résolveur `resoudre_plan_commission`
existaient depuis XSAL6 SANS aucune route : un plan ne pouvait naître que dans
l'admin Django. Couvre :

  * CRUD company-scopé, société posée SERVEUR (jamais lue du corps) ;
  * GARDE MARGE : endpoint gaté `prix_achat_voir`, et aucun montant de marge
    ni prix d'achat dans le payload ;
  * `resoudre/?owner=` : plan dédié PRIME sur le plan par défaut société, et
    la priorité vient du SÉLECTEUR existant (jamais réimplémentée) ;
  * désactiver un plan = non-régression du calcul (le résolveur l'ignore et
    retombe sur le plan par défaut puis sur le mode société) ;
  * isolation multi-tenant (liste et écriture croisée).

Run :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_wir281_plans_commission_rest -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.ventes.models import PlanCommission
from testkit.factories import CompanyFactory, UserFactory, another_tenant

BASE = '/api/django/ventes/plans-commission'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def user_avec_prix_achat(company, username):
    """Rôle FIN portant `prix_achat_voir` — le palier exact de l'endpoint."""
    role = Role.objects.create(
        company=company, nom=f'Directeur {username}',
        permissions=['prix_achat_voir'])
    return UserFactory(company=company, username=username, role=role)


class TestGarde(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.directeur = user_avec_prix_achat(self.company, 'wir281-dir')

    def test_lecture_refusee_sans_prix_achat_voir(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['ventes_voir'])
        vendeur = UserFactory(
            company=self.company, username='wir281-vendeur', role=role)
        r = auth(vendeur).get(f'{BASE}/')
        self.assertEqual(r.status_code, 403, r.content)

    def test_ecriture_refusee_sans_prix_achat_voir(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial2', permissions=['ventes_voir'])
        vendeur = UserFactory(
            company=self.company, username='wir281-vendeur2', role=role)
        r = auth(vendeur).post(f'{BASE}/', {
            'base': 'ca_devis_signe', 'taux_pct': '3'}, format='json')
        self.assertEqual(r.status_code, 403, r.content)

    def test_lecture_autorisee_avec_prix_achat_voir(self):
        r = auth(self.directeur).get(f'{BASE}/')
        self.assertEqual(r.status_code, 200, r.content)

    def test_compte_legacy_normal_refuse(self):
        """Compte hérité SANS rôle fin : le repli `HasPermissionOrLegacy` est
        responsable/admin — un `normal` reste dehors."""
        normal = UserFactory(
            company=self.company, username='wir281-normal',
            role_legacy='normal')
        r = auth(normal).get(f'{BASE}/')
        self.assertEqual(r.status_code, 403, r.content)


class TestCrud(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.directeur = user_avec_prix_achat(self.company, 'wir281-crud')
        self.api = auth(self.directeur)
        self.commercial = UserFactory(
            company=self.company, username='wir281-sami')

    def test_creation_force_la_societe_et_ignore_le_corps(self):
        autre_company, _ = another_tenant()
        r = self.api.post(f'{BASE}/', {
            'owner': self.commercial.id,
            'base': 'ca_devis_signe',
            'taux_pct': '3.50',
            # Tentative d'injection : la société du corps est IGNORÉE.
            'company': autre_company.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        plan = PlanCommission.objects.get(pk=r.data['id'])
        self.assertEqual(plan.company_id, self.company.id)
        self.assertNotIn('company', r.data)

    def test_payload_ne_porte_aucun_montant_sensible(self):
        """GARDE MARGE — le payload ne doit contenir NI prix d'achat NI marge
        calculée : seulement une étiquette de base et des barèmes de règle."""
        r = self.api.post(f'{BASE}/', {
            'base': 'marge_interne', 'taux_pct': '10'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            set(r.data.keys()),
            {'id', 'owner', 'owner_nom', 'base', 'base_display', 'taux_pct',
             'montant_par_kwc', 'paliers', 'actif', 'created_at'})
        for interdit in ('prix_achat', 'marge', 'marge_mad', 'cout_achat'):
            self.assertNotIn(interdit, r.data)

    def test_par_kwc_exige_un_montant(self):
        r = self.api.post(f'{BASE}/', {
            'base': 'par_kwc'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('montant_par_kwc', r.data)

    def test_pourcentage_exige_un_taux(self):
        r = self.api.post(f'{BASE}/', {
            'base': 'ca_devis_signe'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('taux_pct', r.data)

    def test_paliers_doivent_etre_une_liste_dobjets(self):
        r = self.api.post(f'{BASE}/', {
            'base': 'ca_devis_signe', 'taux_pct': '3',
            'paliers': [{'seuil_atteinte_pct': 100}]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('paliers', r.data)

    def test_paliers_valides_acceptes(self):
        r = self.api.post(f'{BASE}/', {
            'base': 'ca_devis_signe', 'taux_pct': '3',
            'paliers': [{'seuil_atteinte_pct': 100, 'taux': 5}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['paliers'], [
            {'seuil_atteinte_pct': 100, 'taux': 5}])

    def test_filtre_owner_et_defaut_societe(self):
        PlanCommission.objects.create(
            company=self.company, owner=self.commercial,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('3'))
        PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))

        dedies = self.api.get(f'{BASE}/?owner={self.commercial.id}')
        resultats = dedies.data.get('results', dedies.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['owner'], self.commercial.id)

        defauts = self.api.get(f'{BASE}/?owner=')
        resultats = defauts.data.get('results', defauts.data)
        self.assertEqual(len(resultats), 1)
        self.assertIsNone(resultats[0]['owner'])

    def test_filtre_actif(self):
        PlanCommission.objects.create(
            company=self.company, owner=None, actif=False,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))
        r = self.api.get(f'{BASE}/?actif=true')
        resultats = r.data.get('results', r.data)
        self.assertEqual(len(resultats), 0)

    def test_owner_dune_autre_societe_refuse(self):
        _, etranger = another_tenant()
        r = self.api.post(f'{BASE}/', {
            'owner': etranger.id, 'base': 'ca_devis_signe',
            'taux_pct': '3'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('owner', r.data)

    def test_isolation_multi_tenant_en_liste(self):
        autre_company, autre_user = another_tenant()
        PlanCommission.objects.create(
            company=autre_company, owner=autre_user,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('50'))
        r = self.api.get(f'{BASE}/')
        resultats = r.data.get('results', r.data)
        self.assertEqual(len(resultats), 0)


class TestResoudre(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.directeur = user_avec_prix_achat(self.company, 'wir281-res')
        self.api = auth(self.directeur)
        self.commercial = UserFactory(
            company=self.company, username='wir281-com')

    def test_plan_dedie_prime_sur_le_mode_societe(self):
        PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))
        dedie = PlanCommission.objects.create(
            company=self.company, owner=self.commercial,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('7'))
        r = self.api.get(f'{BASE}/resoudre/?owner={self.commercial.id}')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['source'], 'plan_dedie')
        self.assertEqual(r.data['plan']['id'], dedie.id)
        self.assertEqual(r.data['owner'], self.commercial.id)

    def test_retombe_sur_le_plan_par_defaut_societe(self):
        defaut = PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))
        r = self.api.get(f'{BASE}/resoudre/?owner={self.commercial.id}')
        self.assertEqual(r.data['source'], 'plan_defaut_societe')
        self.assertEqual(r.data['plan']['id'], defaut.id)

    def test_aucun_plan_renvoie_le_mode_societe(self):
        r = self.api.get(f'{BASE}/resoudre/?owner={self.commercial.id}')
        self.assertEqual(r.data['source'], 'mode_societe')
        self.assertIsNone(r.data['plan'])

    def test_desactiver_un_plan_ne_regresse_pas_le_calcul(self):
        """Désactiver le plan dédié fait retomber sur le plan par défaut —
        le rapport de commissions garde donc une base, il ne tombe pas à zéro."""
        defaut = PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))
        dedie = PlanCommission.objects.create(
            company=self.company, owner=self.commercial,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('7'))

        r = self.api.patch(
            f'{BASE}/{dedie.id}/', {'actif': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

        r = self.api.get(f'{BASE}/resoudre/?owner={self.commercial.id}')
        self.assertEqual(r.data['source'], 'plan_defaut_societe')
        self.assertEqual(r.data['plan']['id'], defaut.id)

    def test_owner_omis_renvoie_le_plan_par_defaut(self):
        defaut = PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.PAR_KWC,
            montant_par_kwc=Decimal('250'))
        r = self.api.get(f'{BASE}/resoudre/')
        self.assertIsNone(r.data['owner'])
        self.assertEqual(r.data['source'], 'plan_defaut_societe')
        self.assertEqual(r.data['plan']['id'], defaut.id)

    def test_owner_dune_autre_societe_refuse(self):
        _, etranger = another_tenant()
        r = self.api.get(f'{BASE}/resoudre/?owner={etranger.id}')
        self.assertEqual(r.status_code, 400, r.content)

    def test_resoudre_gate_par_prix_achat_voir(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial3',
            permissions=['ventes_voir'])
        vendeur = UserFactory(
            company=self.company, username='wir281-vendeur3', role=role)
        r = auth(vendeur).get(f'{BASE}/resoudre/?owner={self.commercial.id}')
        self.assertEqual(r.status_code, 403, r.content)
