"""NTSCM40 — Import CSV/XLSX des événements de demande (`EvenementDemande`,
NTSCM3), via `apps.dataimport` (`ImportJob.target='scm_evenement_demande'`,
mode `creer` UNIQUEMENT — jamais de mise à jour en masse, pour ne jamais
écraser un impact déjà appliqué à des prévisions gelées).

Critère d'acceptation : un fichier CSV de 50 événements valides crée 50
`EvenementDemande`, les lignes avec un produit introuvable sont rejetées
individuellement avec message d'erreur en `ImportJobRow`."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.scm.models import EvenementDemande
from apps.scm.services import creer_evenement_demande_import
from apps.stock.models import Categorie, Produit

from .helpers import auth, make_company, make_user

URL_IMPORT_COMMIT = '/api/django/imports/commit/'


def make_csv(content, name='evenements.csv'):
    return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')


class CreerEvenementDemandeImportServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-import-evt', 'Supply Import Évt')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 400Wc', sku='PAN400',
            prix_vente=1200)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Panneaux')

    def test_cree_depuis_ligne_produit_par_sku(self):
        statut, message = creer_evenement_demande_import(self.company, {
            'produit': 'PAN400', 'date_debut': '2026-06-01',
            'date_fin': '2026-06-30', 'impact_pct': '30',
            'type_evenement': 'promotion', 'libelle': 'Soldes été',
        })
        self.assertEqual(statut, 'cree')
        self.assertIsNone(message)
        ev = EvenementDemande.objects.get(company=self.company, libelle='Soldes été')
        self.assertEqual(ev.produit_id, self.produit.id)
        self.assertEqual(ev.impact_pct, 30)
        self.assertEqual(ev.type_evenement, 'promotion')

    def test_cree_depuis_ligne_produit_par_nom(self):
        statut, _ = creer_evenement_demande_import(self.company, {
            'produit': 'Panneau 400Wc', 'date_debut': '2026-07-01',
            'date_fin': '2026-07-15', 'impact_pct': '-100',
            'type_evenement': 'rupture_fournisseur', 'libelle': 'Rupture connue',
        })
        self.assertEqual(statut, 'cree')

    def test_cree_evenement_global_sans_produit_ni_categorie(self):
        statut, _ = creer_evenement_demande_import(self.company, {
            'date_debut': '2026-08-01', 'date_fin': '2026-08-31',
            'impact_pct': '10', 'libelle': 'Événement société entière',
        })
        self.assertEqual(statut, 'cree')
        ev = EvenementDemande.objects.get(
            company=self.company, libelle='Événement société entière')
        self.assertIsNone(ev.produit_id)
        self.assertIsNone(ev.categorie_id)
        # Type inconnu/absent -> repli sur 'autre' (jamais bloquant).
        self.assertEqual(ev.type_evenement, EvenementDemande.TypeEvenement.AUTRE)

    def test_produit_introuvable_erreur_sans_creer(self):
        statut, message = creer_evenement_demande_import(self.company, {
            'produit': 'INCONNU-999', 'date_debut': '2026-06-01',
            'date_fin': '2026-06-30', 'impact_pct': '20', 'libelle': 'X',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('produit introuvable', message)
        self.assertFalse(EvenementDemande.objects.filter(company=self.company).exists())

    def test_libelle_manquant_erreur(self):
        statut, message = creer_evenement_demande_import(self.company, {
            'date_debut': '2026-06-01', 'date_fin': '2026-06-30',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('libelle', message)

    def test_date_fin_avant_date_debut_erreur(self):
        statut, message = creer_evenement_demande_import(self.company, {
            'date_debut': '2026-06-30', 'date_fin': '2026-06-01',
            'libelle': 'Dates inversées',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('date_fin', message)

    def test_categorie_par_nom(self):
        statut, _ = creer_evenement_demande_import(self.company, {
            'categorie': 'Panneaux', 'date_debut': '2026-09-01',
            'date_fin': '2026-09-10', 'libelle': 'Promo catégorie',
        })
        self.assertEqual(statut, 'cree')
        ev = EvenementDemande.objects.get(
            company=self.company, libelle='Promo catégorie')
        self.assertEqual(ev.categorie_id, self.categorie.id)


class ImportEvenementsDemandeFrameworkApiTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-import-evt-api', 'Supply Import Évt API')
        self.admin = make_user(self.company, 'scm-import-evt-api-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5K', prix_vente=6000)

    def test_import_50_lignes_valides_cree_50_evenements(self):
        lignes = ['sku,date_debut,date_fin,impact_pct,type,libelle']
        for i in range(50):
            lignes.append(f'OND5K,2026-01-0{(i % 9) + 1},2026-01-28,10,promotion,Promo {i}')
        content = '\n'.join(lignes) + '\n'

        resp = auth(self.admin).post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'scm_evenement_demande',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 50)
        self.assertEqual(len(resp.data['skipped']), 0)
        self.assertEqual(
            EvenementDemande.objects.filter(company=self.company).count(), 50)

    def test_ligne_produit_introuvable_rejetee_sans_bloquer_les_autres(self):
        content = (
            'sku,date_debut,date_fin,impact_pct,type,libelle\n'
            'OND5K,2026-02-01,2026-02-28,15,promotion,Valide\n'
            'INEXISTANT,2026-02-01,2026-02-28,15,promotion,Invalide\n'
        )
        resp = auth(self.admin).post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'scm_evenement_demande',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertIn('produit introuvable', resp.data['skipped'][0]['raison'])
        self.assertEqual(
            EvenementDemande.objects.filter(company=self.company, libelle='Valide').count(), 1)

    def test_mode_maj_refuse_pour_cette_cible(self):
        resp = auth(self.admin).post(URL_IMPORT_COMMIT, {
            'file': make_csv('sku,libelle\nOND5K,X\n'),
            'target': 'scm_evenement_demande', 'mode': 'maj',
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)
