"""QJR223 — Deux PATCH simultanés sur deux chemins ne se perdent plus.

LE DÉFAUT. ``views/devis.py::DevisViewSet.overrides`` faisait ``get_object()``
SANS ``select_for_update`` puis ``domain.overrides.fusionner`` sur le
registre EN MÉMOIRE puis ``ecrire_colonne`` (``.update(overrides=registre)``,
un ``UPDATE`` INCONDITIONNEL de toute la colonne) : deux PATCH concurrents
sur deux chemins DIFFÉRENTS relisaient tous deux le MÊME registre de départ,
fusionnaient chacun sur cette même base, puis s'écrasaient l'un l'autre au
``UPDATE`` — le perdant répondait quand même 200 comme si sa surcharge était
stockée (``ecrire_colonne`` réécrit aussi ``devis.overrides`` EN MÉMOIRE avant
que la course ne tranche).

LE CORRECTIF. Le cycle lire-fusionner-écrire est désormais verrouillé
(``domain.overrides.relire_verrouille``, ``select_for_update(of=('self',))``)
DANS un ``transaction.atomic()`` — le second PATCH BLOQUE jusqu'au commit du
premier, puis relit un registre DÉJÀ enrichi et fusionne par-dessus : les
DEUX surcharges survivent. Aucun ``Devis.save()`` n'est réintroduit :
``updated_at`` et le gel ``prix_par_kwc`` restent inchangés (c'est la raison
d'être de ``ecrire_colonne``, préservée à l'identique).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr223_overrides_concurrence -v 2
"""
import threading
import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


def _api_pour(user):
    """Un ``APIClient`` authentifié — UNE instance par thread (le test de
    concurrence en a besoin de deux, jamais partagées entre threads)."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FixtureBase:
    """Un devis BROUILLON avec kWc + une ligne, pour que ``prix_par_kwc`` soit
    GELÉ dès la création — condition nécessaire pour prouver qu'un PATCH
    d'override ne le retouche jamais (SCA47, ``Devis.save``)."""

    slug = 'qjr223'

    def _construire(self):
        self.company = Company.objects.create(
            slug=self.slug, nom=self.slug)
        self.user = User.objects.create_user(
            username=self.slug, password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR223',
            email=f'{self.slug}@example.com', telephone='+212600000223')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug.upper()}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={'puissance_kwc': 8.52})
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 710W', sku=f'{self.slug}-1',
            prix_vente=Decimal('1200'), prix_achat=Decimal('1'),
            quantite_stock=50)
        creer_ligne(self.devis, produit=produit, designation='Panneau 710W',
                    quantite=Decimal('12'), prix_unitaire=Decimal('1000'),
                    remise=Decimal('0'))
        # SCA47 — le gel n'a lieu qu'à un ``Devis.save()`` où kWc ET total
        # coexistent (« on gèlera au prochain save utile ») : ``creer_ligne``
        # ne re-save pas le devis, ce save-ci EST le prochain save utile.
        self.devis.save()
        self.devis.refresh_from_db()
        self.url = f'/api/django/ventes/devis/{self.devis.id}/overrides/'


