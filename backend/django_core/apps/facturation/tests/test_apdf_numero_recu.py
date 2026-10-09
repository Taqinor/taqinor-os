"""APDF30 (C-APDF-011) — le reçu de paiement est numéroté par une séquence
PROPRE à la société (``Paiement.numero_recu``, posé à la première émission
par ``core.numbering``), imprimée à la place de ``paiement.id``.

Rejoue la sonde PFAC-4 (société 2 → n° 8, nouveau paiement société 6 →
n° 192). Vrai ``generate_recu_pdf`` (rendu réel), texte PyMuPDF, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_numero_recu"
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

_CTR = [0]


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


class NumeroRecuTests(TestCase):
    def _societe(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(nom=f'APDF30 {n}', slug=f'apdf30-{n}')
        client = Client.objects.create(
            company=company, nom='Client', prenom='APDF30',
            email=f'apdf30-{n}@example.invalid')
        facture = Facture.objects.create(
            company=company, reference=f'FAC-APDF30-{n}', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))
        return company, facture

    def _paiement(self, company, facture):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=company, facture=facture, montant=Decimal('100'),
            date_paiement=date(2026, 10, 1), mode=Paiement.Mode.ESPECES)

    def _rendre(self, paiement):
        from apps.ventes.models import Paiement
        from apps.ventes.utils.pdf import generate_recu_pdf
        frais = Paiement.objects.select_related(
            'facture', 'facture__client', 'company').get(pk=paiement.pk)
        return _texte(generate_recu_pdf(frais))

    def test_sequence_par_societe(self):
        co_a, fa = self._societe()
        pa = [self._paiement(co_a, fa) for _ in range(3)]
        co_b, fb = self._societe()
        pb = self._paiement(co_b, fb)
        textes_a = [self._rendre(p) for p in pa]
        texte_b = self._rendre(pb)
        for i, texte in enumerate(textes_a, start=1):
            self.assertIn(f'Reçu de paiement n° REC-{i:04d}', texte)
        self.assertIn('Reçu de paiement n° REC-0001', texte_b)
        self.assertNotIn(f'n° {pb.id} ', texte_b + ' ')

    def test_stable_au_second_rendu(self):
        from apps.ventes.models import Paiement
        co, f = self._societe()
        p = self._paiement(co, f)
        premier = self._rendre(p)
        # CLAUSE PERSISTANCE : numéro stocké, identique au rendu suivant.
        stocke = Paiement.objects.get(pk=p.pk).numero_recu
        self.assertEqual(stocke, 'REC-0001')
        second = self._rendre(p)
        self.assertIn('n° REC-0001', premier)
        self.assertIn('n° REC-0001', second)
        self.assertEqual(Paiement.objects.get(pk=p.pk).numero_recu, stocke)

    def test_independant_des_rollbacks(self):
        """La séquence Postgres globale avance (lignes créées puis annulées) :
        le numéro de reçu, lui, reste contigu dans la société."""
        from django.db import transaction
        co, f = self._societe()
        p1 = self._paiement(co, f)
        self._rendre(p1)
        try:
            with transaction.atomic():
                for _ in range(5):
                    self._paiement(co, f)
                raise RuntimeError('annulation')
        except RuntimeError:
            pass
        p2 = self._paiement(co, f)
        self.assertIn('n° REC-0002', self._rendre(p2))
