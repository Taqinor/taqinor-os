"""VAO9 — mots-clés en base + score, et la garde « aucun mot-clé en dur ».

Ce qui est vérifié :
  * les DEUX niveaux (noyau/large) sont semés, de façon rejouable ;
  * un mot-clé ajouté « par l'écran » (une ligne en base) change le score des
    calculs suivants — sans redéploiement ;
  * un avis porte la LISTE des mots qui l'ont fait remonter (le score seul
    serait un oracle) ;
  * la normalisation survit à la casse, aux accents et aux espaces ;
  * le score est borné ;
  * aucun littéral de mot-clé métier n'existe hors de la table de seed.
"""
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.veille_ao.management.commands.seed_veille_sources import (
    MOTS_CLES, seed_mots_cles_pour_societe,
)
from apps.veille_ao.models import (
    SCORE_MAX, AvisMarche, MotCleVeille, NiveauMotCle, SourceVeille,
    TypeSource,
)
from apps.veille_ao.scoring import (
    calculer_score, mots_cles_actifs, normaliser, scorer_avis,
)
from authentication.models import Company

MODULE_DIR = Path(__file__).resolve().parent.parent

#: Seul le fichier de seed a le droit d'écrire un mot-clé métier en clair.
FICHIER_TABLE_MOTS_CLES = 'management/commands/seed_veille_sources.py'


class SeedMotsClesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Mots')

    def test_seed_cree_les_deux_niveaux(self):
        crees = seed_mots_cles_pour_societe(self.company)
        self.assertEqual(crees, len(MOTS_CLES))
        niveaux = set(
            MotCleVeille.objects.filter(company=self.company)
            .values_list('niveau', flat=True))
        self.assertEqual(
            niveaux, {NiveauMotCle.NOYAU, NiveauMotCle.LARGE})

    def test_seed_rejoue_ne_cree_aucun_doublon(self):
        seed_mots_cles_pour_societe(self.company)
        self.assertEqual(seed_mots_cles_pour_societe(self.company), 0)
        self.assertEqual(
            MotCleVeille.objects.filter(company=self.company).count(),
            len(MOTS_CLES))

    def test_un_mot_du_noyau_pese_plus_qu_un_mot_large(self):
        seed_mots_cles_pour_societe(self.company)
        noyau = MotCleVeille.objects.filter(
            company=self.company, niveau=NiveauMotCle.NOYAU).first()
        large = MotCleVeille.objects.filter(
            company=self.company, niveau=NiveauMotCle.LARGE).first()
        self.assertGreater(noyau.poids, large.poids)

    def test_seed_ne_repondere_pas_un_mot_regle_a_l_ecran(self):
        seed_mots_cles_pour_societe(self.company)
        mot = MotCleVeille.objects.filter(company=self.company).first()
        mot.poids = 42
        mot.actif = False
        mot.save()

        seed_mots_cles_pour_societe(self.company)

        mot.refresh_from_db()
        self.assertEqual(mot.poids, 42)
        self.assertFalse(mot.actif)


class NormalisationTests(SimpleTestCase):
    def test_casse_neutralisee(self):
        self.assertEqual(normaliser('SOLAIRE'), 'solaire')

    def test_accents_neutralises(self):
        self.assertEqual(normaliser('Photovoltaïque'), 'photovoltaique')
        self.assertEqual(normaliser('Énergie'), 'energie')

    def test_espaces_multiples_reduits(self):
        self.assertEqual(normaliser('  pompage    solaire  '),
                         'pompage solaire')

    def test_valeur_vide(self):
        self.assertEqual(normaliser(''), '')
        self.assertEqual(normaliser(None), '')


class CalculDuScoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Score')

    def _mot(self, libelle, poids=10, niveau=NiveauMotCle.NOYAU,
             actif=True):
        return MotCleVeille.objects.create(
            company=self.company, libelle=libelle, niveau=niveau,
            poids=poids, actif=actif)

    def test_score_somme_les_poids_des_mots_declenches(self):
        mots = [self._mot('solaire', poids=10),
                self._mot('pompage', poids=5, niveau=NiveauMotCle.LARGE)]
        score, declenches = calculer_score(
            objet='Pompage solaire pour abreuvement du cheptel',
            acheteur='Commune de Figuig', mots_cles=mots)
        self.assertEqual(score, 15)
        self.assertEqual(declenches, ['pompage', 'solaire'])

    def test_avis_hors_sujet_ne_declenche_rien(self):
        mots = [self._mot('solaire')]
        score, declenches = calculer_score(
            objet='Fourniture de mobilier de bureau',
            acheteur='Province de Test', mots_cles=mots)
        self.assertEqual(score, 0)
        self.assertEqual(declenches, [])

    def test_l_acheteur_compte_aussi(self):
        mots = [self._mot('onee', poids=4, niveau=NiveauMotCle.LARGE)]
        score, declenches = calculer_score(
            objet='Fourniture de luminaires',
            acheteur='ONEE — Branche Eau', mots_cles=mots)
        self.assertEqual(score, 4)
        self.assertEqual(declenches, ['onee'])

    def test_normalisation_appliquee_au_mot_et_au_texte(self):
        mots = [self._mot('photovoltaïque', poids=7,
                          niveau=NiveauMotCle.LARGE)]
        score, declenches = calculer_score(
            objet='INSTALLATION PHOTOVOLTAIQUE DE 300 KWC',
            acheteur='', mots_cles=mots)
        self.assertEqual(score, 7)
        self.assertEqual(declenches, ['photovoltaïque'])

    def test_score_borne(self):
        mots = [self._mot(f'mot{i}', poids=60) for i in range(5)]
        score, _ = calculer_score(
            objet='mot0 mot1 mot2 mot3 mot4', acheteur='', mots_cles=mots)
        self.assertEqual(score, SCORE_MAX)

    def test_mot_desactive_n_est_pas_pris_en_compte(self):
        self._mot('solaire', actif=False)
        actifs = mots_cles_actifs(self.company)
        score, declenches = calculer_score(
            objet='Centrale solaire', acheteur='', mots_cles=actifs)
        self.assertEqual(score, 0)
        self.assertEqual(declenches, [])

    def test_mots_cles_actifs_reste_scope_par_societe(self):
        autre = Company.objects.create(nom='Autre Score')
        self._mot('solaire')
        self.assertEqual(mots_cles_actifs(autre), [])


class MotAjouteChangeLeScoreTests(TestCase):
    """« Un mot-clé ajouté par l'écran change le score des collectes
    suivantes sans redéploiement. »"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Ajout')
        cls.source = SourceVeille.objects.create(
            company=cls.company, code='src', libelle='Source',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test', actif=True)

    def _avis(self):
        return AvisMarche(
            company=self.company, source=self.source,
            objet="Équipement de puits en plaques solaires",
            acheteur='Commune de Chichaoua')

    def test_avant_ajout_le_score_est_nul(self):
        avis = scorer_avis(self._avis())
        self.assertEqual(avis.score, 0)
        self.assertEqual(avis.mots_cles_declenches, [])

    def test_apres_ajout_le_score_change_sans_redeploiement(self):
        MotCleVeille.objects.create(
            company=self.company, libelle='plaques solaires',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)
        avis = scorer_avis(self._avis())
        self.assertEqual(avis.score, 10)
        self.assertEqual(avis.mots_cles_declenches, ['plaques solaires'])

    def test_l_avis_affiche_ses_mots_declencheurs(self):
        MotCleVeille.objects.create(
            company=self.company, libelle='solaires',
            niveau=NiveauMotCle.NOYAU, poids=10)
        MotCleVeille.objects.create(
            company=self.company, libelle='puits',
            niveau=NiveauMotCle.LARGE, poids=3)
        avis = scorer_avis(self._avis())
        avis.save()
        avis.refresh_from_db()
        self.assertEqual(avis.mots_cles_declenches, ['puits', 'solaires'])
        self.assertEqual(avis.score, 13)


class AucunMotCleEnDurTests(SimpleTestCase):
    """« Aucun mot-clé littéral hors table » (test de grep).

    Le fichier de seed EST la table de référence : c'est le seul endroit du
    module autorisé à écrire un mot-clé métier en clair.
    """

    def test_aucun_mot_cle_metier_hors_de_la_table_de_seed(self):
        libelles = [libelle for libelle, _ in MOTS_CLES]
        fautifs = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            if relatif == FICHIER_TABLE_MOTS_CLES:
                continue
            contenu = chemin.read_text(encoding='utf-8').lower()
            for libelle in libelles:
                if f"'{libelle.lower()}'" in contenu:
                    fautifs.append(f'{relatif} ({libelle})')
                elif f'"{libelle.lower()}"' in contenu:
                    fautifs.append(f'{relatif} ({libelle})')
        self.assertEqual(
            fautifs, [],
            "Mot-clé en dur hors de la table : il doit venir de "
            f"MotCleVeille : {fautifs}")

    def test_le_module_de_scoring_ne_contient_aucun_mot_cle(self):
        contenu = (MODULE_DIR / 'scoring.py').read_text(
            encoding='utf-8').lower()
        for libelle, _ in MOTS_CLES:
            self.assertNotIn(f"'{libelle.lower()}'", contenu, libelle)
