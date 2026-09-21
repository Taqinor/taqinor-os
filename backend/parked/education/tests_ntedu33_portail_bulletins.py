"""NTEDU33 — Portail parents : présences (NTEDU12) et bulletins PUBLIÉS
(NTEDU17) en lecture seule.

Comme NTEDU17 (``tests_ntedu17_bulletin.py``), le renderer PDF
(``core.pdf.render_pdf``) est STUBBÉ — ces tests portent sur le contexte/
statut HTTP, jamais sur les octets rendus (WeasyPrint absent du poste)."""
from datetime import date, time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    AnneeScolaire, Bulletin, Classe, CompteParent, Eleve, Famille, Niveau,
    PeriodeScolaire, Presence, Seance,
)

User = get_user_model()


class NTEDU33PortailFixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-portail-bulletin-test',
            defaults={'nom': 'École Portail Bulletin Test'})
        self.user = User.objects.create_user(
            username='admin@ecole-portail-bulletin-test.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.periode = PeriodeScolaire.objects.create(
            company=self.company, annee_scolaire=self.annee,
            libelle='Trimestre 1', ordre=1,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 12, 15))
        self.niveau = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE,
            ordre=1)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau, nom='CP A', capacite_max=30)
        self.famille = Famille.objects.create(
            company=self.company, nom='Bennani')
        self.autre_famille = Famille.objects.create(
            company=self.company, nom='Alaoui')

        self.eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe)
        self.eleve_autre_famille = Eleve.objects.create(
            company=self.company, famille=self.autre_famille, nom='Alaoui',
            prenom='Sara', classe=self.classe)

        self.compte = CompteParent.objects.create(
            company=self.company, famille=self.famille,
            email='parent@bennani.ma', token_acces='tok-bennani-33')


class NTEDU33PublierActionTests(NTEDU33PortailFixtureMixin, TestCase):
    def test_publier_pose_publie_et_date_publication(self):
        bulletin = Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode)
        self.assertFalse(bulletin.publie)
        self.assertIsNone(bulletin.date_publication)

        resp = self.client.post(
            f'/api/django/education/bulletins/{bulletin.id}/publier/')
        self.assertEqual(resp.status_code, 200)

        bulletin.refresh_from_db()
        self.assertTrue(bulletin.publie)
        self.assertIsNotNone(bulletin.date_publication)

    def test_publie_et_date_publication_ne_sont_jamais_modifiables_par_patch(self):
        bulletin = Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode)
        resp = self.client.patch(
            f'/api/django/education/bulletins/{bulletin.id}/',
            {'publie': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        bulletin.refresh_from_db()
        # `publie` est read_only sur le serializer : le PATCH est accepté
        # (champ ignoré) mais ne bascule JAMAIS le brouillon en publié.
        self.assertFalse(bulletin.publie)


class NTEDU33PortailBulletinsTests(NTEDU33PortailFixtureMixin, TestCase):
    def test_bulletin_non_publie_invisible_cote_portail(self):
        Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode,
            appreciation_generale='Brouillon en cours de saisie.')

        resp = self.client.get(
            f'/api/django/public/education/portail/{self.compte.token_acces}/'
            'bulletins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_bulletin_publie_visible_cote_portail(self):
        from django.utils import timezone

        Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode,
            publie=True, date_publication=timezone.now())

        resp = self.client.get(
            f'/api/django/public/education/portail/{self.compte.token_acces}/'
            'bulletins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['eleve'], 'Yasmine Bennani')

    def test_bulletin_dune_autre_famille_jamais_visible(self):
        from django.utils import timezone

        Bulletin.objects.create(
            company=self.company, eleve=self.eleve_autre_famille,
            periode=self.periode, publie=True, date_publication=timezone.now())

        resp = self.client.get(
            f'/api/django/public/education/portail/{self.compte.token_acces}/'
            'bulletins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_token_invalide_renvoie_404_jamais_500(self):
        resp = self.client.get(
            '/api/django/public/education/portail/token-inexistant/'
            'bulletins/')
        self.assertEqual(resp.status_code, 404)


class NTEDU33PortailBulletinPdfTests(NTEDU33PortailFixtureMixin, TestCase):
    def test_pdf_dun_bulletin_publie_telechargeable(self):
        from django.utils import timezone

        bulletin = Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode,
            publie=True, date_publication=timezone.now())

        with mock.patch(
                'apps.education.bulletin_pdf.render_pdf',
                return_value=b'%PDF-1.4 fake'):
            resp = self.client.get(
                f'/api/django/public/education/portail/'
                f'{self.compte.token_acces}/bulletins/{bulletin.id}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_pdf_dun_bulletin_non_publie_refuse(self):
        bulletin = Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode)

        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte.token_acces}/bulletins/{bulletin.id}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_pdf_dun_bulletin_dune_autre_famille_refuse(self):
        from django.utils import timezone

        bulletin = Bulletin.objects.create(
            company=self.company, eleve=self.eleve_autre_famille,
            periode=self.periode, publie=True, date_publication=timezone.now())

        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte.token_acces}/bulletins/{bulletin.id}/pdf/')
        self.assertEqual(resp.status_code, 404)


class NTEDU33PortailPresencesTests(NTEDU33PortailFixtureMixin, TestCase):
    def test_historique_presence_de_la_famille_uniquement(self):
        seance = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Français',
            date=date(2026, 10, 6), heure_debut=time(8, 0),
            heure_fin=time(9, 0))
        Presence.objects.create(
            company=self.company, seance=seance, eleve=self.eleve,
            statut=Presence.Statut.ABSENT)
        Presence.objects.create(
            company=self.company, seance=seance, eleve=self.eleve_autre_famille,
            statut=Presence.Statut.PRESENT)

        resp = self.client.get(
            f'/api/django/public/education/portail/{self.compte.token_acces}/'
            'presences/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['statut'], 'absent')
        self.assertEqual(resp.data['results'][0]['eleve'], 'Yasmine Bennani')

    def test_token_invalide_renvoie_404_jamais_500(self):
        resp = self.client.get(
            '/api/django/public/education/portail/token-inexistant/'
            'presences/')
        self.assertEqual(resp.status_code, 404)
