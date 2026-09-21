"""Tests NTCON14 — Planning TCE multi-lots avec jalons contractuels.

Couvre : création de lots, rattachement de tâches ``gestion_projet.Tache``
EXISTANTES (table de liaison locale ``LotTache`` — aucune écriture chez
``gestion_projet``), Gantt groupé par lot avec code couleur, gardes de
cohérence (dates, entreprise/interne, couleur) et isolation multi-société.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import Lot, LotTache

from .helpers import (
    auth, make_chantier, make_company, make_fournisseur, make_lot,
    make_projet_lie, make_tache, make_user,
)

LOTS = '/api/django/btp-chantier/lots/'
PLANNING = '/api/django/btp-chantier/chantiers/{}/planning-lots/'


class LotCrudTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    def test_creation_lot_minimal(self):
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'Gros-œuvre', 'ordre': 1,
            'montant_ht': '150000.00', 'jalon_contractuel': True,
            'taux_penalite_retard_pmil': '1.000',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        lot = Lot.objects.get(pk=resp.data['id'])
        # Multi-tenant : la société est posée CÔTÉ SERVEUR.
        self.assertEqual(lot.company_id, self.co.id)
        self.assertEqual(lot.montant_ht, Decimal('150000.00'))
        self.assertTrue(lot.jalon_contractuel)

    def test_lot_sous_traite_exige_une_entreprise(self):
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'Électricité',
            'interne': False,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # L'erreur NOMME le champ fautif (règle fondateur).
        self.assertIn('sous_traitant', resp.data)

    def test_lot_interne_refuse_un_sous_traitant(self):
        fournisseur = make_fournisseur(self.co)
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'Plomberie',
            'interne': True, 'sous_traitant': fournisseur.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('interne', resp.data)

    def test_lot_sous_traite_accepte_une_entreprise(self):
        fournisseur = make_fournisseur(self.co)
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'CVC',
            'interne': False, 'sous_traitant': fournisseur.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['sous_traitant_nom'], fournisseur.nom)

    def test_dates_incoherentes_refusees(self):
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'Finitions',
            'date_debut_prevue': '2026-05-10',
            'date_fin_prevue': '2026-05-01',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_fin_prevue', resp.data)

    def test_couleur_invalide_refusee(self):
        resp = self.api.post(LOTS, {
            'chantier': self.chantier.id, 'nom': 'Peinture',
            'couleur': 'bleu',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('couleur', resp.data)

    def test_chantier_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.post(LOTS, {
            'chantier': chantier_autre.id, 'nom': 'Gros-œuvre',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('chantier', resp.data)

    def test_liste_filtree_par_chantier_et_isolee(self):
        make_lot(self.co, self.chantier, nom='Lot A')
        autre = make_company()
        chantier_autre = make_chantier(autre)
        make_lot(autre, chantier_autre, nom='Lot étranger')
        resp = self.api.get(LOTS, {'chantier': self.chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Le projet pagine par défaut (``core.pagination.StandardPagination``)
        # : la liste vit dans ``results`` — même idiome défensif que les autres
        # tests de listes de l'app (test_ntcon1/3/6).
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        noms = [r['nom'] for r in rows]
        self.assertEqual(noms, ['Lot A'])


class LotTachesTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.projet = make_projet_lie(self.co, self.chantier)
        self.lot = make_lot(self.co, self.chantier, nom='Gros-œuvre')
        self.t1 = make_tache(self.co, self.projet, libelle='Fondations')
        self.t2 = make_tache(self.co, self.projet, libelle='Élévations')
        self.api = auth(self.user)

    def url(self, lot=None):
        return f'{LOTS}{(lot or self.lot).id}/taches/'

    def test_rattache_des_taches_existantes(self):
        resp = self.api.post(
            self.url(), {'taches': [self.t1.id, self.t2.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(
            set(LotTache.objects.filter(lot=self.lot)
                .values_list('tache_id', flat=True)),
            {self.t1.id, self.t2.id})
        # Le rattachement porte la société (multi-tenant).
        self.assertTrue(all(
            lt.company_id == self.co.id
            for lt in LotTache.objects.filter(lot=self.lot)))

    def test_redefinir_remplace_l_ensemble(self):
        self.api.post(
            self.url(), {'taches': [self.t1.id, self.t2.id]}, format='json')
        resp = self.api.post(self.url(), {'taches': [self.t2.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(LotTache.objects.filter(lot=self.lot)
                 .values_list('tache_id', flat=True)),
            [self.t2.id])

    def test_tache_deja_dans_un_autre_lot_refusee(self):
        autre_lot = make_lot(self.co, self.chantier, nom='Électricité')
        self.api.post(self.url(), {'taches': [self.t1.id]}, format='json')
        resp = self.api.post(
            self.url(autre_lot), {'taches': [self.t1.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('déjà rattachée', resp.data['detail'])

    def test_tache_cross_tenant_refusee(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        projet_autre = make_projet_lie(autre, chantier_autre)
        tache_autre = make_tache(autre, projet_autre)
        resp = self.api.post(
            self.url(), {'taches': [tache_autre.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(LotTache.objects.filter(lot=self.lot).exists())


class PlanningParLotTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.projet = make_projet_lie(self.co, self.chantier)
        self.api = auth(self.user)

        self.lot1 = make_lot(
            self.co, self.chantier, nom='Gros-œuvre', ordre=1,
            date_debut_prevue='2026-01-05', date_fin_prevue='2026-03-01')
        self.lot2 = make_lot(
            self.co, self.chantier, nom='Électricité', ordre=2,
            couleur='#123456', date_debut_prevue='2026-03-02',
            date_fin_prevue='2026-04-01')
        t1 = make_tache(
            self.co, self.projet, libelle='Fondations', avancement_pct=100)
        t2 = make_tache(
            self.co, self.projet, libelle='Élévations', avancement_pct=50)
        LotTache.objects.create(company=self.co, lot=self.lot1, tache=t1)
        LotTache.objects.create(company=self.co, lot=self.lot1, tache=t2)

    def test_gantt_groupe_par_lot_avec_couleurs(self):
        resp = self.api.get(PLANNING.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual([b['nom'] for b in resp.data],
                         ['Gros-œuvre', 'Électricité'])
        bloc1, bloc2 = resp.data
        self.assertEqual(len(bloc1['taches']), 2)
        self.assertEqual(bloc1['avancement_pct'], 75)
        # Couleur explicite conservée ; repli STABLE de la palette sinon.
        self.assertEqual(bloc2['couleur'], '#123456')
        self.assertTrue(bloc1['couleur'].startswith('#'))
        self.assertEqual(bloc2['taches'], [])

    def test_planning_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.get(PLANNING.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
