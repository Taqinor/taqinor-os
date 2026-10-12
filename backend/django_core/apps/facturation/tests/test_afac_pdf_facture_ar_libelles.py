"""AFAC58 (C-AFAC-050) — tous les libellés du PDF facture ajoutés après
XSAL13 sont traduits en arabe via ``_L()`` / ``LIBELLES`` (et ``TEXTES_AR``
pour les textes d'affichage dynamiques : statut, modes de paiement) ; le
rendu français est inchangé.

Rejoue la sonde FDOC-11 (« Facture générée automatiquement », « Émise »,
« Tél » en français dans la page RTL). Rendu WeasyPrint RÉEL ; seul
l'upload MinIO est neutralisé. ``recu.html`` et ``releve.html`` (figés
``lang=fr``) restent en français — hors périmètre (optionnel).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_pdf_facture_ar_libelles"
"""
import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

_CTR = [0]

#: Clés AFAC58 (libellés ajoutés après XSAL13) — leurs valeurs ``fr`` ne
#: doivent JAMAIS apparaître dans la page arabe.
CLES_AFAC58 = (
    'deja_paye', 'total_deja_paye', 'reste_a_payer', 'periode_service',
    'votre_commande', 'tel', 'instructions_paiement', 'conditions_generales',
    'conditions_paiement', 'facture_generee_le',
)


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class PdfFactureArLibellesTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC58 {n}', slug=f'afac58-{n}')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)
        # Profil société : téléphone, instructions et conditions générales
        # imprimés (best-effort : champ absent → bloc simplement omis).
        self._profil()

    def _profil(self):
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.company)
        for champ, valeur in (('telephone', '+212522000058'),
                              ('instructions_paiement', 'Virement sous 30 j.'),
                              ('conditions_generales', 'Pénalités légales.')):
            if hasattr(profil, champ):
                setattr(profil, champ, valeur)
        profil.save()

    def _facture(self, langue):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, Paiement
        client = Client.objects.create(
            company=self.company, nom='Haddad', prenom='Nadia',
            email=f'afac58-{_nxt()}@example.invalid',
            langue_document=langue)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC58-{_nxt():04d}',
            client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            conditions_paiement='Virement à 30 jours',
            reference_commande_client='BC-CLIENT-58',
            periode_service_debut=date(2026, 9, 1),
            periode_service_fin=date(2026, 9, 30))
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('500'),
            date_paiement=date.today(), mode=Paiement.Mode.VIREMENT)
        return Facture.objects.get(pk=facture.pk)

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def test_aucun_libelle_francais_en_ar(self):
        from apps.ventes.utils.libelles_ar import LIBELLES, TEXTES_AR
        texte = self._pdf(self._facture('ar'))
        for cle in CLES_AFAC58:
            with self.subTest(cle=cle):
                self.assertNotIn(LIBELLES['fr'][cle], texte)
        # Statut et mode de paiement : textes d'affichage traduits.
        self.assertNotIn('Émise', texte)
        self.assertNotIn('Virement ·', texte)
        self.assertTrue(TEXTES_AR['Émise'])

    def test_francais_inchange(self):
        from apps.ventes.utils.libelles_ar import LIBELLES
        texte = self._pdf(self._facture('fr'))
        for cle in ('deja_paye', 'total_deja_paye', 'reste_a_payer',
                    'periode_service', 'votre_commande',
                    'conditions_paiement', 'facture_generee_le'):
            with self.subTest(cle=cle):
                # le gabarit met certains libellés en capitales (CSS) : comparaison insensible à la casse
                self.assertIn(LIBELLES['fr'][cle].lower(), texte.lower())
        self.assertIn('Émise', texte)
        self.assertIn('Virement', texte)

    def test_sans_devis_aucun_tableau_de_garanties(self):
        # VNT38 — une facture sans devis n'imprime aucune garantie.
        texte = self._pdf(self._facture('fr'))
        # En-tête de tableau en capitales (CSS) : comparaison sans casse.
        self.assertNotIn('garanties', texte.lower())

    def test_libelle_hors_arabe_rend_le_texte(self):
        from apps.ventes.utils.libelles_ar import libelle
        self.assertEqual(libelle('Émise', 'fr'), 'Émise')
        self.assertEqual(libelle('Virement (avance)', 'fr'),
                         'Virement (avance)')
        self.assertNotIn('Virement', libelle('Virement (avance)', 'ar'))
        self.assertEqual(libelle('Texte inconnu', 'ar'), 'Texte inconnu')


