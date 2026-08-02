"""AOF140 — ``PlancheAO`` : indices AUTOMATIQUES + référence croisée mémoire.

Ce qui est prouvé ici :

* générer un indice supérieur ARCHIVE le précédent ;
* il est IMPOSSIBLE d'avoir deux planches actives de même code (contrainte en
  base, pas dans une vue) ;
* une planche citée à un indice PÉRIMÉ est détectée, avec le bon message ;
* l'indice n'est jamais saisi : il ne bouge que sur CHANGEMENT D'EMPREINTE ;
* cartouche et bandeau d'engagement sont fournis comme DONNÉES au rendu.

Run :
    python manage.py test apps.ao.tests.test_aof_planches_indices -v2
"""
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, CitationPlanche, PlancheAO, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company


class TestIndiceSuivant(SimpleTestCase):
    def test_la_suite_des_indices(self):
        self.assertEqual(services.indice_suivant(''), 'A')
        self.assertEqual(services.indice_suivant('A'), 'B')
        self.assertEqual(services.indice_suivant('H'), 'I')
        self.assertEqual(services.indice_suivant('Z'), 'AA')
        self.assertEqual(services.indice_suivant('AZ'), 'BA')


class BasePlanche(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF140 Co',
                                              slug='aof140-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-140-1', objet='Planches',
            maitre_ouvrage='Fondation', soumissionnaire='PARTENAIRE SA')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05')
        self.variante = VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Allée 1,94 m', est_retenue=True,
            resultat={'total_modules': 314, 'kwc': '196.250'},
            preuve={'methode': 'balayage exhaustif'})


class TestIndicesAutomatiques(BasePlanche):
    def test_la_premiere_planche_prend_l_indice_A(self):
        planche, creee = services.generer_indice_planche(
            self.ao, '05', empreinte='abc', variante=self.variante,
            toiture=self.toiture)
        self.assertTrue(creee)
        self.assertEqual(planche.indice, 'A')
        self.assertEqual(planche.reference_complete, '05A')

    def test_une_empreinte_inchangee_ne_cree_aucun_indice(self):
        premiere, _ = services.generer_indice_planche(
            self.ao, '05', empreinte='abc')
        seconde, creee = services.generer_indice_planche(
            self.ao, '05', empreinte='abc')
        self.assertFalse(creee)
        self.assertEqual(seconde.pk, premiere.pk)
        self.assertEqual(PlancheAO.objects.count(), 1)

    def test_un_changement_d_empreinte_archive_la_precedente(self):
        premiere, _ = services.generer_indice_planche(
            self.ao, '05', empreinte='abc')
        seconde, creee = services.generer_indice_planche(
            self.ao, '05', empreinte='def', motif='Obstacle écarté')
        self.assertTrue(creee)
        self.assertEqual(seconde.indice, 'B')
        premiere.refresh_from_db()
        self.assertEqual(premiere.statut, PlancheAO.Statut.ARCHIVEE)
        self.assertEqual(seconde.statut, PlancheAO.Statut.ACTIVE)
        self.assertEqual(seconde.motif_revision, 'Obstacle écarté')

    def test_deux_planches_actives_de_meme_code_sont_impossibles(self):
        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlancheAO.objects.create(
                company=self.company, appel_offre=self.ao,
                code_document='05', indice='Z',
                statut=PlancheAO.Statut.ACTIVE)

    def test_l_archivee_reste_consultable(self):
        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        services.generer_indice_planche(self.ao, '05', empreinte='def')
        historique = PlancheAO.objects.filter(
            appel_offre=self.ao, code_document='05').order_by('indice')
        self.assertEqual([p.indice for p in historique], ['A', 'B'])

    def test_deux_codes_vivent_leur_vie(self):
        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        planche_06, _ = services.generer_indice_planche(
            self.ao, '06', empreinte='xyz')
        self.assertEqual(planche_06.indice, 'A')
        self.assertEqual(PlancheAO.objects.filter(
            statut=PlancheAO.Statut.ACTIVE).count(), 2)

    def test_la_revision_est_tracee_au_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        services.generer_indice_planche(
            self.ao, '05', empreinte='def', motif='Cotes confirmées')
        ct = ContentType.objects.get_for_model(AppelOffre)
        entrees = Activity.objects.filter(
            content_type=ct, object_id=self.ao.pk, field='planche')
        self.assertEqual(entrees.count(), 2)
        self.assertEqual(entrees.order_by('id').last().new_value, '05B')


