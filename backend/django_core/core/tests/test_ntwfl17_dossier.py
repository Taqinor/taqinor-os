"""Tests NTWFL17 — dossier transverse (``core.Dossier``).

Acceptance criteria couverte : créer un dossier « Réclamation complexe »,
lier un ticket SAV + un devis + un client, cocher 2 items de checklist,
isolation tenant.

``core`` étant une couche de FONDATION, ces tests ne lui font importer aucune
app métier : les cibles des liens sont désignées par leur clé
``app_label.model`` et résolues via ``ContentType`` (fondation Django).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company, CustomUser

from core.dates import aujourd_hui_local
from core.models import Dossier, DossierChecklistItem, DossierLien
from core.views_dossiers import DossierViewSet, resoudre_content_type

#: Les trois cibles nommées par le critère d'acceptation, en clés de modèle.
CIBLES = ['sav.ticket', 'ventes.devis', 'crm.client']

LISTE = DossierViewSet.as_view({'get': 'list', 'post': 'create'})
DETAIL = DossierViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'})
LIER = DossierViewSet.as_view({'post': 'lier'})
DELIER = DossierViewSet.as_view({'post': 'delier'})
CHECKLIST = DossierViewSet.as_view({'get': 'checklist', 'post': 'checklist'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'company': company})
    if user.company_id != company.id:
        user.company = company
        user.save(update_fields=['company'])
    return user


def appeler(user, **kwargs):
    """POST JSON authentifié sur une action de détail du viewset."""
    requete = APIRequestFactory().post('/', kwargs, format='json')
    force_authenticate(requete, user=user)
    return requete


class ResolutionCibleTests(SimpleTestCase):
    """Unités PURES : la clé « app_label.model » est validée, jamais crue."""

    def test_cle_malformee_refusee(self):
        for brut in ['', '   ', 'crm', 'crm.lead.extra', '.lead', 'crm.']:
            self.assertIsNone(resoudre_content_type(brut), brut)


class DossierModeleTests(TestCase):
    """Le statut et l'échéance vivent hors du funnel commercial."""

    def setUp(self):
        self.company = make_company('ntwfl17-modele', 'NTWFL17 Modèle')

    def test_dossier_en_retard_uniquement_si_ouvert(self):
        aujourdhui = aujourd_hui_local()
        hier = aujourdhui - datetime.timedelta(days=1)
        dossier = Dossier.objects.create(
            company=self.company,
            type_dossier=Dossier.TYPE_RECLAMATION_COMPLEXE,
            titre='Réclamation complexe', echeance=hier)

        self.assertTrue(dossier.est_en_retard(aujourdhui))
        self.assertFalse(dossier.est_ferme)

        dossier.statut = Dossier.STATUT_CLOS
        self.assertTrue(dossier.est_ferme)
        self.assertFalse(dossier.est_en_retard(aujourdhui))

    def test_sans_echeance_jamais_en_retard(self):
        dossier = Dossier.objects.create(
            company=self.company, titre='Sans échéance')
        self.assertFalse(dossier.est_en_retard(aujourd_hui_local()))