class GarantiesFactureTests(TestCase):
    """VNT38 — tableau « Garanties » (désignation, durée, détail) sur toute
    facture rattachée à un devis, FR et AR : durées des fiches produit,
    FIGÉES à l'émission (``Facture.garanties``), vivantes en brouillon ;
    aucune ligne sans durée. Rendu WeasyPrint réel (upload neutralisé)."""

    ONDULEUR = 'Onduleur hybride Deye SUN-8K-SG05LP3'
    BATTERIE = 'Batterie lithium Deye BOS-B-Pack16-A3 16 kWh'

    def setUp(self):
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'VNT38 {n}', slug=f'vnt38-{n}')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _vente(self, langue='fr'):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        n = _nxt()
        client = Client.objects.create(
            company=self.company, nom='Garantie', prenom='VNT38',
            email=f'vnt38-{n}@example.invalid', langue_document=langue)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-VNT38-{n:04d}',
            client=client, statut='accepte', taux_tva=Decimal('20.00'))
        for nom, prix, mois in ((self.ONDULEUR, '12500', 120),
                                (self.BATTERIE, '10000', None)):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'VNT38-{n}-{prix}',
                prix_vente=Decimal(prix), quantite_stock=50,
                garantie_mois=mois)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return devis

    def _tranche(self, devis, type_facture='acompte'):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-VNT38-{_nxt():04d}',
            client=devis.client, devis=devis,
            statut=Facture.Statut.BROUILLON, type_facture=type_facture,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def test_acompte_et_solde_meme_garanties_figees_a_l_emission(self):
        from apps.stock.models import Produit
        from apps.ventes.domain.facturation_ops import emettre_facture
        devis = self._vente()
        acompte = self._tranche(devis)
        solde = self._tranche(devis, 'solde')
        for facture in (acompte, solde):
            texte = self._pdf(facture)
            # En-tête de tableau en capitales (CSS) : comparaison sans casse.
            self.assertIn('garanties', texte.lower())
            self.assertIn('Onduleur 10 ans', texte)
            tableau = texte.lower().split('garanties', 1)[1]
            self.assertNotIn('batterie', tableau)
        emettre_facture(acompte, source='test_vnt38')
        acompte.refresh_from_db()
        self.assertIn({'libelle': 'Onduleur', 'duree': '10 ans',
                       'detail': ''}, acompte.garanties)
        self.assertTrue(all(g['duree'] for g in acompte.garanties))
        Produit.objects.filter(company=self.company,
                               nom=self.ONDULEUR).update(garantie_mois=60)
        # L'émise garde l'instantané ; le brouillon suit le catalogue.
        texte_emise = self._pdf(acompte)
        self.assertIn('Onduleur 10 ans', texte_emise)
        self.assertNotIn('Onduleur 5 ans', texte_emise)
        self.assertIn('Onduleur 5 ans', self._pdf(solde))

    def test_client_arabe(self):
        from apps.ventes.domain.facturation_ops import emettre_facture
        from apps.ventes.utils.garanties import garanties_de_la_vente
        from apps.ventes.utils.pdf import (
            _company_context, _render_html, contexte_vente_facture)
        from apps.ventes.utils.libelles_ar import libelle
        devis = self._vente('ar')
        acompte = self._tranche(devis)
        emettre_facture(acompte, source='test_vnt38_ar')
        acompte.refresh_from_db()
        attendu = [g['designation'] for g in garanties_de_la_vente(devis, 'ar')]
        self.assertEqual([g['libelle'] for g in acompte.garanties], attendu)
        self.assertNotIn('Onduleur', repr(acompte.garanties))
        ctx = _company_context(company=self.company)
        ctx.update({'facture': acompte, 'langue_document': 'ar',
                    'L': lambda cle: libelle(cle, 'ar')})
        ctx.update(contexte_vente_facture(acompte, 'ar'))
        html = _render_html('facture.html', ctx)
        self.assertIn(libelle('garanties', 'ar'), html)
        for designation in attendu:
            self.assertIn(designation, html)


# ── VNT93 — garde FR/AR des clés _L de facture.html et recu.html ────────────

_APPEL_L = re.compile(r"""_L\(\s*(['"])(.*?)\1\s*\)""")


def _gabarit(nom):
    from django.conf import settings
    chemin = Path(settings.BASE_DIR) / 'templates' / 'pdf' / nom
    return chemin.read_text(encoding='utf-8')


