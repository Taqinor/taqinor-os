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
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

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
                self.assertIn(LIBELLES['fr'][cle], texte)
        self.assertIn('Émise', texte)
        self.assertIn('Virement', texte)

    def test_libelle_hors_arabe_rend_le_texte(self):
        from apps.ventes.utils.libelles_ar import libelle
        self.assertEqual(libelle('Émise', 'fr'), 'Émise')
        self.assertEqual(libelle('Virement (avance)', 'fr'),
                         'Virement (avance)')
        self.assertNotIn('Virement', libelle('Virement (avance)', 'ar'))
        self.assertEqual(libelle('Texte inconnu', 'ar'), 'Texte inconnu')
