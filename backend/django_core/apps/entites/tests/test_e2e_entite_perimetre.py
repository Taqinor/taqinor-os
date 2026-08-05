"""NTADM44 — e2e backend « isoler une filiale puis consolider ».

Parcours complet, en une seule histoire et sans aucune donnée réelle :

  1. NTADM1 — une hiérarchie à 2 niveaux : Holding → Filiale A / Filiale B.
  2. NTADM2 — des devis et des leads RATTACHÉS à chaque filiale (plus une
     ligne « non affectée », qui n'appartient à personne).
  3. NTADM3 — un rôle RESTREINT à la filiale A.
  4. Isolation — ce rôle ne voit ni n'atteint la filiale B (liste filtrée,
     404 sur le détail, 403 à la création), et voit bien la filiale A.
  5. NTADM25 — pour un Administrateur SANS restriction, la vue consolidée
     agrège les DEUX filiales côte à côte plus un total.

Déterministe : montants distincts à 5 chiffres (aucune collision possible
avec un id), sociétés aux slugs explicitement distincts, aucune horloge.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..services import creer_entite

User = get_user_model()

URL_DEVIS = '/api/django/ventes/devis/'
URL_LEADS = '/api/django/crm/leads/'
URL_GROUPE = '/api/django/entites/entites/groupe/'

# Permissions du rôle commercial restreint : lecture + écriture ventes/CRM,
# jamais d'administration.
PERMS_COMMERCIAL = [
    'ventes_voir', 'ventes_creer', 'ventes_modifier',
    'crm_voir', 'crm_creer', 'users_voir',
]

MONTANT_A = Decimal('73951')
MONTANT_B = Decimal('21048')
MONTANT_LIBRE = Decimal('40506')


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts : le slug est UNIQUE et
    ``Company.save()`` le dérive du nom — deux sociétés qui retomberaient sur
    le même slug effectif seraient la MÊME ligne, et le test d'isolation ne
    prouverait alors rien."""
    return Company.objects.create(nom=nom, slug=slug)


