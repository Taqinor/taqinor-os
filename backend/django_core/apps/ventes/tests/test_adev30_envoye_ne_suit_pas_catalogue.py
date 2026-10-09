"""ADEV30 (C-ADEV-041, D-ASTK-1) — un devis ENVOYÉ ne suit plus le barème du
jour sur une retouche qui ne change pas son nombre de panneaux : seules les
lignes d'un BROUILLON suivent le catalogue.

Rejoue la sonde VB r3 : envoyé, barème « par panneau » relevé, PATCH de la
seule désignation d'une AUTRE ligne → la ligne forfait était re-tarifée
(TTC +1 200).

Test-du-test : remettre l'appel inconditionnel de la re-tarification dans
``views/ligne_devis.py`` ⇒ ``test_retouche_sans_rapport_ttc_inchange``
échoue ; retirer le test de statut dans ``domain/lignes.py`` ⇒
``test_catalogue_event_ignore_envoye`` échoue. Source réelle (aucun mock).
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.ventes.domain.catalogue import prix_forfait_ht
from apps.ventes.domain.lignes import retarifer_forfaits_par_panneau
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests import test_qjr220_retarification_reconcilier as q220
from apps.ventes.tests.test_pv18_sync_layout import layout

URL = '/api/django/ventes/devis-lignes/'


class EnvoyeNeSuitPasCatalogueTests(q220._Base):

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _devis_envoye(self):
        devis = self._devis(9, pose_a=9)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        devis.refresh_from_db()
        return devis

    def _relever_bareme(self):
        self.pose.prix_par_panneau_ht += Decimal('100')
        self.pose.save(update_fields=['prix_par_panneau_ht'])

    def test_retouche_sans_rapport_ttc_inchange(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        onduleur = devis.lignes.get(designation=q220.RESEAU)
        resp = self.api.patch('%s%s/' % (URL, onduleur.pk),
                              {'designation': 'Onduleur réseau 5 kW'},
                              format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        # CLAUSE PERSISTANCE — relu en base.
        self.assertEqual(self._prix_pose(devis), fige)

    def test_resync_envoye_bareme_fige(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        # Même nombre de panneaux : aucune re-tarification.
        sync_devis_from_layout(devis, layout(panels=9, kwc=4.95),
                               user=self.user)
        self.assertEqual(self._prix_pose(devis), fige)

    def test_envoye_compte_change_retarife(self):
        devis = self._devis_envoye()
        panneau = devis.lignes.get(designation=q220.PANNEAU)
        resp = self.api.patch('%s%s/' % (URL, panneau.pk),
                              {'quantite': '20'}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi').exists())

    def test_catalogue_event_ignore_envoye(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        # Un événement catalogue (aucun compte « avant » : le nombre de
        # panneaux ne change pas) ne re-tarife jamais un envoyé.
        retarifer_forfaits_par_panneau(devis)
        self.assertEqual(self._prix_pose(devis), fige)

    def test_brouillon_suit_catalogue(self):
        devis = self._devis(9, pose_a=9)
        self._relever_bareme()
        onduleur = devis.lignes.get(designation=q220.RESEAU)
        resp = self.api.patch('%s%s/' % (URL, onduleur.pk),
                              {'designation': 'Onduleur réseau 5 kW'},
                              format='json')
        self.assertEqual(resp.status_code, 200)
        self.pose.refresh_from_db()
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 9))
