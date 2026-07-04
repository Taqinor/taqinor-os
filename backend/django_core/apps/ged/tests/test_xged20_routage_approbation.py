"""XGED20 — Routage conditionnel des approbations par métadonnées.

Couvre :
  * deux documents aux métadonnées différentes suivent des chaînes différentes ;
  * l'ordre séquentiel est imposé (étape N+1 seulement après décision de N) ;
  * sans règle, rien ne change (comportement GED18 inchangé).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    APPROBATION_APPROUVE, Cabinet, ChaineApprobationGed, Document, Folder,
    LIFECYCLE_APPROUVE, RegleApprobationGed,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class XGed20Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged20-a', 'Xged20 A')
        self.admin_a = make_user(self.co_a, 'xged20-admin-a', 'admin')
        self.approbateur1 = make_user(self.co_a, 'xged20-appr1', 'admin')
        self.approbateur2 = make_user(self.co_a, 'xged20-appr2', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')


class ResoudreRegleTests(XGed20Base):
    def test_resout_regle_la_plus_specifique(self):
        RegleApprobationGed.objects.create(
            company=self.co_a, libelle='Petit montant',
            condition_group={'field': 'custom_data.montant', 'operator': 'lt',
                             'value': 1000},
            approbateurs=[self.approbateur1.pk], priorite=1)
        RegleApprobationGed.objects.create(
            company=self.co_a, libelle='Gros montant',
            condition_group={'field': 'custom_data.montant', 'operator': 'gte',
                             'value': 1000},
            approbateurs=[self.approbateur1.pk, self.approbateur2.pk],
            priorite=1)
        gros = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Gros contrat',
            custom_data={'montant': 5000})
        petit = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Petit contrat',
            custom_data={'montant': 500})
        regle_gros = services.resoudre_regle_approbation_ged(gros)
        regle_petit = services.resoudre_regle_approbation_ged(petit)
        self.assertEqual(regle_gros.libelle, 'Gros montant')
        self.assertEqual(regle_petit.libelle, 'Petit montant')

    def test_aucune_regle_applicable_renvoie_none(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Sans règle')
        self.assertIsNone(services.resoudre_regle_approbation_ged(doc))


class ChaineSequentielleTests(XGed20Base):
    def test_deux_documents_suivent_chaines_differentes(self):
        RegleApprobationGed.objects.create(
            company=self.co_a, libelle='Chaine 2 niveaux',
            condition_group={'field': 'custom_data.type', 'operator': 'eq',
                             'value': 'gros'},
            approbateurs=[self.approbateur1.pk, self.approbateur2.pk])
        doc_gros = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat',
            custom_data={'type': 'gros'})
        doc_normal = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat normal',
            custom_data={'type': 'normal'})
        demande_gros = services.request_review_avec_routage(
            doc_gros, user=self.admin_a)
        demande_normal = services.request_review_avec_routage(
            doc_normal, user=self.admin_a)
        self.assertTrue(
            ChaineApprobationGed.objects.filter(demande=demande_gros).exists())
        self.assertFalse(
            ChaineApprobationGed.objects.filter(demande=demande_normal).exists())

    def test_ordre_sequentiel_impose(self):
        RegleApprobationGed.objects.create(
            company=self.co_a, libelle='2 niveaux',
            condition_group={'field': 'nom', 'operator': 'eq', 'value': 'Contrat'},
            approbateurs=[self.approbateur1.pk, self.approbateur2.pk])
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')
        demande = services.request_review_avec_routage(doc, user=self.admin_a)
        self.assertEqual(demande.approbateur_id, self.approbateur1.pk)

        # 1ère décision : avance vers le 2e approbateur, demande reste en_attente.
        demande = services.avancer_chaine_approbation_ged(
            demande, user=self.approbateur1)
        demande.refresh_from_db()
        self.assertEqual(demande.approbateur_id, self.approbateur2.pk)
        self.assertNotEqual(demande.statut, APPROBATION_APPROUVE)

        # 2e (dernière) décision : approuve définitivement + avance le document.
        demande = services.avancer_chaine_approbation_ged(
            demande, user=self.approbateur2)
        demande.refresh_from_db()
        doc.refresh_from_db()
        self.assertEqual(demande.statut, APPROBATION_APPROUVE)
        self.assertEqual(doc.statut, LIFECYCLE_APPROUVE)

    def test_sans_regle_comportement_ged18_inchange(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Sans règle')
        demande = services.request_review_avec_routage(doc, user=self.admin_a)
        self.assertFalse(
            ChaineApprobationGed.objects.filter(demande=demande).exists())
        dem = services.avancer_chaine_approbation_ged(
            demande, user=self.admin_a)
        self.assertEqual(dem.statut, APPROBATION_APPROUVE)
