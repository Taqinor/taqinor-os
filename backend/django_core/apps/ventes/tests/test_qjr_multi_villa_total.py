"""QJR8 — Le « Total général » multi-villa cesse d'exclure les lignes hors groupe.

Avant ce correctif, ``selectors.multi_villa_totaux`` calculait son
``grand_total`` en ne sommant QUE les lignes portant un ``groupe_index`` :
dès qu'une ligne était hors groupe, le total général imprimé était INFÉRIEUR
au total du document lui-même — deux chiffres irréconciliables sur la même
page d'un PDF client (origine : devis-model-options-08 / R4-B2.12).

Ce module prouve : (1) ``grand_total`` porte la même population de lignes que
la chaîne canonique du document entier (``ligne_compte_dans_totaux`` honoré),
au centime ; (2) une ligne hors groupe n'est plus silencieusement absente —
elle rejoint une rubrique nommée ; (3) le chemin mono-villa (aucune ligne
groupée) reste inchangé (retourne ``None``).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_multi_villa_total -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

# Compteur de tenants : une société NEUVE à chaque appel sans slug (évite
# qu'un get_or_create sur un slug fixe fasse partager la société entre tests).
_company_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_company_seq)
    c, _ = Company.objects.get_or_create(
        slug=f'test-qjr8-co-{n}', defaults={'nom': f'Test QJR8 Co {n}'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qjr8user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Villa', prenom='Owner',
        email='qjr8@example.com', telephone='+212600000011')


def _produit(company, desig, sku, pu):
    return Produit.objects.create(
        company=company, nom=desig, sku=sku, prix_vente=Decimal(pu),
        prix_achat=Decimal('1'), quantite_stock=100)


class TestGrandTotalIncludesHorsGroupeLines(TestCase):
    """QJR8 — une ligne sans ``groupe_index`` ne disparaît plus du total général."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis_avec_ligne_hors_groupe(self, reference='DEV-QJR8-MIX'):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        # commun (0), Villa A (1), Villa B (2), puis UNE ligne hors groupe
        # (frais de dossier) qui ne porte aucun groupe_index.
        rows = [
            ('Installation commune', '1', '5000', 0, 'Équipement commun'),
            ('Onduleur réseau 8kW', '1', '14000', 1, 'Villa A'),
            ('Panneau mono 550W', '10', '1400', 1, 'Villa A'),
            ('Onduleur réseau 5kW', '1', '11000', 2, 'Villa B'),
            ('Panneau mono 550W', '8', '1400', 2, 'Villa B'),
            ('Frais de dossier', '1', '800', None, ''),
        ]
        for i, (desig, qty, pu, gi, gl) in enumerate(rows):
            LigneDevis.objects.create(
                devis=devis,
                produit=_produit(self.company, desig,
                                 f'{reference[-6:]}-{i}', pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                groupe_index=gi, groupe_label=gl)
        return devis

    def test_grand_total_matches_document_canonical_total(self):
        """grand_total == chaîne canonique sur TOUTES les lignes qui comptent,
        pas seulement les lignes groupées — au centime."""
        from apps.ventes.selectors import _canonical_totaux, multi_villa_totaux

        devis = self._devis_avec_ligne_hors_groupe()
        mv = multi_villa_totaux(devis)
        self.assertIsNotNone(mv)

        toutes_les_lignes = list(devis.lignes.all())
        attendu = _canonical_totaux(
            toutes_les_lignes, remise_globale_pct=devis.remise_globale,
            fallback_taux=devis.taux_tva)

        # 5000 (commun) + 28000 (Villa A) + 22200 (Villa B) + 800 (hors groupe)
        self.assertEqual(attendu['ht_brut'], Decimal('56000.00'))
        self.assertEqual(mv['grand_total']['ht_brut'], attendu['ht_brut'])
        self.assertEqual(mv['grand_total']['ttc'], attendu['ttc'])

        # AVANT le correctif, grand_total ne portait que les lignes groupées
        # (55200.00 HT) — strictement inférieur au total du document : la
        # régression vers ce bug ferait échouer l'assertion ci-dessus.
        somme_lignes_groupees_seules = Decimal('5000.00') + Decimal('28000.00') + Decimal('22200.00')
        self.assertNotEqual(mv['grand_total']['ht_brut'], somme_lignes_groupees_seules)

    def test_ligne_hors_groupe_apparait_dans_une_rubrique_nommee(self):
        """Une ligne hors groupe n'est plus absente du détail : elle apparaît
        dans un groupe dédié plutôt que de disparaître silencieusement."""
        from apps.ventes.selectors import multi_villa_totaux

        devis = self._devis_avec_ligne_hors_groupe()
        mv = multi_villa_totaux(devis)

        labels = [g['label'] for g in mv['groupes']]
        self.assertEqual(
            labels, ['Équipement commun', 'Villa A', 'Villa B', 'Hors groupe'])
        rubrique_hors_groupe = mv['groupes'][-1]
        self.assertIsNone(rubrique_hors_groupe['index'])
        self.assertEqual(
            rubrique_hors_groupe['totaux']['ht_brut'], Decimal('800.00'))

    def test_build_quote_data_grand_total_matches_document_total(self):
        """Le total général exposé au PDF == le total du document affiché
        ailleurs (totaux_all) — même chiffre, pas deux versions différentes."""
        from apps.ventes.quote_engine import build_quote_data

        devis = self._devis_avec_ligne_hors_groupe('DEV-QJR8-BQD')
        data = build_quote_data(devis)
        self.assertIn('multi_villa', data)
        self.assertEqual(
            data['multi_villa']['grand_total']['ttc'], data['totaux_all']['ttc'])
        self.assertAlmostEqual(
            data['multi_villa']['grand_total']['ht_brut'],
            data['totaux_all']['ht_brut'], places=2)

    def test_pas_de_ligne_hors_groupe_pas_de_rubrique_supplementaire(self):
        """Zéro ligne hors groupe (fixture historique) : aucune rubrique
        « Hors groupe » ajoutée — comportement inchangé pour ces devis."""
        from apps.ventes.selectors import multi_villa_totaux

        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR8-ALLGRP',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user)
        rows = [
            ('Installation commune', '1', '5000', 0, 'Équipement commun'),
            ('Onduleur réseau 8kW', '1', '14000', 1, 'Villa A'),
        ]
        for i, (desig, qty, pu, gi, gl) in enumerate(rows):
            LigneDevis.objects.create(
                devis=devis,
                produit=_produit(self.company, desig, f'ALLGRP-{i}', pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                groupe_index=gi, groupe_label=gl)
        mv = multi_villa_totaux(devis)
        labels = [g['label'] for g in mv['groupes']]
        self.assertEqual(labels, ['Équipement commun', 'Villa A'])
