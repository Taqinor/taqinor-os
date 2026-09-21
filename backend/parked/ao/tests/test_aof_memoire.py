"""AOF133 — mémoire technique par SECTIONS COMPOSABLES.

Ce qui est prouvé ici :

* le mémoire s'ASSEMBLE et se REND (sections + gabarit Django) ;
* **la désignation d'un équipement n'apparaît qu'UNE fois en source** : elle
  vit dans le snapshot de l'équipement, jamais dans une section — donc une
  bascule ne demande qu'UN remplacement (le défaut réel : douze désignations à
  changer à la main) ;
* la section « géométries » est ALIMENTÉE par le contexte de calepinage, pas
  rédigée ;
* aucun mot de coût / marge / bénéfice ne sort dans un rendu client (garde
  local ; le ratchet AOF129 l'étend à tous les artefacts).

Run :
    python manage.py test apps.ao.tests.test_aof_memoire -v2
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.ao import services
from apps.ao.fabrique.gabarits import literaux_chiffres
from apps.ao.fabrique.rendus import memoire as rendu_memoire
from apps.ao.models import (
    AppelOffre, BatimentAO, EquipementAO, SectionMemoire, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company

#: Mots INTERDITS dans un rendu remis au maître d'ouvrage.
MOTS_INTERDITS = (
    "prix d'achat", 'coût de revient', 'cout de revient', 'marge',
    'bénéfice', 'benefice', 'maximum posable',
)


class BaseMemoire(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF133 Co',
                                              slug='aof133-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-133-1',
            objet='Centrale photovoltaïque en toiture',
            maitre_ouvrage='Fondation', soumissionnaire='PARTENAIRE SA',
            delai_execution_jours=120)
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')
        VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Allée 1,94 m', est_retenue=True,
            resultat={'total_modules': 314, 'kwc': '196.250'},
            preuve={'methode': 'balayage exhaustif'})
        self.batterie = services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE,
            designation='BOS-G 100 kWh', marque='BOS', quantite=Decimal('1'))
        call_command('seed_sections_memoire', company='aof133-co',
                     stdout=StringIO())


class TestContexte(BaseMemoire):
    def test_le_contexte_porte_les_geometries_retenues(self):
        contexte = rendu_memoire.contexte_memoire(self.ao)
        geometries = contexte['geometries']
        self.assertEqual(geometries['total_modules'], 314)
        self.assertEqual(geometries['puissance_kwc'], '196.250')
        self.assertEqual(geometries['lignes'][0]['batiment'], 'C')
        self.assertEqual(geometries['lignes'][0]['toiture'], '05H')

    def test_le_contexte_porte_le_snapshot_des_equipements(self):
        contexte = rendu_memoire.contexte_memoire(self.ao)
        batterie = contexte['equipements'][EquipementAO.Role.BATTERIE]
        self.assertEqual(batterie['designation'], 'BOS-G 100 kWh')

    def test_l_etude_est_derivee_des_geometries(self):
        contexte = rendu_memoire.contexte_memoire(self.ao)
        self.assertEqual(contexte['etude']['nombre_modules'], 314)
        self.assertEqual(contexte['etude']['nombre_batiments'], 1)


class TestAssemblage(BaseMemoire):
    def test_le_memoire_s_assemble_avec_la_section_geometries(self):
        blocs = rendu_memoire.assembler_memoire(self.ao)
        codes = [b['code'] for b in blocs]
        self.assertIn('METHODOLOGIE', codes)
        self.assertEqual(codes[-1], rendu_memoire.CODE_SECTION_GEOMETRIES)

    def test_la_section_geometries_est_alimentee_par_le_contexte(self):
        blocs = rendu_memoire.assembler_memoire(self.ao)
        geometries = blocs[-1]['corps']
        self.assertIn('314 modules', geometries)
        self.assertIn('196.250 kWc', geometries)
        self.assertIn('05H', geometries)

    def test_les_placeholders_sont_resolus(self):
        blocs = {b['code']: b['corps']
                 for b in rendu_memoire.assembler_memoire(self.ao)}
        self.assertIn('PARTENAIRE SA', blocs['ORGANISATION'])
        self.assertIn('120 jours', blocs['METHODOLOGIE'])
        self.assertNotIn('{{', blocs['METHODOLOGIE'])

    def test_une_condition_d_inclusion_non_satisfaite_exclut_la_section(self):
        SectionMemoire.objects.create(
            company=self.company, code='STOCKAGE_ABSENT',
            titre='Sans stockage', corps='Aucun stockage prévu.',
            conditions_inclusion={'equipements.batterie': False})
        codes = [b['code'] for b in rendu_memoire.assembler_memoire(self.ao)]
        self.assertNotIn('STOCKAGE_ABSENT', codes)

    def test_une_condition_satisfaite_inclut_la_section(self):
        SectionMemoire.objects.create(
            company=self.company, code='STOCKAGE_PRESENT',
            titre='Avec stockage', corps='Le stockage est prévu au marché.',
            conditions_inclusion={'equipements.batterie': True})
        codes = [b['code'] for b in rendu_memoire.assembler_memoire(self.ao)]
        self.assertIn('STOCKAGE_PRESENT', codes)


class TestSourceUniqueDeLaDesignation(BaseMemoire):
    """Le cœur d'AOF133 : UNE source, donc UN remplacement à la bascule."""

    def test_la_designation_n_apparait_dans_aucune_section_source(self):
        for section in SectionMemoire.objects.filter(company=self.company):
            self.assertNotIn('BOS-G', section.corps)
        # Ni dans le gabarit Django lui-même.
        from pathlib import Path

        from django.conf import settings

        gabarit = (Path(settings.BASE_DIR) / 'templates' / 'ao'
                   / 'memoire.html').read_text(encoding='utf-8')
        self.assertNotIn('BOS-G', gabarit)

    def test_changer_le_snapshot_change_TOUT_le_memoire_d_un_coup(self):
        avant = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertIn('BOS-G 100 kWh', avant)
        self.batterie.designation = 'BOS-B Pro-A3 120 kWh'
        self.batterie.save(update_fields=['designation'])
        apres = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertNotIn('BOS-G', apres)
        self.assertIn('BOS-B Pro-A3 120 kWh', apres)

    def test_aucune_section_seedee_ne_porte_de_litteral_chiffre(self):
        for section in SectionMemoire.objects.filter(company=self.company):
            self.assertEqual(
                literaux_chiffres(section.corps), [], section.code)


