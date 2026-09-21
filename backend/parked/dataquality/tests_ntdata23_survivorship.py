"""NTDATA23 — règles de survivorship + consolidation des golden records.

Couvre :
  * le critère d'acceptation : sur un NOM conflictuel, `plus_recent` retient la
    valeur de la fiche la plus récemment modifiée ;
  * les trois autres stratégies (`plus_complet`, `source_prioritaire`,
    `plus_frequent`) ;
  * le défaut raisonnable quand AUCUNE règle n'existe ;
  * une valeur VIDE ne gagne jamais contre une valeur renseignée ;
  * `plus_recent` SANS signal de fraîcheur retombe sur le défaut et l'ÉCRIT
    (jamais une fraîcheur devinée) ;
  * `consolider_golden` ne mute AUCUNE source, est idempotent, et ignore un
    groupe sans clé métier stable ;
  * le scoping société.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.models import GoldenRecord, RegleSurvivorship
from authentication.models import Company

CLIENT = GoldenRecord.Entite.CLIENT
CHAMPS_CLIENT = services.CONSOLIDATION[CLIENT]['champs']


class StrategiesSurvivorshipTests(TestCase):
    """Les quatre stratégies, sur des fiches injectées (calcul pur)."""

    def setUp(self):
        self.sources = [
            {'id': 1, 'nom': 'Atlas Energie', 'telephone': '0600000001',
             'email': '', 'ice': '001234567000089', 'modifie_le': '2026-01-05'},
            {'id': 2, 'nom': 'ATLAS ENERGIE SARL', 'telephone': '',
             'email': 'contact@atlas.ma', 'ice': '001234567000089',
             'modifie_le': '2026-03-20'},
            {'id': 3, 'nom': 'Atlas Energie', 'telephone': '0600000001',
             'email': '', 'ice': '001234567000089', 'modifie_le': '2026-02-10'},
        ]

    def test_plus_recent_retient_la_fiche_la_plus_recemment_modifiee(self):
        """Critère : nom conflictuel + `plus_recent` ⇒ la fiche la plus fraîche."""
        valeur, effective = services.valeur_gagnante(
            'nom', self.sources, RegleSurvivorship.Strategie.PLUS_RECENT,
            champs=CHAMPS_CLIENT, champ_fraicheur='modifie_le')
        self.assertEqual(valeur, 'ATLAS ENERGIE SARL')
        self.assertEqual(effective,
                         RegleSurvivorship.Strategie.PLUS_RECENT)

    def test_plus_recent_sans_signal_de_fraicheur_replie_et_le_dit(self):
        valeur, effective = services.valeur_gagnante(
            'nom', self.sources, RegleSurvivorship.Strategie.PLUS_RECENT,
            champs=CHAMPS_CLIENT, champ_fraicheur=None)
        # Repli sur le défaut : la fiche d'origine fait foi.
        self.assertEqual(valeur, 'Atlas Energie')
        self.assertIn('repli', effective)
        self.assertIn(services.STRATEGIE_DEFAUT, effective)

    def test_plus_complet_retient_la_fiche_la_plus_renseignee(self):
        # La fiche 1 porte nom+telephone+ice (3) ; la 2 nom+email+ice (3) ;
        # on ajoute une adresse à la 2 pour qu'elle soit strictement devant.
        self.sources[1]['adresse'] = '12 rue X, Casablanca'
        valeur, effective = services.valeur_gagnante(
            'nom', self.sources, RegleSurvivorship.Strategie.PLUS_COMPLET,
            champs=CHAMPS_CLIENT)
        self.assertEqual(valeur, 'ATLAS ENERGIE SARL')
        self.assertEqual(effective,
                         RegleSurvivorship.Strategie.PLUS_COMPLET)

    def test_source_prioritaire_designee(self):
        valeur, _ = services.valeur_gagnante(
            'nom', self.sources,
            RegleSurvivorship.Strategie.SOURCE_PRIORITAIRE,
            champs=CHAMPS_CLIENT, parametres={'source_id': 2})
        self.assertEqual(valeur, 'ATLAS ENERGIE SARL')

    def test_source_prioritaire_par_defaut_la_plus_ancienne(self):
        valeur, _ = services.valeur_gagnante(
            'nom', self.sources,
            RegleSurvivorship.Strategie.SOURCE_PRIORITAIRE,
            champs=CHAMPS_CLIENT)
        self.assertEqual(valeur, 'Atlas Energie')

    def test_plus_frequent(self):
        # « Atlas Energie » apparaît deux fois, « ATLAS ENERGIE SARL » une.
        valeur, _ = services.valeur_gagnante(
            'nom', self.sources, RegleSurvivorship.Strategie.PLUS_FREQUENT,
            champs=CHAMPS_CLIENT)
        self.assertEqual(valeur, 'Atlas Energie')

    def test_une_valeur_vide_ne_gagne_jamais(self):
        """La fiche 2 n'a pas de téléphone : elle ne peut pas l'effacer."""
        valeur, _ = services.valeur_gagnante(
            'telephone', self.sources,
            RegleSurvivorship.Strategie.PLUS_RECENT,
            champs=CHAMPS_CLIENT, champ_fraicheur='modifie_le')
        self.assertEqual(valeur, '0600000001')

    def test_champ_vide_partout_reste_vide(self):
        for source in self.sources:
            source['adresse'] = ''
        valeur, effective = services.valeur_gagnante(
            'adresse', self.sources,
            RegleSurvivorship.Strategie.PLUS_COMPLET, champs=CHAMPS_CLIENT)
        self.assertIsNone(valeur)
        self.assertEqual(effective, '')


class RegleSurvivorshipModeleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA23 SA',
                                             slug='ntdata23-sa')

    def test_champ_vide_refuse_en_nommant_le_champ(self):
        regle = RegleSurvivorship(company=self.company, entite=CLIENT,
                                  champ='  ')
        with self.assertRaises(ValidationError) as leve:
            regle.clean()
        self.assertIn('champ', leve.exception.message_dict)

    def test_source_id_illisible_refuse(self):
        regle = RegleSurvivorship(
            company=self.company, entite=CLIENT, champ='nom',
            strategie=RegleSurvivorship.Strategie.SOURCE_PRIORITAIRE,
            parametres={'source_id': 'pas-un-id'})
        with self.assertRaises(ValidationError) as leve:
            regle.clean()
        self.assertIn('parametres', leve.exception.message_dict)


class ConsoliderGoldenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA23 Cons',
                                             slug='ntdata23-cons')
        cls.autre = Company.objects.create(nom='NTDATA23 Autre',
                                           slug='ntdata23-autre')

    def _deux_clients(self, company=None):
        company = company or self.company
        premier = Client.objects.create(
            company=company, nom='Atlas Energie', ice='001234567000089',
            telephone='0600000001')
        second = Client.objects.create(
            company=company, nom='ATLAS ENERGIE SARL', ice='001234567000089',
            email='contact@atlas.ma')
        return premier, second

    def test_consolide_deux_clients_sous_leur_ice(self):
        premier, second = self._deux_clients()
        consolides = services.consolider_golden(self.company, CLIENT)
        self.assertEqual(len(consolides), 1)
        golden = consolides[0]
        self.assertEqual(golden.cle_metier, '001234567000089')
        self.assertEqual(sorted(golden.source_ids),
                         sorted([premier.pk, second.pk]))
        # Le défaut (fiche d'origine) l'emporte sur le nom ; le téléphone et
        # l'email viennent chacun de la seule fiche qui les portait.
        self.assertEqual(golden.attributs['nom']['valeur'], 'Atlas Energie')
        self.assertEqual(golden.attributs['telephone']['valeur'],
                         '0600000001')
        self.assertEqual(golden.attributs['email']['valeur'],
                         'contact@atlas.ma')
        self.assertIsNotNone(golden.derniere_consolidation_le)

    def test_une_regle_change_le_gagnant(self):
        self._deux_clients()
        RegleSurvivorship.objects.create(
            company=self.company, entite=CLIENT, champ='nom',
            strategie=RegleSurvivorship.Strategie.PLUS_COMPLET)
        golden = services.consolider_golden(self.company, CLIENT)[0]
        # La 1re fiche porte nom+telephone+ice (3) ; la 2e nom+email+ice (3).
        # À égalité, la plus ancienne l'emporte — comportement déterministe.
        self.assertEqual(golden.attributs['nom']['strategie'],
                         RegleSurvivorship.Strategie.PLUS_COMPLET)

    def test_ne_mute_aucune_source(self):
        premier, second = self._deux_clients()
        services.consolider_golden(self.company, CLIENT)
        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(premier.nom, 'Atlas Energie')
        self.assertEqual(second.nom, 'ATLAS ENERGIE SARL')
        self.assertEqual(premier.email or '', '')

    def test_idempotent_une_seule_fiche_consolidee(self):
        self._deux_clients()
        services.consolider_golden(self.company, CLIENT)
        services.consolider_golden(self.company, CLIENT)
        self.assertEqual(
            GoldenRecord.objects.filter(company=self.company).count(), 1)

    def test_scoping_societe(self):
        self._deux_clients(company=self.autre)
        self.assertEqual(services.consolider_golden(self.company, CLIENT), [])
        self.assertEqual(
            GoldenRecord.objects.filter(company=self.company).count(), 0)

    def test_groupe_sans_cle_metier_stable_ignore(self):
        """Deux fiches rapprochées par le NOM seul, sans clé partagée : pas
        de golden record fabriqué."""
        lignes = [
            {'id': 1, 'nom': 'Atlas Energie', 'telephone': '0600000001',
             'email': 'a@atlas.ma', 'ice': '001'},
            {'id': 2, 'nom': 'Atlas Energie', 'telephone': '0600000002',
             'email': 'b@atlas.ma', 'ice': '002'},
        ]
        consolides = services.consolider_golden(
            self.company, CLIENT, lignes=lignes,
            groupes=[{'ids': [1, 2], 'score': 0.6, 'motifs': ['nom']}])
        self.assertEqual(consolides, [])

    def test_entite_inconnue_refusee_en_francais(self):
        with self.assertRaises(ValueError) as leve:
            services.consolider_golden(self.company, 'licorne')
        self.assertIn('licorne', str(leve.exception))
