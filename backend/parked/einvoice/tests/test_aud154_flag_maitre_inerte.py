"""AUD154 — l'app einvoice est REELLEMENT inerte quand le flag maître est OFF.

Le module promet (`apps/einvoice/services.py:1-8`) « app entièrement inerte
tant que le flag n'est pas posé — ``generer`` renvoie ``None`` sans rien
écrire », et `generer` tenait parole (garde en tête de fonction).

`transmettre(fe)`, lui, ne testait QUE `is_dgi_transmission_enabled()` — un
flag DISTINCT (`DGI_TRANSMISSION_ENABLED`) — jamais `is_einvoice_enabled()`,
et faisait son `TransmissionDGI.objects.get_or_create(...)` (écriture en base)
AVANT même de tester ce flag-là. Une `FactureElectronique` créée quand le flag
maître était actif restait donc transmissible après sa désactivation : le
fondateur coupait la facturation électronique, et une transmission partait
quand même vers la DGI.

Côté API, `regenerer_action` sérialisait le `None` renvoyé par `regenerer`
quand le flag maître était OFF — un 201 CREATED portant un objet vide, c'est-
à-dire un succès annoncé pour une régénération qui n'a jamais eu lieu.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.einvoice import services
from apps.einvoice.models import FactureElectronique, TransmissionDGI

from ._fixtures import make_company, make_facture, make_user, seller_profile


class FlagMaitreOffTests(TestCase):
    """`EINVOICE_ENABLED` reste à son défaut (OFF) dans toute cette classe."""

    ENDPOINT = '/api/django/einvoice/factures-electroniques/'

    def setUp(self):
        self.company = make_company('einvoice-aud154', 'EInvoice AUD154')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-AUD154-0001')
        self.user = make_user(self.company, 'einv-aud154')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        # L'e-facture existe : elle a été générée QUAND le flag maître était
        # encore actif. C'est tout le scénario — le flag est coupé ensuite.
        with override_settings(EINVOICE_ENABLED=True), \
                patch('apps.einvoice.services._minio_client',
                      side_effect=lambda: MagicMock()):
            self.fe = services.generer(self.facture.id, self.company)

    # ── transmettre : aucune écriture, aucun objet renvoyé ─────────────────
    def test_transmettre_n_ecrit_aucune_transmission(self):
        resultat = services.transmettre(self.fe)
        self.assertIsNone(resultat)
        self.assertEqual(
            TransmissionDGI.objects.filter(einvoice=self.fe).count(), 0)

    @override_settings(DGI_TRANSMISSION_ENABLED=True,
                       DGI_TRANSMISSION_URL='https://simpl.example/api')
    def test_flag_de_transmission_seul_ne_reveille_pas_l_app(self):
        """Le flag de transmission est DISTINCT : il ne peut pas, à lui seul,
        faire partir une transmission alors que la facturation électronique
        est coupée."""
        resultat = services.transmettre(self.fe)
        self.assertIsNone(resultat)
        self.assertEqual(
            TransmissionDGI.objects.filter(einvoice=self.fe).count(), 0)

    def test_transmettre_action_renvoie_204_sans_rien_ecrire(self):
        reponse = self.api.post(f'{self.ENDPOINT}{self.fe.id}/transmettre/')
        self.assertEqual(reponse.status_code, 204, reponse.content)
        self.assertEqual(
            TransmissionDGI.objects.filter(einvoice=self.fe).count(), 0)

    # ── regenerer : 204 no-op au lieu d'un 201 portant `None` ──────────────
    def test_regenerer_action_renvoie_204(self):
        reponse = self.api.post(f'{self.ENDPOINT}{self.fe.id}/regenerer/')
        self.assertEqual(reponse.status_code, 204, reponse.content)
        # Aucune nouvelle version : la v1 de setUp reste seule.
        self.assertEqual(
            FactureElectronique.objects.filter(company=self.company).count(),
            1)

    # ── garde ciblé : flag maître ON, tout refonctionne ────────────────────
    @override_settings(EINVOICE_ENABLED=True)
    def test_flag_maitre_on_la_transmission_repart(self):
        transmission = services.transmettre(self.fe)
        self.assertIsNotNone(transmission)
        self.assertEqual(transmission.statut,
                         TransmissionDGI.Statut.EN_ATTENTE)
