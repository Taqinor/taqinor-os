"""Tests YHIRE12 — UNE surface bulletins (portail self-service).

``rh`` portail ``mes-bulletins`` fusionne les dépôts externes (FG196,
``rh.BulletinPaie``) et les bulletins GÉNÉRÉS/validés (``paie.BulletinPaie``,
lus UNIQUEMENT via ``apps.paie.selectors.mes_bulletins_valides``), dédupliqués
par mois (le généré prime).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh.models import BulletinPaie as RhBulletinPaie, DossierEmploye

User = get_user_model()

URL = '/api/django/rh/portail/mes-bulletins/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, user=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', user=user)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_attachment(company, employe):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(DossierEmploye)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=employe.id,
        file_key=f'attachments/{Attachment.objects.count()}.pdf',
        filename='b.pdf', size=10, mime='application/pdf')


def _make_paie_bulletin(company, employe, annee, mois, statut='valide'):
    """Construit un profil paie + période + bulletin GÉNÉRÉ validé."""
    from apps.paie.models import BulletinPaie as PaieBulletinPaie, PeriodePaie, \
        ProfilPaie

    profil, _ = ProfilPaie.objects.get_or_create(
        company=company, employe=employe)
    periode, _ = PeriodePaie.objects.get_or_create(
        company=company, annee=annee, mois=mois,
        defaults={'statut': PeriodePaie.STATUT_VALIDEE})
    return PaieBulletinPaie.objects.create(
        company=company, periode=periode, profil=profil, statut=statut)


class MesBulletinsFusionTests(TestCase):
    def setUp(self):
        self.company = make_company('yh12-a', 'A')
        self.user = make_user(self.company, 'yh12-user')
        self.employe = make_employe(self.company, 'YH12-1', user=self.user)

    def test_fusion_depose_et_genere(self):
        att = make_attachment(self.company, self.employe)
        RhBulletinPaie.objects.create(
            company=self.company, employe=self.employe, attachment=att,
            annee=2026, mois=5)
        _make_paie_bulletin(self.company, self.employe, 2026, 6)

        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200)
        rows = resp.data
        self.assertEqual(len(rows), 2)
        sources = {(r['annee'], r['mois']): r['source'] for r in rows}
        self.assertEqual(sources[(2026, 5)], 'depose')
        self.assertEqual(sources[(2026, 6)], 'genere')

    def test_genere_prime_sur_depose_meme_mois(self):
        att = make_attachment(self.company, self.employe)
        RhBulletinPaie.objects.create(
            company=self.company, employe=self.employe, attachment=att,
            annee=2026, mois=6)
        _make_paie_bulletin(self.company, self.employe, 2026, 6)

        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], 'genere')

    def test_bulletin_non_valide_absent(self):
        _make_paie_bulletin(
            self.company, self.employe, 2026, 7, statut='brouillon')
        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_employe_ne_voit_pas_bulletin_autrui(self):
        autre_user = make_user(self.company, 'yh12-other')
        autre = make_employe(self.company, 'YH12-2', user=autre_user)
        _make_paie_bulletin(self.company, autre, 2026, 6)

        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_sans_dossier_vide(self):
        orphan = make_user(self.company, 'yh12-orphan')
        resp = auth(orphan).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])
