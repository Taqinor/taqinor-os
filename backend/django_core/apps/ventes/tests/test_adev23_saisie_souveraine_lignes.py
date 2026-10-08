"""ADEV23 (C-ADEV-030) — un prix (resp. une quantité) TAPÉ via
``/devis-lignes/`` pose ``prix_manuel`` (resp. ``quantite_manuelle``) et la
réponse HTTP égale la ligne RELUE en base après la re-tarification.

Rejoue la sonde VB p1 : POST d'un prix sur un forfait au panneau → la réponse
disait 12 345, la base gardait le barème.

Test-du-test : retirer la pose de ``prix_manuel`` ⇒ ``test_prix_tape_conserve``
échoue ; supprimer le ``refresh_from_db`` de la réponse ⇒
``test_reponse_egale_base`` échoue. Source réelle :
``retarifer_forfaits_par_panneau`` (aucun mock).
"""
from decimal import Decimal

from apps.ventes.domain.catalogue import prix_forfait_ht
from apps.ventes.tests import test_qjr220_retarification_reconcilier as q220
from rest_framework.test import APIClient

URL = '/api/django/ventes/devis-lignes/'


class SaisieSouveraineLignesTests(q220._Base):

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.devis = self._devis(9, pose_a=9)

    def _poster_pose(self, **corps):
        donnees = {'devis': self.devis.id, 'produit': self.pose.id,
                   'designation': q220.POSE, 'quantite': '1', 'remise': '0'}
        donnees.update(corps)
        resp = self.api.post(URL, donnees, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        return resp

    def test_prix_tape_conserve(self):
        resp = self._poster_pose(prix_unitaire='12345')
        ligne = self.devis.lignes.get(pk=resp.data['id'])
        self.assertEqual(ligne.prix_unitaire, Decimal('12345'))
        self.assertTrue(ligne.prix_manuel)

        patch = self.api.patch('%s%s/' % (URL, ligne.pk),
                               {'prix_unitaire': '22222'}, format='json')
        self.assertEqual(patch.status_code, 200, getattr(patch, 'data', patch))
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, Decimal('22222'))
        self.assertTrue(ligne.prix_manuel)
        # CLAUSE PERSISTANCE — relecture par l'API.
        relu = self.api.get('%s%s/' % (URL, ligne.pk))
        self.assertEqual(Decimal(str(relu.data['prix_unitaire'])),
                         Decimal('22222'))
        self.assertTrue(relu.data['prix_manuel'])

    def test_reponse_egale_base(self):
        # La ligne pose existante (barème de 9 panneaux) : un PATCH de la
        # quantité de panneaux re-tarife la pose ; la réponse de la ligne
        # PANNEAU et celle d'une ligne forfait non saisie suivent la base.
        pose = self.devis.lignes.get(designation=q220.POSE)
        resp = self.api.patch('%s%s/' % (URL, pose.pk),
                              {'designation': q220.POSE}, format='json')
        self.assertEqual(resp.status_code, 200)
        pose.refresh_from_db()
        self.assertEqual(Decimal(str(resp.data['prix_unitaire'])),
                         pose.prix_unitaire)
        # Un POST d'un forfait SANS prix tapé : la réponse égale le prix
        # re-tarifé en base (barème du compte courant), pas le corps.
        ajout = self._poster_pose(prix_unitaire='1')
        ligne = self.devis.lignes.get(pk=ajout.data['id'])
        self.assertEqual(Decimal(str(ajout.data['prix_unitaire'])),
                         ligne.prix_unitaire)
        self.assertEqual(ajout.data['prix_manuel'], ligne.prix_manuel)

    def test_quantite_tapee_conservee(self):
        panneau = self.devis.lignes.get(designation=q220.PANNEAU)
        resp = self.api.patch('%s%s/' % (URL, panneau.pk),
                              {'quantite': '12'}, format='json')
        self.assertEqual(resp.status_code, 200)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite, Decimal('12'))
        self.assertTrue(panneau.quantite_manuelle)
        self.assertTrue(resp.data['quantite_manuelle'])

    def test_prix_manuel_false_explicite(self):
        resp = self._poster_pose(prix_unitaire='12345', prix_manuel=False)
        ligne = self.devis.lignes.get(pk=resp.data['id'])
        self.assertFalse(ligne.prix_manuel)
        # Barème : la ligne suit le compte courant (9 panneaux).
        self.assertEqual(ligne.prix_unitaire, prix_forfait_ht(self.pose, 9))
        self.assertEqual(Decimal(str(resp.data['prix_unitaire'])),
                         ligne.prix_unitaire)

    def test_ligne_sans_prix_reste_au_bareme(self):
        pose = self.devis.lignes.get(designation=q220.POSE)
        self.api.patch('%s%s/' % (URL, pose.pk),
                       {'designation': 'Installation (pose)'}, format='json')
        pose.refresh_from_db()
        self.assertFalse(pose.prix_manuel)
