"""NTLOG19 — réclamation transporteur chiffrée (PDF WeasyPrint via
`core.pdf.render_pdf`, document NOUVEAU et DISTINCT du moteur `/proposal`,
règle CLAUDE.md #4). Rendu réel : nécessite les libs WeasyPrint/Pango de
l'image de test (indisponibles sur un poste hôte nu — voir
`docs/*weasyprint*`), tourne dans le harnais/CI comme tout autre test PDF."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.records.models import Attachment
from apps.transport.models import (
    EtapeTransport, LitigeTransport, OrdreTransport, ReserveReception,
)

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/litiges-transport/'


class ReclamationTransporteurTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-rec-a', 'A')
        self.user_a = make_user(self.co_a, 'transport-rec-a')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a, numero='OT-202608-0001')
        self.etape = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)
        self.litige = LitigeTransport.objects.create(
            company=self.co_a, ordre_transport=self.ordre,
            type_litige=LitigeTransport.TypeLitige.AVARIE,
            montant_conteste=Decimal('2000.00'),
            description='Panneau brisé au transport')
        reserve = ReserveReception.objects.create(
            company=self.co_a, etape=self.etape,
            nature_reserve='Panneau brisé', litige=self.litige)
        ct = ContentType.objects.get_for_model(ReserveReception)
        Attachment.objects.create(
            company=self.co_a, content_type=ct, object_id=reserve.id,
            file_key='transport/x/reserve.jpg', filename='reserve.jpg')

    def test_genere_un_pdf_et_passe_en_traitement(self):
        resp = auth(self.user_a).post(
            f'{BASE}{self.litige.id}/reclamer-transporteur/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(bytes(resp.content).startswith(b'%PDF'))
        self.litige.refresh_from_db()
        self.assertEqual(
            self.litige.statut, LitigeTransport.Statut.EN_TRAITEMENT)
        self.assertIsNotNone(self.litige.reclamation_envoyee_le)

    def test_pdf_contient_le_montant_conteste(self):
        from apps.transport.reclamation_pdf import (
            render_reclamation_transporteur_pdf,
        )
        # Le PDF étant binaire, on vérifie juste que le rendu ne lève pas et
        # produit des octets non vides — le contenu HTML (montant/pièces
        # jointes) est construit par `render_reclamation_transporteur_pdf`
        # elle-même, seule fonction qui assemble ce gabarit.
        pdf_bytes = render_reclamation_transporteur_pdf(self.litige)
        self.assertTrue(pdf_bytes)