class TestCartoucheEtBandeau(BasePlanche):
    def test_le_cartouche_est_une_donnee(self):
        planche, _ = services.generer_indice_planche(
            self.ao, '05', empreinte='abc', variante=self.variante)
        self.assertEqual(planche.cartouche['code_document'], '05')
        self.assertEqual(planche.cartouche['indice'], 'A')
        self.assertEqual(planche.cartouche['soumissionnaire'],
                         'PARTENAIRE SA')
        self.assertEqual(planche.cartouche['maitre_ouvrage'], 'Fondation')

    def test_le_bandeau_porte_l_engagement_de_la_variante(self):
        planche, _ = services.generer_indice_planche(
            self.ao, '05', empreinte='abc', variante=self.variante)
        self.assertEqual(planche.bandeau_engagement['modules_engages'], 314)
        self.assertEqual(planche.bandeau_engagement['methode'],
                         'balayage exhaustif')

    def test_sans_variante_le_bandeau_reste_vide_plutot_qu_invente(self):
        planche, _ = services.generer_indice_planche(
            self.ao, '07', empreinte='abc')
        self.assertEqual(planche.bandeau_engagement, {})


class TestCitationsPerimees(BasePlanche):
    def _citation(self, code, indice, emplacement='Mémoire §3'):
        return CitationPlanche.objects.create(
            company=self.company, appel_offre=self.ao, code_document=code,
            indice_cite=indice, emplacement=emplacement)

    def test_une_citation_a_l_indice_courant_est_propre(self):
        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        self._citation('05', 'A')
        self.assertEqual(services.citations_perimees(self.ao), [])

    def test_une_citation_a_un_indice_perime_est_detectee(self):
        services.generer_indice_planche(self.ao, '05', empreinte='abc')
        self._citation('05', 'A')
        services.generer_indice_planche(self.ao, '05', empreinte='def')
        perimees = services.citations_perimees(self.ao)
        self.assertEqual(len(perimees), 1)
        self.assertEqual(perimees[0]['indice_cite'], 'A')
        self.assertEqual(perimees[0]['indice_actif'], 'B')
        self.assertIn("l'indice courant est B", perimees[0]['message'])
        self.assertIn('Mémoire §3', perimees[0]['message'])

    def test_une_citation_vers_une_planche_inexistante_est_detectee(self):
        self._citation('09', 'A', emplacement='Mémoire §7')
        perimees = services.citations_perimees(self.ao)
        self.assertEqual(len(perimees), 1)
        self.assertIsNone(perimees[0]['indice_actif'])
        self.assertIn("n'existe pas", perimees[0]['message'])

    def test_le_defaut_reel_05H_06H_06I(self):
        """Le dossier réel numérotait 05H/06H/06I À LA MAIN — plus jamais."""
        for empreinte in ('e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8'):
            planche, _ = services.generer_indice_planche(
                self.ao, '05', empreinte=empreinte)
        self.assertEqual(planche.reference_complete, '05H')
        self._citation('05', 'G', emplacement='Mémoire §4')
        perimees = services.citations_perimees(self.ao)
        self.assertEqual(perimees[0]['indice_actif'], 'H')

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF140 X', slug='aof140-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-140-X', objet='X')
        CitationPlanche.objects.create(
            company=autre, appel_offre=ao, code_document='05',
            indice_cite='A')
        self.assertEqual(services.citations_perimees(self.ao), [])