class TestRenduHtml(BaseMemoire):
    def test_le_memoire_se_rend(self):
        html = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertIn('Mémoire technique', html)
        self.assertIn('Centrale photovoltaïque en toiture', html)
        self.assertIn('PARTENAIRE SA', html)
        # Apostrophe typographique : le gabarit auto-échappe le contexte, une
        # apostrophe droite ne ressort JAMAIS telle quelle du rendu.
        self.assertIn('Géométries d’implantation retenues', html)

    def test_aucun_mot_de_cout_ne_sort_dans_le_rendu(self):
        """Garde local ; le ratchet AOF129 l'étend à tous les artefacts."""
        html = rendu_memoire.rendre_memoire_html(self.ao).lower()
        for mot in MOTS_INTERDITS:
            self.assertNotIn(mot, html, mot)

    def test_le_tableau_de_references_ne_liste_que_des_ao_gagnes(self):
        from apps.ao.models import ResultatAO

        autre = AppelOffre.objects.create(
            company=self.company, reference='AO-133-REF',
            objet='Toiture lycée', acheteur='Académie')
        ResultatAO.objects.create(
            company=self.company, appel_offre=autre,
            issue=ResultatAO.Issue.GAGNE)
        perdu = AppelOffre.objects.create(
            company=self.company, reference='AO-133-PERDU', objet='Perdu')
        ResultatAO.objects.create(
            company=self.company, appel_offre=perdu,
            issue=ResultatAO.Issue.PERDU)
        html = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertIn('Toiture lycée', html)
        self.assertNotIn('AO-133-PERDU', html)
