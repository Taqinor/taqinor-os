"""NTWMS28 — parcours de prélèvement en SERPENTIN (S-shape routing).

Critère d'acceptation testé : sur une vague de 20 lignes réparties dans
4 allées, le parcours proposé ne traverse jamais deux fois la même allée sans
nécessité — chaque allée forme UN SEUL bloc contigu, et le sens de parcours
alterne d'une allée à l'autre.

Run :
    python manage.py test apps.stock.test_ntwms28_parcours_serpentin -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Categorie, EmplacementStock, Produit
from apps.stock.services import (
    creer_vague_depuis_besoins, ordonner_parcours_serpentin,
    recalculer_parcours_vague,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestAlgorithmeSerpentin(TestCase):
    """L'algorithme est PUR (stdlib) : il se teste sans base de données."""

    def _entrees(self):
        entrees = []
        for allee in ('01', '02', '03', '04'):
            for casier in range(1, 6):
                entrees.append({
                    'cle': f'{allee}-{casier}', 'zone': 'A', 'allee': allee,
                    'ordre': casier,
                })
        return entrees

    def test_chaque_allee_forme_un_bloc_contigu(self):
        ordonnees = ordonner_parcours_serpentin(self._entrees())

        allees = [entree['allee'] for entree in ordonnees]
        blocs = [allees[0]]
        for allee in allees[1:]:
            if allee != blocs[-1]:
                blocs.append(allee)
        self.assertEqual(blocs, ['01', '02', '03', '04'])
        self.assertEqual(len(blocs), len(set(blocs)))

    def test_le_sens_alterne_d_une_allee_a_l_autre(self):
        ordonnees = ordonner_parcours_serpentin(self._entrees())
        par_allee = {}
        for entree in ordonnees:
            par_allee.setdefault(entree['allee'], []).append(entree['ordre'])

        self.assertEqual(par_allee['01'], [1, 2, 3, 4, 5])
        self.assertEqual(par_allee['02'], [5, 4, 3, 2, 1])
        self.assertEqual(par_allee['03'], [1, 2, 3, 4, 5])
        self.assertEqual(par_allee['04'], [5, 4, 3, 2, 1])

    def test_lignes_sans_casier_restent_a_la_fin(self):
        entrees = self._entrees() + [
            {'cle': 'libre', 'zone': '', 'allee': '', 'ordre': 1000}]
        ordonnees = ordonner_parcours_serpentin(entrees)
        self.assertEqual(ordonnees[-1]['cle'], 'libre')

    def test_liste_vide_ne_casse_pas(self):
        self.assertEqual(ordonner_parcours_serpentin([]), [])
        self.assertEqual(ordonner_parcours_serpentin(None), [])


class TestVagueSerpentin(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms28-co', 'NTWMS28 Co')
        self.admin = User.objects.create_user(
            username='ntwms28_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS28', is_principal=True)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Zone NTWMS28',
            strategie_picking_defaut=Categorie.StrategiePicking.ZONE)
        self.produits = []
        ordre = 1
        for allee in ('01', '02', '03', '04'):
            for casier in range(1, 6):
                produit = Produit.objects.create(
                    company=self.company, nom=f'Produit {allee}-{casier}',
                    sku=f'P{allee}{casier}-NTWMS28', categorie=self.categorie,
                    prix_achat=Decimal('10'), prix_vente=Decimal('20'),
                    quantite_stock=50)
                bin_loc = BinLocation.objects.create(
                    company=self.company, emplacement=self.emplacement,
                    code=f'A-{allee}-{casier}', zone='A', allee=allee,
                    casier=str(casier), ordre=ordre)
                BinAffectation.objects.create(
                    company=self.company, bin=bin_loc, produit=produit,
                    quantite=50)
                self.produits.append(produit)
                ordre += 1

    def _allees_du_parcours(self, vague):
        return [ligne.bin.allee
                for ligne in vague.lignes.select_related('bin')
                .order_by('ordre_parcours')]

    def test_vingt_lignes_quatre_allees_chacune_traversee_une_fois(self):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': p.id, 'quantite': 1}
                     for p in self.produits])

        self.assertEqual(vague.lignes.count(), 20)
        allees = self._allees_du_parcours(vague)
        blocs = [allees[0]]
        for allee in allees[1:]:
            if allee != blocs[-1]:
                blocs.append(allee)
        self.assertEqual(len(blocs), 4)
        self.assertEqual(len(blocs), len(set(blocs)))

    def test_recalcul_est_idempotent(self):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': p.id, 'quantite': 1}
                     for p in self.produits[:8]])
        avant = list(vague.lignes.order_by('ordre_parcours')
                     .values_list('id', flat=True))
        recalculer_parcours_vague(vague)
        apres = list(vague.lignes.order_by('ordre_parcours')
                     .values_list('id', flat=True))
        self.assertEqual(avant, apres)
