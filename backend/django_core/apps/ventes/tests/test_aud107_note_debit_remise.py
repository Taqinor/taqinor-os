"""AUD107 — la note de débit honore enfin la remise globale.

Quand l'appelant ne fournit pas de ``lignes`` et que la facture source en a,
``creer_note_debit`` copie 1:1 produit, désignation, quantité, prix unitaire,
remise DE LIGNE et taux TVA — jamais la remise GLOBALE du document. ``NoteDebit``
n'avait aucun champ ``remise_globale`` et sa propriété ``total_ht`` était une
simple somme des lignes. Seul le chemin de repli « facture SANS lignes »
utilisait la propriété remise-aware de la facture ; le chemin normal, qui est le
cas courant, ne le faisait jamais.

C'est le miroir exact du défaut de l'Avoir (AUD106) : une pénalité de retard
adossée à une facture remisée à 15 % majorait le client sur le montant NON
remisé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, NoteDebit
from apps.ventes.tests.test_aud105_pdf_facture_remise import montant
from apps.ventes.utils.pdf import _company_context, _render_html
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _valeurs_totaux(html):
    import re
    bloc = html.split('<div class="totaux">', 1)[1]
    bloc = bloc.split('<div class="footer"', 1)[0]
    return {
        lib: montant(val)
        for lib, val in re.findall(
            r'<span>([^<]*)</span>\s*<span>([^<]*)</span>', bloc)
        if 'MAD' in val
    }


class TestNoteDebitRemiseGlobale(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role

        self.company = Company.objects.create(
            nom='AUD107 Co', slug=f'aud107-{_nxt()}')
        role = Role.objects.create(
            company=self.company, nom=f'Admin {_nxt()}',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username=f'aud107_{_nxt()}', password='x', role=role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD107', prenom='Client',
            telephone='+212600000108')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD107-{_nxt()}',
            prix_vente=Decimal('20000'), quantite_stock=50)
        # 20 000 HT brut, remise globale 15 %, TVA 20 % → 17 000 HT net.
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD107-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('20000'),
            taux_tva=Decimal('20.00'))

    def _creer(self, payload=None):
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'creer-note-debit/',
            payload or {'motif': 'Pénalités de retard'}, format='json')
        return resp

    def test_repli_facture_entiere_applique_la_remise(self):
        resp = self._creer()
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(pk=resp.data['id'])
        self.assertEqual(note.remise_globale, Decimal('15.00'))
        self.assertEqual(note.total_ht, Decimal('17000.00'))
        self.assertEqual(note.total_ttc, Decimal('20400.00'))

    def test_le_pdf_note_debit_se_reconcilie_au_centime(self):
        resp = self._creer()
        note = NoteDebit.objects.get(pk=resp.data['id'])
        ctx = _company_context(company=self.company)
        ctx['note_debit'] = note
        valeurs = _valeurs_totaux(_render_html('note_debit.html', ctx))
        sous_total = next(v for lib, v in valeurs.items()
                          if 'Sous-total' in lib)
        remise = next(v for lib, v in valeurs.items() if 'Remise' in lib)
        tva = sum(v for lib, v in valeurs.items() if lib.startswith('TVA'))
        ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
        self.assertEqual(sous_total, Decimal('20000.00'))
        self.assertEqual(remise, Decimal('-3000.00'))
        self.assertEqual(sous_total + remise + tva, ttc)
        self.assertEqual(ttc, Decimal('20400.00'))

    def test_note_sans_remise_reste_inchangee(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD107-N{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('20000'),
            taux_tva=Decimal('20.00'))
        resp = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-note-debit/',
            {'motif': 'Complément'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(pk=resp.data['id'])
        self.assertEqual(note.remise_globale, Decimal('0'))
        self.assertEqual(note.total_ht, Decimal('20000.00'))
        self.assertEqual(note.total_ttc, Decimal('24000.00'))

    def test_le_mixin_est_partage_par_les_trois_documents(self):
        from apps.facturation.models import Avoir, Facture as FactureModel
        from apps.facturation.totaux import TotauxDocumentMixin

        for modele in (FactureModel, Avoir, NoteDebit):
            self.assertTrue(
                issubclass(modele, TotauxDocumentMixin),
                f'{modele.__name__} ne tire plus ses totaux du mixin unique.')
            for nom in ('total_ht', 'total_tva', 'tva_par_taux', 'total_ttc',
                        'totaux_affichage', '_remise_globale_active'):
                self.assertIs(getattr(modele, nom),
                              getattr(TotauxDocumentMixin, nom))