class DossierApiTests(TestCase):
    """Parcours complet du critère d'acceptation, via le viewset."""

    def setUp(self):
        self.company = make_company('ntwfl17-api', 'NTWFL17 API')
        self.user = make_user(self.company, 'ntwfl17-user')
        self.autre_company = make_company('ntwfl17-autre', 'NTWFL17 Autre')
        self.autre_user = make_user(self.autre_company, 'ntwfl17-autre-user')

    def _creer_dossier(self):
        requete = APIRequestFactory().post('/', {
            'type_dossier': Dossier.TYPE_RECLAMATION_COMPLEXE,
            'titre': 'Onduleur HS + facture contestée',
            'priorite': Dossier.PRIORITE_HAUTE,
        }, format='json')
        force_authenticate(requete, user=self.user)
        reponse = LISTE(requete)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse.data['id']

    def test_creer_lier_trois_objets_et_cocher_deux_items(self):
        dossier_id = self._creer_dossier()
        dossier = Dossier.objects.get(pk=dossier_id)
        # La société vient du serveur, jamais du corps.
        self.assertEqual(dossier.company_id, self.company.id)

        liens_avant = DossierLien.objects.filter(dossier=dossier).count()
        for cle in CIBLES:
            reponse = LIER(
                appeler(self.user, cle_modele=cle, object_id=7,
                        libelle=f'cible {cle}'),
                pk=dossier_id)
            self.assertEqual(reponse.status_code, 201, (cle, reponse.data))
        self.assertEqual(
            DossierLien.objects.filter(dossier=dossier).count(),
            liens_avant + len(CIBLES))
        self.assertEqual(
            sorted(lien.cle_modele for lien in dossier.liens.all()),
            sorted(CIBLES))

        # Re-lier la MÊME cible ne duplique pas (contrainte d'unicité).
        reponse = LIER(
            appeler(self.user, cle_modele=CIBLES[0], object_id=7),
            pk=dossier_id)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            DossierLien.objects.filter(dossier=dossier).count(),
            liens_avant + len(CIBLES))

        for rang, libelle in enumerate(
                ['Constat sur site', 'Avoir émis', 'Client rappelé'], start=1):
            reponse = CHECKLIST(
                appeler(self.user, libelle=libelle, ordre=rang),
                pk=dossier_id)
            self.assertEqual(reponse.status_code, 201, reponse.data)

        items = list(dossier.checklist.order_by('ordre'))
        for item in items[:2]:
            reponse = CHECKLIST(
                appeler(self.user, item_id=item.pk, fait=True),
                pk=dossier_id)
            self.assertEqual(reponse.status_code, 200, reponse.data)

        coches = DossierChecklistItem.objects.filter(
            dossier=dossier, fait=True)
        self.assertEqual(coches.count(), 2)
        for item in coches:
            self.assertEqual(item.fait_par_id, self.user.id)
            self.assertIsNotNone(item.fait_le)

    def test_delier_retire_le_lien(self):
        dossier_id = self._creer_dossier()
        LIER(appeler(self.user, cle_modele=CIBLES[0], object_id=11),
             pk=dossier_id)
        restants = DossierLien.objects.filter(dossier_id=dossier_id).count()

        reponse = DELIER(
            appeler(self.user, cle_modele=CIBLES[0], object_id=11),
            pk=dossier_id)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['detache'])
        self.assertEqual(
            DossierLien.objects.filter(dossier_id=dossier_id).count(),
            restants - 1)

    def test_cle_modele_inconnue_refusee(self):
        dossier_id = self._creer_dossier()
        reponse = LIER(
            appeler(self.user, cle_modele='pasune.app', object_id=1),
            pk=dossier_id)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('cle_modele', reponse.data)

    def test_isolation_tenant(self):
        dossier_id = self._creer_dossier()

        requete = APIRequestFactory().get('/')
        force_authenticate(requete, user=self.autre_user)
        self.assertEqual(DETAIL(requete, pk=dossier_id).status_code, 404)

        requete = APIRequestFactory().get('/')
        force_authenticate(requete, user=self.autre_user)
        reponse = LISTE(requete)
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.data
        if isinstance(resultats, dict):
            resultats = resultats.get('results', [])
        self.assertEqual([d['id'] for d in resultats], [])

        reponse = LIER(
            appeler(self.autre_user, cle_modele=CIBLES[0], object_id=3),
            pk=dossier_id)
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(
            DossierLien.objects.filter(dossier_id=dossier_id).count(), 0)


class CiblesReellesTests(TestCase):
    """Les trois clés du critère d'acceptation désignent de VRAIS modèles."""

    def test_content_types_existent(self):
        for cle in CIBLES:
            app_label, model = cle.split('.')
            self.assertTrue(
                ContentType.objects.filter(
                    app_label=app_label, model=model).exists(), cle)
