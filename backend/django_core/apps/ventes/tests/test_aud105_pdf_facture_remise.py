"""AUD105 — le PDF facture ne décompte plus la remise globale DEUX fois.

``templates/pdf/facture.html`` imprimait « Sous-total HT » = ``facture.total_ht``
puis « Remise globale (X %) » = ``total_ht × remise / 100``. Or depuis QX1
``Facture.total_ht`` EST le HT NET dès que ``remise_globale > 0`` : le document
CLIENT affichait un net étiqueté « Sous-total » et lui appliquait le
pourcentage une SECONDE fois. Le correctif QX1/QX2 avait été appliqué partout
ailleurs (PDF bon de commande, export UBL) — seul le document le plus imprimé
avait été oublié, et aucun gate CI ne l'a vu.

Scénario chiffré de la fiche : remise 15 % sur 20 000 HT brut, TVA 20 %.
Le client recevait « Sous-total 17 000 − Remise 2 550 », qui ne retombait sur
aucun total de la page.
"""
import re
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.utils.pdf import _company_context, _render_html
from authentication.models import Company

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def valeurs_totaux(html):
    """Les lignes du bloc « Totaux » du document rendu : [(libellé, valeur)].

    On lit le DOCUMENT RENDU, jamais le modèle : c'est ce que reçoit le client
    qui doit se réconcilier."""
    bloc = html.split('<div class="totaux">', 1)[1]
    bloc = bloc.split('<!-- XFAC12', 1)[0]
    return re.findall(
        r'<span>([^<]*)</span>\s*<span>([^<]*)</span>', bloc)


def montant(texte):
    """« −3 000.00 MAD » → Decimal('-3000.00 »). Tolère l'espace fine."""
    brut = (texte.replace('MAD', '')
            .replace('−', '-').replace(' ', '')
            .replace(' ', '').replace(' ', '').strip())
    return Decimal(brut)


class TestPdfFactureRemiseGlobale(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD105 Co', slug=f'aud105-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD105', prenom='Client',
            telephone='+212600000106')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'AUD105-{_nxt()}',
            prix_vente=Decimal('20000'), quantite_stock=10)
        # 20 000 HT brut, remise globale 15 %, TVA 20 %.
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD105-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('20000'),
            taux_tva=Decimal('20.00'))

    def _rendu(self, facture=None):
        ctx = _company_context(company=self.company)
        ctx['facture'] = facture or self.facture
        return _render_html('facture.html', ctx)

    def test_chiffres_du_scenario(self):
        lignes = valeurs_totaux(self._rendu())
        valeurs = {lib: montant(val) for lib, val in lignes}
        sous_total = next(v for lib, v in valeurs.items()
                          if 'ous-total' in lib)
        remise = next(v for lib, v in valeurs.items() if 'emise' in lib)
        ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
        tva = [v for lib, v in valeurs.items() if lib.startswith('TVA')]
        self.assertEqual(sous_total, Decimal('20000.00'))
        self.assertEqual(remise, Decimal('-3000.00'))
        self.assertEqual(sum(tva), Decimal('3400.00'))
        self.assertEqual(ttc, Decimal('20400.00'))

    def test_la_chaine_imprimee_se_reconcilie_au_centime(self):
        lignes = valeurs_totaux(self._rendu())
        valeurs = {lib: montant(val) for lib, val in lignes}
        sous_total = next(v for lib, v in valeurs.items()
                          if 'ous-total' in lib)
        remise = next(v for lib, v in valeurs.items() if 'emise' in lib)
        ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
        tva = sum(v for lib, v in valeurs.items() if lib.startswith('TVA'))
        # ``remise`` est déjà NÉGATIVE dans le document (« −3 000,00 »).
        self.assertEqual(sous_total + remise + tva, ttc)

    def test_taux_mixtes_se_reconcilient_aussi(self):
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'AUD105P-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=100)
        LigneFacture.objects.create(
            facture=self.facture, produit=panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10.00'))
        valeurs = {lib: montant(val)
                   for lib, val in valeurs_totaux(self._rendu())}
        sous_total = next(v for lib, v in valeurs.items()
                          if 'ous-total' in lib)
        remise = next(v for lib, v in valeurs.items() if 'emise' in lib)
        ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
        tva = sum(v for lib, v in valeurs.items() if lib.startswith('TVA'))
        self.assertEqual(sous_total, Decimal('30000.00'))
        self.assertEqual(sous_total + remise + tva, ttc)

    def test_sans_remise_le_document_est_inchange(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD105-N{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('20000'),
            taux_tva=Decimal('20.00'))
        valeurs = {lib: montant(val)
                   for lib, val in valeurs_totaux(self._rendu(facture))}
        self.assertEqual(
            next(v for lib, v in valeurs.items() if 'ous-total' in lib),
            Decimal('20000.00'))
        self.assertFalse([lib for lib in valeurs if 'emise' in lib])
        self.assertEqual(
            next(v for lib, v in valeurs.items() if 'TTC' in lib),
            Decimal('24000.00'))

    def test_facture_de_tranche_a_montants_figes_inchangee(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD105-T{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'),
            montant_ht=Decimal('5100'), montant_tva=Decimal('1020'),
            montant_ttc=Decimal('6120'))
        valeurs = {lib: montant(val)
                   for lib, val in valeurs_totaux(self._rendu(facture))}
        # Montants FIGÉS : `_remise_globale_active` est faux, aucune ligne de
        # remise n'est imprimée et le sous-total est le HT figé.
        self.assertEqual(
            next(v for lib, v in valeurs.items() if 'ous-total' in lib),
            Decimal('5100.00'))
        self.assertFalse([lib for lib in valeurs if 'emise' in lib])
        self.assertEqual(
            next(v for lib, v in valeurs.items() if 'TTC' in lib),
            Decimal('6120.00'))
