"""AUD108 — les CINQ PDF d'argent legacy ont enfin leurs garde-fous.

``docs/invariants.md`` ancrait TVA-CHAIN, TOTALS-RECONCILE et
NO-PRIX-ACHAT-CLIENT-FACING sur ``test_quote_engine_formats.py``, c'est-à-dire
UNIQUEMENT le moteur devis premium. Le PDF facture, le PDF avoir, le PDF note
de débit, le relevé de compte client et la quittance — tous client-facing et
explicitement conservés en legacy par la règle #4 — n'avaient AUCUN test
équivalent. C'est exactement ce trou qui a laissé passer AUD105 (la remise
globale décomptée deux fois sur le document le plus imprimé) sans qu'aucun gate
CI ne bronche pendant toute la vie du document.

Deux invariants, adossés à des tests de RENDU (on lit le HTML produit, jamais
le modèle) :

  (a) TOTALS-RECONCILE-LEGACY-PDF — ``Sous-total − Remise + Σ TVA == Total TTC``
      au centime, sur un document à remise globale ET taux mixtes (10/20) ;
      pour le relevé et la quittance, dont la chaîne est un solde et non une
      TVA, c'est la même exigence transposée : ``facturé − payé − avoirs ==
      solde dû`` et ``montant réglé + solde restant == TTC de la facture``.
  (b) NO-PRIX-ACHAT-LEGACY-PDF — ``Produit.prix_achat`` (indicateur de marge
      GÉNÉRATEUR-ONLY) n'apparaît dans AUCUN des cinq documents. La protection
      existait DE FAIT (les gabarits n'utilisent que designation / quantite /
      prix_unitaire / remise) ; rien ne l'empêchait de disparaître au prochain
      commit.

GOLDENS. Chaque document porte ses valeurs ATTENDUES en dur, dérivées à la main
du scénario chiffré (20 000 HT brut, remise 15 %, taux mixtes 10/20) — un
golden lisible en revue, plutôt qu'un instantané HTML complet qui casserait au
premier changement de CSS sans rien prouver de plus sur l'argent.
"""
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Avoir, Facture, LigneAvoir, LigneFacture, LigneNoteDebit, NoteDebit,
    Paiement,
)
from apps.ventes.utils.pdf import _company_context, _render_html
from authentication.models import Company

User = get_user_model()
_CTR = [0]

#: Le prix d'achat semé dans le catalogue — il ne doit JAMAIS être imprimé.
PRIX_ACHAT_SENTINELLE = Decimal('7777.77')


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _montant(texte):
    brut = (texte.replace('MAD', '').replace('−', '-')
            .replace(' ', '').replace('\xa0', '')
            .replace(' ', '').strip())
    return Decimal(brut)


def _lignes_totaux(html):
    """{libellé: Decimal} du bloc « Totaux » du document RENDU."""
    bloc = html.split('<div class="totaux">', 1)[1]
    bloc = bloc.split('<div class="footer"', 1)[0]
    bloc = bloc.split('<!-- XFAC12', 1)[0]
    return {
        lib.strip(): _montant(val)
        for lib, val in re.findall(
            r'<span>([^<]*)</span>\s*<span>([^<]*)</span>', bloc)
        if 'MAD' in val
    }


def _chaine_reconcilie(valeurs):
    """``Sous-total − Remise + Σ TVA == Total TTC`` (la remise est déjà
    négative dans le document rendu)."""
    sous_total = next(v for lib, v in valeurs.items() if 'ous-total' in lib)
    remise = next((v for lib, v in valeurs.items() if 'emise globale' in lib),
                  Decimal('0'))
    tva = sum((v for lib, v in valeurs.items() if lib.startswith('TVA')),
              Decimal('0'))
    ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
    return sous_total, remise, tva, ttc


