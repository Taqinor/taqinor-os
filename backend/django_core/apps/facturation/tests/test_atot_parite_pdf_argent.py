# -*- coding: utf-8 -*-
"""ATOT16 (C-ATOT-016, C-ATOT-021) — parité « API ↔ PDF imprimé » des CINQ
documents d'argent legacy : facture, avoir, note de débit, bon de commande et
pro-forma.

Pour chaque document généré par les services réels (``utils/pdf.generate_*``,
rendu WeasyPrint réel), le texte est extrait par PyMuPDF ; chaque montant de
la chaîne imprimée — Sous-total, Remise, Arrondi, Total HT, TVA (par taux ou
une ligne), TTC — doit égaler, au centime :

  * la source serveur (``totaux_affichage`` pour facture / avoir / note de
    débit ; ``option_totaux`` pour BC / pro-forma) ;
  * l'API (``FactureSerializer``, ``AvoirSerializer``, ``NoteDebitSerializer``,
    ``BonCommandeSerializer`` ; ``Devis.total_ttc`` pour le pro-forma) ;

et l'oracle ``verifier_chaine_document`` (ATOT13) doit tenir sur les nombres
LUS (Sous-total − Remise − Arrondi = Total HT ; Total HT + Σ TVA = TTC).

Scénarios : mono-taux sans remise, taux MIXTES 10/20 avec remise globale,
palier d'arrondi 100. Une ÉNUMÉRATION des gabarits d'argent (ceux qui
importent la macro ``_chaine_totaux.html``) échoue si un gabarit n'est pas
couvert ici.

Test-du-test : retirer la ligne « Total HT » de la macro ⇒ la parité
facture (cas remisé) échoue ; ajouter un gabarit d'argent fictif important
la macro ⇒ ``test_tous_les_gabarits_d_argent_sont_couverts`` échoue.

Source réelle : seuls l'upload MinIO (``_upload_pdf``) et le logo
(``_download``) sont neutralisés.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_parite_pdf_argent"
"""
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.facturation.tests.oracles_argent import verifier_chaine_document

User = get_user_model()

ZERO = Decimal('0')
CENT = Decimal('0.01')

#: Gabarits d'argent couverts par cette parité (nom de fichier).
GABARITS_COUVERTS = frozenset({
    'facture.html', 'avoir.html', 'note_debit.html', 'bon_commande.html',
    'proforma.html',
})

#: Scénarios chiffrés : (désignation, quantité, P.U. HT, taux TVA).
SCENARIOS = {
    'mono_taux': {
        'lignes': [('Kit solaire', '1', '5820', '20')],
        'remise_globale': Decimal('0'),
    },
    'taux_mixtes_remise': {
        'lignes': [('Panneaux', '1', '10000', '10'),
                   ('Onduleur', '1', '10000', '20')],
        'remise_globale': Decimal('15'),
    },
    'palier_100': {
        'lignes': [('Kit PV', '1', '125047.50', '20')],
        'remise_globale': Decimal('0'),
        'arrondi_pas': 100,
    },
}

#: Libellés imprimés par document : (sous-total, TTC).
LIBELLES = {
    'facture': ('Sous-total HT', 'Total TTC'),
    'avoir': ('Sous-total HT crédité', 'Total crédité TTC'),
    'note_debit': ('Sous-total HT', 'Total dû en supplément (TTC)'),
    'bon_commande': ('Sous-total HT', 'Total TTC'),
    'proforma': ('Sous-total HT', 'Total TTC (indicatif)'),
}

_PAIRE = re.compile(r'\s*(.+?)\s+([−-])?\s?([0-9]+\.[0-9]{2}) MAD')
_TAUX = re.compile(r'\(([0-9]+(?:\.[0-9]+)?) ?%\)')


def _q(valeur):
    return Decimal(str(valeur if valeur is not None else 0)).quantize(
        CENT, rounding=ROUND_HALF_UP)


def _texte_pdf(octets):
    import fitz  # PyMuPDF (dépendance existante, requirements.txt)
    with fitz.open(stream=octets, filetype='pdf') as doc:
        texte = '\n'.join(page.get_text() for page in doc)
    return re.sub(r'\s+', ' ', texte)


