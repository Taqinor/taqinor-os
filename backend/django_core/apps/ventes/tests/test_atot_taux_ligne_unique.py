# -*- coding: utf-8 -*-
"""ATOT20 (C-ATOT-009) — UNE règle pour le taux d'une ligne de devis.

* toute ligne PRODUIT naît avec ``taux_tva`` posé : celui du produit
  (TVA-LIGNE, DC7), sinon celui du DEVIS — par l'écrivain unique
  ``creer_ligne``, donc pour chaque chemin (``remplacer_lignes``,
  ``cloner_lignes``, l'import de lignes sans produit) ; une section/note
  reste sans taux ;
* l'aller-retour « ouvrir → Enregistrer sans toucher » d'un devis aux lignes
  NULL (l'écran les relit au taux du devis, ``lignesServeurVersEcran``, et
  renvoie ce taux explicitement) laisse ``total_ttc`` identique.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_atot_taux_ligne_unique"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.domain.lignes import cloner_lignes, creer_ligne, remplacer_lignes
from apps.ventes.models import LigneDevis
from testkit.factories import CompanyFactory, DevisFactory, ProduitFactory


class TauxLigneUniqueTests(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.devis = DevisFactory(company=self.company, taux_tva=Decimal('20.00'))
        self.panneau = ProduitFactory(
            company=self.company, nom='Panneau Canadian Solar 710W',
            prix_vente=Decimal('1200'), tva=Decimal('10.00'))
        self.onduleur = ProduitFactory(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            prix_vente=Decimal('9000'), tva=Decimal('20.00'))
        self.socles = ProduitFactory(
            company=self.company, nom='Socles', prix_vente=Decimal('80'), tva=None)

    def _taux(self, devis):
        return list(devis.lignes.order_by('ordre', 'id').values_list('taux_tva', flat=True))

    def test_nouvelle_ligne_nait_avec_taux(self):
        # creer_ligne : produit à 10 % → 10 ; produit sans taux → taux du devis.
        p = creer_ligne(self.devis, produit=self.panneau, designation=self.panneau.nom,
                        quantite=Decimal('1'), prix_unitaire=Decimal('1200'))
        s = creer_ligne(self.devis, produit=self.socles, designation='Socles',
                        quantite=Decimal('1'), prix_unitaire=Decimal('80'))
        # Ligne sans produit (chemin de l'import NTMIG11) → taux du devis.
        i = creer_ligne(self.devis, designation='Main d’œuvre importée',
                        quantite=Decimal('1'), prix_unitaire=Decimal('500'))
        sec = creer_ligne(self.devis, produit=None, designation='Champ PV',
                          quantite=None, prix_unitaire=None, type_ligne='section')
        for ligne in (p, s, i, sec):
            ligne.refresh_from_db()
        self.assertEqual(p.taux_tva, Decimal('10.00'))
        self.assertEqual(s.taux_tva, Decimal('20.00'))
        self.assertEqual(i.taux_tva, Decimal('20.00'))
        self.assertIsNone(sec.taux_tva)

    def test_nouvelle_ligne_nait_avec_taux_remplacer_lignes(self):
        remplacer_lignes(self.devis, [
            {'produit': self.panneau.id, 'quantite': '8', 'prix_unitaire': '1200'},
            {'produit': self.socles.id, 'quantite': '8', 'prix_unitaire': '80'},
        ], self.company)
        self.assertEqual(self._taux(self.devis), [Decimal('10.00'), Decimal('20.00')])

    def test_nouvelle_ligne_nait_avec_taux_cloner_lignes(self):
        remplacer_lignes(self.devis, [
            {'produit': self.panneau.id, 'quantite': '8', 'prix_unitaire': '1200'},
            {'produit': self.socles.id, 'quantite': '8', 'prix_unitaire': '80'},
        ], self.company)
        cible = DevisFactory(company=self.company, taux_tva=Decimal('20.00'))
        cloner_lignes(self.devis, cible)
        self.assertNotIn(None, self._taux(cible))
        self.assertEqual(self._taux(cible), self._taux(self.devis))

    def test_aller_retour_sans_saisie_total_identique(self):
        # DEV-DEMO-0001 : trois lignes historiques à taux NULL (chiffrées au
        # taux du devis), panneau produit à 10 %.
        remplacer_lignes(self.devis, [
            {'produit': self.panneau.id, 'quantite': '8', 'prix_unitaire': '1200'},
            {'produit': self.onduleur.id, 'quantite': '1', 'prix_unitaire': '9000'},
            {'produit': self.socles.id, 'quantite': '8', 'prix_unitaire': '80'},
        ], self.company)
        LigneDevis.objects.filter(devis=self.devis).update(taux_tva=None)
        self.devis.refresh_from_db()
        total_avant = self.devis.total_ttc
        # L'écran relit chaque ligne NULL au taux du DEVIS et renvoie ce taux
        # explicitement (payload `lignesEcranVersPayload`).
        remplacer_lignes(self.devis, [
            {'produit': li.produit_id, 'quantite': str(li.quantite),
             'prix_unitaire': str(li.prix_unitaire), 'taux_tva': '20'}
            for li in self.devis.lignes.order_by('ordre', 'id')
        ], self.company)
        self.devis.refresh_from_db()
        self.assertEqual(self._taux(self.devis), [Decimal('20.00')] * 3)
        self.assertEqual(self.devis.total_ttc, total_avant)
