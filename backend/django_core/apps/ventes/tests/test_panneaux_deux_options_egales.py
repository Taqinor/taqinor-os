"""ACAL-NB2OPT — un devis DEUX OPTIONS à comptes ÉGAUX n'affiche plus la somme.

LE DÉFAUT (prouvé sur le devis de production DEV-202610-0024, scénario « Les
deux (Sans + Avec) ») : les panneaux sont stockés en DEUX lignes du même
produit, 8 ``variante='sans'`` + 8 ``variante='avec'``. La couverture du PDF
et de la proposition annonçait « 16 panneaux » et 11,36 kWc — la SOMME des
deux paniers — au-dessus d'un tableau qui liste 8 panneaux.

LA CAUSE : le scalaire global (``panneaux_et_watt_lu`` sur toutes les lignes)
additionne 8 + 8 ; la correction L-2OPT (clés legacy = option AVEC) ne se
déclenchait que si les deux comptes DIFFÉRAIENT (``divergents``). À comptes
égaux, rien ne remplaçait la somme.

LA RÈGLE : dès qu'une ligne panneau porte une variante (ou que les comptes
divergent), ``nb_panneaux`` / ``puissance_kwc`` / ``watt`` décrivent UNE
option (AVEC par défaut, celle rendue quand le document est rétréci). Un
devis aux seules lignes panneau communes reste byte-identique.

Lancer :
    powershell -File scripts/test-backend.ps1 \
        -Modules "apps.ventes.tests.test_panneaux_deux_options_egales"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

PANNEAU = 'Panneau Canadien Solar 710W'
RESEAU = 'Onduleur réseau Huawei 5kW Monophasé'
HYBRIDE = 'Onduleur hybride Deye 5kW Monophasé'
BATTERIE = 'Batterie Dyness 5 kWh'
DEUX_OPTIONS = 'Les deux (Sans + Avec)'
FACTURES_REELLES = [1200, 1200, 1300, 1400, 1600, 1800,
                    1900, 1900, 1700, 1500, 1300, 1200]

EQUIPEMENT = ((RESEAU, '1', '8000.00', ''),
              (HYBRIDE, '1', '14000.00', ''),
              (BATTERIE, '1', '20000.00', ''),
              ('Installation', '1', '4000.00', ''))

#: DEV-202610-0024 : 8 panneaux « sans » + 8 « avec », même produit.
EGAUX = ((PANNEAU, '8', '1166.67', 'sans'),
         (PANNEAU, '8', '1166.67', 'avec')) + EQUIPEMENT
#: Témoin historique : UNE ligne panneau commune de 8.
COMMUN = ((PANNEAU, '8', '1166.67', ''),) + EQUIPEMENT
#: Témoin L-2OPT : comptes divergents 6 / 8.
DIVERGENTS = ((PANNEAU, '6', '1166.67', 'sans'),
              (PANNEAU, '8', '1166.67', 'avec')) + EQUIPEMENT


class PanneauxDeuxOptionsEgalesTests(TestCase):

    def _devis(self, slug, lignes):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.create(company=company, nom=f'C {slug}')
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, statut='brouillon', taux_tva=Decimal('20'),
            remise_globale=Decimal('0'), mode_installation='residentiel',
            etude_params={'scenario': DEUX_OPTIONS,
                          'factures_mensuelles_reelles':
                              list(FACTURES_REELLES)})
        for i, (nom, qte, pu, variante) in enumerate(lignes):
            produit = Produit.objects.create(
                company=company, nom=nom, sku=f'{slug}-{i}',
                prix_vente=Decimal(pu), quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), variante=variante)
        return Devis.objects.get(pk=devis.pk)

    def _build(self, devis, pdf_options=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis, pdf_options)

    def test_comptes_egaux_varies_une_option_jamais_la_somme(self):
        """ROUGE avant le correctif : 16 panneaux, 11,36 kWc."""
        data = self._build(self._devis('nb2opt-egaux', EGAUX))
        self.assertEqual(data['nb_panneaux_sans'], 8)
        self.assertEqual(data['nb_panneaux_avec'], 8)
        self.assertFalse(data['panneaux_divergents'])
        self.assertEqual(data['nb_panneaux'], 8)
        self.assertEqual(data['puissance_kwc'], 5.68)

    def test_comptes_egaux_document_retreci_a_sans(self):
        data = self._build(self._devis('nb2opt-sans', EGAUX),
                           {'variante_option': 'sans'})
        self.assertEqual(data['nb_panneaux'], 8)
        self.assertEqual(data['puissance_kwc'], 5.68)

    def test_comptes_egaux_le_registre_reste_souverain(self):
        """QJR63 — un kWc imposé au registre passe toujours devant."""
        devis = self._devis('nb2opt-reg', EGAUX)
        with patch('apps.ventes.quote_engine.builder._kwc_du_registre',
                   return_value=6.0):
            data = self._build(devis)
        self.assertEqual(data['nb_panneaux'], 8)
        self.assertEqual(data['puissance_kwc'], 6.0)

    def test_ligne_panneau_commune_inchangee(self):
        data = self._build(self._devis('nb2opt-commun', COMMUN))
        self.assertEqual(data['nb_panneaux_sans'], 8)
        self.assertEqual(data['nb_panneaux_avec'], 8)
        self.assertFalse(data['panneaux_divergents'])
        self.assertEqual(data['nb_panneaux'], 8)
        self.assertEqual(data['puissance_kwc'], 5.68)

    def test_comptes_divergents_portent_toujours_l_option_avec(self):
        data = self._build(self._devis('nb2opt-div', DIVERGENTS))
        self.assertEqual(data['nb_panneaux_sans'], 6)
        self.assertEqual(data['nb_panneaux_avec'], 8)
        self.assertTrue(data['panneaux_divergents'])
        self.assertEqual(data['nb_panneaux'], 8)
        self.assertEqual(data['puissance_kwc'], 5.68)
