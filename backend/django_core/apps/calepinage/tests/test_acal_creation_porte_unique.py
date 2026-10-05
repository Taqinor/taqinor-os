"""ACAL182 — UNE porte de création sur un lead (D-ACAL-12).

Constat C-ACAL-007 (audit 2026-10-04) : quatre portes créaient un calepinage
sur un lead, chacune à sa façon — ``POST calepinages/`` (``perform_create``
nu : ni chatter, ni client du lead, titre vide), ``depuis-lead`` (relecture
maison sans verrou), ``depuis-modele`` sans modèle et la reprise du tracé
public (``liste_calepinages().exists()``) — et rien n'empêchait un second
calepinage OUVERT pour le même lead.

Ce qui est tenu ici, sur les portes RÉELLES et un PostgreSQL réel (aucun
mock du verrou ni de la source) :
  * chaque porte écrit la ligne CREATION, pose le client du lead et le MÊME
    titre de repli ;
  * un second appel ne crée rien : ``depuis-lead`` rend l'existant
    (``cree: false``), les autres répondent 409 ``{lead,
    calepinage_existant}`` (contrat ``calepinage_creation_conflit.json``) ;
  * le verrou consultatif sérialise deux créations concurrentes.

Run :
    python manage.py test apps.calepinage.tests.test_acal_creation_porte_unique -v2
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
import unittest

from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.test import TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.creation import (
    creer_pour_lead,
    ouvrir_ou_creer_pour_lead,
    _verrou_creation,
)
from apps.calepinage.services.reprise_public import reprendre_trace_public
from apps.crm.models import Client, Lead
from apps.records.models import Activity
from authentication.models import Company

from .test_api_liste import URL, BaseApiCalepinage

CONTRAT_CONFLIT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_creation_conflit.json').read_text(encoding='utf-8'))

CONTOUR_LATLNG = [[33.4999, -7.6001], [33.4999, -7.5999],
                  [33.5001, -7.5999], [33.5001, -7.6001]]


def _creations(calepinage):
    return Activity.objects.filter(
        content_type=ContentType.objects.get_for_model(Calepinage),
        object_id=calepinage.pk, kind=Activity.Kind.CREATION).count()


class PorteUniqueTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lead = Client.objects.create(company=self.company,
                                                 nom='Client du lead')

    def _lead(self, nom, **champs):
        return Lead.objects.create(company=self.company, nom=nom,
                                   client=self.client_lead, **champs)

    def _portes(self):
        """``(nom, geste)`` — chaque geste crée sur SON lead et rend le pk."""
        def post_liste(lead):
            reponse = self.api.post(URL, {'lead': lead.pk}, format='json')
            self.assertEqual(reponse.status_code, 201, reponse.data)
            return reponse.data['id']

        def depuis_lead(lead):
            reponse = self.api.post(f'{URL}depuis-lead/', {'lead': lead.pk},
                                    format='json')
            self.assertEqual(reponse.status_code, 201, reponse.data)
            return reponse.data['calepinage']

        def depuis_modele(lead):
            reponse = self.api.post(f'{URL}depuis-modele/',
                                    {'lead_id': lead.pk}, format='json')
            self.assertEqual(reponse.status_code, 201, reponse.data)
            return reponse.data['id']

        def reprise(lead):
            calepinage = reprendre_trace_public(lead.pk, self.company)
            self.assertIsNotNone(calepinage)
            return calepinage.pk

        return (('POST calepinages/', post_liste),
                ('depuis-lead', depuis_lead),
                ('depuis-modele', depuis_modele),
                ('reprise du tracé public', reprise))

    def test_chaque_porte_ecrit_chatter_client_et_meme_titre(self):
        for rang, (nom, geste) in enumerate(self._portes()):
            with self.subTest(porte=nom):
                lead = self._lead(f'Toiture {rang}',
                                  roof_outline=CONTOUR_LATLNG)
                calepinage = Calepinage.objects.get(pk=geste(lead))
                self.assertEqual(calepinage.lead_id, lead.pk)
                self.assertEqual(calepinage.client_id, self.client_lead.pk)
                self.assertEqual(calepinage.titre, f'Calepinage {lead.nom}')
                self.assertEqual(_creations(calepinage), 1)

    def test_second_appel_renvoie_l_existant_409_ou_cree_false(self):
        lead = self._lead('Villa ouverte', roof_outline=CONTOUR_LATLNG)
        existant = creer_pour_lead(lead.pk, self.company, user=self.user)

        reponse = self.api.post(f'{URL}depuis-lead/', {'lead': lead.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['calepinage'], existant.pk)
        self.assertFalse(reponse.data['cree'])

        for url, corps in ((URL, {'lead': lead.pk}),
                           (f'{URL}depuis-modele/', {'lead_id': lead.pk})):
            with self.subTest(porte=url):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
                self.assertEqual(sorted(reponse.data),
                                 sorted(CONTRAT_CONFLIT['exemple']))
                self.assertEqual(reponse.data['calepinage_existant'],
                                 existant.pk)
                self.assertIn(f'#{existant.pk}', reponse.data['lead'])

        self.assertIsNone(reprendre_trace_public(lead.pk, self.company))
        self.assertEqual(
            Calepinage.objects.filter(lead_id=lead.pk).count(), 1)

    def test_responsable_valide_meme_societe(self):
        lead = self._lead('Villa responsable')
        reponse = self.api.post(URL, {'lead': lead.pk,
                                      'responsable': self.user_autre.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('responsable', reponse.data)
        self.assertFalse(Calepinage.objects.filter(lead_id=lead.pk).exists())

        reponse = self.api.post(URL, {'lead': lead.pk,
                                      'responsable': self.user.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).responsable_id,
            self.user.pk)

    def test_le_calepinage_cree_se_renomme(self):
        """Le client du lead posé à la création ne bloque pas un PATCH."""
        lead = self._lead('Villa renommée')
        pk = self.api.post(URL, {'lead': lead.pk}, format='json').data['id']
        reponse = self.api.patch(f'{URL}{pk}/', {'titre': 'Nouveau nom'},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)


@unittest.skipUnless(connection.vendor == 'postgresql',
                     'verrou consultatif PostgreSQL')
class VerrouCreationTest(TransactionTestCase):
    """Deux transactions RÉELLES : B attend que A relâche le verrou."""

    def setUp(self):
        self.company = Company.objects.create(nom='Verrou Co',
                                              slug='acal182-verrou')
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Villa concurrente')

    def test_verrou_serialise_deux_creations(self):
        a_le_verrou = threading.Event()
        relacher = threading.Event()
        resultat = {}

        def fil_a():
            try:
                with transaction.atomic():
                    with _verrou_creation(self.company.pk, self.lead.pk):
                        a_le_verrou.set()
                        resultat['a'] = creer_pour_lead(
                            self.lead.pk, self.company).pk
                        relacher.wait(15)
            finally:
                connection.close()

        def fil_b():
            try:
                a_le_verrou.wait(15)
                calepinage, cree = ouvrir_ou_creer_pour_lead(
                    self.lead.pk, self.company)
                resultat['b'] = (calepinage.pk, cree)
            finally:
                connection.close()

        a = threading.Thread(target=fil_a)
        b = threading.Thread(target=fil_b)
        a.start()
        b.start()
        self.assertTrue(a_le_verrou.wait(15))
        time.sleep(1.0)
        # B est BLOQUÉ sur le verrou tant que A n'a pas validé.
        self.assertNotIn('b', resultat)
        relacher.set()
        a.join(15)
        b.join(15)

        self.assertEqual(resultat['b'], (resultat['a'], False))
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)
