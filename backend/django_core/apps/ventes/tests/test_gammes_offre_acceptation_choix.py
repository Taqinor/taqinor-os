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
from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.public_views import _gammes_public
from apps.ventes.services import gamme_soeur
from apps.ventes.tests._gammes_offre_common import GammeBase, url_accept


class TestAcceptationChoix(GammeBase):

    def test_gamme_refusee_disparait_du_choix(self):
        source, soeur = self._paire('DEV-GAM-042')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        soeur.refresh_from_db()
        self.assertIsNone(gamme_soeur(soeur))
        self.assertIsNone(_gammes_public(soeur))
