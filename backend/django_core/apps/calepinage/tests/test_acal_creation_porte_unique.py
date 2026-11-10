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
import unittest

from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.test import TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.creation import (
    _creer_pour_lead,
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

    def _poser_trace(self, lead):
        """Le tracé public posé APRÈS la création du lead.

        Un lead CRÉÉ avec un tracé déclenche déjà la reprise (récepteur
        ``lead_created`` → ``reprendre_trace_public``, CAL110) : la porte
        serait franchie avant le geste testé. ``update`` n'émet aucun
        signal — le geste mesuré est alors le SEUL créateur.
        """
        Lead.objects.filter(pk=lead.pk).update(roof_outline=CONTOUR_LATLNG)
        lead.refresh_from_db()
        return lead

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
            self._poser_trace(lead)
            calepinage = reprendre_trace_public(lead.pk, self.company)
            self.assertIsNotNone(calepinage)
            return calepinage.pk

        return (('POST calepinages/', post_liste),
                ('depuis-lead', depuis_lead),
                ('depuis-modele', depuis_modele),
                ('reprise du tracé public', reprise))

    def test_lead_hors_portee_404_sur_chaque_porte(self):
        """ACON3 — un Commercial A (portée « soi ») ne crée, ne rattache, ni
        ne duplique rien sur le lead d'un collègue B : chaque porte répond
        comme pour un lead absent ; sur son propre lead, 201."""
        from django.contrib.auth import get_user_model

        from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
        from apps.calepinage.services.modeles import marquer_modele
        from apps.roles.models import Role
        from apps.roles.permissions_registre import SCOPE_SELF

        from .test_calx370_projet_json import fichier

        User = get_user_model()
        role = Role.objects.create(
            company=self.company, nom='Commercial ACON3',
            permissions=[CAL_VOIR, CAL_GERER, SCOPE_SELF])
        a = User.objects.create_user(username='acon3_a', password='x',
                                     company=self.company, role=role)
        b = User.objects.create_user(username='acon3_b', password='x',
                                     company=self.company, role=role)
        api_a = self._client(a)
        lead_a = self._lead('Villa de A', owner=a)
        lead_b1 = self._lead('Villa de B', owner=b)
        modele = Calepinage.objects.create(company=self.company,
                                           client=self.client_lead,
                                           titre='Modèle ACON3')
        marquer_modele(modele, user=self.user)
        c = _creer_pour_lead(lead_a.pk, self.company, user=a)
        motif = f'Lead introuvable (#{lead_b1.pk}).'
        gestes = (
            ('depuis-lead', 404, lambda: api_a.post(
                f'{URL}depuis-lead/', {'lead': lead_b1.pk}, format='json')),
            ('POST calepinages/', 404, lambda: api_a.post(
                URL, {'lead': lead_b1.pk}, format='json')),
            ('PATCH lead', 404, lambda: api_a.patch(
                f'{URL}{c.pk}/', {'lead': lead_b1.pk}, format='json')),
            ('depuis-modele', 404, lambda: api_a.post(
                f'{URL}depuis-modele/',
                {'modele_id': modele.pk, 'lead_id': lead_b1.pk},
                format='json')),
            ('import-projet', 404, lambda: api_a.post(
                f'{URL}import-projet/',
                {'projet': fichier(), 'lead': lead_b1.pk}, format='json')),
            # Dupliquer : le MÊME refus qu'un lead absent de la société.
            ('dupliquer', 400, lambda: api_a.post(
                f'{URL}{c.pk}/dupliquer/', {'lead': lead_b1.pk},
                format='json')),
        )
        for nom, attendu, geste in gestes:
            with self.subTest(porte=nom):
                reponse = geste()
                self.assertEqual(reponse.status_code, attendu, reponse.data)
                if nom != 'depuis-modele':
                    self.assertIn(motif, str(reponse.data))
        self.assertFalse(
            Calepinage.objects.filter(lead_id=lead_b1.pk).exists())
        c.refresh_from_db()
        self.assertEqual(c.lead_id, lead_a.pk)
        # Sur SON lead, A crée comme avant.
        lead_a2 = self._lead('Villa 2 de A', owner=a)
        reponse = api_a.post(f'{URL}depuis-lead/', {'lead': lead_a2.pk},
                             format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        # La reprise du tracé public (sans utilisateur) reste inchangée.
        self._poser_trace(lead_b1)
        self.assertIsNotNone(reprendre_trace_public(lead_b1.pk, self.company))

    def test_creation_corps_multipart_refuse_415(self):
        # CI #997 fuzz : ``responsable``/``custom_data`` sont typés (clé, objet
        # JSON) — un formulaire n'en porte que des chaînes : JSON seul (415).
        lead = self._lead('Villa multipart')
        reponse = self.api.post(
            URL, {'lead_id': lead.pk, 'responsable': 'None'},
            format='multipart')
        self.assertEqual(reponse.status_code, 415, reponse.content)
        self.assertFalse(Calepinage.objects.filter(lead_id=lead.pk).exists())

    def test_chaque_porte_ecrit_chatter_client_et_meme_titre(self):
        for rang, (nom, geste) in enumerate(self._portes()):
            with self.subTest(porte=nom):
                lead = self._lead(f'Toiture {rang}')
                calepinage = Calepinage.objects.get(pk=geste(lead))
                self.assertEqual(calepinage.lead_id, lead.pk)
                self.assertEqual(calepinage.client_id, self.client_lead.pk)
                # ACAL300 — jamais le nom d'une personne par défaut : le titre
                # reste vide, le nom affiché retombe sur « Calepinage #N ».
                self.assertEqual(calepinage.titre, '')
                self.assertEqual(str(calepinage), f'Calepinage #{calepinage.pk}')
                self.assertEqual(_creations(calepinage), 1)

    def test_second_appel_renvoie_l_existant_409_ou_cree_false(self):
        lead = self._lead('Villa ouverte')
        existant = _creer_pour_lead(lead.pk, self.company, user=self.user)
        self._poser_trace(lead)

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

    def test_depuis_lead_inconnu_404_et_corps_patch_publie_ferme(self):
        # ENF11 (nocturne 15/10) — lead bien formé inconnu de la société :
        # 404 (comme depuis-modele) ; le PATCH publie ses seules clés admises.
        reponse = self.api.post(f'{URL}depuis-lead/', {'lead': 999999999},
                                format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        from apps.calepinage.serializers import CalepinageSerializer
        cles = CalepinageSerializer.cles_patch()
        self.assertIn('titre', cles)
        self.assertIn('id', cles)
        self.assertNotIn('nom', cles)
        self.assertNotIn('layout_hash', cles)

    def test_responsable_valide_meme_societe(self):
        lead = self._lead('Villa responsable')
        reponse = self.api.post(URL, {'lead': lead.pk,
                                      'responsable': self.user_autre.pk},
                                format='json')
        # compte d'une autre société = id inconnu pour celle-ci : 404 (doctrine
        # IdInconnu404Mixin), corps nommé sous ``responsable``.
        self.assertEqual(reponse.status_code, 404, reponse.data)
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
                        resultat['a'] = _creer_pour_lead(
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
        # B est BLOQUÉ sur le verrou tant que A n'a pas validé : il est
        # toujours vivant après une seconde d'attente sur lui.
        b.join(1.0)
        self.assertTrue(b.is_alive())
        self.assertNotIn('b', resultat)
        relacher.set()
        a.join(15)
        b.join(15)

        self.assertEqual(resultat['b'], (resultat['a'], False))
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)
