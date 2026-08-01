"""AOF186 — seed de démonstration « AO FRDISI » : rejouable, prouvé, borné.

Ce que ce module verrouille :

  1. **Le seed REFUSE de s'exécuter si les goldens divergent.** C'est sa PORTE :
     un seed qui figerait un chiffre faux serait pire que pas de seed du tout,
     puisque l'argument de ce moteur EST la preuve. Un golden trafiqué doit
     produire une ``CommandError`` et AUCUNE écriture.
  2. **Il est rejouable sans doublon.** Deux exécutions donnent exactement le
     même jeu : les clés de rapprochement sont métier (référence acheteur, code
     de bâtiment, code de planche, repère d'obstacle), jamais techniques.
  3. **Les chiffres viennent des GOLDENS, jamais d'une recopie.** Les comptes
     148 / 120 / 314 et les engagements 152 / 120 / 288 sont lus dans les JSON —
     le test compare le jeu semé au fichier, pas à une constante écrite ici.
  4. **Jamais en production par défaut** : ``--confirmer`` est obligatoire, et
     hors ``DEBUG`` un réglage explicite est exigé en plus.
  5. **Aucun coût de revient** n'est semé.

Run :
    python manage.py test apps.ao.tests.test_seed_demo -v2
"""
import json
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ao.management.commands import seed_ao_demo as seed
from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, LigneBordereau, ObstacleAO,
    ReleveAO, ToitureAO, VarianteCalepinage,
)
from authentication.models import Company


def _golden(nom):
    return seed.charger_golden(nom)


class LesGoldensSontLaSeuleSourceDeVerite(SimpleTestCase):
    def test_les_trois_goldens_sont_lisibles(self):
        for fichier, _c, _d, _f in seed.BATIMENTS:
            document = _golden(fichier)
            self.assertIn('golden', document)
            self.assertIn('compte_temoin', document['golden'])

    def test_la_verification_rejoue_les_trois_comptes(self):
        verifies = seed.verifier_goldens()
        self.assertEqual(len(verifies), 3)
        for fichier, compte in verifies:
            self.assertEqual(compte, _golden(fichier)['golden']
                             ['compte_temoin'])

    def test_un_golden_absent_est_une_erreur_explicite(self):
        with self.assertRaises(CommandError):
            seed.charger_golden('bat_Z_inexistant.json')

    def test_le_seed_ne_recopie_aucun_compte_en_dur(self):
        """Les comptes témoins ne sont écrits nulle part dans la commande."""
        import inspect

        source = inspect.getsource(seed)
        for compte in ('148', '314', '288', '152'):
            self.assertNotIn(
                '= %s' % compte, source,
                'compte %s recopié dans le seed : les goldens doivent rester '
                'la seule source de vérité géométrique.' % compte)


class LeSeedRefuseUnGoldenDivergent(SimpleTestCase):
    def test_un_compte_temoin_trafique_bloque_le_seed(self):
        vrai = seed.charger_golden

        def _trafique(nom):
            document = json.loads(json.dumps(vrai(nom)))
            if nom == 'bat_C_ecole.json':
                document['golden']['compte_temoin'] = 999
            return document

        with mock.patch.object(seed, 'charger_golden', _trafique):
            with self.assertRaises(CommandError) as ctx:
                seed.verifier_goldens()
        self.assertIn('DIVERGENCE', str(ctx.exception))
        self.assertIn('999', str(ctx.exception))


