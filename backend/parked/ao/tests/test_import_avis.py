"""AOF169 — import des avis de marchés publics : l'AMONT du tunnel.

Trois choses sont verrouillées ici :

  1. **Un CSV d'avis crée des affaires DÉDUPLIQUÉES par référence acheteur**,
     et un ré-import n'en duplique AUCUNE. Un avis paraît, puis paraît
     rectifié : la seconde parution met à jour, elle n'ouvre pas un second
     dossier.
  2. **AUCUN appel réseau vers un portail public** n'existe dans ``apps/ao``.
     C'est la règle #5 du dépôt, et c'est un test de GREP sur tout le paquet —
     pas une bonne intention en commentaire. Un scraping à risque ToS exigerait
     un fichier ``tos_risk/`` et l'accord explicite du fondateur ; ici la voie
     choisie est l'import, donc la question ne se pose pas.
  3. **NOTRE référence reste générée par la plateforme.** La référence de
     l'acheteur va dans son propre champ : les confondre rendrait impossible de
     retrouver un dossier à partir de l'avis publié, et ferait entrer dans
     notre séquence un numéro que nous ne contrôlons pas.

Run :
    python manage.py test apps.ao.tests.test_import_avis -v2
"""
import io
import os
import re
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.ao import imports, services
from apps.ao.models import AppelOffre
from apps.ao.platform import PLATFORM
from authentication.models import Company

#: Racine du paquet ``apps/ao`` — cible du test de grep anti-scraping.
PAQUET_AO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Ce qu'aucun fichier d'``apps/ao`` n'a le droit de contenir (règle #5).
MOTIFS_INTERDITS = (
    r'marchespublics\.gov\.ma',
    r'\brequests\.(get|post|put|patch|delete)\b',
    r'\bhttpx\.',
    r'\burllib\.request\b',
    r'\bBeautifulSoup\b',
    r'\bselenium\b',
    r'\bplaywright\b',
    r'\bscrapy\b',
)

ENTETE = ('reference;acheteur;objet;lot;montant;date_limite;date_ouverture;'
          'mode_passation\n')
LIGNE_1 = ('AO/2026/014;Commune de Berrechid;Centrale PV 500 kWc;Lot 1;'
           '4200000,00;15/09/2026;16/09/2026;appel_ouvert\n')
LIGNE_2 = ('AO/2026/021;Province de Settat;Pompage solaire;;'
           '1250000;01/10/2026;02/10/2026;consultation\n')


def _csv(*lignes):
    return (ENTETE + ''.join(lignes)).encode('utf-8')


class _Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aof169-co', defaults={'nom': 'AOF169'})
        self.autre, _ = Company.objects.get_or_create(
            slug='aof169-autre', defaults={'nom': 'Autre'})


