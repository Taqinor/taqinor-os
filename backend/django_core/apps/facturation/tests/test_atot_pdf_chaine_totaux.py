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
from django.test import TestCase

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


@patch('apps.ventes.utils.pdf._download', return_value=None)
class RemiseNegocieeTests(TestCase):
    """VNT71 — la facture COMPLÈTE d'un avenant négocié (388 : V1 acceptée
    54 500 → V2 acceptée 49 000 par remise 10 % + arrondi 65,82) imprime
    « Remise négociée −4624.35 MAD », montant seul, sans « (10 %) » ; la
    chaîne reste juste (Sous-total − Remise − Arrondi = Total HT, Total HT
    + TVA = 49000.00). Première vente, avoir et macro par défaut : ligne
    « Remise globale (x %) » d'hier, octet pour octet."""

    def setUp(self):
        from apps.ventes.models import Devis
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = creer_devis_388(self.company, self.user, self.client_obj,
                                  'DEV-VNT71-V1', remise_globale=Decimal('0'))
        self.v2 = creer_devis_388(self.company, self.user, self.client_obj,
                                  'DEV-VNT71-V2', version=2,
                                  version_parent=self.v1)
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2)

    def _facture_complete(self, devis, reference):
        from apps.ventes.domain.facturation_ops import (
            copier_devis_sur_facture)
        facture = Facture.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            reference=reference, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        copier_devis_sur_facture(facture, devis)
        return Facture.objects.get(pk=facture.pk)

    def _texte(self, generer, pk):
        patcheur, boite = _capturer_pdf()
        with patcheur:
            generer(pk)
        return _texte_pdf(boite['pdf'])

    def test_avenant_negocie_facture_complete(self, _dl):
        from apps.ventes.selectors import predecesseur_accepte
        from apps.ventes.utils.pdf import generate_facture_pdf
        self.assertEqual(predecesseur_accepte(self.v2).pk, self.v1.pk)
        facture = self._facture_complete(self.v2, 'FAC-VNT71-0001')
        texte = self._texte(generate_facture_pdf, facture.pk)
        self.assertRegex(texte, r'Remise négociée [−-] ?4624\.35 MAD')
        self.assertNotIn('Remise globale', texte)
        self.assertNotIn('Remise négociée (', texte)
        motif = (r'Sous-total HT ' + _N + r' MAD Remise négociée [−-] ?' + _N
                 + r' MAD Arrondi commercial [−-] ?' + _N + r' MAD Total HT '
                 + _N + r' MAD(.*?)Total TTC ' + _N + r' MAD')
        trouve = re.search(motif, texte[texte.rfind('Sous-total HT '):])
        self.assertIsNotNone(trouve, texte[-1500:])
        sous_total, remise, arrondi, total_ht = (
            Decimal(x) for x in trouve.groups()[:4])
        tva = sum((Decimal(x) for x in re.findall(
            r'TVA \([0-9.]+%\) ' + _N + r' MAD', trouve.group(5))),
            Decimal('0'))
        ttc = Decimal(trouve.group(6))
        self.assertEqual((sous_total, remise, arrondi, total_ht),
                         (Decimal('46243.50'), Decimal('4624.35'),
                          Decimal('65.82'), Decimal('41553.33')))
        self.assertEqual(sous_total - remise - arrondi, total_ht)
        self.assertEqual(total_ht + tva, ttc)
        self.assertEqual(ttc, Decimal('49000.00'))

    def test_premiere_vente_et_avoir_inchanges(self, _dl):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        from apps.ventes.utils.pdf import (
            generate_avoir_pdf, generate_facture_pdf)
        seul = creer_devis_388(self.company, self.user, self.client_obj,
                               'DEV-VNT71-SEUL')
        premiere = self._facture_complete(seul, 'FAC-VNT71-0002')
        texte = self._texte(generate_facture_pdf, premiere.pk)
        self.assertRegex(
            texte, r'Remise globale \(10\.00 ?%\) [−-] ?4624\.35 MAD')
        self.assertNotIn('Remise négociée', texte)
        # L'avoir de la facture d'avenant garde sa ligne d'hier.
        facture = self._facture_complete(self.v2, 'FAC-VNT71-0003')
        avoir = Avoir.objects.create(
            company=self.company, client=self.client_obj, facture=facture,
            reference='AV-VNT71-0001', taux_tva=Decimal('20.00'),
            remise_globale=facture.remise_globale)
        for ligne in facture.lignes.all():
            LigneAvoir.objects.create(
                avoir=avoir, produit=ligne.produit,
                designation=ligne.designation, quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire, remise=ligne.remise,
                taux_tva=ligne.taux_tva)
        texte_avoir = self._texte(generate_avoir_pdf, avoir.pk)
        self.assertIn('Remise globale (10.00%)', texte_avoir)
        self.assertNotIn('Remise négociée', texte_avoir)

    def test_macro_par_defaut_octet_identique(self, _dl):
        from django.template import engines
        moteur = engines['jinja2']
        t = {'ht_brut': Decimal('100'), 'remise': Decimal('10'),
             'arrondi': Decimal('0'), 'ht_net': Decimal('90'),
             'tva_par_taux': [], 'ttc': Decimal('90')}
        lib = {'sous_total': 'Sous-total HT',
               'remise_globale': 'Remise globale',
               'remise_negociee': 'Remise négociée', 'arrondi': 'Arrondi',
               'total_ht': 'Total HT', 'tva': 'TVA', 'total_ttc': 'Total TTC',
               'base_ht': 'Base HT'}
        entete = "{% from '_chaine_totaux.html' import chaine_totaux %}"

        def rendu(appel):
            return moteur.from_string(entete + appel).render(
                {'t': t, 'lib': lib})

        defaut = rendu('{{ chaine_totaux(t, 10, lib) }}')
        self.assertEqual(defaut, rendu(
            '{{ chaine_totaux(t, 10, lib, remise_negociee=False) }}'))
        self.assertIn('<span>Remise globale (10%)</span>', defaut)
        negociee = rendu(
            '{{ chaine_totaux(t, 10, lib, remise_negociee=True) }}')
        self.assertIn('<span>Remise négociée</span>', negociee)
        self.assertEqual(
            negociee.replace('Remise négociée', 'Remise globale (10%)'),
            defaut)