class E2eEntitePerimetreTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client, Lead
        from apps.roles.models import Role
        from apps.ventes.models import Devis, LigneDevis

        # ── 1. Hiérarchie à 2 niveaux (NTADM1) ─────────────────────────────
        self.company = _company('NTADM44 Groupe', 'ntadm44-groupe')
        self.holding = creer_entite(self.company, nom='Holding', code='H')
        self.filiale_a = creer_entite(
            self.company, nom='Filiale A', code='FA', parent=self.holding)
        self.filiale_b = creer_entite(
            self.company, nom='Filiale B', code='FB', parent=self.holding)

        # Société VOISINE : rien d'elle ne doit jamais apparaître.
        self.voisine = _company('NTADM44 Voisine', 'ntadm44-voisine')
        self.entite_voisine = creer_entite(
            self.voisine, nom='Filiale voisine', code='FA')

        # ── 2. Documents rattachés par filiale (NTADM2) ────────────────────
        self.client_metier = Client.objects.create(
            company=self.company, nom='Client Groupe')

        def _devis(reference, entite, montant):
            devis = Devis.objects.create(
                company=self.company, reference=reference, entite=entite,
                client=self.client_metier, taux_tva=Decimal('0'),
                remise_globale=Decimal('0'))
            LigneDevis.objects.create(
                devis=devis, designation=reference, quantite=Decimal('1'),
                prix_unitaire=montant, remise=Decimal('0'),
                taux_tva=Decimal('0'))
            return devis

        self.devis_a = _devis('E2E-A', self.filiale_a, MONTANT_A)
        self.devis_b = _devis('E2E-B', self.filiale_b, MONTANT_B)
        self.devis_libre = _devis('E2E-LIBRE', None, MONTANT_LIBRE)

        Lead.objects.create(
            company=self.company, nom='Lead A', entite=self.filiale_a)
        Lead.objects.create(
            company=self.company, nom='Lead B', entite=self.filiale_b)
        Lead.objects.create(company=self.company, nom='Lead libre')

        # Devis de la société voisine (jamais visible ici).
        client_voisin = Client.objects.create(
            company=self.voisine, nom='Client voisin')
        devis_voisin = Devis.objects.create(
            company=self.voisine, reference='E2E-VOISIN',
            entite=self.entite_voisine, client=client_voisin,
            taux_tva=Decimal('0'), remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis_voisin, designation='Voisin', quantite=Decimal('1'),
            prix_unitaire=Decimal('99999'), remise=Decimal('0'),
            taux_tva=Decimal('0'))

        # ── 3. Rôle RESTREINT à la filiale A (NTADM3) ──────────────────────
        self.role_a = Role.objects.create(
            company=self.company, nom='Commercial Filiale A',
            permissions=list(PERMS_COMMERCIAL))
        self.role_a.entites_visibles.add(self.filiale_a)

        self.user_a = User.objects.create_user(
            username='ntadm44_a', password='pw', company=self.company,
            role=self.role_a, role_legacy='responsable')
        self.admin = User.objects.create_user(
            username='ntadm44_admin', password='pw', company=self.company,
            role_legacy='admin', is_staff=True)

        self.api_a = APIClient()
        self.api_a.force_authenticate(self.user_a)
        self.api_admin = APIClient()
        self.api_admin.force_authenticate(self.admin)

    # ── 4. Isolation ───────────────────────────────────────────────────────
    def test_1_isolation_liste_devis(self):
        resp = self.api_a.get(URL_DEVIS)
        self.assertEqual(resp.status_code, 200)
        refs = {d['reference'] for d in resp.data['results']}
        self.assertEqual(refs, {'E2E-A', 'E2E-LIBRE'})
        self.assertNotIn('E2E-VOISIN', refs)

    def test_2_isolation_liste_leads(self):
        resp = self.api_a.get(URL_LEADS)
        self.assertEqual(resp.status_code, 200)
        noms = {lead['nom'] for lead in resp.data['results']}
        self.assertEqual(noms, {'Lead A', 'Lead libre'})

    def test_3_detail_filiale_b_introuvable(self):
        """404 et jamais 403 : le devis de la filiale B n'existe pas pour lui."""
        resp = self.api_a.get(f'{URL_DEVIS}{self.devis_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_4_detail_filiale_a_accessible(self):
        resp = self.api_a.get(f'{URL_DEVIS}{self.devis_a.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reference'], 'E2E-A')

    def test_5_creation_vers_filiale_b_refusee(self):
        resp = self.api_a.post(
            URL_DEVIS,
            {'client': self.client_metier.id, 'entite': self.filiale_b.id},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_6_creation_vers_filiale_a_autorisee(self):
        resp = self.api_a.post(
            URL_DEVIS,
            {'client': self.client_metier.id, 'entite': self.filiale_a.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['entite'], self.filiale_a.id)

    def test_7_la_vue_groupe_reste_fermee_au_role_restreint(self):
        resp = self.api_a.get(URL_GROUPE)
        self.assertIn(resp.status_code, (401, 403))

    # ── 5. Consolidation (NTADM25) ─────────────────────────────────────────
    def test_8_consolidation_agrege_les_deux_filiales(self):
        resp = self.api_admin.get(URL_GROUPE)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['disponible'])

        par_code = {c['code']: c for c in resp.data['entites']}
        # 3 entités ACTIVES : la holding (sans document) et ses 2 filiales.
        self.assertEqual(sorted(par_code), ['FA', 'FB', 'H'])
        self.assertEqual(par_code['FA']['ca_devis'], '73951.00')
        self.assertEqual(par_code['FB']['ca_devis'], '21048.00')
        self.assertEqual(par_code['H']['ca_devis'], '0.00')

    def test_9_le_total_ignore_les_lignes_non_affectees(self):
        resp = self.api_admin.get(URL_GROUPE)
        total = resp.data['total']
        self.assertEqual(total['ca_devis'], '94999.00')
        self.assertEqual(total['nb_devis'], 2)

    def test_10_aucune_fuite_de_la_societe_voisine(self):
        resp = self.api_admin.get(URL_GROUPE)
        codes = [c['code'] for c in resp.data['entites']]
        # La voisine a une entité de MÊME code « FA » : elle ne doit pas
        # apparaître deux fois, ni gonfler le total.
        self.assertEqual(codes.count('FA'), 1)
        self.assertEqual(resp.data['total']['ca_devis'], '94999.00')
