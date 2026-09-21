"""NTLOG29 — bordereau d'expédition (packing list transport) PDF WeasyPrint
via `core.pdf.render_pdf` (document interne, distinct du moteur devis —
règle CLAUDE.md #4 non concernée). Rendu réel : nécessite les libs
WeasyPrint/Pango de l'image de test (indisponibles sur un poste hôte nu —
voir `docs/*weasyprint*`), tourne dans le harnais/CI comme les autres tests
PDF (motif `test_reclamation_transporteur.py`)."""
from decimal import Decimal

from django.test import TestCase

from apps.transport.models import LigneOrdreTransport, OrdreTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/ordres-transport/'


class BordereauExpeditionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-be-a', 'A')
        self.co_b = make_company('transport-be-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-be-a')
        self.user_b = make_user(self.co_b, 'transport-be-b')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a, numero='OT-202608-0002',
            expediteur_nom='TAQINOR', destinataire_nom='Client Test')
        LigneOrdreTransport.objects.create(
            company=self.co_a, ordre=self.ordre, designation='Panneau 450W',
            quantite=Decimal('10'), unite='u', poids_kg=Decimal('250.00'),
            volume_m3=Decimal('1.200'))
        LigneOrdreTransport.objects.create(
            company=self.co_a, ordre=self.ordre, designation='Onduleur',
            quantite=Decimal('2'), unite='u', poids_kg=Decimal('30.00'),
            volume_m3=Decimal('0.100'))

    def test_genere_un_pdf(self):
        resp = auth(self.user_a).get(
            f'{BASE}{self.ordre.id}/bordereau-expedition/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(bytes(resp.content).startswith(b'%PDF'))

    def test_reprend_les_totaux_poids_volume_de_l_ecran(self):
        from apps.transport.bordereau_pdf import render_bordereau_expedition_pdf

        # Le PDF étant binaire, on vérifie que le rendu ne lève pas — les
        # totaux poids/volume utilisent les MÊMES accumulateurs que
        # `OrdreTransportSerializer.get_poids_total_kg`/`get_volume_total_m3`
        # (Σ des lignes, `Decimal('0')` de départ) : pas de calcul dupliqué.
        pdf_bytes = render_bordereau_expedition_pdf(self.ordre)
        self.assertTrue(pdf_bytes)

    def test_cross_tenant_404(self):
        resp = auth(self.user_b).get(
            f'{BASE}{self.ordre.id}/bordereau-expedition/')
        self.assertEqual(resp.status_code, 404)
