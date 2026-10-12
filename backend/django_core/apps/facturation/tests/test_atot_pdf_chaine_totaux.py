# -*- coding: utf-8 -*-
"""ATOT11 — facture, avoir et note de débit impriment la chaîne COMPLÈTE
Sous-total HT → Remise → Arrondi → **Total HT** → TVA par taux → TTC, par
UNE macro Jinja partagée (``templates/pdf/_chaine_totaux.html``).

Constat C-ATOT-017 (sonde V2 TSORT-4) : sur une facture remisée, la base
nette ``ht_net`` n'apparaissait nulle part dans le texte du PDF — le lecteur
voyait « Sous-total − Remise » puis la TVA, sans la base sur laquelle la TVA
est calculée.

Scénario FAC-DEMO-0002 : une ligne 5 820,00 HT à 20 %, ``remise_globale = 5``
→ remise 291,00, Total HT 5 529,00, TVA 1 105,80, TTC 6 634,80.

Source réelle : ``utils/pdf.generate_*_pdf`` (rendu WeasyPrint réel), texte lu
par PyMuPDF ; seul l'upload MinIO (``_upload_pdf``) et le logo sont neutralisés.

Test-du-test : retirer la ligne Total HT de la macro ⇒ les trois tests
échouent.
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Avoir, Facture, LigneAvoir, LigneFacture, LigneNoteDebit, NoteDebit,
)
from authentication.models import Company

User = get_user_model()

_N = r'([0-9]+\.[0-9]{2})'


def _texte_pdf(octets):
    import fitz  # PyMuPDF
    with fitz.open(stream=octets, filetype='pdf') as doc:
        texte = '\n'.join(page.get_text() for page in doc)
    return re.sub(r'\s+', ' ', texte)


def _capturer_pdf():
    """Renvoie (patch, boîte) : la boîte reçoit les octets PDF uploadés."""
    boite = {}

    def _upload(pdf_bytes, key):
        boite['pdf'] = pdf_bytes

    return patch('apps.ventes.utils.pdf._upload_pdf', side_effect=_upload), boite


@patch('apps.ventes.utils.pdf._download', return_value=None)
class PdfChaineTotauxTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='atot11-co', defaults={'nom': 'ATOT11 Co'})
        self.user = User.objects.create_user(
            username='atot11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Chaine', prenom='ATOT11',
            telephone='+212600000011')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit solaire', prix_vente=Decimal('5820'),
            quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference='FAC-DEMO-0002', statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Kit solaire', quantite=Decimal('1'),
            prix_unitaire=Decimal('5820'), taux_tva=Decimal('20.00'))

    def _texte(self, generer, pk):
        patcheur, boite = _capturer_pdf()
        with patcheur:
            generer(pk)
        return _texte_pdf(boite['pdf'])

    def _verifier_chaine(self, texte, libelle_ttc):
        motif = (
            r'Sous-total HT[^0-9]*?' + _N + r' MAD'
            r'.*?Remise globale \([0-9.]+ ?%\) [−-] ?' + _N + r' MAD'
            r'.*?Total HT ' + _N + r' MAD'
            r'.*?TVA \([0-9.]+%\) ' + _N + r' MAD'
            r'.*?' + re.escape(libelle_ttc) + r' ' + _N + r' MAD')
        trouve = re.search(motif, texte)
        self.assertIsNotNone(trouve, texte[-1200:])
        sous_total, remise, total_ht, tva, ttc = (
            Decimal(x) for x in trouve.groups())
        self.assertEqual(sous_total, Decimal('5820.00'))
        self.assertEqual(remise, Decimal('291.00'))
        self.assertEqual(total_ht, Decimal('5529.00'))
        # Sous-total − Remise − Arrondi (0) = Total HT ; Total HT + Σ TVA = TTC.
        self.assertEqual(sous_total - remise, total_ht)
        self.assertEqual(total_ht + tva, ttc)
        self.assertEqual(ttc, Decimal('6634.80'))
        self.assertIn('Total HT 5529.00 MAD', texte)

    def test_facture(self, _dl):
        from apps.ventes.utils.pdf import generate_facture_pdf
        texte = self._texte(generate_facture_pdf, self.facture.id)
        self._verifier_chaine(texte, 'Total TTC')
        # VNT35 — facture complète sans devis : aucun « Objet de la vente ».
        self.assertNotIn('Objet de la vente', texte)

    def test_avoir(self, _dl):
        from apps.ventes.utils.pdf import generate_avoir_pdf
        avoir = Avoir.objects.create(
            company=self.company, client=self.client_obj,
            facture=self.facture, reference='AV-DEMO-0002',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneAvoir.objects.create(
            avoir=avoir, produit=self.produit, designation='Kit solaire',
            quantite=Decimal('1'), prix_unitaire=Decimal('5820'),
            taux_tva=Decimal('20.00'))
        texte = self._texte(generate_avoir_pdf, avoir.id)
        self._verifier_chaine(texte, 'Total crédité TTC')

    def test_note_debit(self, _dl):
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        note = NoteDebit.objects.create(
            company=self.company, client=self.client_obj,
            facture=self.facture, reference='ND-DEMO-0002',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneNoteDebit.objects.create(
            note_debit=note, produit=self.produit, designation='Kit solaire',
            quantite=Decimal('1'), prix_unitaire=Decimal('5820'),
            taux_tva=Decimal('20.00'))
        texte = self._texte(generate_note_debit_pdf, note.id)
        self._verifier_chaine(texte, 'Total dû en supplément (TTC)')


@patch('apps.ventes.utils.pdf._download', return_value=None)
class ObjetDeLaVenteTests(TestCase):
    """VNT35 — facture de TRANCHE (sans ligne) : bloc « Objet de la vente »
    (matériel de l'option retenue + chaîne de prix du devis 388), figé à
    l'émission, vivant en brouillon ; jamais ``prix_achat`` ; la chaîne
    d'argent de la facture elle-même est inchangée (aucune ligne créée)."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        from apps.ventes.tests.test_echeancier_somme_total import (
            ECHEANCIER_LIBRE, creer_devis_388)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = creer_devis_388(self.company, self.user, self.client_obj,
                                  'DEV-VNT35-V1', ECHEANCIER_LIBRE)
        Produit.objects.filter(company=self.company).update(
            prix_achat=Decimal('7777.77'))
        Produit.objects.filter(company=self.company,
                               nom='Panneau 600 W').update(marque='SolarMarque')

    def _tranche(self, devis, reference, statut='brouillon'):
        from apps.ventes.tests.test_echeancier_somme_total import (
            VENT_ACOMPTE_15000, facture_tranche)
        return facture_tranche(devis, reference, 'acompte', '15000.00',
                               '12720.41', '2279.59', statut=statut,
                               ventilation=VENT_ACOMPTE_15000)

    def _texte(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        patcheur, boite = _capturer_pdf()
        with patcheur:
            generate_facture_pdf(facture.pk)
        return _texte_pdf(boite['pdf'])

    def _reviser(self):
        from apps.ventes.models import Devis
        from apps.ventes.tests._quote_engine_common import make_devis
        v2 = make_devis(self.company, self.user, self.client_obj,
                        [('Panneau 710 W', '10', '1200', '10'),
                         ('Onduleur + structure + pose', '1', '36643.50',
                          '20')],
                        remise_globale='10', reference='DEV-VNT35-V2')
        Devis.objects.filter(pk=v2.pk).update(
            statut='accepte', version=2, version_parent=self.v1)
        Devis.objects.filter(pk=self.v1.pk).update(is_active=False,
                                                   superseded_by=v2)
        return Devis.objects.get(pk=v2.pk)

    def test_golden_388_fige_a_l_emission(self, _dl):
        from apps.ventes.domain.facturation_ops import emettre_facture
        facture = self._tranche(self.v1, 'FAC-VNT35-0001')
        texte = self._texte(facture)
        self.assertIn('Objet de la vente', texte)
        self.assertIn('DEV-VNT35-V1', texte)
        for montant in ('46243.50', '4624.35', '65.82', '41553.33',
                        '49000.00'):
            self.assertIn(f'{montant} MAD', texte)
        self.assertIn('Panneau 600 W', texte)
        self.assertIn('SolarMarque', texte)
        self.assertNotIn('7777', texte)
        emettre_facture(facture, source='test_vnt35')
        facture.refresh_from_db()
        self.assertEqual(facture.objet_vente['total_ttc'], '49000.00')
        self.assertEqual(facture.objet_vente['devis_reference'],
                         'DEV-VNT35-V1')
        self.assertNotIn('7777', repr(facture.objet_vente))
        avant = self._texte(facture)
        v2 = self._reviser()
        apres = self._texte(facture)
        # L'émise garde la V1 (8 panneaux 600 W), jamais la V2 (10 × 710 W).
        for texte in (avant, apres):
            self.assertIn('Panneau 600 W', texte)
            self.assertNotIn('Panneau 710 W', texte)
            self.assertIn('46243.50 MAD', texte)
        # La facture elle-même : aucune ligne, argent et ventilation intacts.
        facture.refresh_from_db()
        self.assertEqual(facture.lignes.count(), 0)
        self.assertEqual(facture.total_ttc, Decimal('15000.00'))
        self.assertEqual(facture.ventilation_tva[0]['base_ht'], '2644.90')
        # Un brouillon suit la version qui fait foi (V2).
        brouillon = self._tranche(v2, 'FAC-VNT35-0002')
        texte_v2 = self._texte(brouillon)
        self.assertIn('Panneau 710 W', texte_v2)
        self.assertIn('DEV-VNT35-V2', texte_v2)
        self.assertIn('48643.50 MAD', texte_v2)
        self.assertNotIn('7777', texte_v2)


# ── VNT71 — « Remise négociée » sur la facture d'un avenant négocié ─────────

_LIB_CHAINE = {'sous_total': 'Sous-total HT', 'remise_globale': 'Remise globale',
               'remise_negociee': 'Remise négociée',
               'arrondi': 'Arrondi commercial', 'total_ht': 'Total HT',
               'tva': 'TVA', 'total_ttc': 'Total TTC', 'base_ht': 'Base HT'}
_T_388 = {'ht_brut': Decimal('46243.50'), 'remise': Decimal('4624.35'),
          'arrondi': Decimal('65.82'), 'ht_net': Decimal('41553.33'),
          'tva_par_taux': [
              {'taux': Decimal('10'), 'base_ht': Decimal('8640.00'),
               'montant': Decimal('864.00')},
              {'taux': Decimal('20'), 'base_ht': Decimal('32913.33'),
               'montant': Decimal('6582.67')}],
          'tva': Decimal('7446.67'), 'ttc': Decimal('49000.00')}


class ChaineMacroRemiseNegocieeTests(SimpleTestCase):
    """VNT71 — la macro partagée : sans ``remise_negociee`` (facture, avoir,
    ND, BC, pro-forma d'hier) le rendu est OCTET-IDENTIQUE à
    ``remise_negociee=False`` ; avec, seule la ligne de remise change de
    libellé (montant, sans « (x %) »)."""

    def _rendre(self, appel):
        from django.template import engines
        env = engines['jinja2'].env
        source = ("{% from '_chaine_totaux.html' import chaine_totaux %}"
                  '{{ ' + appel + ' }}')
        return env.from_string(source).render(t=_T_388, lib=_LIB_CHAINE)

    def test_defaut_octet_identique(self):
        for kw in ('', ', ventilation=True', ', tva_ventilee=False'):
            defaut = self._rendre('chaine_totaux(t, 10, lib' + kw + ')')
            faux = self._rendre(
                'chaine_totaux(t, 10, lib' + kw + ', remise_negociee=False)')
            self.assertEqual(defaut, faux)
            self.assertIn('Remise globale (10%)', defaut)
            self.assertNotIn('Remise négociée', defaut)

    def test_seul_le_libelle_change(self):
        defaut = self._rendre('chaine_totaux(t, 10, lib)')
        negociee = self._rendre(
            'chaine_totaux(t, 10, lib, remise_negociee=True)')
        self.assertIn('<span>Remise négociée</span>', negociee)
        self.assertNotIn('Remise globale', negociee)
        self.assertNotIn('Remise négociée (', negociee)
        self.assertEqual(
            negociee.replace('Remise négociée', 'Remise globale (10%)'),
            defaut)


@patch('apps.ventes.utils.pdf._download', return_value=None)
class RemiseNegocieeFactureTests(TestCase):
    """VNT71 — l'avenant négocié 54 500 → 49 000 (remise 10 % + arrondi
    65,82, ARRONDI-100) facturé COMPLET imprime « Remise négociée
    −4624.35 MAD » sans « (10 %) » ; la chaîne lue tient (Sous-total −
    Remise − Arrondi = Total HT ; Total HT + Σ TVA = 49000.00) ; une
    facture du même panier SANS prédécesseur accepté garde « Remise
    globale (10.00%) »."""

    def setUp(self):
        from apps.ventes.models import Devis
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        from apps.ventes.tests.test_echeancier_somme_total import (
            LIGNES_388, creer_devis_388)
        from apps.ventes.utils.options import option_totaux
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        v1 = make_devis(self.company, self.user, self.client_obj, LIGNES_388,
                        reference='DEV-VNT71-V1')
        self.assertEqual(Decimal(str(option_totaux(v1)['ttc'])),
                         Decimal('54500.00'))
        self.v2 = creer_devis_388(self.company, self.user, self.client_obj,
                                  'DEV-VNT71-V2', version=2,
                                  version_parent=v1)
        Devis.objects.filter(pk=v1.pk).update(
            statut='accepte', is_active=False, superseded_by=self.v2)

    def _facture(self, devis, reference):
        from apps.ventes.domain.facturation_ops import (
            copier_devis_sur_facture)
        facture = Facture.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            reference=reference, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        copier_devis_sur_facture(facture, devis)
        return Facture.objects.get(pk=facture.pk)

    def _texte(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        patcheur, boite = _capturer_pdf()
        with patcheur:
            generate_facture_pdf(facture.pk)
        return _texte_pdf(boite['pdf'])

    def test_avenant_negocie_facture_complet(self, _dl):
        from apps.facturation.tests.oracles_argent import (
            verifier_chaine_document)
        from apps.facturation.tests.test_atot_parite_pdf_argent import (
            figures_lues)
        facture = self._facture(self.v2, 'FAC-VNT71-0001')
        self.assertEqual(facture.total_ttc, Decimal('49000.00'))
        texte = self._texte(facture)
        self.assertRegex(texte, r'Remise négociée [−-] ?4624\.35 MAD')
        self.assertNotIn('Remise globale', texte)
        self.assertNotRegex(texte, r'Remise négociée \(')
        lues = figures_lues(texte, 'Sous-total HT', 'Total TTC')
        self.assertEqual(lues['ht_brut'], Decimal('46243.50'))
        self.assertEqual(lues['remise'], Decimal('4624.35'))
        self.assertEqual(lues['arrondi'], Decimal('65.82'))
        self.assertEqual(lues['ht_net'], Decimal('41553.33'))
        self.assertEqual(lues['ttc'], Decimal('49000.00'))
        self.assertTrue(verifier_chaine_document(None, figures=lues))

    def test_sans_predecesseur_accepte_remise_globale(self, _dl):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        seul = creer_devis_388(self.company, self.user, self.client_obj,
                               'DEV-VNT71-SEUL')
        texte = self._texte(self._facture(seul, 'FAC-VNT71-0002'))
        self.assertRegex(texte, r'Remise globale \(10\.00 ?%\) [−-] ?'
                                r'4624\.35 MAD')
        self.assertNotIn('Remise négociée', texte)
