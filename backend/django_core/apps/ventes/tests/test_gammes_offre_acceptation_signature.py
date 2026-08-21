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
from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.tests._gammes_offre_common import GammeBase, url_accept


class TestAcceptationSignature(GammeBase):

    def test_signature_referencee_sur_la_gamme_choisie(self):
        from apps.ventes.models import DevisSignature
        source, soeur = self._paire('DEV-GAM-041')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        sig = DevisSignature.objects.filter(devis=soeur).first()
        self.assertIsNotNone(sig)
        self.assertFalse(DevisSignature.objects.filter(devis=source).exists())
