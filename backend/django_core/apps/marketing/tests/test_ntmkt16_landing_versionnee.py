"""NTMKT16 — Landing pages versionnées et publiées.

Couvre : éditer un formulaire crée une v2 en BROUILLON (la page publique ne
bouge pas), publier bascule la page publique, l'historique reste consultable,
et le rendu public reste EXACTEMENT celui d'avant tant qu'aucune version n'est
publiée.
"""
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import FormulaireIntake, VersionFormulaireIntake


class VersionsLandingTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt16', nom='NTMKT16')
        self.formulaire = FormulaireIntake.objects.create(
            company=self.co, nom='Pompage', slug='pompage',
            champs=[{'nom': 'nom'}], actif=True)

    def test_sans_version_publiee_le_rendu_public_est_inchange(self):
        self.assertIsNone(
            mkt_services.derniere_version_publiee(self.formulaire))
        url = reverse('mkt-formulaire-intake-public',
                      kwargs={'slug': 'pompage'})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['champs'], [{'nom': 'nom'}])
        self.assertIsNone(res.json()['page'])

    def test_chaque_edition_cree_une_nouvelle_version_brouillon(self):
        v1 = mkt_services.creer_version_formulaire(
            self.formulaire, {'titre': 'V1'})
        v2 = mkt_services.creer_version_formulaire(
            self.formulaire, {'titre': 'V2'})
        self.assertEqual([v1.version, v2.version], [1, 2])
        self.assertFalse(v2.publie)
        self.assertEqual(v2.company_id, self.co.id)
        # Tant que rien n'est publié, la page publique reste sans contenu.
        self.assertIsNone(
            mkt_services.derniere_version_publiee(self.formulaire))

    def test_publier_bascule_la_page_publique(self):
        v1 = mkt_services.creer_version_formulaire(
            self.formulaire, {'titre': 'V1', 'pitch': 'Premier'})
        mkt_services.publier_version_formulaire(v1)
        url = reverse('mkt-formulaire-intake-public',
                      kwargs={'slug': 'pompage'})
        self.assertEqual(self.client.get(url).json()['page']['titre'], 'V1')

        v2 = mkt_services.creer_version_formulaire(
            self.formulaire, {'titre': 'V2', 'pitch': 'Second'})
        # v2 en brouillon : la page publique montre encore v1.
        self.assertEqual(self.client.get(url).json()['page']['titre'], 'V1')
        mkt_services.publier_version_formulaire(v2)
        page = self.client.get(url).json()['page']
        self.assertEqual(page['titre'], 'V2')
        self.assertEqual(page['version'], 2)
        # L'historique reste consultable.
        self.assertEqual(
            VersionFormulaireIntake.objects.filter(
                formulaire=self.formulaire).count(), 2)

    def test_publier_est_idempotent(self):
        v1 = mkt_services.creer_version_formulaire(self.formulaire, {})
        mkt_services.publier_version_formulaire(v1)
        premiere_date = v1.date_publication
        mkt_services.publier_version_formulaire(v1)
        v1.refresh_from_db()
        self.assertEqual(v1.date_publication, premiere_date)

    def test_numero_de_version_ne_regresse_pas_apres_suppression(self):
        mkt_services.creer_version_formulaire(self.formulaire, {})
        v2 = mkt_services.creer_version_formulaire(self.formulaire, {})
        v2.delete()
        v3 = mkt_services.creer_version_formulaire(self.formulaire, {})
        # Plus-haut-utilisé + 1 (jamais un count(), qui aurait redonné 2).
        self.assertEqual(v3.version, 3)

    def test_scoping_societe_de_la_page_publique(self):
        autre = Company.objects.create(slug='ntmkt16b', nom='Autre')
        formulaire_b = FormulaireIntake.objects.create(
            company=autre, nom='Autre', slug='autre-slug', actif=True)
        v = mkt_services.creer_version_formulaire(
            formulaire_b, {'titre': 'Chez B'})
        mkt_services.publier_version_formulaire(v)
        url = reverse('mkt-formulaire-intake-public',
                      kwargs={'slug': 'pompage'})
        self.assertIsNone(self.client.get(url).json()['page'])
