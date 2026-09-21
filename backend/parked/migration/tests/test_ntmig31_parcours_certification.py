"""Tests NTMIG31 — programme de formation partenaire (parcours + badge).

Critère d'acceptation : terminer le parcours « Compta » propose d'ajouter la
spécialité ``compta`` au partenaire, validée par un admin.

Couvre aussi : le parcours kb est résolu via ``kb.selectors`` (scopé
société), l'article inconnu est refusé, la clôture est refusée tant qu'il
reste des articles, la spécialité n'est jamais ajoutée sans validation
explicite, un ``metier`` hors référentiel ne propose rien, l'idempotence de
la validation, l'isolation multi-société et la garde de rôle.

Run :
    python manage.py test apps.migration.tests.test_ntmig31_parcours_certification -v2
"""
from django.test import TestCase

from apps.crm.models import Partenaire
from apps.kb.models import KbArticle, KbParcours, KbParcoursArticle
from apps.migration.models import ParcoursCertificationPartenaire

from ._base import auth, make_admin, make_company, make_user

PARCOURS_CERT = '/api/django/migration/parcours-certification-partenaire/'


class Ntmig31ParcoursCertificationTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig31', 'NTMIG31')
        self.admin = make_admin(self.company, 'ntmig31-admin')
        self.api = auth(self.admin)
        self.partenaire = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig31-token')
        self.parcours = KbParcours.objects.create(
            company=self.company, nom='Certification Compta', metier='compta')
        self.article1 = KbArticle.objects.create(
            company=self.company, titre='Notions comptables de base')
        self.article2 = KbArticle.objects.create(
            company=self.company, titre='TVA et facturation')
        KbParcoursArticle.objects.create(
            company=self.company, parcours=self.parcours,
            article=self.article1, ordre=1)
        KbParcoursArticle.objects.create(
            company=self.company, parcours=self.parcours,
            article=self.article2, ordre=2)

    def _instancier(self, **extra):
        payload = {'parcours': self.parcours.pk, 'partenaire': self.partenaire.pk}
        payload.update(extra)
        return self.api.post(f'{PARCOURS_CERT}instancier/', payload, format='json')

    def test_instancier_puis_terminer_propose_la_specialite(self):
        resp = self._instancier()
        self.assertEqual(resp.status_code, 201, resp.data)
        instance_id = resp.data['id']
        self.assertEqual(resp.data['nb_articles'], 2)
        self.assertEqual(resp.data['specialite'], 'compta')
        self.assertEqual(resp.data['progression'], 0)

        for article_id in (self.article1.pk, self.article2.pk):
            coche = self.api.post(
                f'{PARCOURS_CERT}{instance_id}/cocher/',
                {'article': article_id}, format='json')
            self.assertEqual(coche.status_code, 200, coche.data)
        self.assertEqual(coche.data['progression'], 100)

        termine = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/terminer/', {}, format='json')
        self.assertEqual(termine.status_code, 200, termine.data)
        self.assertEqual(termine.data['statut'], 'termine')
        self.assertFalse(termine.data['proposition_validee'])

        # La spécialité n'est PAS ajoutée tant qu'un admin ne l'a pas validée.
        self.partenaire.refresh_from_db()
        self.assertEqual(self.partenaire.specialites, [])

        valide = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/valider-specialite/', {},
            format='json')
        self.assertEqual(valide.status_code, 200, valide.data)
        self.assertTrue(valide.data['proposition_validee'])
        self.assertEqual(valide.data['valide_par'], self.admin.pk)

        self.partenaire.refresh_from_db()
        self.assertEqual(self.partenaire.specialites, ['compta'])

    def test_terminer_refuse_tant_qu_il_reste_des_articles(self):
        instance_id = self._instancier().data['id']
        self.api.post(
            f'{PARCOURS_CERT}{instance_id}/cocher/',
            {'article': self.article1.pk}, format='json')
        resp = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(resp.data['articles_restants']), 1)

    def test_valider_specialite_refusee_avant_cloture(self):
        instance_id = self._instancier().data['id']
        resp = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/valider-specialite/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.partenaire.refresh_from_db()
        self.assertEqual(self.partenaire.specialites, [])

    def test_valider_specialite_deux_fois_refusee(self):
        instance_id = self._instancier().data['id']
        for article_id in (self.article1.pk, self.article2.pk):
            self.api.post(
                f'{PARCOURS_CERT}{instance_id}/cocher/',
                {'article': article_id}, format='json')
        self.api.post(f'{PARCOURS_CERT}{instance_id}/terminer/', {}, format='json')
        self.api.post(
            f'{PARCOURS_CERT}{instance_id}/valider-specialite/', {},
            format='json')
        resp = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/valider-specialite/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        # Idempotent : la spécialité n'apparaît toujours qu'une fois.
        self.partenaire.refresh_from_db()
        self.assertEqual(self.partenaire.specialites, ['compta'])

    def test_metier_hors_referentiel_ne_propose_rien(self):
        parcours_libre = KbParcours.objects.create(
            company=self.company, nom='Onboarding poseur', metier='poseur')
        KbParcoursArticle.objects.create(
            company=self.company, parcours=parcours_libre,
            article=self.article1, ordre=1)
        resp = self._instancier(parcours=parcours_libre.pk)
        self.assertEqual(resp.status_code, 201, resp.data)
        instance_id = resp.data['id']
        self.assertEqual(resp.data['specialite'], '')

        self.api.post(
            f'{PARCOURS_CERT}{instance_id}/cocher/',
            {'article': self.article1.pk}, format='json')
        self.api.post(f'{PARCOURS_CERT}{instance_id}/terminer/', {}, format='json')
        valide = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/valider-specialite/', {},
            format='json')
        self.assertEqual(valide.status_code, 400)

    def test_article_inconnu_refuse(self):
        instance_id = self._instancier().data['id']
        resp = self.api.post(
            f'{PARCOURS_CERT}{instance_id}/cocher/',
            {'article': 999999}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            ParcoursCertificationPartenaire.objects.get(
                pk=instance_id).avancement, {})

    def test_parcours_d_une_autre_societe_introuvable(self):
        autre = make_company('ntmig31-bis', 'NTMIG31 bis')
        etranger = KbParcours.objects.create(
            company=autre, nom='Parcours voisin', metier='compta')
        resp = self._instancier(parcours=etranger.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(ParcoursCertificationPartenaire.objects.exists())

    def test_partenaire_d_une_autre_societe_refuse(self):
        autre = make_company('ntmig31-ter', 'NTMIG31 ter')
        etranger = Partenaire.objects.create(
            company=autre, nom='Partenaire voisin', token_acces='ntmig31-tok-2')
        resp = self._instancier(partenaire=etranger.pk)
        self.assertEqual(resp.status_code, 400)

    def test_role_limite_refuse(self):
        limite = make_user(self.company, 'ntmig31-limite')
        resp = auth(limite).get(PARCOURS_CERT)
        self.assertEqual(resp.status_code, 403)

    def test_post_direct_refuse(self):
        resp = self.api.post(
            PARCOURS_CERT, {'partenaire': self.partenaire.pk}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(ParcoursCertificationPartenaire.objects.exists())

    def test_instantane_fige_a_l_instanciation(self):
        """Ajouter un article au parcours modèle après coup ne réécrit pas
        une formation déjà en cours."""
        instance_id = self._instancier().data['id']
        article3 = KbArticle.objects.create(
            company=self.company, titre='Déclarations fiscales')
        KbParcoursArticle.objects.create(
            company=self.company, parcours=self.parcours,
            article=article3, ordre=3)
        detail = self.api.get(f'{PARCOURS_CERT}{instance_id}/')
        self.assertEqual(detail.data['nb_articles'], 2)
