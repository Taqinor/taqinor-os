"""GAMMES — 4b. Acceptation : la signature référence la gamme choisie.

Partie 4b sur 8 de l'ancien `test_gammes_offre.py`, scindé le 2026-08-21.
Ce test vivait dans `TestAcceptationGamme` ; il occupe désormais SA classe et
SON module pour être parallélisable — le raisonnement complet, mesures CI à
l'appui, est dans l'en-tête de `test_gammes_offre_acceptation.py`.
L'assertion est identique à l'octet près.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_acceptation_signature -v 2
"""
from unittest import mock

from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.tests._gammes_offre_common import GammeBase, url_accept


class TestAcceptationSignature(GammeBase):
    """MOTEUR PDF BOUCHONNÉ (24/08/2026) — pourquoi c'est sûr ICI.

    Mesure : cette classe pesait 167,6 s puis 111,7 s (runs 32711511999 et
    32746943023, `scripts/ci_shard_class_timings.json`) pour UN test — la
    classe la plus lourde de toute la suite. Le coût n'est pas le test : c'est
    `accept_devis` qui, à chaque acceptation réussie, appelle
    `_store_signed_pdf` → un rendu WeasyPrint RÉEL du moteur premium.

    Le bouchon ne peut rien affaiblir de CE test :
      * son assertion porte sur l'existence d'un `DevisSignature` rattaché à la
        BONNE gamme (et sur son absence sur la gamme sœur) — jamais sur les
        octets du PDF, ses pages, sa clé MinIO, ni sur l'appel du moteur ;
      * `_store_signed_pdf` est best-effort : tout son corps est dans un
        `try/except` qui avale l'exception, et il s'exécute APRÈS l'écriture de
        la signature. Le sort du rendu ne pouvait donc, par construction, pas
        changer le verdict.

    Ce que le bouchon masquerait est prouvé ailleurs : le stockage de
    `signed_pdf_key` avec `persist=True` par
    `apps.ventes.tests.test_qj22_signed_artifact`, et le rendu réel de bout en
    bout par `test_roof_pipeline.TestQ7ProposalAcceptSuccess` et
    `test_lead_quotes.TestProposalRealRender`.

    Cible de patch : l'attribut du PAQUET `apps.ventes.quote_engine` — c'est
    lui que lit le `from ... import` local à `_store_signed_pdf`, donc résolu
    à l'appel."""

    @mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                return_value='devis/1/DEV-GAM-041.pdf')
    def test_signature_referencee_sur_la_gamme_choisie(self, _moteur):
        from apps.ventes.models import DevisSignature
        source, soeur = self._paire('DEV-GAM-041')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        sig = DevisSignature.objects.filter(devis=soeur).first()
        self.assertIsNotNone(sig)
        self.assertFalse(DevisSignature.objects.filter(devis=source).exists())
