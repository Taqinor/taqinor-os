"""ACAL90 (C-ACAL-111, D-ACAL-22) — une resynchronisation ne recrée plus une
ligne de kit RETIRÉE À LA MAIN : le devis mémorise la classe retirée
(``etude_params.kit_retire``) et la réponse le DIT dans ``avertissements``.

Vraies Devis/LigneDevis (devis composé par ``build_devis_from_layout``),
suppression par l'API réelle, resynchronisation réelle (``sync-layout``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_kit_retire"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.catalogue import classer_produit
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_from_layout
from authentication.models import Company

User = get_user_model()


def _layout(panneaux):
    return {'scenario': 'reseau', 'panelWatt': 550,
            'result': {'panels': panneaux, 'kwc': round(panneaux * 0.55, 2),
                       'annualKwh': 9000, 'savings': 8000}}


def _transports(devis):
    return [li for li in Devis.objects.get(pk=devis.pk).lignes.all()
            if classer_produit(li.designation or '') == 'transport']


def _signature_hors_panneau(devis):
    return sorted(
        (li.designation, str(li.quantite), str(li.prix_unitaire))
        for li in Devis.objects.get(pk=devis.pk).lignes.all()
        if classer_produit(li.designation or '') != 'panneau')


def _chaines(valeur):
    """Toutes les chaînes EXACTES d'un ``build_quote_data`` (les
    désignations de lignes y figurent telles quelles)."""
    if isinstance(valeur, str):
        return {valeur.strip()}
    if isinstance(valeur, dict):
        valeur = list(valeur.values())
    if isinstance(valeur, (list, tuple)):
        sortie = set()
        for element in valeur:
            sortie |= _chaines(element)
        return sortie
    return set()


class KitRetireALaMain(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL90 Co',
                                              slug='acal90-co')
        self.user = User.objects.create_user(
            username='acal90', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL90')
        self.produits = {}
        for nom, sku, prix in (
                ('Panneau Jinko 550W', 'A90-PAN', '1100'),
                ('Onduleur réseau Growatt 10kW', 'A90-OND', '14000'),
                ('Transport', 'A90-TRA', '1000')):
            self.produits[sku] = Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
        self.devis = build_devis_from_layout(
            layout=_layout(10), user=self.user, company=self.company,
            client=self.client_obj)
        transports = _transports(self.devis)
        self.assertEqual(len(transports), 1, 'le kit porte un Transport')
        # Le prix négocié (900) que la recréation aurait remplacé par 1000.
        transports[0].prix_unitaire = Decimal('900')
        transports[0].save(update_fields=['prix_unitaire'])
        self.transport = transports[0]

    def _supprimer_transport(self):
        r = self.api.delete(
            f'/api/django/ventes/devis-lignes/{self.transport.id}/')
        self.assertIn(r.status_code, (200, 204), r.content)

    def _sync(self, panneaux):
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/sync-layout/',
            _layout(panneaux), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data

    def _marqueur(self):
        return (Devis.objects.get(pk=self.devis.pk).etude_params
                or {}).get('kit_retire')

    def test_devis_neuf_sans_marqueur(self):
        self.assertIsNone(self._marqueur())

    def test_suppression_ligne_kit_pose_le_marqueur(self):
        self._supprimer_transport()
        self.assertEqual(self._marqueur(), ['transport'])

    def test_resync_ne_recree_pas_transport_retire(self):
        self._supprimer_transport()
        resultat = self._sync(11)
        self.assertFalse(resultat['inchange'])
        self.assertEqual(_transports(self.devis), [])
        # Second sync sans changement : inchangé, toujours aucun Transport.
        self.assertTrue(self._sync(11)['inchange'])
        self.assertEqual(_transports(self.devis), [])
        # Ce que le client voit (PDF /proposal) : aucune ligne Transport.
        from apps.ventes.quote_engine.builder import build_quote_data
        valeurs = _chaines(build_quote_data(
            Devis.objects.get(pk=self.devis.pk)))
        self.assertNotIn('Transport', valeurs)

    def test_resync_annonce_la_classe_non_recreee(self):
        self._supprimer_transport()
        resultat = self._sync(11)
        self.assertTrue(
            any('Transport non recréé' in a
                for a in resultat['avertissements']),
            resultat['avertissements'])

    def test_reajout_manuel_retire_le_marqueur(self):
        self._supprimer_transport()
        produit = self.produits['A90-TRA']
        r = self.api.post('/api/django/ventes/devis-lignes/', {
            'devis': self.devis.id, 'produit': produit.id,
            'designation': produit.nom, 'quantite': '1',
            'prix_unitaire': '900', 'remise': '0'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(self._marqueur())

    def test_resync_envoye_total_inchange_hors_panneau(self):
        self._supprimer_transport()
        Devis.objects.filter(pk=self.devis.pk).update(statut='envoye')
        avant = _signature_hors_panneau(self.devis)
        self._sync(11)
        devis = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(devis.statut, 'envoye')
        self.assertEqual(_signature_hors_panneau(self.devis), avant)
        panneaux = [li for li in devis.lignes.all()
                    if classer_produit(li.designation or '') == 'panneau']
        self.assertEqual(sum(int(li.quantite) for li in panneaux), 11)