class LaCommandeNePartJamaisParAccident(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aof186-co', defaults={'nom': 'AOF186'})

    def test_sans_confirmer_la_commande_refuse(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_ao_demo', company='aof186-co')
        self.assertIn('--confirmer', str(ctx.exception))
        self.assertEqual(AppelOffre.objects.count(), 0)

    @override_settings(DEBUG=False, SEED_AO_DEMO_AUTORISE=False)
    def test_hors_debug_un_reglage_explicite_est_exige(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_ao_demo', company='aof186-co',
                         confirmer=True)
        self.assertIn('SEED_AO_DEMO_AUTORISE', str(ctx.exception))
        self.assertEqual(AppelOffre.objects.count(), 0)

    @override_settings(DEBUG=False, SEED_AO_DEMO_AUTORISE=True)
    def test_le_reglage_explicite_debloque_hors_debug(self):
        call_command('seed_ao_demo', company='aof186-co', confirmer=True,
                     stdout=StringIO())
        self.assertEqual(AppelOffre.objects.count(), 1)

    def test_une_societe_inconnue_est_refusee(self):
        with self.assertRaises(CommandError):
            call_command('seed_ao_demo', company='societe-fantome',
                         confirmer=True)


@override_settings(DEBUG=True)
class LeJeuSemeCorrespondAuxGoldens(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aof186-jeu', defaults={'nom': 'AOF186 jeu'})
        self.sortie = StringIO()
        call_command('seed_ao_demo', company='aof186-jeu', confirmer=True,
                     stdout=self.sortie)
        self.ao = AppelOffre.objects.get(company=self.company)

    def test_l_affaire_porte_la_reference_de_demonstration(self):
        self.assertEqual(self.ao.reference_acheteur, seed.REFERENCE_DEMO)
        self.assertTrue(self.ao.reference.startswith('AO-'))

    def test_les_trois_batiments_sont_la_avec_leur_engagement(self):
        batiments = {b.code: b for b in BatimentAO.objects.filter(
            appel_offre=self.ao)}
        self.assertEqual(sorted(batiments), ['A', 'B', 'C'])
        for fichier, code, _d, _f in seed.BATIMENTS:
            self.assertEqual(batiments[code].engagement_modules,
                             _golden(fichier)['golden']['engagement'])

    def test_l_engagement_global_est_la_somme_des_batiments(self):
        attendu = sum(_golden(f)['golden']['engagement']
                      for f, _c, _d, _fo in seed.BATIMENTS)
        self.assertEqual(self.ao.engagement_modules, attendu)

    def test_chaque_toiture_porte_sa_forme(self):
        formes = {t.batiment.code: t.forme
                  for t in ToitureAO.objects.filter(
                      batiment__appel_offre=self.ao).select_related(
                          'batiment')}
        for _f, code, _d, forme in seed.BATIMENTS:
            self.assertEqual(formes[code], forme, code)

    def test_tous_les_obstacles_des_goldens_sont_semes(self):
        attendu = sum(len(_golden(f)['obstacles'])
                      for f, _c, _d, _fo in seed.BATIMENTS)
        self.assertEqual(
            ObstacleAO.objects.filter(
                toiture__batiment__appel_offre=self.ao).count(), attendu)

    def test_les_provenances_moteur_sont_traduites(self):
        """``RELEVE`` côté moteur, ``MESURE`` côté modèle — jamais deviné."""
        obstacles = ObstacleAO.objects.filter(
            toiture__batiment__appel_offre=self.ao)
        valeurs = set(obstacles.values_list('provenance', flat=True))
        self.assertNotIn('RELEVE', valeurs)
        self.assertIn(ObstacleAO.Provenance.MESURE, valeurs)

    def test_les_ecartes_sont_semes_et_reconnaissables(self):
        """Les objets ÉCARTÉS restent en base : sans eux, l'échelle de
        décomposition qui chiffre ce que leur retrait rapporte est
        irreproductible."""
        ecartes = [o for doc in (_golden(f) for f, _c, _d, _fo
                                 in seed.BATIMENTS)
                   for o in doc['obstacles'] if o['provenance'] == 'ECARTE']
        self.assertTrue(ecartes)
        self.assertEqual(
            ObstacleAO.objects.filter(
                toiture__batiment__appel_offre=self.ao,
                provenance=ObstacleAO.Provenance.ECARTE).count(),
            len(ecartes))

    def test_chaque_toiture_a_une_variante_retenue_au_compte_du_golden(self):
        variantes = {v.toiture.batiment.code: v
                     for v in VarianteCalepinage.objects.filter(
                         appel_offre=self.ao).select_related(
                             'toiture__batiment')}
        for fichier, code, _d, _f in seed.BATIMENTS:
            variante = variantes[code]
            self.assertTrue(variante.est_retenue)
            self.assertEqual(variante.total_modules,
                             _golden(fichier)['golden']['compte_temoin'])

    def test_le_releve_temoin_est_seme_et_date(self):
        releve = ReleveAO.objects.get(appel_offre=self.ao)
        self.assertEqual(releve.date_visite, seed.DATE_RELEVE)
        self.assertTrue(releve.contradictoire)

    def test_les_quantites_du_bordereau_sont_les_engagements(self):
        """L'invariant du dossier : quantités du bordereau = engagements."""
        bordereau = BordereauPrix.objects.get(appel_offre=self.ao)
        lignes = LigneBordereau.objects.filter(bordereau=bordereau)
        self.assertEqual(lignes.count(), 3)
        total = sum(int(ligne.quantite) for ligne in lignes)
        self.assertEqual(total, self.ao.engagement_modules)

    def test_aucun_cout_de_revient_n_est_seme(self):
        bordereau = BordereauPrix.objects.get(appel_offre=self.ao)
        for ligne in LigneBordereau.objects.filter(bordereau=bordereau):
            champs = {f.name for f in ligne._meta.get_fields()}
            self.assertNotIn('prix_achat', champs)
            self.assertGreater(ligne.prix_unitaire, Decimal('0'))

    def test_la_sortie_annonce_les_goldens_verifies(self):
        texte = self.sortie.getvalue()
        self.assertIn('vérifié', texte)
        for fichier, _c, _d, _f in seed.BATIMENTS:
            self.assertIn(fichier, texte)


@override_settings(DEBUG=True)
class LeSeedEstRejouableSansDoublon(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aof186-rejeu', defaults={'nom': 'AOF186 rejeu'})

    def _semer(self):
        call_command('seed_ao_demo', company='aof186-rejeu', confirmer=True,
                     stdout=StringIO())

    def _compte(self):
        return {
            'ao': AppelOffre.objects.filter(company=self.company).count(),
            'batiments': BatimentAO.objects.filter(
                company=self.company).count(),
            'toitures': ToitureAO.objects.filter(
                company=self.company).count(),
            'obstacles': ObstacleAO.objects.filter(
                company=self.company).count(),
            'variantes': VarianteCalepinage.objects.filter(
                company=self.company).count(),
            'releves': ReleveAO.objects.filter(company=self.company).count(),
            'bordereaux': BordereauPrix.objects.filter(
                company=self.company).count(),
            'lignes': LigneBordereau.objects.filter(
                company=self.company).count(),
        }

    def test_deux_executions_donnent_le_meme_jeu(self):
        self._semer()
        premier = self._compte()
        self._semer()
        self.assertEqual(premier, self._compte())

    def test_la_reference_de_l_affaire_ne_change_pas_au_rejeu(self):
        self._semer()
        reference = AppelOffre.objects.get(company=self.company).reference
        self._semer()
        self.assertEqual(
            AppelOffre.objects.get(company=self.company).reference, reference)

    def test_une_autre_societe_a_son_propre_jeu(self):
        self._semer()
        autre, _ = Company.objects.get_or_create(
            slug='aof186-autre', defaults={'nom': 'Autre'})
        seed.semer(autre)
        self.assertEqual(AppelOffre.objects.filter(
            reference_acheteur=seed.REFERENCE_DEMO).count(), 2)
        self.assertEqual(self._compte()['ao'], 1)
