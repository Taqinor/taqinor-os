"""Un devis à OPTION UNIQUE qui porte des lignes VARIANTÉES : le PDF imprime ce
que le noyau facture.

LE DÉFAUT (reproduit le 30/09/2026, base de dev, transaction annulée ; un cas
en prod : DEV-202609-0006, brouillon). ``LigneDevis.variante`` ('sans' /
'avec') n'a de sens que sur un devis à DEUX options (L-2OPT). Quand le devis
redevient mono-option — le vendeur retire l'onduleur réseau, ou l'onduleur de
l'option « avec » est passé en ligne optionnelle —, les étiquettes restent :

* le NOYAU (``utils.options.option_lines`` / ``option_totaux``) voit un devis
  mono-option et facture TOUTES ses lignes (``option_effective`` = '') ;
* le BUILDER, lui, rendait le panier de l'option servie, filtré par variante :
  les lignes étiquetées de l'AUTRE option disparaissaient du document.

Deux prix pour la même vente : DEV-202609-0006 affichait 23 766 MAD TTC au PDF
pendant que l'ERP (``Devis.total_ttc``, échéancier, factures) comptait
86 269,87. Un devis réseau seul à 6 panneaux « sans » + 8 « avec » : 27 600,02
imprimés contre 38 800,06 facturés.

LA RÈGLE APPLIQUÉE : celle que le moteur suit déjà pour l'artefact PV86 et
pour Z1, et que QJR300 / D12 ont tranchée (« le PDF s'aligne sur le noyau —
les lignes du vendeur sont souveraines ») : un document à option unique rend
TOUTES les lignes du devis, son étiquette suit la batterie RÉELLE, et un
avertissement INTERNE nomme la contradiction pour que le vendeur assainisse
ses lignes. Le noyau ne change pas : l'argent reste exactement celui d'hier.

Lancer :
    powershell -File scripts/test-backend.ps1 \
        -Modules "apps.ventes.tests.test_pdf_mono_option_lignes_variantees"
"""
from decimal import Decimal

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

#: Les deux champs PV L-2OPT : 6 panneaux « sans », 8 « avec ».
CHAMPS = ((PANNEAU, '6', '1166.67', 'sans'),
          (PANNEAU, '8', '1166.67', 'avec'))
POSE = (('Installation', '1', '4000.00', ''),)


