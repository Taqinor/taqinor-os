"""N58 — tests de la configuration des statuts métier (StatutConfig).

Couvre : scoping société, company forcée côté serveur, GET effectif (défauts
fusionnés avec surcharges), upsert en masse, et l'invariance des clés
canoniques (couche purement cosmétique)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_statuses import StatutConfig
from apps.installations.models import Installation
from apps.sav.models import Ticket
from apps.ventes.models import BonCommande

User = get_user_model()

BASE = '/api/django/parametres/statuts/'


def _company(slug='stat-co', nom='Stat Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class StatutConfigTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='stat_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)

    # ── Défauts effectifs (rien d'enregistré) ────────────────────────────
    def test_effective_chantier_defaults_match_source(self):
        r = self.api.get(BASE + 'effective/', {'domaine': 'chantier'})
        self.assertEqual(r.status_code, 200)
        results = r.data['results']
        # Liste COMPLÈTE et ordonnée == entonnoir canonique du modèle source.
        keys = [row['cle'] for row in results]
        self.assertEqual(keys, list(Installation.STATUT_ORDER))
        labels = {row['cle']: row['libelle'] for row in results}
        # Libellés byte-identiques aux libellés codés en dur.
        self.assertEqual(labels['signe'], 'Signé')
        self.assertEqual(labels['materiel_commande'], 'Matériel commandé')
        # Rien n'est personnalisé tant qu'aucune surcharge n'existe.
        self.assertTrue(all(not row['personnalise'] for row in results))

    def test_effective_sav_and_bc_defaults(self):
        r = self.api.get(BASE + 'effective/', {'domaine': 'sav'})
        self.assertEqual([row['cle'] for row in r.data['results']],
                         list(Ticket.STATUT_ORDER))
        r2 = self.api.get(BASE + 'effective/', {'domaine': 'bon_commande'})
        self.assertEqual([row['cle'] for row in r2.data['results']],
                         [v for v, _ in BonCommande.Statut.choices])

    def test_effective_requires_valid_domaine(self):
        self.assertEqual(
            self.api.get(BASE + 'effective/').status_code, 400)
        self.assertEqual(
            self.api.get(BASE + 'effective/',
                         {'domaine': 'leads'}).status_code, 400)

    # ── Surcharge → fusionnée dans la liste effective ────────────────────
    def test_override_label_and_order_reflected_in_effective(self):
        # Renomme « signe » et le pousse en position 5.
        self.api.post(BASE, {
            'domaine': 'chantier', 'cle': 'signe',
            'libelle': 'Contrat signé', 'ordre': 5}, format='json')
        r = self.api.get(BASE + 'effective/', {'domaine': 'chantier'})
        rows = {row['cle']: row for row in r.data['results']}
        self.assertEqual(rows['signe']['libelle'], 'Contrat signé')
        self.assertEqual(rows['signe']['ordre'], 5)
        self.assertTrue(rows['signe']['personnalise'])
        # Le libellé par défaut reste exposé (pour un bouton « réinitialiser »).
        self.assertEqual(rows['signe']['libelle_defaut'], 'Signé')

    # ── company FORCÉE côté serveur (jamais lue du corps) ────────────────
    def test_company_forced_on_create(self):
        other = _company(slug='stat-evil', nom='Evil')
        r = self.api.post(BASE, {
            'domaine': 'sav', 'cle': 'nouveau', 'libelle': 'Reçu',
            'company': other.id}, format='json')
        self.assertEqual(r.status_code, 201)
        obj = StatutConfig.objects.get(id=r.data['id'])
        # company = celle de l'utilisateur, JAMAIS celle du corps.
        self.assertEqual(obj.company_id, self.company.id)

    # ── Clé inconnue refusée (on ne configure que des statuts existants) ──
    def test_unknown_key_rejected(self):
        r = self.api.post(BASE, {
            'domaine': 'chantier', 'cle': 'inexistant',
            'libelle': 'X'}, format='json')
        self.assertEqual(r.status_code, 400)

    # ── Upsert en masse (bulk) ───────────────────────────────────────────
    def test_bulk_upsert(self):
        r = self.api.put(BASE + 'bulk/', {
            'domaine': 'sav',
            'statuts': [
                {'cle': 'nouveau', 'libelle': 'À traiter', 'ordre': 0},
                {'cle': 'cloture', 'libelle': 'Fermé', 'ordre': 1,
                 'actif': False},
                {'cle': 'inconnu', 'libelle': 'ignoré'},  # ignoré en silence
            ]}, format='json')
        self.assertEqual(r.status_code, 200)
        rows = {row['cle']: row for row in r.data['results']}
        self.assertEqual(rows['nouveau']['libelle'], 'À traiter')
        self.assertEqual(rows['cloture']['libelle'], 'Fermé')
        self.assertFalse(rows['cloture']['actif'])
        # La clé inconnue n'a PAS été créée.
        self.assertFalse(StatutConfig.objects.filter(cle='inconnu').exists())

    # ── Scoping société : une société ne voit pas l'autre ────────────────
    def test_company_scoped_list(self):
        self.api.post(BASE, {
            'domaine': 'chantier', 'cle': 'signe',
            'libelle': 'Scopé'}, format='json')
        other = _company(slug='stat-other', nom='Other')
        other_admin = User.objects.create_user(
            username='stat_other_admin', password='x',
            role_legacy='admin', company=other)
        api2 = _auth(other_admin)
        r = api2.get(BASE, {'domaine': 'chantier'})
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 0)
        # La liste effective de l'autre société reste sur les défauts.
        eff = api2.get(BASE + 'effective/', {'domaine': 'chantier'})
        self.assertTrue(all(not row['personnalise']
                            for row in eff.data['results']))

    # ── Écriture réservée admin/responsable (pas le palier limité) ───────
    def test_write_forbidden_for_limited_role(self):
        viewer = User.objects.create_user(
            username='stat_viewer', password='x',
            role_legacy='normal', company=self.company)
        api2 = _auth(viewer)
        # Lecture OK.
        self.assertEqual(
            api2.get(BASE + 'effective/',
                     {'domaine': 'sav'}).status_code, 200)
        # Écriture refusée.
        r = api2.post(BASE, {
            'domaine': 'sav', 'cle': 'nouveau', 'libelle': 'X'},
            format='json')
        self.assertEqual(r.status_code, 403)

    # ── La clé d'une surcharge ne peut pas migrer ────────────────────────
    def test_cannot_reassign_key(self):
        r = self.api.post(BASE, {
            'domaine': 'chantier', 'cle': 'signe',
            'libelle': 'A'}, format='json')
        obj_id = r.data['id']
        r2 = self.api.patch(f'{BASE}{obj_id}/', {
            'cle': 'planifie'}, format='json')
        self.assertEqual(r2.status_code, 400)
