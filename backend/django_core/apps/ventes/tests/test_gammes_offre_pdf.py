"""GAMMES — 5. UN PDF = UNE GAMME.

Partie 5 sur 6 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

Décision fondateur 2026-08-18 couverte ici : chaque gamme a son propre
jeton/PDF, jamais un document fusionné.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_pdf -v 2
"""
from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.public_views import _gammes_public
from apps.ventes.tests._gammes_offre_common import GammeBase, url_proposal


class TestPdfParGamme(GammeBase):

    def test_chaque_gamme_a_son_propre_jeton(self):
        source, soeur = self._paire('DEV-GAM-050')
        t_source = ShareLink.for_devis(source).token
        t_soeur = ShareLink.for_devis(soeur).token
        self.assertNotEqual(t_source, t_soeur)

    def test_le_lien_de_la_carte_pointe_le_jeton_de_la_soeur(self):
        """Chaque carte de gamme ouvre le document ET le PDF de SA gamme —
        jamais un PDF fusionné des deux gammes."""
        source, soeur = self._paire('DEV-GAM-051')
        bloc = _gammes_public(source)
        t_soeur = ShareLink.objects.filter(devis=soeur).first().token
        self.assertIn(t_soeur, bloc['soeur']['proposition_path'])

    def test_le_payload_du_jeton_soeur_rend_la_soeur(self):
        source, soeur = self._paire('DEV-GAM-052', nom='Premium')
        lien = ShareLink.for_devis(soeur)
        resp = APIClient().get(url_proposal(lien.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reference'], soeur.reference)
        self.assertEqual(resp.data['gammes']['courante']['nom'], 'Premium')
        self.assertEqual(resp.data['gammes']['soeur']['nom'], 'Essentielle')