class LeVerrouEstPose(_FixtureBase, TestCase):
    """Preuve mécanique : le cycle lire-fusionner-écrire émet bien un
    ``SELECT ... FOR UPDATE`` — sans lui, aucune sérialisation n'existe."""

    def setUp(self):
        self._construire()
        self.api = _api_pour(self.user)

    def _verrous(self, requetes):
        return [q['sql'] for q in requetes.captured_queries
                if 'FOR UPDATE' in q['sql']]

    def test_le_patch_verrouille_la_ligne(self):
        with CaptureQueriesContext(connection) as requetes:
            r = self.api.patch(
                self.url, {'taille.nb_panneaux': {'valeur': 14}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(
            self._verrous(requetes),
            'aucun SELECT ... FOR UPDATE : le PATCH ne verrouille plus le '
            'cycle lire-fusionner-écrire — deux PATCH concurrents peuvent à '
            'nouveau se perdre en silence.')

    def test_le_delete_verrouille_la_ligne(self):
        self.api.patch(self.url, {'scenario': {'valeur': 'Avec batterie'}},
                       format='json')
        with CaptureQueriesContext(connection) as requetes:
            r = self.api.delete(f'{self.url}?chemin=scenario')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(
            self._verrous(requetes),
            'aucun SELECT ... FOR UPDATE sur le DELETE (regenerer) : la '
            'même course existe entre un DELETE et un PATCH concurrents.')


class UpdatedAtEtPrixParKwcInchanges(_FixtureBase, TestCase):
    """La raison d'être de ``ecrire_colonne`` (QJR58) : un PATCH d'override,
    même verrouillé, ne doit JAMAIS faire repartir ``Devis.save()``."""

    def setUp(self):
        self._construire()
        self.api = _api_pour(self.user)
        self.assertIsNotNone(
            self.devis.prix_par_kwc,
            'prérequis du test : prix_par_kwc doit être GELÉ avant le PATCH')

    def test_prix_par_kwc_et_updated_at_ne_bougent_pas(self):
        prix_avant = self.devis.prix_par_kwc
        maj_avant = self.devis.updated_at

        r = self.api.patch(
            self.url, {'taille.nb_panneaux': {'valeur': 14}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.prix_par_kwc, prix_avant,
            'le verrou QJR223 ne doit JAMAIS faire repartir Devis.save() '
            '(SCA47 : le gel de prix_par_kwc romprait le write-once)')
        self.assertEqual(
            self.devis.updated_at, maj_avant,
            'le verrou QJR223 ne doit JAMAIS faire repartir Devis.save() '
            '(VX98 : updated_at avancerait sur un devis dont rien n\'a bougé)')


class DeuxPatchConcurrentsNePerdentPlusUnChemin(_FixtureBase, TransactionTestCase):
    """LE test : deux VRAIS threads, deux connexions DB, deux chemins
    DIFFÉRENTS, patchés en même temps.

    ``TransactionTestCase`` (et non ``TestCase``) — comme
    ``test_premium_security.py::test_err17`` : un thread réel reçoit sa
    PROPRE connexion DB hors de la transaction atomique du test ; sous
    ``TestCase`` il ne verrait jamais les données commitées par l'autre
    thread. ``TransactionTestCase`` commite réellement, donc les deux
    threads se voient — la course ne peut se rejouer qu'ainsi.
    """

    def setUp(self):
        self._construire()

    def tearDown(self):
        connection.close()

    def test_les_deux_chemins_survivent_le_perdant_repond_quand_meme_200(self):
        # DEUX threads TRAVAILLEURS (A et B) + le thread de test qui
        # orchestre SANS jamais lui-même bloquer sur le verrou DB — sinon
        # rien ne pourrait jamais relâcher A pendant que B est bloqué dessus
        # (un appel HTTP synchrone bloqué ne peut pas relâcher qui que ce soit).
        acquis = threading.Event()
        b_a_tente = threading.Event()
        relacher = threading.Event()
        resultats = {}

        from apps.ventes.domain import overrides as registre_overrides
        original = registre_overrides.relire_verrouille

        def relire_verrouille_instrumente(devis):
            if not acquis.is_set():
                # Thread A : acquiert RÉELLEMENT le verrou (DANS le
                # transaction.atomic() ouvert par la vue), puis attend —
                # le verrou reste tenu tout le temps de l'attente.
                res = original(devis)
                acquis.set()
                relacher.wait(5)
                return res
            # Thread B : signale qu'il s'apprête à tenter le MÊME verrou
            # (donc à bloquer réellement tant que A ne l'a pas relâché),
            # puis tente pour de vrai.
            b_a_tente.set()
            return original(devis)

        registre_overrides.relire_verrouille = relire_verrouille_instrumente
        try:
            def thread_a():
                api = _api_pour(self.user)
                r = api.patch(
                    self.url, {'taille.nb_panneaux': {'valeur': 14}},
                    format='json')
                resultats['a'] = (r.status_code, r.data)
                connection.close()

            def thread_b():
                api = _api_pour(self.user)
                r = api.patch(
                    self.url, {'scenario': {'valeur': 'Avec batterie'}},
                    format='json')
                resultats['b'] = (r.status_code, r.data)
                connection.close()

            ta = threading.Thread(target=thread_a)
            ta.start()
            self.assertTrue(acquis.wait(5), 'le thread A n’a jamais acquis le verrou')

            tb = threading.Thread(target=thread_b)
            tb.start()
            self.assertTrue(
                b_a_tente.wait(5), 'le thread B n’a jamais tenté le verrou')
            # Attend que le SELECT ... FOR UPDATE de B soit RÉELLEMENT bloqué
            # dans PostgreSQL AVANT de relâcher A — une attente de CONDITION,
            # jamais un délai arbitraire : un ordonnancement chanceux ne
            # prouverait rien (le défaut d'origine est justement une course de
            # timing). Observée dans ``pg_locks.granted = false`` (un waiter de
            # verrou non accordé), PAS dans pg_stat_activity : en CI le texte
            # de ``query`` d'une autre session n'est pas fiable (troncature,
            # visibilité) — la ligne de verrou, elle, existe toujours.

            def _b_bloque_sur_le_verrou():
                with connection.cursor() as curseur:
                    curseur.execute(
                        "SELECT count(*) FROM pg_locks WHERE granted = false")
                    return curseur.fetchone()[0] > 0
            pacage = threading.Event()  # jamais signalé : pur régulateur de boucle
            limite = time.monotonic() + 5
            while not _b_bloque_sur_le_verrou():
                self.assertLess(
                    time.monotonic(), limite,
                    'le SELECT FOR UPDATE de B ne s’est jamais bloqué en base')
                pacage.wait(0.05)

            relacher.set()
            ta.join(10)
            tb.join(10)
            self.assertFalse(ta.is_alive(), 'le thread A ne s’est jamais terminé')
            self.assertFalse(tb.is_alive(), 'le thread B ne s’est jamais terminé')
        finally:
            registre_overrides.relire_verrouille = original

        # Le perdant d'une VRAIE course répondait quand même 200 (c'était
        # exactement le défaut) : les DEUX réponses doivent être 200 ici AUSSI
        # — la différence est que les DEUX chemins doivent survivre en base.
        self.assertEqual(resultats['a'][0], 200, resultats['a'][1])
        self.assertEqual(resultats['b'][0], 200, resultats['b'][1])

        self.devis.refresh_from_db()
        registre = self.devis.overrides or {}
        self.assertIn(
            'taille.nb_panneaux', registre,
            "AVANT QJR223 : le chemin du thread A pouvait disparaître, "
            "écrasé par le registre plus ancien que B avait fusionné.")
        self.assertIn(
            'scenario', registre,
            "AVANT QJR223 : le chemin du thread B pouvait disparaître, "
            "écrasé par le registre plus ancien que A avait fusionné.")
        self.assertEqual(registre['taille.nb_panneaux']['valeur'], 14)
        self.assertEqual(registre['scenario']['valeur'], 'Avec batterie')
