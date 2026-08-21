"""GAMMES — 4. Acceptation de la gamme choisie.

Partie 4 sur 6 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

C'EST LA PARTIE QUI BORNE LE PALIER BACKEND : `TestAcceptationGamme` est
mesurée à ~195 s (`scripts/ci_shard_class_timings.json`) — une CLASSE étant
indivisible sous `--parallel`, aucun nombre de lanes ne descend sous elle.
Elle vit désormais dans SON module pour que le placeur LPT puisse l'isoler
et donner les 39 autres tests de la famille `gammes_offre` à d'autres lanes.

Décision fondateur 2026-08-18 couverte ici : l'acceptation de la gamme
choisie auto-refuse l'autre (YDOCF3).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_acceptation -v 2
"""
from rest_framework.test import APIClient

from apps.ventes.models import Devis, ShareLink
from apps.ventes.public_views import _gammes_public
from apps.ventes.services import gamme_soeur
from apps.ventes.tests._gammes_offre_common import GammeBase, url_accept


class TestAcceptationGamme(GammeBase):

    def test_signer_la_soeur_auto_refuse_la_gamme_non_retenue(self):
        """Le jeton de la gamme choisie signe SON devis (loi 53-05) et
        effondre l'autre gamme (« variante non retenue », YDOCF3)."""
        source, soeur = self._paire('DEV-GAM-040', nom='Premium')
        lien_soeur = ShareLink.for_devis(soeur)
        resp = APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui',
            'consent_esign': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        soeur.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(soeur.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(soeur.accepte_par_nom, 'Salma Alaoui')
        self.assertEqual(source.statut, Devis.Statut.REFUSE)
        self.assertEqual(source.motif_refus, 'variante non retenue')
        self.assertFalse(source.is_active)

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

    def test_gamme_refusee_disparait_du_choix(self):
        source, soeur = self._paire('DEV-GAM-042')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        soeur.refresh_from_db()
        self.assertIsNone(gamme_soeur(soeur))
        self.assertIsNone(_gammes_public(soeur))
