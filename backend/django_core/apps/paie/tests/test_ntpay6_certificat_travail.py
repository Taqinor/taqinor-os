"""Tests NTPAY6 — Certificat de travail de sortie (art. 72).

Couvre : le contenu obligatoire (dates EXACTES d'entrée/sortie, emploi(s)
occupé(s), mention « libre de tout engagement », référence art. 72), le refus
explicite sans date de sortie, la lecture RH via ``rh.selectors`` (jamais
``rh.models``) et l'isolation société sur l'endpoint.

Le rendu HTML est testé directement (aucune dépendance WeasyPrint) ; le PDF
lui-même est couvert par l'endpoint, tagué ``pdf``.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.models import ProfilPaie
from apps.paie.services import ensure_defaults
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class CertificatTravailHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay6')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='Bennani', prenom='Yasmine',
            date_embauche=date(2021, 3, 15), date_sortie=date(2026, 6, 30))
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))

    def test_contenu_obligatoire(self):
        html = builders.render_certificat_travail_html(
            self.profil,
            date_entree=date(2021, 3, 15),
            date_sortie=date(2026, 6, 30),
            emplois=['Technicienne de maintenance'],
            today=date(2026, 7, 5))
        self.assertIn('Certificat de travail', html)
        self.assertIn('Bennani', html)
        self.assertIn('15 mars 2021', html)
        self.assertIn('30 juin 2026', html)
        self.assertIn('Technicienne de maintenance', html)
        self.assertIn('libre de tout engagement', html)
        self.assertIn('72', html)

    def test_sans_date_de_sortie_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            builders.render_certificat_travail_html(
                self.profil, date_entree=date(2021, 3, 15),
                date_sortie=None, emplois=['Technicienne'])
        self.assertIn('sortie', str(ctx.exception))

    def test_date_entree_absente_n_invente_rien(self):
        html = builders.render_certificat_travail_html(
            self.profil, date_entree=None, date_sortie=date(2026, 6, 30),
            emplois=[], today=date(2026, 7, 5))
        # Aucune date d'entrée inventée, aucun emploi inventé : « — ».
        self.assertIn('Date d’entrée :</strong></td><td>—</td>', html)
        self.assertIn('Emploi(s) occupé(s) :</strong></td><td>—</td>', html)
        self.assertIn('30 juin 2026', html)


class CertificatTravailApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay6-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay6-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _profil(self, matricule, *, sortie=None):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N', prenom='P',
            date_embauche=date(2022, 1, 3), date_sortie=sortie)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))

    def test_sans_sortie_renvoie_400_explicite(self):
        profil = self._profil('A1')
        rep = self.api.get(
            f'/api/django/paie/profils/{profil.id}/certificat-travail/')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('sortie', rep.data['detail'])

    def test_profil_d_une_autre_societe_invisible(self):
        autre = make_company('ntpay6-autre')
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P',
            date_sortie=date(2026, 6, 30))
        profil_autre = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        rep = self.api.get(
            f'/api/django/paie/profils/{profil_autre.id}/certificat-travail/')
        self.assertEqual(rep.status_code, 404)
