"""GAMMES — 4a. Acceptation : signer la sœur auto-refuse la gamme non retenue.

Partie 4a sur 8 de l'ancien `test_gammes_offre.py`, scindé le 2026-08-21
(voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

POURQUOI CETTE CLASSE N'A QU'UN SEUL TEST — c'est TOUT le sujet du volet G.
`TestAcceptationGamme` portait ses TROIS tests dans une seule classe, et une
CLASSE est l'unité INDIVISIBLE de `manage.py test --parallel` : Django affecte
une classe entière à UN worker, qui l'exécute en série. Mesure sur trois runs
CI verts consécutifs (journaux du job `backend-tests-shard (0)`, qui ne
contenait que ce module) :

    run 32439017665 — « Ran 42 tests in 350,345s », dont 348,81 s de silence
                      entre la dernière ligne de TestPayloadPublic
                      (02:14:39.2014982Z) et la première de
                      TestAcceptationGamme (02:20:28.0130228Z)
    run 32434442077 — « Ran 42 tests in 406,976s », silence 405,38 s
    run 32400031804 — « Ran 42 tests in 385,627s », silence 383,97 s

Autrement dit : 3 tests = 99,5 à 99,7 % du module, ~110 à 150 s CHACUN, et
les 39 autres tests de la famille pèsent ensemble ~1,5 s. Tant que ces trois
tests partageaient une classe, ils s'exécutaient l'un après l'autre sur un
seul worker : ~380 s de plancher que NI un shard de plus NI un découpage par
module ne pouvaient franchir.

Un test par classe, une classe par module : les trois blocs deviennent
déplaçables par `scripts/ci_shard.py` ET parallélisables par Django. Les
assertions, elles, sont identiques à l'octet près.

Les deux frères : `test_gammes_offre_acceptation_signature.py` et
`test_gammes_offre_acceptation_choix.py`.

Décision fondateur 2026-08-18 couverte ici : l'acceptation de la gamme
choisie auto-refuse l'autre (YDOCF3).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_acceptation -v 2
"""
from rest_framework.test import APIClient

from apps.ventes.models import Devis, ShareLink
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
