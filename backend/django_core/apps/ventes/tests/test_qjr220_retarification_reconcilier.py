# -*- coding: utf-8 -*-
"""QJR220 — la re-tarification des forfaits par panneau tourne sur les DEUX
chemins qui CHANGENT le compte de panneaux.

TEST ROUGE D'ABORD : ``lignes.retarifer_forfaits_par_panneau`` (QJR83) était
correcte et honorait D12, mais elle n'avait qu'UN appelant dans tout le dépôt
(``lignes.remplacer_lignes``). Or ``MODE_RECONCILIER`` n'appelle JAMAIS
``ecrire_lignes`` alors que c'est LE mode qui change un compte de panneaux sur
un devis existant, et ``LigneDevisViewSet`` en change aussi : une sync-layout
9 → 20 panneaux laissait la pose au barème de 9 — de l'argent faux sur un
document client (l'incident 9→20 que le fichier de test de QJR83 nomme).

Aucun montant n'est écrit en dur ici : tous sont DÉRIVÉS de
``catalogue.prix_forfait_ht``, la seule formule.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr220_retarification_reconcilier -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.catalogue import prix_forfait_ht
from apps.ventes.models import Devis
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests.test_pv18_sync_layout import layout, make_company

User = get_user_model()

PANNEAU = 'Panneau Jinko 550W'
RESEAU = 'Onduleur réseau Huawei 5kW'
POSE = 'Installation'

#: Le barème du fondateur pour la POSE (``seed_catalogue``) : part fixe + part
#: par panneau. Les MONTANTS attendus sont dérivés, jamais recopiés.
POSE_FIXE, POSE_PAR_PANNEAU = '2000', '250'


class _Base(TestCase):

    def setUp(self):
        self.company = make_company('qjr220-co')
        self.user = User.objects.create_user(
            username='qjr220user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR220')
        self.panneau = Produit.objects.create(
            company=self.company, nom=PANNEAU, sku='QJR220-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=500)
        self.onduleur = Produit.objects.create(
            company=self.company, nom=RESEAU, sku='QJR220-ONDR',
            prix_vente=Decimal('14000'), prix_achat=Decimal('1'),
            quantite_stock=500)
        self.pose = Produit.objects.create(
            company=self.company, nom=POSE, sku='QJR220-INST',
            prix_vente=Decimal('4800'), prix_achat=Decimal('1'),
            quantite_stock=500,
            prix_fixe_ht=Decimal(POSE_FIXE),
            prix_par_panneau_ht=Decimal(POSE_PAR_PANNEAU))
        self.compteur = 0

    def _devis(self, nb_panneaux, *, pose_a, prix_manuel=False):
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR220-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'))
        devis.lignes.create(
            produit=self.panneau, designation=PANNEAU,
            quantite=Decimal(str(nb_panneaux)),
            prix_unitaire=self.panneau.prix_vente, remise=Decimal('0'),
            ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation=RESEAU, quantite=Decimal('1'),
            prix_unitaire=self.onduleur.prix_vente, remise=Decimal('0'),
            ordre=2)
        devis.lignes.create(
            produit=self.pose, designation=POSE, quantite=Decimal('1'),
            prix_unitaire=prix_forfait_ht(self.pose, pose_a),
            remise=Decimal('0'), ordre=3, prix_manuel=prix_manuel)
        return devis

    def _prix_pose(self, devis):
        return devis.lignes.get(designation=POSE).prix_unitaire


class CheminReconcilier(_Base):
    """MODE_RECONCILIER — l'incident 9 → 20, épinglé."""

    def test_sync_layout_9_vers_20_requote_la_pose(self):
        """LE ROUGE : la pose restait au barème de 9 panneaux."""
        devis = self._devis(9, pose_a=9)
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 9))

        sync_devis_from_layout(devis, layout(panels=20, kwc=11.0),
                               user=self.user)

        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))

    def test_les_abstentions_D12_sont_preservees_et_dites(self):
        """Un prix SAISI À LA MAIN n'est jamais réécrit — et on le DIT."""
        devis = self._devis(9, pose_a=9, prix_manuel=True)
        fige = self._prix_pose(devis)

        resultat = sync_devis_from_layout(
            devis, layout(panels=20, kwc=11.0), user=self.user)

        self.assertEqual(self._prix_pose(devis), fige)
        messages = ' | '.join(resultat.get('avertissements') or ())
        self.assertIn(POSE, messages)

    def test_un_layout_inchange_ne_touche_rien(self):
        """Non-régression : aucune écriture quand rien ne bouge."""
        devis = self._devis(20, pose_a=20)
        avant = self._prix_pose(devis)
        sync_devis_from_layout(devis, layout(panels=20, kwc=11.0),
                               user=self.user)
        self.assertEqual(self._prix_pose(devis), avant)


class CheminViewsetDeLigne(_Base):
    """``LigneDevisViewSet`` — l'autre chemin qui change le compte."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_modifier_la_quantite_de_panneaux_requote_la_pose(self):
        """LE ROUGE (second chemin) : la pose restait au barème d'avant."""
        devis = self._devis(9, pose_a=9)
        ligne = devis.lignes.get(designation=PANNEAU)

        resp = self.api.patch(
            '/api/django/ventes/devis-lignes/%s/' % ligne.id,
            {'quantite': '20'}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))

    def test_retirer_une_ligne_de_panneaux_requote_aussi(self):
        devis = self._devis(9, pose_a=9)
        ajout = self.api.post(
            '/api/django/ventes/devis-lignes/',
            {'devis': devis.id, 'produit': self.panneau.id,
             'designation': PANNEAU, 'quantite': '11',
             'prix_unitaire': '1100', 'remise': '0'}, format='json')
        self.assertEqual(ajout.status_code, 201, getattr(ajout, 'data', ajout))
        # 9 + 11 = 20 panneaux.
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))

        resp = self.api.delete(
            '/api/django/ventes/devis-lignes/%s/' % ajout.data['id'])
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', resp))
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 9))

    def test_ajouter_une_ligne_de_panneaux_requote(self):
        devis = self._devis(9, pose_a=9)
        resp = self.api.post(
            '/api/django/ventes/devis-lignes/',
            {'devis': devis.id, 'produit': self.panneau.id,
             'designation': PANNEAU, 'quantite': '11',
             'prix_unitaire': '1100', 'remise': '0'}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))
