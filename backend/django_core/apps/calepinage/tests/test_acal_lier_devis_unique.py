"""ACAL33 — ``lier_devis`` est le SEUL écrivain de ``Calepinage.devis``.

Quatre portes, toutes contre la base réelle (aucun mock) :

* le CRUD (PATCH ``{devis}``) ne touche plus le champ — il est LU seulement ;
* ``depuis-modele`` avec un devis déjà rattaché rend un 400 NOMMÉ et ne crée
  aucune copie ;
* ``lier_devis`` refuse de re-pointer un calepinage lié à un devis ACTIF en
  nommant les DEUX références, mais re-pointe un ancien devis INACTIF
  (remplacé par une révision — prérequis D-ACAL-3) ;
* la base garantit un calepinage par devis et par société
  (``UniqueConstraint calepinage_un_par_devis``).
"""
from __future__ import annotations

import copy

from django.db import IntegrityError, transaction

from apps.calepinage.models import Calepinage
from apps.calepinage.services.liens import LiaisonRefusee, lier_devis
from apps.calepinage.services.modeles import marquer_modele
from apps.ventes.models import Devis

from .test_api_liste import URL, BaseApiCalepinage, url_detail
from .test_calx351_depuis_modele import DOCUMENT

URL_DEPUIS_MODELE = f'{URL}depuis-modele/'


class LierDevisSeulEcrivainTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3301')
        self.devis_2 = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3302')
        self.a = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa A')
        lier_devis(self.a, self.devis.pk)
        self.b = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa B')

    def test_patch_devis_sans_effet(self):
        # ACAL179 — la clé en lecture seule est REFUSÉE en la nommant (jamais
        # un 200 silencieux) ; dans tous les cas, devis n'est pas écrit.
        reponse = self.api.patch(url_detail(self.b.pk),
                                 {'devis': self.devis_2.pk}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('devis', reponse.data)
        self.b.refresh_from_db()
        self.assertIsNone(self.b.devis_id,
                          'le CRUD ne doit jamais écrire Calepinage.devis')
        self.a.refresh_from_db()
        self.assertEqual(self.a.devis_id, self.devis.pk)

    def test_depuis_modele_devis_deja_lie_400(self):
        modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Modèle villa',
            roof_layout=copy.deepcopy(DOCUMENT))
        marquer_modele(modele)
        avant = Calepinage.objects.count()
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': modele.pk, 'lead_id': self.lead.pk,
            'devis_id': self.devis.pk}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        message = str(reponse.data['devis_id'])
        self.assertIn('DEV-202610-3301', message)
        self.assertIn('Villa A', message)
        self.assertIn(f'#{self.a.pk}', message)
        self.assertEqual(Calepinage.objects.count(), avant,
                         'aucune copie ne doit être créée')

    def test_depuis_modele_devis_libre_passe_par_lier_devis(self):
        # ACAL117 (D-ACAL-15) — le lead cible d'un modèle porte un repère.
        self.lead.roof_point = {'lat': 33.5, 'lng': -7.6}
        self.lead.save(update_fields=['roof_point'])
        modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Modèle villa',
            roof_layout=copy.deepcopy(DOCUMENT))
        marquer_modele(modele)
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': modele.pk, 'lead_id': self.lead.pk,
            'devis_id': self.devis_2.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.devis_id, self.devis_2.pk)

    def test_lier_devis_refuse_repointage_devis_actif(self):
        with self.assertRaises(LiaisonRefusee) as refus:
            lier_devis(self.a, self.devis_2.pk)
        message = str(refus.exception)
        self.assertEqual(refus.exception.champ, 'devis')
        self.assertIn('DEV-202610-3301', message)
        self.assertIn('DEV-202610-3302', message)
        self.assertNotIn('détachez', message)
        self.a.refresh_from_db()
        self.assertEqual(self.a.devis_id, self.devis.pk)

    def test_lier_devis_accepte_ancien_inactif(self):
        Devis.objects.filter(pk=self.devis.pk).update(is_active=False)
        lier_devis(self.a, self.devis_2.pk)
        self.a.refresh_from_db()
        self.assertEqual(self.a.devis_id, self.devis_2.pk)

    def test_contrainte_un_calepinage_par_devis(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Calepinage.objects.create(
                    company=self.company, lead_id=self.lead.pk,
                    titre='Doublon', devis=self.devis)
        # Sans devis, aucune limite.
        Calepinage.objects.create(company=self.company,
                                  lead_id=self.lead.pk, titre='Libre 1')
        Calepinage.objects.create(company=self.company,
                                  lead_id=self.lead.pk, titre='Libre 2')


class GenererDevisNeRepointeJamaisTest(BaseApiCalepinage):
    """Le pont « Générer le devis » hérite de la règle : un calepinage lié à
    un devis ACTIF n'est jamais re-pointé — 409 NOMMÉ avant toute création
    (jamais un devis orphelin, jamais un 500)."""

    def test_lie_a_un_actif_d_une_autre_empreinte_409_sans_creation(self):
        from unittest import mock

        from .test_api_generer_devis import LAYOUT, url_generer

        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3303', layout_hash='d' * 64)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa C',
            roof_layout=LAYOUT, layout_hash='c' * 64)
        lier_devis(calepinage, devis.pk)
        avant = Devis.objects.count()
        with mock.patch(
                'apps.ventes.services.validate_composition_for_layout',
                return_value=[]):
            reponse = self.api.post(url_generer(calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('DEV-202610-3303', str(reponse.data))
        self.assertEqual(Devis.objects.count(), avant)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.devis_id, devis.pk)
