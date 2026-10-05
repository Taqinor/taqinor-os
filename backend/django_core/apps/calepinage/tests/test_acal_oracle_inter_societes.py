"""ACAL298 — un id d'une autre société et un id absent : la MÊME réponse.

Constat C-ACAL-015 (C5, S3). Deux sociétés réelles en base de test, aucun
mock : pour chaque paire (id voisin, id absent), les deux 400 sont
octet-identiques hors l'id cité — même clé de champ, même texte, même code.

* ``devis`` / ``client`` au POST, ``responsable`` au PATCH : bornés par
  ``core.mixins.SameCompanyFKSerializerMixin.get_fields`` ;
* ``module_produit`` / ``onduleur_produit`` / ``optimiseur_produit`` de
  l'entrée électrique : validés par ``apps.stock.selectors.get_produit_scoped``
  AVANT toute écriture (``services/electrique.py:enregistrer_entree``).

Run :
    python manage.py test apps.calepinage.tests.test_acal_oracle_inter_societes -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/calepinage/calepinages/'
ABSENT = 999999


def _normalise(donnees, pk):
    """La réponse rendue comparable : l'id cité remplacé par « N ».

    L'enveloppe additive ``error`` (YAPIC3, ``core.exceptions``) porte un
    ``request_id`` tiré au hasard à CHAQUE requête : il est retiré avant la
    comparaison (le reste de l'enveloppe — code, message, champs — reste
    comparé octet pour octet).
    """
    donnees = dict(donnees)
    enveloppe = donnees.get('error')
    if isinstance(enveloppe, dict):
        donnees['error'] = {k: v for k, v in enveloppe.items()
                            if k != 'request_id'}
    return {cle: [str(m).replace(str(pk), 'N') for m in
                  (valeurs if isinstance(valeurs, list) else [valeurs])]
            for cle, valeurs in donnees.items()}


def _champs(donnees):
    """Les clés de champ du 400, hors l'enveloppe additive ``error``."""
    return [cle for cle in donnees if cle != 'error']


class OracleInterSocietesTest(TestCase):
    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL298 Six',
                                              slug='acal298-six')
        self.voisine = Company.objects.create(nom='ACAL298 Deux',
                                              slug='acal298-deux')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal298_admin', password='x', company=self.societe,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.lead = Lead.objects.create(company=self.societe,
                                        nom='Toiture ACAL298')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=self.lead.pk, titre='Villa 298')

        self.client_voisin = Client.objects.create(company=self.voisine,
                                                   nom='Client voisin')
        self.devis_voisin = Devis.objects.create(
            company=self.voisine, client=self.client_voisin,
            reference='DEV-ACAL298-VOISIN')
        self.user_voisin = User.objects.create_user(
            username='acal298_voisin', password='x', company=self.voisine)
        self.produit_voisin = Produit.objects.create(
            company=self.voisine, nom='Module voisin', sku='ACAL298-MOD',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)

    # ── utilitaires ─────────────────────────────────────────────────────
    def _paire(self, envoi, etranger):
        r1 = envoi(etranger)
        r2 = envoi(ABSENT)
        self.assertEqual(r1.status_code, 400, r1.data)
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertEqual(_normalise(r1.data, etranger),
                         _normalise(r2.data, ABSENT))
        return r1

    def _instantane(self):
        c = Calepinage.objects.get(pk=self.calepinage.pk)
        return (c.devis_id, c.client_id, c.responsable_id,
                (c.resultat or {}).get('entree_electrique'))

    # ── sérialiseur : devis / client / responsable ─────────────────────
    def test_devis_etranger_et_absent_meme_reponse(self):
        # Réconciliation vague B : ACAL33 fait de ``lier_devis`` le SEUL
        # écrivain de ``Calepinage.devis`` — le champ est en LECTURE SEULE au
        # CRUD. Un devis d'une autre société et un devis absent reçoivent donc
        # la MÊME réponse : la création réussit, rien n'est lié, aucun 400
        # ne trahit l'existence du devis voisin. ACAL182 (un seul calepinage
        # ouvert par lead) : chaque envoi vise un lead encore libre.
        reponses = []
        for pk in (self.devis_voisin.pk, ABSENT):
            libre = Lead.objects.create(company=self.societe,
                                        nom=f'Lead libre {pk}')
            reponse = self.api.post(URL, {
                'titre': 'Nouveau', 'lead': libre.pk, 'devis': pk},
                format='json')
            self.assertEqual(reponse.status_code, 201, reponse.data)
            self.assertIsNone(reponse.data['devis'])
            self.assertIsNone(
                Calepinage.objects.get(pk=reponse.data['id']).devis_id)
            reponses.append(sorted(reponse.data))
        self.assertEqual(reponses[0], reponses[1])
        self.assertFalse(Calepinage.objects.filter(
            devis_id=self.devis_voisin.pk).exists())

    def test_client_etranger_et_absent_meme_reponse(self):
        r = self._paire(lambda pk: self.api.post(URL, {
            'titre': 'Nouveau', 'client': pk}, format='json'),
            self.client_voisin.pk)
        self.assertEqual(_champs(r.data), ['client'])
        self.assertEqual(r.data['client'][0].code, 'does_not_exist')

    def test_responsable_etranger_et_absent_meme_reponse_au_patch(self):
        avant = self._instantane()
        r = self._paire(lambda pk: self.api.patch(
            f'{URL}{self.calepinage.pk}/', {'responsable': pk},
            format='json'), self.user_voisin.pk)
        self.assertEqual(_champs(r.data), ['responsable'])
        self.assertEqual(r.data['responsable'][0].code, 'does_not_exist')
        self.assertEqual(self._instantane(), avant)

    # ── entrée électrique : produits désignés ──────────────────────────
    def _entree(self, champ):
        return lambda pk: self.api.post(
            f'{URL}{self.calepinage.pk}/entree-electrique/', {champ: pk},
            format='json')

    def test_entree_electrique_produit_etranger_refuse_comme_absent(self):
        for champ in ('module_produit', 'onduleur_produit',
                      'optimiseur_produit'):
            with self.subTest(champ=champ):
                r = self._paire(self._entree(champ), self.produit_voisin.pk)
                self.assertEqual(_champs(r.data), [champ])
                self.assertEqual(
                    _normalise(r.data, self.produit_voisin.pk)[champ],
                    ['Produit introuvable dans votre catalogue (#N).'])

    def test_entree_electrique_refus_n_ecrit_rien(self):
        avant = self._instantane()
        r = self.api.post(
            f'{URL}{self.calepinage.pk}/entree-electrique/',
            {'module_produit': self.produit_voisin.pk, 'dc_m': 42.0},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(self._instantane(), avant)

    def test_entree_electrique_produit_de_la_societe_et_effacement_admis(self):
        mien = Produit.objects.create(
            company=self.societe, nom='Mon module', sku='ACAL298-MIEN',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)
        from apps.calepinage.services.electrique import enregistrer_entree
        entree = enregistrer_entree(self.calepinage,
                                    {'module_produit': mien.pk})
        self.assertEqual(entree['module_produit'], mien.pk)
        entree = enregistrer_entree(self.calepinage, {'module_produit': None})
        self.assertIsNone(entree['module_produit'])
        entree = enregistrer_entree(self.calepinage, {'onduleur_produit': ''})
        self.assertEqual(entree['onduleur_produit'], '')
