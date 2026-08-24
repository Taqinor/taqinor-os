"""GAMMES — 4c. Acceptation : la gamme refusée disparaît du choix.

Partie 4c sur 8 de l'ancien `test_gammes_offre.py`, scindé le 2026-08-21.
Ce test vivait dans `TestAcceptationGamme` ; il occupe désormais SA classe et
SON module pour être parallélisable — le raisonnement complet, mesures CI à
l'appui, est dans l'en-tête de `test_gammes_offre_acceptation.py`.
Les assertions sont identiques à l'octet près.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_acceptation_choix -v 2
"""
from unittest import mock

from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.public_views import _gammes_public
from apps.ventes.services import gamme_soeur
from apps.ventes.tests._gammes_offre_common import GammeBase, url_accept


class TestAcceptationChoix(GammeBase):
    """MOTEUR PDF BOUCHONNÉ (24/08/2026) — mêmes raisons, mêmes preuves que
    `test_gammes_offre_acceptation_signature.TestAcceptationSignature` (lire
    son docstring : il porte le raisonnement complet).

    Mesure propre à cette classe : 138,5 s puis 99,6 s pour UN test (runs
    32711511999 et 32746943023) — deuxième bloc indivisible le plus lourd de
    la suite, et là encore c'est le rendu WeasyPrint de `_store_signed_pdf`
    qui coûte, pas le test. Les deux assertions portent sur la disparition de
    la gamme refusée (`gamme_soeur`, `_gammes_public`) : rien du PDF."""

    @mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                return_value='devis/1/DEV-GAM-042.pdf')
    def test_gamme_refusee_disparait_du_choix(self, _moteur):
        source, soeur = self._paire('DEV-GAM-042')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        soeur.refresh_from_db()
        self.assertIsNone(gamme_soeur(soeur))
        self.assertIsNone(_gammes_public(soeur))