def figures_lues(texte, lib_sous_total, lib_ttc):
    """Chaîne d'argent LUE dans le texte du PDF : ``{ht_brut, remise,
    arrondi, ht_net, tva_par_taux|tva, ttc, total_ht_imprime}``.

    Le bloc commence à la DERNIÈRE occurrence du libellé de sous-total (le
    tableau des lignes porte, lui aussi, une colonne « Total HT ») et
    s'arrête au TTC."""
    debut = texte.rfind(lib_sous_total + ' ')
    assert debut >= 0, f'« {lib_sous_total} » absent du PDF : {texte[-800:]}'
    lues = {'remise': ZERO, 'arrondi': ZERO, 'ttc': None}
    tva = []
    total_ht = None
    for m in _PAIRE.finditer(texte, debut):
        libelle, montant = m.group(1).strip(), Decimal(m.group(3))
        if libelle == lib_ttc:
            lues['ttc'] = montant
            break
        if libelle.startswith(lib_sous_total) and 'ht_brut' not in lues:
            lues['ht_brut'] = montant
        elif libelle.startswith('Remise globale'):
            lues['remise'] = montant
        elif libelle == 'Arrondi commercial':
            lues['arrondi'] = montant
        elif libelle == 'Total HT':
            total_ht = montant
        elif libelle.startswith('TVA'):
            taux = _TAUX.search(libelle)
            tva.append((Decimal(taux.group(1)) if taux else None, montant))
    assert lues['ttc'] is not None, f'« {lib_ttc} » absent : {texte[-800:]}'
    assert 'ht_brut' in lues, f'sous-total illisible : {texte[-800:]}'
    lues['total_ht_imprime'] = total_ht is not None
    # La macro n'imprime « Total HT » que s'il diffère du sous-total
    # (remise ou arrondi > 0) : absent, il VAUT le sous-total imprimé.
    lues['ht_net'] = total_ht if total_ht is not None else lues['ht_brut']
    if len(tva) == 1 and tva[0][0] is None:
        lues['tva'] = tva[0][1]
    else:
        lues['tva_par_taux'] = [{'taux': t, 'montant': mt} for t, mt in tva]
    return lues


def _capturer_upload():
    boite = {}

    def _upload(pdf_bytes, key):
        boite['pdf'] = pdf_bytes

    return patch('apps.ventes.utils.pdf._upload_pdf',
                 side_effect=_upload), boite