class _BaseDocumentsLegacy(TestCase):
    """Scénario commun : 20 000 HT brut à taux MIXTES, remise globale 15 %.

    Panneaux 10 000 à 10 % + onduleur 10 000 à 20 %. HT net 17 000
    (8 500 + 8 500), TVA 850 + 1 700 = 2 550, TTC 19 550.
    """

    GOLDEN_HT_BRUT = Decimal('20000.00')
    GOLDEN_REMISE = Decimal('-3000.00')
    GOLDEN_TVA = Decimal('2550.00')
    GOLDEN_TTC = Decimal('19550.00')

    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD108 Co', slug=f'aud108-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud108_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD108', prenom='Client',
            telephone='+212600000109')
        # prix_achat SEMÉ : il doit rester invisible sur les cinq documents.
        self.panneaux = Produit.objects.create(
            company=self.company, nom='Panneaux', sku=f'AUD108P-{_nxt()}',
            prix_vente=Decimal('10000'), prix_achat=PRIX_ACHAT_SENTINELLE,
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AUD108O-{_nxt()}',
            prix_vente=Decimal('10000'), prix_achat=PRIX_ACHAT_SENTINELLE,
            quantite_stock=100)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD108-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneaux,
            designation='Panneaux', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), taux_tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.onduleur,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), taux_tva=Decimal('20.00'))

    def _ctx(self):
        return _company_context(company=self.company)

    def _rendu_facture(self):
        ctx = self._ctx()
        ctx['facture'] = self.facture
        return _render_html('facture.html', ctx)

    def _avoir(self):
        avoir = Avoir.objects.create(
            company=self.company, reference=f'AV-AUD108-{_nxt()}',
            facture=self.facture, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'),
            remise_globale=self.facture.remise_globale)
        for ligne in self.facture.lignes.all():
            LigneAvoir.objects.create(
                avoir=avoir, produit=ligne.produit,
                designation=ligne.designation, quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire, remise=ligne.remise,
                taux_tva=ligne.taux_tva)
        return avoir

    def _rendu_avoir(self):
        ctx = self._ctx()
        ctx['avoir'] = self._avoir()
        return _render_html('avoir.html', ctx)

    def _note_debit(self):
        note = NoteDebit.objects.create(
            company=self.company, reference=f'ND-AUD108-{_nxt()}',
            facture=self.facture, client=self.client_obj,
            statut=NoteDebit.Statut.EMISE, taux_tva=Decimal('20.00'),
            remise_globale=self.facture.remise_globale)
        for ligne in self.facture.lignes.all():
            LigneNoteDebit.objects.create(
                note_debit=note, produit=ligne.produit,
                designation=ligne.designation, quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire, remise=ligne.remise,
                taux_tva=ligne.taux_tva)
        return note

    def _rendu_note_debit(self):
        ctx = self._ctx()
        ctx['note_debit'] = self._note_debit()
        return _render_html('note_debit.html', ctx)

    def _rendu_releve(self):
        from apps.ventes.recouvrement import _releve_data
        ctx = self._ctx()
        ctx['releve'] = _releve_data(self.client_obj)
        return _render_html('releve.html', ctx)

    def _paiement(self):
        return Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('10000'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.VIREMENT)

    def _rendu_recu(self, paiement=None):
        from apps.ventes.utils.nombre_lettres import montant_en_lettres
        paiement = paiement or self._paiement()
        ctx = self._ctx()
        ctx['paiement'] = paiement
        ctx['client_nom'] = 'AUD108 Client'
        ctx['facture_reference'] = self.facture.reference
        ctx['affectations'] = []
        ctx['solde_restant'] = self.facture.montant_du
        ctx['montant_lettres'] = montant_en_lettres(paiement.montant)
        return _render_html('recu.html', ctx)


class TestChaineTotauxPdfFacture(_BaseDocumentsLegacy):
    """Invariant (a) — PDF FACTURE."""

    def test_totaux_reconcilient_au_centime(self):
        valeurs = _lignes_totaux(self._rendu_facture())
        sous_total, remise, tva, ttc = _chaine_reconcilie(valeurs)
        self.assertEqual(sous_total, self.GOLDEN_HT_BRUT)
        self.assertEqual(remise, self.GOLDEN_REMISE)
        self.assertEqual(tva, self.GOLDEN_TVA)
        self.assertEqual(ttc, self.GOLDEN_TTC)
        self.assertEqual(sous_total + remise + tva, ttc)


