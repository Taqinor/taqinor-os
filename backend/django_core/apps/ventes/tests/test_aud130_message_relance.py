"""AUD130 — le placeholder `{reference}` des niveaux semés partait au client.

`seed_defaults` écrit trois messages contenant `{reference}` et AUCUN code ne
les formatait : `send_relance_email` faisait `corps_msg = message.strip()` puis
l'insérait tel quel, la lettre PDF rendait `{{ message or "…" }}` sans
substitution, et le beat passait `niveau.message` brut. Le client recevait
littéralement « Mise en demeure : la facture {reference} est en retard ».

Arbitrage (la tâche demande de TRANCHER, pas de cumuler) : les placeholders
sont CONSERVÉS dans les messages semés et RENDUS par une fonction unique,
`recouvrement.rendre_message_relance(niveau, facture)`, appelée par
`send_relance_email` ET `generate_lettre_relance_pdf`.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Facture, FollowupLevel

User = get_user_model()


class TestAud130MessageRelance(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='aud130-co', defaults={'nom': 'AUD130 Co'})[0]
        self.user = User.objects.create_user(
            username='aud130_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Debiteur', prenom='AUD130',
            email='aud130@example.com', telephone='+212600000130')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD130-0007',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('1000.00'),
            date_echeance=date.today() - timedelta(days=40))
        # Le message EXACT semé par `seed_defaults` (niveau « Mise en demeure »).
        self.niveau = FollowupLevel.objects.create(
            company=self.company, ordre=2, nom='Mise en demeure',
            delai_jours=30,
            message=('Mise en demeure : la facture {reference} est en retard '
                     'de paiement. Un règlement immédiat est attendu.'))
        mail.outbox = []

    # ── le rendu lui-même ────────────────────────────────────────────────
    def test_rendre_message_relance_substitue_les_variables_declarees(self):
        from apps.ventes.recouvrement import rendre_message_relance
        niveau = FollowupLevel(
            company=self.company, ordre=9, nom='Test', delai_jours=1,
            message=('Facture {reference} — {client} doit {montant_du} MAD '
                     'depuis {jours_retard} jours.'))
        rendu = rendre_message_relance(niveau, self.facture)
        self.assertNotIn('{', rendu)
        self.assertIn('FAC-AUD130-0007', rendu)
        self.assertIn('Debiteur', rendu)
        self.assertIn('40', rendu)

    def test_variable_inconnue_ne_leve_pas_et_ne_laisse_pas_d_accolade(self):
        from apps.ventes.recouvrement import rendre_message_relance
        rendu = rendre_message_relance(
            'Bonjour {client}, cf. {variable_inexistante} et {  } — fin.',
            self.facture)
        self.assertNotIn('{', rendu)
        self.assertNotIn('}', rendu)
        self.assertIn('Debiteur', rendu)

    def test_accepte_une_chaine_un_dict_ou_un_niveau(self):
        """Les trois formes de `niveau` en circulation doivent être acceptées."""
        from apps.ventes.recouvrement import rendre_message_relance
        attendu_fragment = 'FAC-AUD130-0007'
        for forme in (
            self.niveau,
            {'message': self.niveau.message},
            self.niveau.message,
        ):
            rendu = rendre_message_relance(forme, self.facture)
            self.assertIn(attendu_fragment, rendu)
            self.assertNotIn('{', rendu)

    # ── les deux surfaces client ─────────────────────────────────────────
    def test_email_de_relance_rend_la_vraie_reference(self):
        from apps.ventes.email_service import send_relance_email
        send_relance_email(
            self.facture, niveau_nom=self.niveau.nom,
            message=self.niveau.message, user=self.user)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].body
        self.assertNotIn('{', corps)
        self.assertIn('FAC-AUD130-0007', corps)

    def test_lettre_pdf_rend_la_vraie_reference(self):
        from apps.ventes.utils.pdf import generate_lettre_relance_pdf
        niveau = {'ordre': 2, 'nom': 'Mise en demeure', 'delai_jours': 30}
        pdf_bytes = generate_lettre_relance_pdf(
            self.facture, niveau, self.niveau.message)
        self.assertTrue(pdf_bytes)
        texte = self._pdf_text(pdf_bytes)
        self.assertNotIn('{reference}', texte)
        self.assertIn('FAC-AUD130-0007', texte)

    @staticmethod
    def _pdf_text(pdf_bytes):
        """Texte du PDF via fitz/PyMuPDF (déjà une dépendance du backend,
        même extraction que `test_quote_engine_snapshot._extract_text`)."""
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            return '\n'.join(page.get_text() for page in doc)
        finally:
            doc.close()