@patch('apps.ventes.utils.pdf._download', return_value=None)
class PariteDocumentsArgentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company

        self.company = Company.objects.create(
            nom='ATOT16 Co', slug='atot16-co')
        self.user = User.objects.create_user(
            username='atot16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Parite', prenom='ATOT16',
            email='atot16@example.invalid', telephone='+212600000016',
            adresse='Casablanca')
        self._n = 0

    # ── Fabrique des documents (services/modèles réels) ────────────────────

    def _suivant(self):
        self._n += 1
        return self._n

    def _produit(self, nom, prix):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'ATOT16-{self._suivant()}',
            prix_vente=Decimal(prix), quantite_stock=500)

    def _facture(self, scenario):
        from apps.ventes.models import Facture, LigneFacture
        sc = SCENARIOS[scenario]
        facture = Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference=f'FAC-ATOT16-{self._suivant():04d}',
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
            remise_globale=sc['remise_globale'],
            arrondi_pas=sc.get('arrondi_pas', 0))
        for desig, qte, pu, taux in sc['lignes']:
            LigneFacture.objects.create(
                facture=facture, produit=self._produit(desig, pu),
                designation=desig, quantite=Decimal(qte),
                prix_unitaire=Decimal(pu), taux_tva=Decimal(taux))
        return Facture.objects.get(pk=facture.pk)

    def _copie(self, modele, modele_ligne, fk, prefixe, facture):
        champs = {}
        if any(f.name == 'arrondi_pas' for f in modele._meta.fields):
            champs['arrondi_pas'] = facture.arrondi_pas  # palier hérité
        doc = modele.objects.create(
            company=self.company, client=self.client_obj, facture=facture,
            reference=f'{prefixe}-ATOT16-{self._suivant():04d}',
            taux_tva=Decimal('20.00'),
            remise_globale=facture.remise_globale, **champs)
        for ligne in facture.lignes.all():
            modele_ligne.objects.create(**{
                fk: doc, 'produit': ligne.produit,
                'designation': ligne.designation, 'quantite': ligne.quantite,
                'prix_unitaire': ligne.prix_unitaire, 'remise': ligne.remise,
                'taux_tva': ligne.taux_tva})
        return modele.objects.get(pk=doc.pk)

    def _devis(self, scenario):
        from apps.ventes.models import Devis, LigneDevis
        sc = SCENARIOS[scenario]
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj,
            reference=f'DEV-ATOT16-{self._suivant():04d}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            remise_globale=sc['remise_globale'])
        for desig, qte, pu, taux in sc['lignes']:
            LigneDevis.objects.create(
                devis=devis, produit=self._produit(desig, pu),
                designation=desig, quantite=Decimal(qte),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                taux_tva=Decimal(taux))
        return Devis.objects.get(pk=devis.pk)

    def _pdf_stocke(self, generer, pk):
        patcheur, boite = _capturer_upload()
        with patcheur:
            generer(pk)
        return _texte_pdf(boite['pdf'])

    # ── Assertions de parité ───────────────────────────────────────────────

    def _parite_totaux(self, lues, attendu, api, contexte):
        """``lues`` (PDF) == ``attendu`` (totaux_affichage) == ``api``."""
        self.assertEqual(lues['ht_brut'], _q(attendu['ht_brut']), contexte)
        self.assertEqual(lues['remise'], _q(attendu['remise']), contexte)
        self.assertEqual(lues['arrondi'], _q(attendu['arrondi']), contexte)
        self.assertEqual(lues['ht_net'], _q(attendu['ht_net']), contexte)
        self.assertEqual(lues['ttc'], _q(attendu['ttc']), contexte)
        if _q(attendu['remise']) > 0 or _q(attendu['arrondi']) > 0:
            self.assertTrue(
                lues['total_ht_imprime'],
                f'{contexte} : « Total HT » (base nette) absent du PDF '
                'alors que remise/arrondi > 0.')
        par_taux_lu = {b['taux']: b['montant']
                       for b in lues.get('tva_par_taux', [])}
        par_taux_attendu = {Decimal(str(b['taux'])): _q(b['montant'])
                            for b in attendu['tva_par_taux']}
        self.assertEqual(par_taux_lu, par_taux_attendu, contexte)
        # API (sérialiseur réel) == PDF.
        self.assertEqual(_q(api['total_ht']), lues['ht_net'], contexte)
        self.assertEqual(_q(api['total_ttc']), lues['ttc'], contexte)
        self.assertEqual(_q(api['total_tva']), sum(par_taux_lu.values(), ZERO),
                         contexte)
        if 'tva_par_taux' in api:
            par_taux_api = {Decimal(str(b['taux'])): _q(b['montant'])
                            for b in api['tva_par_taux']}
            self.assertEqual(par_taux_api, par_taux_lu, contexte)
        verifier_chaine_document(None, figures=lues)

    def _parite_option(self, lues, totaux, contexte):
        """BC / pro-forma : ``lues`` == ``option_totaux`` (une ligne TVA)."""
        self.assertEqual(lues['ht_brut'],
                         _q(totaux.get('ht_brut', totaux['ht'])), contexte)
        self.assertEqual(lues['remise'], _q(totaux.get('remise')), contexte)
        self.assertEqual(lues['arrondi'], _q(totaux.get('arrondi')), contexte)
        self.assertEqual(lues['ht_net'], _q(totaux['ht']), contexte)
        self.assertEqual(lues['tva'], _q(totaux['tva']), contexte)
        self.assertEqual(lues['ttc'], _q(totaux['ttc']), contexte)
        if _q(totaux.get('remise')) > 0 or _q(totaux.get('arrondi')) > 0:
            self.assertTrue(lues['total_ht_imprime'],
                            f'{contexte} : « Total HT » absent du PDF.')
        verifier_chaine_document(None, figures=lues)

    # ── Facture / avoir / note de débit ───────────────────────────────────

    def test_facture(self, _dl):
        from apps.ventes.serializers_facturation import FactureSerializer
        from apps.ventes.utils.pdf import generate_facture_pdf
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                facture = self._facture(scenario)
                texte = self._pdf_stocke(generate_facture_pdf, facture.pk)
                lues = figures_lues(texte, *LIBELLES['facture'])
                facture.refresh_from_db()
                self._parite_totaux(
                    lues, facture.totaux_affichage,
                    FactureSerializer(facture).data, f'facture {scenario}')

    def test_avoir(self, _dl):
        from apps.ventes.models import Avoir, LigneAvoir
        from apps.ventes.serializers_facturation import AvoirSerializer
        from apps.ventes.utils.pdf import generate_avoir_pdf
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                avoir = self._copie(Avoir, LigneAvoir, 'avoir', 'AV',
                                    self._facture(scenario))
                texte = self._pdf_stocke(generate_avoir_pdf, avoir.pk)
                lues = figures_lues(texte, *LIBELLES['avoir'])
                avoir.refresh_from_db()
                self._parite_totaux(
                    lues, avoir.totaux_affichage,
                    AvoirSerializer(avoir).data, f'avoir {scenario}')

    def test_note_debit(self, _dl):
        from apps.ventes.models import LigneNoteDebit, NoteDebit
        from apps.ventes.serializers_facturation import NoteDebitSerializer
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                note = self._copie(NoteDebit, LigneNoteDebit, 'note_debit',
                                   'ND', self._facture(scenario))
                texte = self._pdf_stocke(generate_note_debit_pdf, note.pk)
                lues = figures_lues(texte, *LIBELLES['note_debit'])
                note.refresh_from_db()
                self._parite_totaux(
                    lues, note.totaux_affichage,
                    NoteDebitSerializer(note).data, f'note {scenario}')

    # ── Bon de commande / pro-forma (chaîne de l'option du devis) ─────────

    def test_bon_commande(self, _dl):
        from apps.ventes.models import BonCommande
        from apps.ventes.serializers_facturation import BonCommandeSerializer
        from apps.ventes.utils.options import option_totaux
        from apps.ventes.utils.pdf import generate_bon_commande_pdf
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                devis = self._devis(scenario)
                bc = BonCommande.objects.create(
                    company=self.company, client=self.client_obj,
                    devis=devis,
                    reference=f'BC-ATOT16-{self._suivant():04d}',
                    statut=BonCommande.Statut.CONFIRME)
                texte = _texte_pdf(generate_bon_commande_pdf(bc.pk))
                lues = figures_lues(texte, *LIBELLES['bon_commande'])
                self._parite_option(lues, option_totaux(devis),
                                    f'BC {scenario}')
                api = BonCommandeSerializer(bc).data
                self.assertEqual(_q(api['total_ht']), lues['ht_net'])
                self.assertEqual(_q(api['total_tva']), lues['tva'])
                self.assertEqual(_q(api['total_ttc']), lues['ttc'])

    def test_proforma(self, _dl):
        from apps.ventes.utils.options import option_totaux
        from apps.ventes.utils.pdf import generate_proforma_pdf
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                devis = self._devis(scenario)
                texte = _texte_pdf(generate_proforma_pdf(
                    devis, f'PF-ATOT16-{self._suivant():04d}'))
                lues = figures_lues(texte, *LIBELLES['proforma'])
                self._parite_option(lues, option_totaux(devis),
                                    f'pro-forma {scenario}')
                self.assertEqual(_q(devis.total_ttc), lues['ttc'])

    # ── Énumération des gabarits d'argent ─────────────────────────────────

    def test_tous_les_gabarits_d_argent_sont_couverts(self, _dl):
        dossier = Path(settings.BASE_DIR) / 'templates' / 'pdf'
        gabarits = set()
        for chemin in dossier.glob('*.html'):
            if chemin.name.startswith('_'):
                continue
            if '_chaine_totaux.html' in chemin.read_text(encoding='utf-8'):
                gabarits.add(chemin.name)
        self.assertTrue(gabarits, 'aucun gabarit d\'argent trouvé')
        self.assertEqual(
            gabarits - GABARITS_COUVERTS, set(),
            'Gabarit(s) d\'argent sans parité API ↔ PDF (ATOT16) : '
            'ajoutez-les à cette suite.')
        self.assertEqual(GABARITS_COUVERTS - gabarits, set(),
                         'Gabarit couvert qui n\'importe plus la macro.')


