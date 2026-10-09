"""APAR61 (C-APAR-013, D-APAR-4) — l'identité vendeur imprimée sur une
facture est FIGÉE à l'émission (``Facture.identite_vendeur``) et le PDF d'une
facture émise se rend depuis cet instantané : changer le RIB de la société ne
change pas le PDF d'une facture déjà émise ; une nouvelle facture prend le
nouveau RIB ; une facture sans instantané (antérieure) suit le profil vivant.

Rejoue la sonde VB p5 (`rendu2 (apres changement profil) contient nouveau
RIB: True` sur une facture émise). Rendu WeasyPrint réel ; seul l'upload
MinIO est neutralisé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_facture_apar61_identite_vendeur"
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

R1 = '011 780 0000111111111111 11'
R2 = '022 780 0000222222222222 22'


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class IdentiteVendeurFigeeTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from authentication.models import Company
        self.company = Company.objects.create(nom='APAR61', slug='apar61-co')
        self.profile = CompanyProfile.get(company=self.company)
        self.profile.rib = R1
        self.profile.banque = 'Banque Une'
        self.profile.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='APAR61',
            email='apar61@example.invalid')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _facture(self, ref, statut='brouillon'):
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        produit, _ = Produit.objects.get_or_create(
            company=self.company, sku='APAR61-P',
            defaults={'nom': 'Centrale', 'prix_vente': Decimal('1000')})
        facture = Facture.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Centrale',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return facture

    def _emettre(self, facture):
        from apps.ventes.domain.facturation_ops import emettre_facture
        emettre_facture(facture, source='test_apar61')
        facture.refresh_from_db()
        return facture

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def _changer_rib(self, rib, banque):
        self.profile.rib = rib
        self.profile.banque = banque
        self.profile.save()

    def test_rib_fige_a_l_emission(self):
        f120 = self._emettre(self._facture('FAC-APAR61-0120'))
        self.assertIn(R1, self._pdf(f120))
        self._changer_rib(R2, 'Banque Deux')
        # CLAUSE PERSISTANCE : l'instantané relu est inchangé.
        f120.refresh_from_db()
        self.assertEqual(f120.identite_vendeur['rib'], R1)
        texte = self._pdf(f120)
        self.assertIn(R1, texte)
        self.assertNotIn(R2, texte)

    def test_nouvelle_facture_prend_le_nouveau_rib(self):
        self._emettre(self._facture('FAC-APAR61-0121'))
        self._changer_rib(R2, 'Banque Deux')
        nouvelle = self._emettre(self._facture('FAC-APAR61-0122'))
        self.assertIn(R2, self._pdf(nouvelle))

    def test_facture_sans_instantane_suit_le_profil(self):
        ancienne = self._facture('FAC-APAR61-0100', statut='emise')
        self.assertIsNone(ancienne.identite_vendeur)
        self._changer_rib(R2, 'Banque Deux')
        texte = self._pdf(ancienne)
        self.assertIn(R2, texte)
