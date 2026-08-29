"""QJR11 — la bande « Autres tailles proposées » passe par la chaîne canonique.

``public_views._variant_summaries`` publiait AU CLIENT le prix d'une taille
alternative par une SEPTIÈME chaîne monétaire écrite à la main. Elle était
fausse de trois façons (audit L3 du 29/08/2026) :

  1. aucun filtre ``compte_dans_totaux`` → elle comptait les lignes
     optionnelles NON activées et tentait de multiplier une ligne de
     section/note (``quantite`` NULL) — un ``TypeError`` que l'``except`` de
     sortie transformait en bande VIDE (constat V1) ;
  2. elle appliquait le ``taux_tva`` du DEVIS au lieu du taux PAR LIGNE
     (devis à taux mixtes 10 % panneaux / 20 % reste) ;
  3. sur un frère à DEUX options elle sommait les DEUX paniers — un montant
     qui n'existe dans aucun document.

Ce module verrouille le remplacement par ``utils.options.option_totaux`` et,
surtout, que la bande SURVIT à la ligne de section.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_variant_summaries -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.public_views import _variant_summaries
from apps.ventes.utils.options import totaux_affichage_repli

User = get_user_model()


def _company(slug='qjr11-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'QJR11 Co'})[0]


class TestVariantSummariesChaineCanonique(TestCase):
    """Le total publié d'un frère = son total d'AFFICHAGE, au centime."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='qjr11user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Nadia',
            email='nadia@qjr11.ma', telephone='+212611000411')

    # ── fixture ────────────────────────────────────────────────────────────
    def _devis(self, reference, **kwargs):
        params = {
            'company': self.company, 'reference': reference,
            'client': self.client_obj, 'statut': 'brouillon',
            'taux_tva': Decimal('20.00'), 'remise_globale': Decimal('0'),
            'created_by': self.user,
        }
        params.update(kwargs)
        return Devis.objects.create(**params)

    def _produit(self, nom, sku, pu):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_vente=Decimal(pu), prix_achat=Decimal('1'),
            quantite_stock=50)

    def _ligne(self, devis, nom, sku, pu, qty='1', taux='20.00',
               optionnelle=False, ordre=0):
        return LigneDevis.objects.create(
            devis=devis, produit=self._produit(nom, sku, pu),
            designation=nom, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=Decimal(taux), optionnelle=optionnelle, ordre=ordre)

    def _section(self, devis, texte, ordre=0):
        """Ligne de section : ``quantite``/``prix_unitaire`` NULL — c'est elle
        qui faisait lever l'ancienne chaîne et disparaître la bande."""
        return LigneDevis.objects.create(
            devis=devis, produit=None, designation=texte,
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='section', ordre=ordre)

    def _frere_complet(self, source):
        """Frère PIÉGÉ : deux options réelles (réseau / hybride+batterie),
        deux taux de TVA (10 % panneaux, 20 % reste), une ligne optionnelle
        NON activée et une ligne de section, plus 10 % de remise globale.

        Panier « avec batterie » (celui que porte le total d'affichage) :
            panneaux 10 × 2 000       = 20 000 HT à 10 %
            onduleur hybride 1 × 12 000 = 12 000 HT à 20 %
            batterie 2 × 9 000        = 18 000 HT à 20 %
            ------------------------------------------------
            HT brut 50 000 → remise 10 % → HT net 45 000
            TVA = 18 000 × 10 % + 27 000 × 20 % = 1 800 + 5 400 = 7 200
            TTC = 52 200,00
        """
        frere = self._devis(
            'DEV-QJR11-B', version_parent=source, version=2, is_active=True,
            remise_globale=Decimal('10'), note='Taille supérieure',
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        self._section(frere, 'Champ photovoltaïque', ordre=0)
        self._ligne(frere, 'Panneau solaire 550 W', 'QJR11-PAN', '2000',
                    qty='10', taux='10.00', ordre=1)
        self._ligne(frere, 'Onduleur réseau 5 kW', 'QJR11-OND-RES', '8000',
                    ordre=2)
        self._ligne(frere, 'Onduleur hybride 5 kW', 'QJR11-OND-HYB', '12000',
                    ordre=3)
        self._ligne(frere, 'Batterie 5 kWh', 'QJR11-BAT', '9000', qty='2',
                    ordre=4)
        self._ligne(frere, 'Monitoring premium 3 ans', 'QJR11-OPT', '3000',
                    optionnelle=True, ordre=5)
        return frere

    # ── tests ──────────────────────────────────────────────────────────────
    def test_bande_survit_a_la_ligne_section_et_total_canonique(self):
        """Le cas complet : la bande est TOUJOURS rendue et son prix est le
        total d'affichage du frère, au centime."""
        source = self._devis('DEV-QJR11-A')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC', '2000',
                    qty='6', taux='10.00')
        frere = self._frere_complet(source)

        summaries = _variant_summaries(source)

        # (1) La bande SURVIT — l'ancienne chaîne levait sur la section et
        # l'``except`` renvoyait [] : plus aucune « autre taille » affichée.
        self.assertEqual(len(summaries), 1, summaries)
        self.assertEqual(summaries[0]['id'], frere.id)
        self.assertEqual(summaries[0]['reference'], 'DEV-QJR11-B')
        self.assertEqual(summaries[0]['note'], 'Taille supérieure')

        # (2) Égalité au centime avec le total d'AFFICHAGE de ce frère.
        self.assertAlmostEqual(summaries[0]['total_ttc'], 52200.00, places=2)
        affiche = totaux_affichage_repli(frere)
        self.assertEqual(affiche['nb_options'], 2)
        self.assertAlmostEqual(
            summaries[0]['total_ttc'], round(float(affiche['total']), 2),
            places=2)

    def test_les_deux_options_ne_sont_jamais_additionnees(self):
        """Le prix publié est celui de l'option AVEC, pas la somme des deux."""
        source = self._devis('DEV-QJR11-C')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC2', '2000',
                    qty='6', taux='10.00')
        self._frere_complet(source)

        total = _variant_summaries(source)[0]['total_ttc']
        # Somme des deux paniers (58 000 HT → 52 200 HT net → 20 % à plat) :
        # 62 640, le montant que l'ancienne chaîne publiait.
        self.assertNotAlmostEqual(total, 62640.00, places=2)
        self.assertLess(total, 62640.00)

    def test_ligne_optionnelle_non_activee_hors_du_prix(self):
        """Activer l'option de 3 000 HT DOIT changer le prix publié ; tant
        qu'elle ne l'est pas, elle n'y entre pas."""
        source = self._devis('DEV-QJR11-D')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC3', '2000',
                    qty='6', taux='10.00')
        frere = self._frere_complet(source)

        avant = _variant_summaries(source)[0]['total_ttc']
        self.assertAlmostEqual(avant, 52200.00, places=2)

        frere.lignes.filter(designation='Monitoring premium 3 ans').update(
            optionnelle=False)
        apres = _variant_summaries(source)[0]['total_ttc']
        # + 3 000 HT brut → + 2 700 HT net → + 540 de TVA → + 3 240 TTC.
        self.assertAlmostEqual(apres, 55440.00, places=2)

    def test_taux_de_tva_par_ligne_et_non_taux_du_devis(self):
        """Le panier 10 % reste à 10 % : appliquer le taux du devis (20 %) à
        tout donnerait 54 000, pas 52 200."""
        source = self._devis('DEV-QJR11-E')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC4', '2000',
                    qty='6', taux='10.00')
        self._frere_complet(source)

        total = _variant_summaries(source)[0]['total_ttc']
        self.assertNotAlmostEqual(total, 54000.00, places=2)
        self.assertAlmostEqual(total, 52200.00, places=2)

    def test_frere_mono_option_inchange(self):
        """Un frère sans deux options garde son total complet (aucune
        régression du comportement historique)."""
        source = self._devis('DEV-QJR11-F')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC5', '2000',
                    qty='6', taux='20.00')
        frere = self._devis(
            'DEV-QJR11-Fb', version_parent=source, version=2, is_active=True)
        self._ligne(frere, 'Panneau solaire 550 W', 'QJR11-FB', '2000',
                    qty='8', taux='20.00')

        summaries = _variant_summaries(source)
        self.assertEqual(len(summaries), 1)
        # 8 × 2 000 = 16 000 HT, TVA 20 % → 19 200,00 TTC.
        self.assertAlmostEqual(summaries[0]['total_ttc'], 19200.00, places=2)
        self.assertAlmostEqual(
            summaries[0]['total_ttc'],
            round(float(totaux_affichage_repli(frere)['total']), 2), places=2)

    def test_frere_100_pourcent_structurel_ne_supprime_pas_la_bande(self):
        """Un frère qui ne porte QUE des lignes de section reste listé, à 0 —
        la bande n'est jamais supprimée par une ligne sans prix."""
        source = self._devis('DEV-QJR11-G')
        self._ligne(source, 'Panneau solaire 550 W', 'QJR11-SRC6', '2000',
                    qty='6', taux='20.00')
        frere = self._devis(
            'DEV-QJR11-Gb', version_parent=source, version=2, is_active=True)
        self._section(frere, 'À chiffrer', ordre=0)

        summaries = _variant_summaries(source)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]['id'], frere.id)
        self.assertAlmostEqual(summaries[0]['total_ttc'], 0.0, places=2)
