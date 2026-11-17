"""TCH73 — l'ERP dans les tâches : convertir les à-faire personnels, lier une tâche à une activité.

Base requise (`TestCase`) : joué par la CI. Deux sociétés réelles (`'a'`, `'b'`), deux comptes dans A.
Les activités sont posées par `fabriques.activite` ; chaque test relit les lignes STOCKÉES (la tâche
née, l'activité source) et compare la réponse aux échantillons `convertir_activite.json` et
`lier_activite.json`. Invariant 30 : une activité liée reste OUVERTE ; seule la conversion clôt sa
source.
"""
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.taches.choix import LienEtat, Source
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.taches import Tache
from apps.taches.services.erp import convertir_activites
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

PREFIXE = '/api/django/taches/'
CONVERTIR = PREFIXE + 'convertir-activite/'
LIER = PREFIXE + 'taches/lier-activite/'


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.u2 = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    @staticmethod
    def _faite(activite):
        """L'activité marquée faite (la fabrique pose `done=False`)."""
        activite.done = True
        activite.save(update_fields=['done'])
        return activite

    def _api(self, compte=None):
        api = APIClient()
        api.force_authenticate(compte or self.u1)
        return api


class ConvertirTests(_Base):
    def test_200_partiel_avec_les_raisons(self):
        convertible = fabriques.activite(self.u1, summary='Rappeler Lydec', note='Avant midi')
        collegue = fabriques.activite(self.u1, summary='Pour u2', assigned_to=self.u2)
        close = self._faite(fabriques.activite(self.u1, summary='Déjà faite'))
        deja = fabriques.activite(self.u1, summary='Déjà convertie')
        fabriques.tache(self.u1, titre='Déjà convertie', activite_origine=deja)
        d_un_autre = fabriques.activite(self.u2, summary='À-faire de u2')
        ids = [convertible.pk, collegue.pk, close.pk, deja.pk, d_un_autre.pk, 999999]

        reponse = self._api().post(CONVERTIR, {'activite_ids': ids}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('convertir_activite')))
        nee = Tache.objects.get(activite_origine=convertible)
        self.assertEqual(corps['converties'], [{'activite_id': convertible.pk, 'tache_id': nee.pk}])
        self.assertEqual(corps['refusees'], [
            {'activite_id': collegue.pk, 'raison': 'assignee_a_un_collegue'},
            {'activite_id': close.pk, 'raison': 'close'},
            {'activite_id': deja.pk, 'raison': 'deja_convertie'},
            {'activite_id': d_un_autre.pk, 'raison': 'introuvable'},
            {'activite_id': 999999, 'raison': 'introuvable'},
        ])
        self.assertEqual((nee.titre, nee.notes, nee.source, nee.proprietaire_id),
                         ('Rappeler Lydec', 'Avant midi', Source.ACTIVITE, self.u1.pk))
        self.assertEqual(nee.jour_prevu, convertible.due_date)
        convertible.refresh_from_db()
        self.assertTrue(convertible.done)  # la conversion clôt sa source
        for refusee in (collegue, deja, d_un_autre):
            refusee.refresh_from_db()
            self.assertFalse(refusee.done)
        self.assertEqual(corps['geste_id'], GesteAnnulable.objects.get(proprietaire=self.u1).pk)

    def test_toutes_un_seul_geste(self):
        premiere = fabriques.activite(self.u1, summary='Un')
        seconde = fabriques.activite(self.u1, summary='Deux', due_date=None)
        self._faite(fabriques.activite(self.u1, summary='Faite'))
        fabriques.activite(self.u1, summary='Pour u2', assigned_to=self.u2)

        rendu = convertir_activites(self.u1, toutes=True)

        self.assertEqual([c['activite_id'] for c in rendu['converties']], [premiere.pk, seconde.pk])
        self.assertEqual(rendu['refusees'], [])
        gestes = GesteAnnulable.objects.filter(proprietaire=self.u1)
        self.assertEqual([(g.pk, g.type) for g in gestes], [(rendu['geste_id'], 'conversion')])
        self.assertEqual(len(gestes[0].operations), 2)
        sans_jour = Tache.objects.get(activite_origine=seconde)
        self.assertEqual((sans_jour.jour_prevu, sans_jour.triee_le), (None, None))  # À trier

    def test_rejouer_ne_cree_rien(self):
        activite = fabriques.activite(self.u1, summary='Une fois')
        convertir_activites(self.u1, ids=[activite.pk])
        second = convertir_activites(self.u1, ids=[activite.pk])
        self.assertEqual(second, {'converties': [], 'geste_id': None,
                                  'refusees': [{'activite_id': activite.pk, 'raison': 'deja_convertie'}]})
        self.assertEqual(Tache.objects.filter(activite_origine=activite).count(), 1)

    def test_une_autre_societe_ne_voit_rien(self):
        activite = fabriques.activite(self.u1, summary='Société A')
        rendu = convertir_activites(self.ailleurs, ids=[activite.pk])
        self.assertEqual(rendu['refusees'], [{'activite_id': activite.pk, 'raison': 'introuvable'}])
        activite.refresh_from_db()
        self.assertFalse(activite.done)

    def test_annuler_la_conversion_rouvre_l_a_faire(self):
        from apps.taches.services.gestes import annuler_geste
        activite = fabriques.activite(self.u1, summary='Rappeler Lydec')
        rendu = convertir_activites(self.u1, ids=[activite.pk])
        activite.refresh_from_db()
        self.assertTrue(activite.done)
        bilan = annuler_geste(self.u1, rendu['geste_id'])
        self.assertEqual(bilan['conflits'], [])
        activite.refresh_from_db()
        self.assertFalse(activite.done)
        self.assertIsNone(activite.done_at)
        self.assertFalse(Tache.objects.filter(activite_origine=activite).exists())

    def test_annuler_un_autre_geste_ne_rouvre_rien(self):
        from apps.taches.services.gestes import annuler_geste
        activite = self._faite(fabriques.activite(self.u1, summary='Close à la main'))
        tache = fabriques.tache(self.u1, titre='Liée', activite_origine=activite)
        geste = GesteAnnulable.objects.create(company=self.a, proprietaire=self.u1, type='creation', message='x',
                                              operations=[{'op': 'creation', 'objet': 'tache', 'id': tache.pk}])
        annuler_geste(self.u1, geste.pk)
        activite.refresh_from_db()
        self.assertTrue(activite.done)

    def test_corps_sans_ids_400_au_champ(self):
        reponse = self._api().post(CONVERTIR, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['activite_ids'], ['Requis.'])


