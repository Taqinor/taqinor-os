"""Tests du journal des modifications de tâches et jalons (XPRJ26).

``ProjetActivity`` ne tracait QUE le statut du ``Projet`` (PROJ3). XPRJ26
étend le journal, côté serveur, aux champs sensibles des ``Tache`` (statut,
dates prévues, charge, assigné) et ``Jalon`` (date, statut, facturation_pct) —
ancien → nouveau, auteur, horodatage — visibles dans la timeline fusionnée
``projets/<id>/historique/``. Conformité audit/loi 09-08.

Couvre : un PATCH de tâche/jalon écrit la ligne de journal EXACTE (par champ
réellement changé) ; aucune entrée si rien de suivi n'a changé ; la timeline
fusionnée mélange projet/tâche/jalon triée par date ; les entrées historiques
de statut PROJET restent inchangées (rétro-compatibilité) ; isolation société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Jalon, Projet, ProjetActivity, Tache

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class JournalTacheApiTests(TestCase):
    BASE = '/api/django/gestion-projet/taches/'

    def setUp(self):
        self.co = make_company('gp-j26-t', 'S')
        self.user = make_user(self.co, 'gp-j26-t-u')
        self.projet = Projet.objects.create(
            company=self.co, code='P-J26T', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Pose',
            statut=Tache.Statut.A_FAIRE)

    def test_patch_statut_ecrit_ligne_journal_exacte(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.tache.id}/',
            {'statut': Tache.Statut.EN_COURS}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entrees = ProjetActivity.objects.filter(
            cible_type=ProjetActivity.CibleType.TACHE, cible_id=self.tache.id)
        self.assertEqual(entrees.count(), 1)
        entree = entrees.first()
        self.assertEqual(entree.champ, 'statut')
        self.assertEqual(entree.old_value, 'a_faire')
        self.assertEqual(entree.new_value, 'en_cours')
        self.assertEqual(entree.auteur_id, self.user.id)
        self.assertEqual(entree.company_id, self.co.id)
        self.assertEqual(entree.projet_id, self.projet.id)

    def test_patch_plusieurs_champs_une_entree_par_champ(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.tache.id}/',
            {
                'statut': Tache.Statut.EN_COURS,
                'charge_estimee': '3.50',
                'date_debut_prevue': '2026-08-01',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entrees = ProjetActivity.objects.filter(
            cible_type=ProjetActivity.CibleType.TACHE, cible_id=self.tache.id)
        champs = set(entrees.values_list('champ', flat=True))
        self.assertEqual(
            champs, {'statut', 'charge_estimee', 'date_debut_prevue'})

    def test_patch_sans_changement_suivi_aucune_entree(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.tache.id}/',
            {'description': 'Nouvelle note'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            ProjetActivity.objects.filter(
                cible_type=ProjetActivity.CibleType.TACHE,
                cible_id=self.tache.id).exists())

    def test_patch_meme_valeur_aucune_entree(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.tache.id}/',
            {'statut': Tache.Statut.A_FAIRE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            ProjetActivity.objects.filter(
                cible_type=ProjetActivity.CibleType.TACHE,
                cible_id=self.tache.id).exists())

    def test_assigne_journalise(self):
        from apps.gestion_projet.models import RessourceProfil

        ressource = RessourceProfil.objects.create(
            company=self.co, nom='Karim')
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.tache.id}/',
            {'assigne': ressource.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = ProjetActivity.objects.get(
            cible_type=ProjetActivity.CibleType.TACHE,
            cible_id=self.tache.id, champ='assigne_id')
        self.assertEqual(entree.old_value, '')
        self.assertEqual(entree.new_value, str(ressource.id))


class JournalJalonApiTests(TestCase):
    BASE = '/api/django/gestion-projet/jalons/'

    def setUp(self):
        self.co = make_company('gp-j26-j', 'S')
        self.user = make_user(self.co, 'gp-j26-j-u')
        self.projet = Projet.objects.create(
            company=self.co, code='P-J26J', nom='P')
        self.jalon = Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1),
            facturation_pct=Decimal('30'))

    def test_patch_date_prevue_ecrit_ligne_journal(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.jalon.id}/',
            {'date_prevue': '2026-02-01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = ProjetActivity.objects.get(
            cible_type=ProjetActivity.CibleType.JALON,
            cible_id=self.jalon.id, champ='date_prevue')
        self.assertEqual(entree.old_value, '2026-01-01')
        self.assertEqual(entree.new_value, '2026-02-01')
        self.assertEqual(entree.auteur_id, self.user.id)

    def test_patch_facturation_pct_journalise(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.jalon.id}/',
            {'facturation_pct': '50'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = ProjetActivity.objects.get(
            cible_type=ProjetActivity.CibleType.JALON,
            cible_id=self.jalon.id, champ='facturation_pct')
        self.assertEqual(entree.old_value, '30')

    def test_patch_sans_changement_suivi_aucune_entree(self):
        api = auth(self.user)
        resp = api.patch(
            f'{self.BASE}{self.jalon.id}/',
            {'description': 'note'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            ProjetActivity.objects.filter(
                cible_type=ProjetActivity.CibleType.JALON,
                cible_id=self.jalon.id).exists())


class TimelineFusionneeTests(TestCase):
    """La timeline ``projets/<id>/historique/`` fusionne projet+tâche+jalon."""
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co = make_company('gp-j26-tl', 'S')
        self.user = make_user(self.co, 'gp-j26-tl-u')
        self.projet = Projet.objects.create(
            company=self.co, code='P-J26TL', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Pose',
            statut=Tache.Statut.A_FAIRE)
        self.jalon = Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1))

    def test_historique_fusionne_projet_tache_jalon(self):
        api = auth(self.user)
        api.post(f'{self.BASE}{self.projet.id}/planifier/')
        api.patch(
            f'/api/django/gestion-projet/taches/{self.tache.id}/',
            {'statut': Tache.Statut.EN_COURS}, format='json')
        api.patch(
            f'/api/django/gestion-projet/jalons/{self.jalon.id}/',
            {'date_prevue': '2026-03-01'}, format='json')

        resp = api.get(f'{self.BASE}{self.projet.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        cibles = {row['cible_type'] for row in resp.data}
        self.assertEqual(cibles, {'projet', 'tache', 'jalon'})
        self.assertEqual(len(resp.data), 3)

    def test_entree_historique_statut_projet_cible_projet(self):
        """Rétro-compatibilité : les transitions de statut projet restent
        ``cible_type='projet'`` avec ``cible_id`` posé au projet lui-même."""
        api = auth(self.user)
        api.post(f'{self.BASE}{self.projet.id}/planifier/')
        entree = ProjetActivity.objects.get(projet=self.projet)
        self.assertEqual(entree.cible_type, ProjetActivity.CibleType.PROJET)
        self.assertEqual(entree.cible_id, self.projet.id)
        self.assertEqual(entree.old_value, 'brouillon')
        self.assertEqual(entree.new_value, 'planifie')


class JournalIsolationTenantTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-j26-iso-a', 'A')
        self.co_b = make_company('gp-j26-iso-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-j26-iso-a-u')
        self.user_b = make_user(self.co_b, 'gp-j26-iso-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-ISO-A', nom='A')
        self.tache_a = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='T',
            statut=Tache.Statut.A_FAIRE)

    def test_autre_societe_ne_peut_pas_patcher(self):
        api = auth(self.user_b)
        resp = api.patch(
            f'/api/django/gestion-projet/taches/{self.tache_a.id}/',
            {'statut': Tache.Statut.EN_COURS}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            ProjetActivity.objects.filter(cible_id=self.tache_a.id).exists())