class UnCSVDAvisCreeDesAffaires(_Base):
    def test_deux_avis_creent_deux_affaires(self):
        rapport = imports.importer_avis(
            self.company, _csv(LIGNE_1, LIGNE_2), 'avis.csv')
        self.assertEqual(rapport['crees'], 2)
        self.assertEqual(rapport['mis_a_jour'], 0)
        self.assertEqual(rapport['rejets'], [])
        self.assertEqual(AppelOffre.objects.filter(
            company=self.company).count(), 2)

    def test_les_champs_de_l_avis_sont_repris(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        ao = AppelOffre.objects.get(company=self.company,
                                    reference_acheteur='AO/2026/014')
        self.assertEqual(ao.acheteur, 'Commune de Berrechid')
        self.assertEqual(ao.objet, 'Centrale PV 500 kWc')
        self.assertEqual(ao.lot, 'Lot 1')
        self.assertEqual(ao.montant_estime, Decimal('4200000.00'))
        self.assertEqual(ao.date_limite, date(2026, 9, 15))
        self.assertEqual(ao.date_ouverture_plis, date(2026, 9, 16))
        self.assertEqual(ao.mode_passation, 'appel_ouvert')

    def test_une_affaire_importee_part_au_statut_identifie(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        ao = AppelOffre.objects.get(company=self.company)
        self.assertEqual(ao.statut, AppelOffre.Statut.IDENTIFIE)

    def test_notre_reference_est_generee_par_la_plateforme(self):
        """La référence de l'acheteur n'entre JAMAIS dans notre séquence."""
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        ao = AppelOffre.objects.get(company=self.company)
        self.assertNotEqual(ao.reference, 'AO/2026/014')
        self.assertTrue(re.match(r'^AO-\d{6}-\d+$', ao.reference),
                        ao.reference)
        self.assertEqual(ao.reference_acheteur, 'AO/2026/014')


class UnReImportNeDupliqueRien(_Base):
    def test_le_meme_fichier_deux_fois_ne_cree_rien_de_plus(self):
        fichier = _csv(LIGNE_1, LIGNE_2)
        imports.importer_avis(self.company, fichier, 'avis.csv')
        second = imports.importer_avis(self.company, fichier, 'avis.csv')
        self.assertEqual(second['crees'], 0)
        self.assertEqual(second['mis_a_jour'], 2)
        self.assertEqual(AppelOffre.objects.filter(
            company=self.company).count(), 2)

    def test_un_avis_rectifie_met_a_jour_sans_renumeroter(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        avant = AppelOffre.objects.get(company=self.company)
        rectifie = ('AO/2026/014;Commune de Berrechid;Centrale PV 600 kWc;'
                    'Lot 1;4900000,00;30/09/2026;01/10/2026;appel_ouvert\n')
        imports.importer_avis(self.company, _csv(rectifie), 'avis.csv')
        apres = AppelOffre.objects.get(company=self.company)
        self.assertEqual(apres.pk, avant.pk)
        self.assertEqual(apres.reference, avant.reference)
        self.assertEqual(apres.objet, 'Centrale PV 600 kWc')
        self.assertEqual(apres.date_limite, date(2026, 9, 30))

    def test_un_avis_rectifie_n_efface_pas_ce_qu_il_ne_redit_pas(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        partiel = 'reference;objet\nAO/2026/014;Centrale PV 600 kWc\n'
        imports.importer_avis(self.company, partiel.encode('utf-8'),
                              'avis.csv')
        ao = AppelOffre.objects.get(company=self.company)
        self.assertEqual(ao.objet, 'Centrale PV 600 kWc')
        self.assertEqual(ao.acheteur, 'Commune de Berrechid')
        self.assertEqual(ao.date_limite, date(2026, 9, 15))

    def test_un_avis_deja_avance_ne_recule_pas_d_etape(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        AppelOffre.objects.filter(company=self.company).update(
            statut=AppelOffre.Statut.CHIFFRAGE)
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        ao = AppelOffre.objects.get(company=self.company)
        self.assertEqual(ao.statut, AppelOffre.Statut.CHIFFRAGE)

    def test_la_deduplication_est_bornee_a_la_societe(self):
        """Deux sociétés du même ERP ne partagent jamais leurs dossiers."""
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        rapport = imports.importer_avis(self.autre, _csv(LIGNE_1), 'avis.csv')
        self.assertEqual(rapport['crees'], 1)
        self.assertEqual(AppelOffre.objects.filter(
            reference_acheteur='AO/2026/014').count(), 2)


class LesLignesInvalidesSontRejeteesUneParUne(_Base):
    def test_une_ligne_sans_reference_est_rejetee_sans_bloquer_les_autres(self):
        sans_reference = ';Commune X;Objet valide;;;;;\n'
        rapport = imports.importer_avis(
            self.company, _csv(sans_reference, LIGNE_1), 'avis.csv')
        self.assertEqual(rapport['crees'], 1)
        self.assertEqual(len(rapport['rejets']), 1)
        self.assertTrue(any('référence acheteur' in e
                            for e in rapport['rejets'][0]['erreurs']))

    def test_une_date_illisible_est_rejetee_avec_son_motif(self):
        mauvaise_date = ('AO/2026/099;Commune Y;Objet;;;pas-une-date;;\n')
        rapport = imports.importer_avis(
            self.company, _csv(mauvaise_date), 'avis.csv')
        self.assertEqual(rapport['crees'], 0)
        self.assertTrue(any("n'est pas une date lisible" in e
                            for e in rapport['rejets'][0]['erreurs']))

    def test_un_mode_de_passation_inconnu_est_rejete(self):
        mauvais_mode = ('AO/2026/098;Commune Z;Objet;;;;;mode_invente\n')
        rapport = imports.importer_avis(
            self.company, _csv(mauvais_mode), 'avis.csv')
        self.assertTrue(any('mode de passation' in e
                            for e in rapport['rejets'][0]['erreurs']))

    def test_l_apercu_ne_touche_jamais_la_base(self):
        avant = AppelOffre.objects.count()
        apercu = imports.previsualiser(_csv(LIGNE_1, LIGNE_2), 'avis.csv',
                                       'avis')
        self.assertEqual(apercu['valides'], 2)
        self.assertEqual(AppelOffre.objects.count(), avant)


class LaSaisieManuelleSuitLesMemesRegles(_Base):
    def test_une_saisie_valide_cree_l_affaire(self):
        ao, cree, erreurs = imports.saisir_avis(self.company, {
            'reference_acheteur': 'AO/2026/030', 'objet': 'Ombrières PV',
            'acheteur': 'Université', 'date_limite': '20/11/2026',
        })
        self.assertTrue(cree)
        self.assertEqual(erreurs, [])
        self.assertEqual(ao.date_limite, date(2026, 11, 20))

    def test_une_saisie_incomplete_est_refusee_avec_ses_motifs(self):
        ao, cree, erreurs = imports.saisir_avis(self.company, {'objet': ''})
        self.assertIsNone(ao)
        self.assertFalse(cree)
        self.assertEqual(len(erreurs), 2)

    def test_la_saisie_deduplique_comme_l_import(self):
        imports.importer_avis(self.company, _csv(LIGNE_1), 'avis.csv')
        ao, cree, _e = imports.saisir_avis(self.company, {
            'reference_acheteur': 'AO/2026/014', 'objet': 'Autre libellé'})
        self.assertFalse(cree)
        self.assertEqual(AppelOffre.objects.filter(
            company=self.company).count(), 1)


class LeServiceEstLePointDeContactUnique(_Base):
    def test_une_reference_acheteur_vide_est_refusee(self):
        with self.assertRaises(ValidationError):
            services.creer_appel_offre_depuis_avis(
                self.company, {'objet': 'Sans référence'})

    def test_le_service_existe_sous_le_nom_attendu_par_la_veille(self):
        """``apps/veille_ao`` (Groupe VAO) appellera CETTE fonction.

        Si un futur agent en ajoute une seconde, l'ERP aura deux règles de
        déduplication d'avis — exactement ce que ce nom unique empêche.
        """
        self.assertTrue(callable(
            getattr(services, 'creer_appel_offre_depuis_avis', None)))

    def test_la_spec_avis_est_declaree_au_manifeste(self):
        self.assertIn('avis', PLATFORM['import_specs'])
        self.assertIn('avis', imports.FIELD_MAPS_AO)


class AucunAppelReseauVersUnPortailPublic(SimpleTestCase):
    """Règle #5 : la voie choisie est l'IMPORT, donc rien ne sort du process."""

    def _sources(self):
        for racine, _dirs, fichiers in os.walk(PAQUET_AO):
            if '__pycache__' in racine or os.sep + 'tests' in racine:
                continue
            for nom in fichiers:
                if nom.endswith('.py'):
                    yield os.path.join(racine, nom)

    def test_le_paquet_ao_ne_contient_aucun_appel_reseau(self):
        trouves = []
        for chemin in self._sources():
            with io.open(chemin, encoding='utf-8') as fh:
                source = fh.read()
            for motif in MOTIFS_INTERDITS:
                if re.search(motif, source):
                    trouves.append('%s : %s' % (
                        os.path.relpath(chemin, PAQUET_AO), motif))
        self.assertEqual(
            trouves, [],
            "appel réseau détecté dans apps/ao — la collecte automatique "
            "d'avis vit dans apps/veille_ao, sous gate de la règle #5 "
            '(fichier tos_risk/ + accord écrit du fondateur).')

    def test_le_test_de_grep_voit_reellement_les_fichiers(self):
        """Garde du garde : un balayage vide passerait toujours."""
        fichiers = list(self._sources())
        self.assertGreater(len(fichiers), 5)
        self.assertTrue(any(f.endswith('imports.py') for f in fichiers))