class TestChaineTotauxPdfAvoir(_BaseDocumentsLegacy):
    """Invariant (a) — PDF AVOIR."""

    def test_totaux_reconcilient_au_centime(self):
        valeurs = _lignes_totaux(self._rendu_avoir())
        sous_total, remise, tva, ttc = _chaine_reconcilie(valeurs)
        self.assertEqual(sous_total, self.GOLDEN_HT_BRUT)
        self.assertEqual(remise, self.GOLDEN_REMISE)
        self.assertEqual(tva, self.GOLDEN_TVA)
        self.assertEqual(ttc, self.GOLDEN_TTC)
        self.assertEqual(sous_total + remise + tva, ttc)


class TestChaineTotauxPdfNoteDebit(_BaseDocumentsLegacy):
    """Invariant (a) — PDF NOTE DE DÉBIT."""

    def test_totaux_reconcilient_au_centime(self):
        valeurs = _lignes_totaux(self._rendu_note_debit())
        sous_total, remise, tva, ttc = _chaine_reconcilie(valeurs)
        self.assertEqual(sous_total, self.GOLDEN_HT_BRUT)
        self.assertEqual(remise, self.GOLDEN_REMISE)
        self.assertEqual(tva, self.GOLDEN_TVA)
        self.assertEqual(ttc, self.GOLDEN_TTC)
        self.assertEqual(sous_total + remise + tva, ttc)


class TestChaineSoldesReleveClient(_BaseDocumentsLegacy):
    """Invariant (a) transposé — RELEVÉ DE COMPTE CLIENT."""

    def test_soldes_reconcilient_au_centime(self):
        self._paiement()
        valeurs = _lignes_totaux(self._rendu_releve())
        facture = next(v for lib, v in valeurs.items() if 'facturé' in lib)
        paye = next(v for lib, v in valeurs.items() if 'payé' in lib)
        avoirs = next(v for lib, v in valeurs.items() if 'avoirs' in lib)
        du = next(v for lib, v in valeurs.items() if 'dû' in lib)
        self.assertEqual(facture, self.GOLDEN_TTC)
        self.assertEqual(paye, Decimal('10000.00'))
        self.assertEqual(avoirs, Decimal('0.00'))
        self.assertEqual(facture - paye - avoirs, du)


class TestChaineSoldeQuittance(_BaseDocumentsLegacy):
    """Invariant (a) transposé — QUITTANCE (reçu de paiement)."""

    def test_montant_regle_plus_solde_restant_egale_le_ttc(self):
        paiement = self._paiement()
        html = self._rendu_recu(paiement)
        montants = [
            _montant(m) for m in
            re.findall(r'>\s*([\d\s., \xa0]+)\s*MAD\s*<', html)]
        self.assertIn(Decimal('10000.00'), montants)
        self.assertIn(self.facture.montant_du, montants)
        self.assertEqual(
            paiement.montant + self.facture.montant_du, self.GOLDEN_TTC)


class TestAucunPrixAchatDansLesCinqDocuments(_BaseDocumentsLegacy):
    """Invariant (b) — le prix d'achat ne fuit sur AUCUN document client."""

    def _sentinelles(self):
        # Toutes les écritures plausibles du prix d'achat semé.
        return ('7777.77', '7777,77', '7 777.77', '7777')

    def _assert_absent(self, html, document):
        for motif in self._sentinelles():
            self.assertNotIn(
                motif, html,
                f'Le prix d\'achat fuit sur le document {document} '
                f'(motif « {motif} ») — indicateur de marge '
                f'GÉNÉRATEUR-ONLY, jamais client-facing.')

    def test_pdf_facture(self):
        self._assert_absent(self._rendu_facture(), 'facture')

    def test_pdf_avoir(self):
        self._assert_absent(self._rendu_avoir(), 'avoir')

    def test_pdf_note_debit(self):
        self._assert_absent(self._rendu_note_debit(), 'note de débit')

    def test_releve_client(self):
        self._paiement()
        self._assert_absent(self._rendu_releve(), 'relevé de compte')

    def test_quittance(self):
        self._assert_absent(self._rendu_recu(), 'quittance')