def cles_l(nom):
    """Les clés LITTÉRALES passées à ``_L('…')`` dans le gabarit ``nom``
    (les appels dynamiques ``_L(r.mode)`` passent par ``TEXTES_AR``)."""
    return sorted({m.group(2) for m in _APPEL_L.finditer(_gabarit(nom))})


def repli_facture():
    """Le dict de repli FR du macro ``_L`` de facture.html (sans ``L`` dans
    le contexte, une clé absente s'imprime BRUTE)."""
    src = _gabarit('facture.html')
    trouve = re.search(r'\{\{ (\{.*?\})\.get\(cle, cle\) \}\}', src, re.S)
    assert trouve, 'dict de repli du macro _L introuvable dans facture.html'
    return ast.literal_eval(trouve.group(1))


class CataloguesLibellesTests(SimpleTestCase):
    """VNT93 — chaque clé ``_L`` de facture.html a sa traduction dans
    ``LIBELLES['ar']`` (ou est un texte français de ``TEXTES_AR``), son
    libellé ``LIBELLES['fr']`` ET son repli dans le dict du macro ; chaque
    clé de recu.html (le texte français EST la clé, repli = la clé) a sa
    traduction arabe. Jamais une clé brute imprimée au client.

    Test-du-test : retirer ``'remise_negociee'`` du dict de repli de
    facture.html ⇒ ``test_facture_html`` échoue."""

    def test_extraction_non_vide(self):
        self.assertIn('remise_negociee', cles_l('facture.html'))
        self.assertIn('Reste dû sur la vente', cles_l('recu.html'))

    def test_facture_html(self):
        from apps.ventes.utils.libelles_ar import LIBELLES, TEXTES_AR
        repli = repli_facture()
        for cle in cles_l('facture.html'):
            with self.subTest(cle=cle):
                if cle in TEXTES_AR:  # texte français : repli = lui-même
                    continue
                self.assertIn(cle, LIBELLES['fr'])
                self.assertIn(cle, LIBELLES['ar'])
                self.assertEqual(repli.get(cle), LIBELLES['fr'][cle])

    def test_recu_html(self):
        from apps.ventes.utils.libelles_ar import LIBELLES, libelle
        for cle in cles_l('recu.html'):
            with self.subTest(cle=cle):
                self.assertNotEqual(libelle(cle, 'ar'), cle)
                if cle in LIBELLES['fr']:  # clé de catalogue : repli = clé
                    self.assertEqual(LIBELLES['fr'][cle], cle)


class RenduArabeSansCleBruteTests(TestCase):
    """VNT93 — rendu arabe RÉEL (facture de tranche d'une vente, brouillon
    puis émise ; reçu de son paiement) : aucune clé ``snake_case`` de
    ``_L`` imprimée, aucun libellé français du reçu."""

    _vente = GarantiesFactureTests._vente
    _tranche = GarantiesFactureTests._tranche
    ONDULEUR = GarantiesFactureTests.ONDULEUR
    BATTERIE = GarantiesFactureTests.BATTERIE

    def setUp(self):
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'VNT93 {n}', slug=f'vnt93-{n}')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _cles_brutes(self, texte):
        return [c for c in cles_l('facture.html')
                if '_' in c and c in texte]

    def test_facture_et_recu_arabes(self):
        from apps.ventes.domain.facturation_ops import emettre_facture
        from apps.ventes.models import Paiement
        from apps.ventes.utils.pdf import (
            generate_facture_pdf, generate_recu_pdf)
        devis = self._vente('ar')
        tranche = self._tranche(devis)
        texte = _texte(self.objets[generate_facture_pdf(tranche.id)])
        self.assertEqual(self._cles_brutes(texte), [])
        emettre_facture(tranche, source='test_vnt93')
        tranche.refresh_from_db()
        texte = _texte(self.objets[generate_facture_pdf(tranche.id)])
        self.assertEqual(self._cles_brutes(texte), [])
        paiement = Paiement.objects.create(
            company=self.company, facture=tranche, montant=Decimal('1200'),
            date_paiement=date.today(), mode=Paiement.Mode.VIREMENT)
        frais = Paiement.objects.select_related(
            'facture', 'facture__client', 'company').get(pk=paiement.pk)
        with patch('apps.ventes.utils.pdf._html_to_pdf',
                   side_effect=lambda html: html):
            html = generate_recu_pdf(frais)
        for francais in ('Reçu de paiement n°', 'Date du règlement',
                         'Solde restant dû', 'Reste dû sur la vente',
                         'Quittance générée automatiquement le'):
            with self.subTest(francais=francais):
                self.assertNotIn(francais, html)
