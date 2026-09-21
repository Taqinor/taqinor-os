"""NTHOT12 — Main courante / passations d'équipe.

Done = une note saisie par l'équipe de nuit est visible par l'équipe du matin
avec horodatage et auteur, tests.
"""
from django.test import TestCase

from apps.hospitality.models import MainCourante

from .helpers import auth, make_company, make_user


class MainCouranteApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-mc', 'Hôtel')
        self.nuit = make_user(self.co, 'hot-mc-nuit', role='normal')
        self.matin = make_user(self.co, 'hot-mc-matin', role='normal')

    def test_note_visible_par_toute_lequipe_avec_auteur_et_horodatage(self):
        resp = auth(self.nuit).post(
            '/api/django/hospitality/main-courante/',
            {'categorie': 'consigne', 'texte': 'Client chambre 12 arrive tard.'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        note_id = resp.data['id']
        self.assertEqual(resp.data['auteur'], self.nuit.pk)
        self.assertTrue(resp.data['date_note'])

        resp2 = auth(self.matin).get('/api/django/hospitality/main-courante/')
        self.assertEqual(resp2.status_code, 200)
        rows = resp2.data['results'] if isinstance(resp2.data, dict) else resp2.data
        self.assertTrue(any(r['id'] == note_id for r in rows))

    def test_auteur_et_societe_poses_serveur_jamais_lus_du_corps(self):
        autre_co = make_company('hot-mc-autre', 'Autre hôtel')
        resp = auth(self.nuit).post(
            '/api/django/hospitality/main-courante/',
            {
                'categorie': 'incident', 'texte': 'Fuite salle de bain 5.',
                'auteur': 999999, 'company': autre_co.pk,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        note = MainCourante.objects.get(pk=resp.data['id'])
        self.assertEqual(note.auteur_id, self.nuit.pk)
        self.assertEqual(note.company_id, self.co.pk)

    def test_filtre_categorie(self):
        MainCourante.objects.create(
            company=self.co, auteur=self.nuit,
            categorie=MainCourante.Categorie.FINANCE, texte='Caisse OK.')
        MainCourante.objects.create(
            company=self.co, auteur=self.nuit,
            categorie=MainCourante.Categorie.INCIDENT, texte='Ampoule HS.')
        resp = auth(self.matin).get(
            '/api/django/hospitality/main-courante/', {'categorie': 'finance'})
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertTrue(all(r['categorie'] == 'finance' for r in rows))
        self.assertEqual(len(rows), 1)

    def test_tenant_isolation(self):
        autre_co = make_company('hot-mc-b', 'B')
        autre_user = make_user(autre_co, 'hot-mc-b-user')
        MainCourante.objects.create(
            company=self.co, auteur=self.nuit,
            categorie=MainCourante.Categorie.AUTRE, texte='Note société A.')
        resp = auth(autre_user).get('/api/django/hospitality/main-courante/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)

    def test_journal_append_only_pas_de_modification_ni_suppression(self):
        note = MainCourante.objects.create(
            company=self.co, auteur=self.nuit,
            categorie=MainCourante.Categorie.AUTRE, texte='Note initiale.')
        resp = auth(self.nuit).patch(
            f'/api/django/hospitality/main-courante/{note.pk}/',
            {'texte': 'Modifiée'}, format='json')
        self.assertEqual(resp.status_code, 405)
        resp2 = auth(self.nuit).delete(
            f'/api/django/hospitality/main-courante/{note.pk}/')
        self.assertEqual(resp2.status_code, 405)
