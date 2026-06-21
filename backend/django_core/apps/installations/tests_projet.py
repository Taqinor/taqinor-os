"""
FG293 / FG296 / FG298 — couche GESTION DE PROJET du chantier.

Couvre :
  * FG293 — JalonProjet : CRUD via l'API, dates cible/réelle, filtre par
    chantier, scope société, garde tenant sur le chantier ciblé.
  * FG296 — ModeleProjet + instanciation : l'action `instancier` pré-crée les
    jalons standard et complète la nomenclature gelée du chantier
    (idempotent, additif), scope société.
  * FG298 — ReunionChantier : compte-rendu horodaté (ordre du jour / présents /
    décisions / actions), rédacteur posé côté serveur, scope société.

Run :
    python manage.py test apps.installations.tests_projet -v2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import (
    JalonProjet, ModeleProjet, ModeleProjetJalon,
    ModeleProjetBomLigne, ReunionChantier,
)
from apps.installations.services import (
    create_installation_from_devis, instantiate_modele_projet,
)

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'proj-co-{n}'
    nom = nom or f'Proj Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user, type_installation='residentiel'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'proj-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation=type_installation)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-PROJ-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation=type_installation)
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


# ── FG293 — Jalons & phases de projet ────────────────────────────────────────

class TestFG293Jalons(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'p293-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_create_jalon_sets_company_server_side(self):
        """FG293 — un jalon créé via l'API porte la société du user (jamais du
        corps), même si le corps tente une autre société."""
        other = make_company()
        r = self.api.post(f'{BASE}/jalons-projet/', {
            'installation': self.inst.id,
            'phase': 'etude', 'libelle': 'Étude technique',
            'date_cible': '2026-07-01',
            'company': other.id,  # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        jalon = JalonProjet.objects.get(id=r.data['id'])
        self.assertEqual(jalon.company_id, self.company.id)
        self.assertEqual(jalon.phase, 'etude')
        self.assertEqual(str(jalon.date_cible), '2026-07-01')

    def test_phase_display_in_payload(self):
        """FG293 — le libellé français de la phase est exposé en lecture."""
        r = self.api.post(f'{BASE}/jalons-projet/', {
            'installation': self.inst.id, 'phase': 'mes', 'libelle': 'MES',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['phase_display'], 'Mise en service')

    def test_update_date_reelle(self):
        """FG293 — la date réelle (constatée) se pose par PATCH."""
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase='pose', libelle='Pose', date_cible=datetime.date(2026, 7, 10))
        r = self.api.patch(f'{BASE}/jalons-projet/{jalon.id}/', {
            'date_reelle': '2026-07-12', 'atteint': True,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        jalon.refresh_from_db()
        self.assertEqual(str(jalon.date_reelle), '2026-07-12')
        self.assertTrue(jalon.atteint)

    def test_filter_by_installation(self):
        """FG293 — la liste se filtre par chantier."""
        inst2 = make_chantier(self.company, self.user)
        JalonProjet.objects.create(
            company=self.company, installation=self.inst, libelle='J1')
        JalonProjet.objects.create(
            company=self.company, installation=inst2, libelle='J2')
        r = self.api.get(f'{BASE}/jalons-projet/',
                         {'installation': self.inst.id})
        self.assertEqual(r.status_code, 200)
        libelles = [j['libelle'] for j in r.data['results']]
        self.assertIn('J1', libelles)
        self.assertNotIn('J2', libelles)

    def test_company_isolation(self):
        """FG293 — la société B ne voit pas les jalons de A."""
        JalonProjet.objects.create(
            company=self.company, installation=self.inst, libelle='Secret A')
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p293b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/jalons-projet/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_cross_company_installation_rejected(self):
        """FG293 — impossible de rattacher un jalon à un chantier d'une autre
        société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p293c-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b = make_chantier(company_b, user_b)
        # user de la société A tente de viser le chantier de B.
        r = self.api.post(f'{BASE}/jalons-projet/', {
            'installation': inst_b.id, 'libelle': 'Intrus',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── FG296 — Modèles de projet (templates de chantier-type) ───────────────────

class TestFG296ModeleProjet(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'p296-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.inst.date_signature = datetime.date(2026, 6, 1)
        self.inst.save(update_fields=['date_signature'])
        self.modele = ModeleProjet.objects.create(
            company=self.company, nom='Résidentiel standard',
            type_installation='residentiel')
        ModeleProjetJalon.objects.create(
            company=self.company, modele=self.modele, phase='etude',
            libelle='Étude', ordre=0, offset_jours=0)
        ModeleProjetJalon.objects.create(
            company=self.company, modele=self.modele, phase='appro',
            libelle='Appro', ordre=1, offset_jours=7)
        ModeleProjetBomLigne.objects.create(
            company=self.company, modele=self.modele,
            designation='Câble solaire 6mm²', quantite=Decimal('100'), ordre=0)

    def test_instantiate_service_creates_jalons_and_bom(self):
        """FG296 — l'instanciation crée les jalons (date cible = signature +
        offset) et ajoute les lignes de BoM type au chantier."""
        bom_before = len(self.inst.bom or [])
        result = instantiate_modele_projet(self.inst, self.modele, self.user)
        self.assertEqual(result['jalons_crees'], 2)
        self.assertEqual(result['bom_lignes_ajoutees'], 1)
        jalons = list(self.inst.jalons.order_by('ordre'))
        self.assertEqual([j.libelle for j in jalons], ['Étude', 'Appro'])
        self.assertEqual(jalons[0].date_cible, datetime.date(2026, 6, 1))
        self.assertEqual(jalons[1].date_cible, datetime.date(2026, 6, 8))
        self.inst.refresh_from_db()
        self.assertEqual(len(self.inst.bom), bom_before + 1)

    def test_instantiate_is_idempotent(self):
        """FG296 — ré-appliquer le même modèle ne crée aucun doublon."""
        instantiate_modele_projet(self.inst, self.modele, self.user)
        result2 = instantiate_modele_projet(self.inst, self.modele, self.user)
        self.assertEqual(result2['jalons_crees'], 0)
        self.assertEqual(self.inst.jalons.count(), 2)

    def test_instancier_endpoint(self):
        """FG296 — l'action API `instancier` applique le modèle au chantier."""
        r = self.api.post(
            f'{BASE}/modeles-projet/{self.modele.id}/instancier/',
            {'installation': self.inst.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['jalons_crees'], 2)
        self.assertEqual(self.inst.jalons.count(), 2)

    def test_instancier_requires_installation(self):
        """FG296 — l'action `instancier` exige le champ installation."""
        r = self.api.post(
            f'{BASE}/modeles-projet/{self.modele.id}/instancier/', {},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_instancier_rejects_cross_company_chantier(self):
        """FG296 — on ne peut pas instancier un modèle sur le chantier d'une
        autre société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p296b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b = make_chantier(company_b, user_b)
        r = self.api.post(
            f'{BASE}/modeles-projet/{self.modele.id}/instancier/',
            {'installation': inst_b.id}, format='json')
        self.assertEqual(r.status_code, 404, r.data)

    def test_modele_list_nested_jalons(self):
        """FG296 — la liste des modèles imbrique les jalons et lignes de BoM."""
        r = self.api.get(f'{BASE}/modeles-projet/')
        self.assertEqual(r.status_code, 200)
        modele = next(m for m in r.data['results'] if m['id'] == self.modele.id)
        self.assertEqual(len(modele['jalons']), 2)
        self.assertEqual(len(modele['bom_lignes']), 1)

    def test_modele_company_isolation(self):
        """FG296 — la société B ne voit pas les modèles de A."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p296c-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/modeles-projet/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)


# ── FG298 — Comptes-rendus de réunion de chantier ────────────────────────────

class TestFG298Reunion(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'p298-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_create_reunion_sets_author_server_side(self):
        """FG298 — la réunion porte le rédacteur = user courant et la société,
        posés côté serveur."""
        other = make_company()
        r = self.api.post(f'{BASE}/reunions-chantier/', {
            'installation': self.inst.id,
            'titre': 'Réunion de lancement',
            'date_reunion': '2026-06-15T09:00:00Z',
            'ordre_du_jour': 'Planning, accès chantier',
            'presents': 'Reda, Sami, le client',
            'decisions': 'Pose la semaine 26',
            'actions': 'Commander la structure',
            'redige_par': 999999,   # ignoré côté serveur
            'company': other.id,    # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        reunion = ReunionChantier.objects.get(id=r.data['id'])
        self.assertEqual(reunion.company_id, self.company.id)
        self.assertEqual(reunion.redige_par_id, self.user.id)
        self.assertEqual(reunion.decisions, 'Pose la semaine 26')
        self.assertEqual(r.data['redige_par_nom'], self.user.username)

    def test_filter_by_installation(self):
        """FG298 — la liste se filtre par chantier."""
        inst2 = make_chantier(self.company, self.user)
        ReunionChantier.objects.create(
            company=self.company, installation=self.inst, titre='CR1')
        ReunionChantier.objects.create(
            company=self.company, installation=inst2, titre='CR2')
        r = self.api.get(f'{BASE}/reunions-chantier/',
                         {'installation': self.inst.id})
        self.assertEqual(r.status_code, 200)
        titres = [x['titre'] for x in r.data['results']]
        self.assertIn('CR1', titres)
        self.assertNotIn('CR2', titres)

    def test_company_isolation(self):
        """FG298 — la société B ne voit pas les CR de A."""
        ReunionChantier.objects.create(
            company=self.company, installation=self.inst, titre='Secret A')
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p298b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/reunions-chantier/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_cross_company_installation_rejected(self):
        """FG298 — impossible de rattacher un CR au chantier d'une autre
        société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'p298c-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b = make_chantier(company_b, user_b)
        r = self.api.post(f'{BASE}/reunions-chantier/', {
            'installation': inst_b.id, 'titre': 'Intrus',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