class _Base(TestCase):

    def _devis(self, slug, lignes, scenario=DEUX_OPTIONS):
        """``lignes`` = [(désignation, qté, PU HT, variante[, optionnelle])]."""
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
            mode_installation='residentiel',
            etude_params={'scenario': scenario} if scenario else {})
        for i, (nom, qte, pu, variante, *reste) in enumerate(lignes):
            produit = Produit.objects.create(
                company=company, nom=nom, sku=f'{slug}-{i}', prix_vente=pu,
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), variante=variante,
                optionnelle=bool(reste and reste[0]))
        return Devis.objects.get(pk=devis.pk)

    def _imprime_et_facture(self, devis):
        """(données, lignes que le PDF imprime, lignes que le noyau facture)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.utils.options import option_lines
        data = build_quote_data(devis)
        rendu = (data['avec_items'] if data['avec_ok'] and not data['sans_ok']
                 else data['sans_items'])
        imprime = sorted((it['designation'], float(it['quantite']))
                         for it in rendu)
        facture = sorted((li.designation, float(li.quantite))
                         for li in option_lines(devis))
        return data, imprime, facture

    def _assert_pdf_egal_noyau(self, devis):
        from apps.ventes.utils.options import option_totaux
        data, imprime, facture = self._imprime_et_facture(devis)
        self.assertFalse(data['deux_options'])
        self.assertEqual(imprime, facture)
        self.assertAlmostEqual(float(data['display_total']),
                               float(option_totaux(devis)['ttc']), places=2)
        return data


class PdfEgalNoyauTests(_Base):
    """Le PDF d'un devis mono-option à lignes variantées = ce que le noyau
    facture — ligne pour ligne, dirham pour dirham."""

    def test_reseau_seul_imprime_les_panneaux_de_l_autre_option(self):
        """ROUGE avant : 6 panneaux imprimés (27 600,02) contre 14 facturés
        (38 800,06). La puissance suit ce qui est vendu : 14 × 710 W."""
        devis = self._devis('mono-reseau', CHAMPS + (
            (RESEAU, '1', '12000.00', ''),) + POSE)
        data = self._assert_pdf_egal_noyau(devis)
        self.assertTrue(data['sans_ok'])
        self.assertFalse(data['avec_ok'])
        self.assertEqual(data['puissance_kwc'], 9.94)

    def test_hybride_et_batterie_seuls(self):
        """ROUGE avant : 8 panneaux imprimés (55 600,03) contre 14 facturés
        (64 000,06). Batterie réelle ⇒ l'option unique est « Avec »."""
        devis = self._devis('mono-hybride', CHAMPS + (
            (HYBRIDE, '1', '17000.00', ''),
            (BATTERIE, '1', '16000.00', '')) + POSE)
        data = self._assert_pdf_egal_noyau(devis)
        self.assertTrue(data['avec_ok'])
        self.assertFalse(data['sans_ok'])

    def test_onduleur_de_l_option_avec_passe_en_optionnel(self):
        """La forme de DEV-202609-0006 : deux options composées, mais
        l'onduleur de l'option « avec » est une ligne OPTIONNELLE (add-on non
        activé). Le noyau facture TOUTES les lignes comptées, batteries
        comprises ; le PDF imprimait le seul panier « sans ». L'option unique
        porte des batteries réelles : elle s'étiquette « Avec »."""
        devis = self._devis('mono-optionnel', (
            (RESEAU, '1', '11666.67', 'sans'),
            ('Deye off-Grid 6kw', '1', '10000.00', '', True),
            (PANNEAU, '1', '1200.00', 'sans'),
            (PANNEAU, '7', '1200.00', 'avec'),
            (BATTERIE, '3', '11666.67', 'avec'),
            ('Installation', '1', '2250.00', 'sans'),
            ('Installation', '1', '3750.00', 'avec')),
            scenario='Avec batterie')
        data = self._assert_pdf_egal_noyau(devis)
        self.assertTrue(data['avec_ok'])
        self.assertFalse(data['sans_ok'])
        # L'add-on non activé reste HORS du document et hors des totaux.
        self.assertNotIn('Deye off-Grid 6kw',
                         [it['designation'] for it in data['avec_items']])

    def test_z1_hybride_seul_reste_tel_quel(self):
        """GARDE — Z1 imprimait déjà toutes les lignes (et le noyau les
        facturait) : 14 panneaux, 9,94 kWc, étiquette « Sans »."""
        devis = self._devis('mono-z1', CHAMPS + (
            (HYBRIDE, '1', '17000.00', ''),) + POSE)
        data = self._assert_pdf_egal_noyau(devis)
        self.assertEqual(data['puissance_kwc'], 9.94)
        self.assertTrue(data['sans_ok'])


class AvertissementInterneTests(_Base):
    """Le vendeur est prévenu de la contradiction — en INTERNE seulement."""

    def test_la_contradiction_est_nommee(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('mono-avert', CHAMPS + (
            (RESEAU, '1', '12000.00', ''),) + POSE)
        avertissements = build_quote_data(devis)['avertissements_internes']
        self.assertTrue(
            any('variant' in a and 'option unique' in a
                for a in avertissements), avertissements)

    def test_aucun_avertissement_sans_etiquette(self):
        """GARDE — un devis mono-option ordinaire (aucune ligne variantée)
        n'est ni recomposé ni signalé."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('mono-sans-etiquette', (
            (PANNEAU, '14', '1166.67', ''),
            (RESEAU, '1', '12000.00', '')) + POSE, scenario=None)
        avertissements = build_quote_data(devis)['avertissements_internes']
        self.assertFalse(any('variant' in a for a in avertissements),
                         avertissements)


class DeuxOptionsTemoinTests(_Base):
    """GARDE — un vrai devis à deux options garde ses deux paniers."""

    def test_chaque_option_garde_ses_propres_panneaux(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('deux-temoin', CHAMPS + (
            (RESEAU, '1', '12000.00', ''),
            (HYBRIDE, '1', '17000.00', ''),
            (BATTERIE, '1', '16000.00', '')) + POSE)
        data = build_quote_data(devis)
        self.assertTrue(data['deux_options'])
        self.assertEqual(data['nb_panneaux_sans'], 6)
        self.assertEqual(data['nb_panneaux_avec'], 8)
        self.assertFalse(any('variant' in a and 'option unique' in a
                             for a in data['avertissements_internes']))