class FiguresLuesTests(SimpleTestCase):
    """Test-du-test du lecteur : une chaîne sans « Total HT » alors qu'une
    remise est imprimée est vue comme Total HT = Sous-total, et l'oracle
    ATOT13 la refuse."""

    def test_chaine_sans_total_ht_refusee(self):
        texte = ('Sous-total HT 20000.00 MAD Remise globale (15.00%) '
                 '−3000.00 MAD TVA (10.00%) 850.00 MAD TVA (20.00%) '
                 '1700.00 MAD Total TTC 19550.00 MAD')
        lues = figures_lues(texte, 'Sous-total HT', 'Total TTC')
        self.assertFalse(lues['total_ht_imprime'])
        with self.assertRaises(AssertionError):
            verifier_chaine_document(None, figures=lues)

    def test_chaine_complete_acceptee(self):
        texte = ('Total HT 1.00 MAD Sous-total HT 20000.00 MAD '
                 'Remise globale (15.00%) −3000.00 MAD Total HT 17000.00 MAD '
                 'TVA (10.00%) 850.00 MAD TVA (20.00%) 1700.00 MAD '
                 'Total TTC 19550.00 MAD')
        lues = figures_lues(texte, 'Sous-total HT', 'Total TTC')
        self.assertEqual(lues['ht_net'], Decimal('17000.00'))
        self.assertEqual(lues['remise'], Decimal('3000.00'))
        self.assertEqual(len(lues['tva_par_taux']), 2)
        self.assertTrue(verifier_chaine_document(None, figures=lues))
