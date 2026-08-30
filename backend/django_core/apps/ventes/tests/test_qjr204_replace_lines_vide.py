"""QJR204 — ``POST /replace-lines`` avec ``lignes: []`` REFUSE, il n'efface pas.

TEST ROUGE D'ABORD : l'endpoint traversait ``ecrire_lignes`` →
``domain/lignes.remplacer_lignes``, qui SUPPRIME puis recrée — une liste vide
effaçait donc TOUTES les lignes d'un devis brouillon/envoyé et répondait 200,
là où ``/atomic`` refusait déjà l'ensemble vide par un 400.

LE VERDICT « AUCUN FLUX LÉGITIME », ÉCRIT : le balayage du dépôt ne trouve
qu'UN appelant de production — ``frontend/src/api/ventesApi.js``
``replaceLignesDevis``, invoqué par ``DevisGenerator.jsx`` à l'enregistrement
d'une édition — et l'écran n'offre AUCUN geste « vider le devis » : sa charge
utile est toujours la liste des lignes restantes. Un vidage devra donc se
DÉCLARER (``remplacer_lignes(..., autoriser_vidage=True)``), jamais s'obtenir
par une liste vide.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr204_replace_lines_vide -v 2
"""
from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain.lignes import MSG_REMPLACEMENT_VIDE, remplacer_lignes
from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Panneau mono 550W', '14', '1100'),
    ('Installation', '1', '4000'),
]


class TestQJR204(APITestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR204-0001')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _url(self, devis=None):
        return ('/api/django/ventes/devis/%s/replace-lines/'
                % (devis or self.devis).id)

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_liste_vide_refusee_en_400_fr_et_lignes_intactes(self):
        resp = self.api.post(self._url(), {'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertEqual(resp.data['detail'], MSG_REMPLACEMENT_VIDE)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_le_refus_est_le_meme_que_celui_de_atomic(self):
        """``/atomic`` refusait déjà l'ensemble vide : les deux chemins
        d'écriture de l'écran répondent maintenant 400 tous les deux."""
        resp = self.api.post(
            '/api/django/ventes/devis/atomic/',
            {'client': self.client_obj.id, 'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_devis_envoye_aussi_protege(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        resp = self.api.post(self._url(), {'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    # ── L'ÉCRIVAIN UNIQUE PORTE LA MÊME GARDE ───────────────────────────────
    def test_ecrivain_unique_refuse_la_liste_vide(self):
        with self.assertRaises(ValueError) as leve:
            remplacer_lignes(self.devis, [], self.company)
        self.assertEqual(str(leve.exception), MSG_REMPLACEMENT_VIDE)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_ecrivain_unique_refuse_composition_none(self):
        """``ecrire_lignes(composition=None)`` traduit en liste vide : le même
        refus le couvre, sans garde séparée."""
        from apps.ventes.domain.pipeline import ecrire_lignes

        with self.assertRaises(ValueError):
            ecrire_lignes(self.devis, None, company=self.company)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_vidage_explicite_reste_possible(self):
        """Un futur flux de vidage DÉCLARE son intention — il ne l'obtient pas
        par omission."""
        remplacer_lignes(self.devis, [], self.company, autoriser_vidage=True)
        self.assertEqual(self.devis.lignes.count(), 0)

    # ── NON-RÉGRESSION ──────────────────────────────────────────────────────
    def test_remplacement_normal_inchange(self):
        produit = self.devis.lignes.first().produit
        resp = self.api.post(self._url(), {'lignes': [{
            'produit': produit.id, 'designation': 'Panneau mono 550W',
            'quantite': '12', 'prix_unitaire': '1100', 'ordre': 0,
        }]}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), 1)
