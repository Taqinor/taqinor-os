"""VAO28 — import de fichier d'avis DANS LE SAS.

Le « Done = » :
  * un CSV d'agrégateur ou de portail sectoriel s'importe dans le sas ;
  * ré-import IDEMPOTENT (empreinte de niveau 2, VAO11) ;
  * rejets LISIBLES, ligne à ligne, en français ;
  * ``import_specs`` déclaré dans ``platform.py`` — et seulement une fois câblé.

Coordination AOF169 : ce chemin alimente le SAS (un humain trie) ;
``apps/ao/imports.importer_avis`` crée des AFFAIRES. Les deux ne fusionnent
jamais — un fichier d'agrégateur de 400 lignes ouvrirait sinon 400 dossiers
dont 380 seraient du bruit. Un test le verrouille.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.veille_ao.imports import (
    FIELD_MAPS_VEILLE, SPEC_AVIS_VEILLE, importer_avis, previsualiser,
)
from apps.veille_ao.models import (
    AvisMarche, MotCleVeille, NiveauMotCle, PorteeExclusion, RegleExclusion,
    SourceVeille, StatutAvis, TypeSource,
)
from apps.veille_ao.platform import PLATFORM

EN_TETES = ('Référence;Objet;Acheteur;Date limite;Montant;Lieu\n')
CSV_AGREGATEUR = (
    EN_TETES
    + 'AO-2026-001;Pompage solaire à Figuig;Commune de Figuig;'
      '20/12/2026 10:00;450000;Figuig\n'
    + 'AO-2026-002;Luminaires solaires;ONEE Branche Eau;'
      '15/01/2027;120000,50;Rabat\n'
)


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Import')
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)

    def _importer(self, texte=CSV_AGREGATEUR, nom='agregateur.csv'):
        return importer_avis(self.company, texte.encode('utf-8'), nom)


class ManifesteTests(SimpleTestCase):
    def test_la_spec_est_declaree_dans_le_manifeste_plateforme(self):
        self.assertIn(SPEC_AVIS_VEILLE, PLATFORM['import_specs'])

    def test_la_carte_d_en_tetes_couvre_les_libelles_courants(self):
        carte = FIELD_MAPS_VEILLE[SPEC_AVIS_VEILLE]
        for entete in ('reference', 'objet', 'acheteur', 'date_limite',
                       'montant', 'lieu'):
            self.assertIn(entete, carte, entete)


class ApercuTests(_Base):
    def test_l_apercu_ne_touche_JAMAIS_la_base(self):
        apercu = previsualiser(CSV_AGREGATEUR.encode('utf-8'), 'a.csv')
        self.assertEqual(apercu['valides'], 2)
        self.assertEqual(apercu['rejetees'], 0)
        self.assertEqual(AvisMarche.objects.count(), 0)

    def test_l_apercu_annonce_EXACTEMENT_ce_que_l_import_fera(self):
        apercu = previsualiser(CSV_AGREGATEUR.encode('utf-8'), 'a.csv')
        resultat = self._importer()
        self.assertEqual(apercu['valides'], resultat['crees'])


class ImportTests(_Base):
    def test_un_csv_d_agregateur_entre_dans_le_sas(self):
        resultat = self._importer()

        self.assertEqual(resultat['crees'], 2)
        self.assertEqual(AvisMarche.objects.filter(
            company=self.company).count(), 2)
        avis = AvisMarche.objects.get(reference_avis='AO-2026-001')
        self.assertEqual(avis.acheteur, 'Commune de Figuig')
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)
        self.assertIsNotNone(avis.date_limite_remise)
        self.assertEqual(str(avis.montant_estime), '450000')

    def test_la_virgule_decimale_francaise_est_lue(self):
        self._importer()
        avis = AvisMarche.objects.get(reference_avis='AO-2026-002')
        self.assertEqual(str(avis.montant_estime), '120000.50')

    def test_les_avis_importes_sont_scorés_comme_les_autres(self):
        self._importer()
        avis = AvisMarche.objects.get(reference_avis='AO-2026-001')
        self.assertEqual(avis.score, 10)
        self.assertEqual(avis.mots_cles_declenches, ['solaire'])

    def test_la_source_par_defaut_est_import_de_fichier(self):
        resultat = self._importer()
        source = SourceVeille.objects.get(pk=resultat['source_id'])
        self.assertEqual(source.type_source, TypeSource.IMPORT_CSV)

    def test_les_regles_d_exclusion_s_appliquent_a_l_import(self):
        RegleExclusion.objects.create(
            company=self.company, portee=PorteeExclusion.ACHETEUR,
            valeur='ONEE', motif='Hors périmètre', actif=True)

        resultat = self._importer()

        self.assertEqual(resultat['auto_ignores'], 1)
        self.assertEqual(
            AvisMarche.objects.get(reference_avis='AO-2026-002').statut,
            StatutAvis.IGNORE)


class IdempotenceTests(_Base):
    def test_reimporter_le_MEME_fichier_ne_double_pas_le_sas(self):
        self._importer()
        second = self._importer()

        self.assertEqual(second['crees'], 0)
        self.assertEqual(second['mis_a_jour'], 2)
        self.assertEqual(AvisMarche.objects.count(), 2)

    def test_une_ligne_RECTIFIEE_met_a_jour_au_lieu_de_dupliquer(self):
        self._importer()
        rectifie = (
            EN_TETES
            + 'AO-2026-001;Pompage solaire à Figuig — LOT 2;'
              'Commune de Figuig;20/12/2026 10:00;450000;Figuig\n')

        self._importer(rectifie, 'rectif.csv')

        self.assertEqual(AvisMarche.objects.count(), 2)
        self.assertIn('LOT 2', AvisMarche.objects.get(
            reference_avis='AO-2026-001').objet)


class RejetsTests(_Base):
    def test_une_ligne_fautive_n_annule_pas_les_autres(self):
        texte = (
            EN_TETES
            + 'AO-1;Pompage solaire;Commune A;20/12/2026;100000;Figuig\n'
            + 'AO-2;Autre lot;Commune B;pas-une-date;200000;Rabat\n'
            + 'AO-3;Luminaires solaires;Commune C;01/02/2027;300000;Rabat\n')

        resultat = self._importer(texte, 'melange.csv')

        self.assertEqual(resultat['crees'], 2)
        self.assertEqual(len(resultat['rejets']), 1)
        self.assertEqual(resultat['rejets'][0]['numero'], 3)

    def test_le_motif_de_rejet_est_en_francais_et_NOMME_le_champ(self):
        texte = EN_TETES + 'AO-9;Objet;Acheteur;pas-une-date;;\n'
        resultat = self._importer(texte, 'rejet.csv')
        motif = resultat['rejets'][0]['erreurs'][0]
        self.assertIn('date limite', motif)
        self.assertIn('jj/mm/aaaa', motif)

    def test_un_montant_illisible_est_rejete_lisiblement(self):
        texte = EN_TETES + 'AO-9;Objet;Acheteur;20/12/2026;beaucoup;\n'
        resultat = self._importer(texte, 'rejet.csv')
        self.assertIn('montant estimé', resultat['rejets'][0]['erreurs'][0])

    def test_une_ligne_sans_objet_ni_acheteur_est_rejetee(self):
        texte = EN_TETES + 'AO-9;;;20/12/2026;100;\n'
        resultat = self._importer(texte, 'vide.csv')
        self.assertEqual(len(resultat['rejets']), 1)
        self.assertIn('Ligne vide', resultat['rejets'][0]['erreurs'][0])


class MultiTenantTests(_Base):
    def test_l_import_n_ecrit_que_dans_la_societe_appelante(self):
        autre = Company.objects.create(nom='Autre société')
        self._importer()
        self.assertEqual(AvisMarche.objects.filter(company=autre).count(), 0)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 2)


class CoordinationAof169Tests(SimpleTestCase):
    """Les deux chemins d'import coexistent — ils ne fusionnent JAMAIS.

    Garde de source : ce module ne crée aucune affaire. Un fichier
    d'agrégateur de 400 lignes doit remplir le SAS, jamais ouvrir 400 dossiers
    dont 380 seraient du bruit.
    """

    def test_l_import_du_sas_ne_cree_AUCUN_appel_d_offres(self):
        import pathlib

        source = (pathlib.Path(__file__).resolve().parents[1]
                  / 'imports.py').read_text(encoding='utf-8')
        for interdit in ('creer_appel_offre_depuis_avis', 'AppelOffre',
                         'apps.ao.models'):
            self.assertNotIn(interdit, source, interdit)

    def test_aucun_appel_reseau_dans_l_import(self):
        """Règle #5 : la source d'un import est un FICHIER, jamais un portail."""
        import ast
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parents[1] / 'imports.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        interdits = {'httpx', 'requests', 'urllib', 'urllib3'}
        for noeud in ast.walk(arbre):
            racines = []
            if isinstance(noeud, ast.Import):
                racines = [a.name.split('.')[0] for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                racines = [(noeud.module or '').split('.')[0]]
            self.assertFalse(set(racines) & interdits, racines)
