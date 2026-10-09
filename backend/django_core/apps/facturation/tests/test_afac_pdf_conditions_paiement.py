"""AFAC56 (C-AFAC-043) — le PDF facture imprime les conditions de paiement
SAISIES (``Facture.conditions_paiement``, qui porte la phrase de retenue de
garantie) ; la note de débit imprime celles de sa facture d'origine ; l'ICE /
IF / RC du client est imprimé dès qu'il est renseigné (règle B2B de
``Facture._client_est_pro``), même pour un client de type particulier.

Rejoue la sonde FDOC-4 (« Retenue de garantie » et « Virement à 30 jours »
absents du PDF ; ICE d'un particulier non imprimé). Rendu WeasyPrint RÉEL ;
seul l'upload MinIO est neutralisé (dict en mémoire).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_pdf_conditions_paiement"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
RETENUE = {'taux_pct': 10, 'liberation': 'reception_definitive'}
ECHEANCIER = [
    {'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 100000},
    {'type': 'solde', 'pct_or_montant': 10},
]


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


class PdfConditionsPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC56 {n}', slug=f'afac56-{n}')
        self.user = User.objects.create_user(
            username=f'afac56-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', prenom='AFAC56',
            email=f'afac56-{n}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _pdf_facture(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def _facture(self, conditions='', client=None):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC56-{_nxt():04d}',
            client=client or self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            conditions_paiement=conditions)

    def test_retenue_garantie_imprimee(self):
        from apps.ventes.models import Devis, Facture, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AFAC56-{_nxt()}',
            client=self.client_obj, statut='accepte', taux_tva=Decimal('20'),
            mode_installation='industriel', echeancier=ECHEANCIER,
            retenue_garantie=RETENUE)
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('100000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        self.assertIn('Retenue de garantie', facture.conditions_paiement)
        texte = self._pdf_facture(facture)
        self.assertIn('Conditions de paiement', texte)
        self.assertIn('Retenue de garantie', texte)

    def test_conditions_saisies_imprimees(self):
        texte = self._pdf_facture(self._facture('Virement à 30 jours'))
        self.assertIn('Virement à 30 jours', texte)
        # Sans conditions saisies : aucun bloc vide.
        vide = self._pdf_facture(self._facture(''))
        self.assertNotIn('Conditions de paiement', vide)

    def test_note_debit_conditions_origine(self):
        from apps.ventes.models import LigneNoteDebit, NoteDebit
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        facture = self._facture('Virement à 30 jours')
        nd = NoteDebit.objects.create(
            company=self.company, reference=f'ND-AFAC56-{_nxt()}',
            facture=facture, client=self.client_obj,
            statut=NoteDebit.Statut.EMISE, motif='Complément',
            taux_tva=Decimal('20'))
        LigneNoteDebit.objects.create(
            note_debit=nd, designation='Complément', quantite=Decimal('1'),
            prix_unitaire=Decimal('500'), taux_tva=Decimal('20'))
        texte = _texte(self.objets[generate_note_debit_pdf(nd.id)])
        self.assertIn('Conditions de paiement', texte)
        self.assertIn('Virement à 30 jours', texte)

    def test_ice_client_particulier_imprime(self):
        from apps.crm.models import Client
        particulier = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            email=f'afac56-p-{_nxt()}@example.invalid',
            type_client='particulier', ice='001234567000089')
        texte = self._pdf_facture(self._facture(client=particulier))
        self.assertIn('ICE : 001234567000089', texte)