class LierTests(_Base):
    def _activite_erp(self, **champs):
        """Activité ERP (pas un à-faire personnel) créée par u2, assignée à u1."""
        champs.setdefault('summary', "Préparer l'appel Benali")
        return fabriques.activite(self.u1, personnelle=False, created_by=self.u2, **champs)

    def test_201_la_tache_garde_l_activite_qui_reste_ouverte(self):
        activite = self._activite_erp()
        reponse = self._api().post(LIER, {'activite_id': activite.pk, 'jour_prevu': None}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        corps = reponse.json()
        exemple = exemple_de('lier_activite')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['tache']), set(exemple['tache']))
        tache = Tache.objects.get(pk=corps['tache']['id'])
        self.assertEqual((tache.activite_origine_id, tache.titre, tache.source),
                         (activite.pk, "Préparer l'appel Benali", Source.ACTIVITE))
        self.assertEqual(corps['tache']['activite_origine_id'], activite.pk)
        self.assertEqual(GesteAnnulable.objects.get(pk=corps['geste_id']).type, 'lien_activite')
        activite.refresh_from_db()
        self.assertFalse(activite.done)  # invariant 30

    def test_409_deja_lie(self):
        activite = self._activite_erp()
        api = self._api()
        self.assertEqual(api.post(LIER, {'activite_id': activite.pk}, format='json').status_code, 201)
        reponse = api.post(LIER, {'activite_id': activite.pk, 'titre': 'Encore'}, format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.json()['code'], 'deja_lie')
        self.assertEqual(Tache.objects.filter(activite_origine=activite).count(), 1)
        activite.refresh_from_db()
        self.assertFalse(activite.done)

    def test_404_hors_de_ses_activites_ouvertes(self):
        a_u2 = fabriques.activite(self.u2, summary='À u2', personnelle=False)
        close = self._faite(self._activite_erp(summary='Close'))
        etrangere = fabriques.activite(self.ailleurs, summary='Autre société', personnelle=False)
        for activite in (a_u2, close, etrangere):
            with self.subTest(activite=activite.summary):
                reponse = self._api().post(LIER, {'activite_id': activite.pk}, format='json')
                self.assertEqual(reponse.status_code, 404)
        self.assertFalse(Tache.objects.exists())

    def test_titre_tape_et_lien_de_la_cible_visible(self):
        client_ct = ContentType.objects.get_by_natural_key('crm', 'client')
        activite = self._activite_erp(content_type=client_ct, object_id=4242)
        with mock.patch('apps.taches.selectors.liens._par_la_porte',
                        side_effect=lambda user, app, cle, pk: {cle: 'Benali Karim'}):
            reponse = self._api().post(LIER, {'activite_id': activite.pk, 'titre': 'Rappeler Karim'},
                                       format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        tache = Tache.objects.get(activite_origine=activite)
        self.assertEqual((tache.titre, tache.content_type_id, tache.object_id, tache.lien_etat, tache.lien_libelle),
                         ('Rappeler Karim', client_ct.pk, 4242, LienEtat.OK, 'Benali Karim'))
        self.assertEqual(reponse.json()['tache']['lien']['libelle'], 'Benali Karim')

    def test_cible_hors_de_portee_tache_sans_lien(self):
        client_ct = ContentType.objects.get_by_natural_key('crm', 'client')
        activite = self._activite_erp(content_type=client_ct, object_id=4242)
        with mock.patch('apps.taches.selectors.liens._par_la_porte', return_value={}):
            reponse = self._api().post(LIER, {'activite_id': activite.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        tache = Tache.objects.get(activite_origine=activite)
        self.assertEqual((tache.content_type_id, tache.object_id, tache.lien_libelle), (None, None, ''))
