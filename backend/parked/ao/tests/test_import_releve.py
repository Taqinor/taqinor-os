"""AOF30 — import CSV d'un relevé (obstacles + chaînes de cotes).

Besoin réel : un technicien relève une toiture sur tableur, hors ligne, sans
tablette. Sans cette porte, son relevé se resaisit à la main — et une saisie
manuelle de 28 obstacles produit des écarts qu'on ne détecte qu'au calepinage.

Trois garanties testées :
  1. un relevé de 28 obstacles s'importe et redonne le MÊME compte que la
     saisie manuelle ;
  2. une provenance invalide est rejetée LIGNE PAR LIGNE, avec un motif en
     français, sans casser les 27 autres ;
  3. le ré-import du même fichier est IDEMPOTENT (mise à jour, pas doublon).

Run :
    python manage.py test apps.ao.tests.test_import_releve -v2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ao import imports
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, ObstacleAO, ReleveAO, ToitureAO,
)
from authentication.models import Company

ENTETE_OBSTACLES = 'repere,nature,x0,x1,y0,y1,hauteur,provenance\n'


def csv_obstacles(nombre=28, provenance='MESURE'):
    lignes = [ENTETE_OBSTACLES]
    for i in range(nombre):
        lignes.append(
            f'O{i:02d},souche,{i}.0,{i + 1}.0,0.0,1.0,0.8,{provenance}\n')
    return ''.join(lignes).encode('utf-8')


#: Séparateur ``|`` entre segments : un ``;`` dans une cellule ferait basculer
#: la détection automatique de délimiteur du CSV et disloquerait la ligne.
CSV_CHAINES = (
    'libelle,axe,segments,mesure,tolerance\n'
    'Façade sud,x,A→B=19.36|B→C=7.92|C→D=4.50|D→E=10.50|E→F=8.50,51.10,0.05\n'
    'Pignon,y,P1=5.0:A_CONFIRMER|P2=7.0,12.0,0.02\n'
).encode('utf-8')


class TestCartesEtParsing(SimpleTestCase):
    def test_les_trois_specs_existent(self):
        """AOF30 posait deux specs ; AOF169 en a ajouté une TROISIÈME.

        ``avis`` (l'amont du tunnel : les avis de marchés publiés créent les
        ``AppelOffre``) est déclaré dans ``imports.FIELD_MAPS_AO`` et exporté
        par ``importer_avis``. La liste gelée ici datait d'AOF30 et refusait
        une spec pourtant voulue — c'est la LISTE qui était périmée, pas le
        module.
        """
        self.assertEqual(set(imports.FIELD_MAPS_AO),
                         {'obstacles', 'chaines', 'avis'})

    def test_les_champs_du_releve_sont_mappes(self):
        carte = imports.FIELD_MAPS_AO['obstacles']
        for entete in ('repere', 'nature', 'x0', 'x1', 'y0', 'y1',
                       'hauteur', 'provenance'):
            self.assertIn(entete, carte, entete)
        carte_chaines = imports.FIELD_MAPS_AO['chaines']
        for entete in ('libelle', 'axe', 'segments', 'mesure', 'tolerance'):
            self.assertIn(entete, carte_chaines, entete)

    def test_apercu_ne_touche_pas_la_base(self):
        """La classe est un ``SimpleTestCase`` : c'est ÇA, la preuve.

        Sous ``SimpleTestCase``, toute requête vers ``default`` lève
        ``DatabaseOperationForbidden``. Si ``previsualiser`` interrogeait ou
        écrivait la base, cet appel exploserait. Compter les obstacles pour
        « vérifier » qu'il n'y en a aucun était donc contre-productif :
        c'était le COMPTAGE lui-même — pas ``previsualiser`` — qui touchait
        la base et faisait échouer le test.
        """
        apercu = imports.previsualiser(
            csv_obstacles(3), 'releve.csv', 'obstacles')
        self.assertEqual(apercu['valides'], 3)
        self.assertEqual(apercu['rejetees'], 0)

    def test_provenance_invalide_rejetee_avec_motif_francais(self):
        contenu = (ENTETE_OBSTACLES
                   + 'A,souche,0,1,0,1,0.8,MESURE\n'
                   + 'B,souche,0,1,0,1,0.8,DEVINETTE\n').encode('utf-8')
        apercu = imports.previsualiser(contenu, 'r.csv', 'obstacles')
        self.assertEqual(apercu['valides'], 1)
        self.assertEqual(apercu['rejetees'], 1)
        rejet = [x for x in apercu['lignes'] if x['erreurs']][0]
        self.assertIn('provenance', rejet['erreurs'][0])
        self.assertIn('DEVINETTE', rejet['erreurs'][0])

    def test_repere_manquant_rejete(self):
        contenu = (ENTETE_OBSTACLES
                   + ',souche,0,1,0,1,0.8,MESURE\n').encode('utf-8')
        apercu = imports.previsualiser(contenu, 'r.csv', 'obstacles')
        self.assertEqual(apercu['rejetees'], 1)
        self.assertIn('repère', apercu['lignes'][0]['erreurs'][0])

    def test_nombre_invalide_rejete(self):
        contenu = (ENTETE_OBSTACLES
                   + 'A,souche,zero,1,0,1,0.8,MESURE\n').encode('utf-8')
        apercu = imports.previsualiser(contenu, 'r.csv', 'obstacles')
        self.assertEqual(apercu['rejetees'], 1)
        self.assertIn("n'est pas un nombre",
                      apercu['lignes'][0]['erreurs'][0])

    def test_parsing_des_segments(self):
        apercu = imports.previsualiser(CSV_CHAINES, 'c.csv', 'chaines')
        self.assertEqual(apercu['valides'], 2)
        segments = apercu['lignes'][0]['champs']['segments']
        self.assertEqual(len(segments), 5)
        self.assertEqual(segments[0], {'libelle': 'A→B', 'valeur_m': 19.36,
                                       'statut': 'MESURE'})
        self.assertEqual(apercu['lignes'][1]['champs']['segments'][0][
            'statut'], 'A_CONFIRMER')

    def test_segment_mal_forme_rejete(self):
        contenu = (
            'libelle,axe,segments,mesure\n'
            'Sud,x,A→B,10.0\n'
        ).encode('utf-8')
        apercu = imports.previsualiser(contenu, 'c.csv', 'chaines')
        self.assertEqual(apercu['rejetees'], 1)
        self.assertIn('format attendu', apercu['lignes'][0]['erreurs'][0])


class TestImportEffectif(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF30 Co', slug='aof30-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-30-1', objet='Import')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def test_28_obstacles_donnent_28_obstacles(self):
        resultat = imports.importer_obstacles(
            self.toiture, csv_obstacles(28), 'releve.csv')
        self.assertEqual(resultat['crees'], 28)
        self.assertEqual(resultat['rejets'], [])
        self.assertEqual(self.toiture.obstacles.count(), 28)

    def test_reimport_idempotent_par_repere(self):
        imports.importer_obstacles(
            self.toiture, csv_obstacles(28), 'releve.csv')
        resultat = imports.importer_obstacles(
            self.toiture, csv_obstacles(28), 'releve.csv')
        self.assertEqual(resultat['crees'], 0)
        self.assertEqual(resultat['mis_a_jour'], 28)
        self.assertEqual(self.toiture.obstacles.count(), 28)

    def test_une_ligne_invalide_ne_casse_pas_l_import(self):
        contenu = (ENTETE_OBSTACLES
                   + 'A,souche,0,1,0,1,0.8,MESURE\n'
                   + 'B,souche,0,1,0,1,0.8,DEVINETTE\n'
                   + 'C,souche,0,1,0,1,0.8,PLAN\n').encode('utf-8')
        resultat = imports.importer_obstacles(
            self.toiture, contenu, 'releve.csv')
        self.assertEqual(resultat['crees'], 2)
        self.assertEqual(len(resultat['rejets']), 1)
        self.assertEqual(
            set(self.toiture.obstacles.values_list('repere', flat=True)),
            {'A', 'C'})

    def test_le_degagement_est_applique_a_l_import(self):
        imports.importer_obstacles(
            self.toiture, csv_obstacles(1, provenance='DEVINE'), 'r.csv')
        obstacle = self.toiture.obstacles.get(repere='O00')
        self.assertEqual(obstacle.provenance, 'DEVINE')
        self.assertEqual(obstacle.degagement_m, Decimal('0.50'))
        self.assertTrue(obstacle.regle_degagement)
        self.assertFalse(obstacle.engageable)

    def test_import_rattache_le_releve(self):
        import datetime

        releve = ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=datetime.date(2026, 7, 27), contradictoire=True)
        imports.importer_obstacles(
            self.toiture, csv_obstacles(3), 'r.csv', releve=releve)
        self.assertEqual(
            self.toiture.obstacles.filter(releve=releve).count(), 3)

    def test_import_des_chaines_calcule_la_fermeture(self):
        resultat = imports.importer_chaines(
            self.toiture, CSV_CHAINES, 'chaines.csv')
        self.assertEqual(resultat['crees'], 2)
        chaine = ChaineCotes.objects.get(
            toiture=self.toiture, libelle='Façade sud')
        self.assertEqual(chaine.residu_m, Decimal('0.320'))
        self.assertEqual(chaine.verdict, ChaineCotes.Verdict.ECART)
        self.assertEqual(chaine.tolerance_m, Decimal('0.050'))

    def test_reimport_des_chaines_idempotent(self):
        imports.importer_chaines(self.toiture, CSV_CHAINES, 'c.csv')
        resultat = imports.importer_chaines(
            self.toiture, CSV_CHAINES, 'c.csv')
        self.assertEqual(resultat['crees'], 0)
        self.assertEqual(resultat['mis_a_jour'], 2)
        self.assertEqual(self.toiture.chaines_cotes.count(), 2)

    def test_import_scope_societe(self):
        autre = Company.objects.create(nom='AOF30 X', slug='aof30-x')
        imports.importer_obstacles(self.toiture, csv_obstacles(2), 'r.csv')
        self.assertEqual(
            ObstacleAO.objects.filter(company=autre).count(), 0)
        self.assertEqual(
            ObstacleAO.objects.filter(company=self.company).count(), 2)
