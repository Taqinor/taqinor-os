"""
CH1 — Étapes/gates configurables du cycle de vie chantier (StageModele).

Couvre :
  * l'amorçage IDEMPOTENT du cycle de vie PV international (10 étapes, ordre,
    drapeaux bloquants + exigences, protégées) ;
  * l'amorçage n'écrase JAMAIS une configuration éditée par le Directeur ;
  * le mapping PROPRE de l'enum hérité à 7 statuts (et des 5 statuts
    historiques hors entonnoir) sur les nouvelles étapes ;
  * l'étape courante d'un chantier existant (sans pointeur `etape`) DÉRIVÉE de
    son statut — les chantiers d'avant CH1 fonctionnent sans migration de
    données — et la synchronisation du pointeur après un changement de statut ;
  * l'ajout / retrait / réordonnancement d'étapes par société ;
  * le scope multi-société (une société ne voit jamais les étapes d'une autre).

Run :
    python manage.py test apps.installations.tests_ch1_stages -v2
"""
import itertools

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation, StageModele
from apps.installations.services import (
    DEFAULT_LIFECYCLE_GATES, LEGACY_STATUT_TO_STAGE, etape_courante, seed_stages,
    stage_pour_statut, stages_actifs, stages_configures,
    sync_etape_from_statut,
)

_seq = itertools.count(1)


def make_company(nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ch1-co-{n}', defaults={'nom': nom or f'CH1 Co {n}'})
    return company


def make_installation(company, statut=Installation.Statut.SIGNE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CH1',
        email=f'ch1-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CH1-{n}', client=client,
        statut=statut)


class SeedStagesTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_seed_cree_le_cycle_international_ordonne(self):
        seed_stages(self.company)
        stages = list(StageModele.objects.filter(
            company=self.company).order_by('ordre'))
        self.assertEqual(len(stages), len(DEFAULT_LIFECYCLE_GATES))
        self.assertEqual(
            [s.cle for s in stages], [d[0] for d in DEFAULT_LIFECYCLE_GATES])
        # Toutes protégées (système), toutes actives.
        self.assertTrue(all(s.protege for s in stages))
        self.assertTrue(all(s.actif for s in stages))

    def test_seed_pose_les_gates_bloquants_et_exigences(self):
        seed_stages(self.company)
        by_cle = {s.cle: s for s in StageModele.objects.filter(
            company=self.company)}
        mes = by_cle['mise_en_service']
        self.assertTrue(mes.bloquant)
        self.assertTrue(mes.exige_tests)
        self.assertEqual(mes.statut_legacy, Installation.Statut.INSTALLE)
        autor = by_cle['autorisations']
        self.assertTrue(autor.bloquant)
        self.assertTrue(autor.exige_dossier)
        appro = by_cle['approvisionnement']
        self.assertTrue(appro.bloquant)
        self.assertTrue(appro.exige_materiel)
        remise = by_cle['remise_client']
        self.assertTrue(remise.bloquant)
        self.assertTrue(remise.exige_checklist)
        self.assertTrue(remise.exige_pack)
        self.assertEqual(remise.statut_legacy,
                         Installation.Statut.RECEPTIONNE)
        # Une étape consultative n'est pas bloquante.
        self.assertFalse(by_cle['etude_site'].bloquant)

    def test_seed_idempotent_et_preserve_les_editions(self):
        seed_stages(self.company)
        stage = StageModele.objects.get(
            company=self.company, cle='conception')
        stage.libelle = 'Bureau d’études'
        stage.ordre = 42
        stage.bloquant = True
        stage.save()
        again = seed_stages(self.company)
        self.assertEqual(again, [])  # rien de recréé
        self.assertEqual(StageModele.objects.filter(
            company=self.company).count(), len(DEFAULT_LIFECYCLE_GATES))
        stage.refresh_from_db()
        # L'édition du Directeur est intacte.
        self.assertEqual(stage.libelle, 'Bureau d’études')
        self.assertEqual(stage.ordre, 42)
        self.assertTrue(stage.bloquant)

    def test_stages_actifs_amorce_puis_filtre_les_inactives(self):
        stages = stages_actifs(self.company)
        self.assertEqual(len(stages), len(DEFAULT_LIFECYCLE_GATES))
        StageModele.objects.filter(
            company=self.company, cle='conception').update(actif=False)
        stages = stages_actifs(self.company)
        self.assertEqual(len(stages), len(DEFAULT_LIFECYCLE_GATES) - 1)
        self.assertNotIn('conception', [s.cle for s in stages])

    def test_stages_configures_interrupteur(self):
        self.assertFalse(stages_configures(self.company))
        seed_stages(self.company)
        self.assertTrue(stages_configures(self.company))


class LegacyMappingTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def test_chaque_statut_herite_mappe_sur_une_etape(self):
        # Les 7 canoniques ET les 5 historiques hors entonnoir.
        for statut in Installation.Statut.values:
            stage = stage_pour_statut(self.company, statut)
            self.assertIsNotNone(
                stage, f'Statut « {statut} » sans étape mappée')

    def test_mapping_canonique_attendu(self):
        for statut, cle in LEGACY_STATUT_TO_STAGE.items():
            stage = stage_pour_statut(self.company, statut)
            self.assertEqual(stage.cle, cle)
        # Statuts hérités : rabattus via canonical_statut d'abord.
        self.assertEqual(
            stage_pour_statut(self.company, 'pose').cle, 'mise_en_service')
        self.assertEqual(
            stage_pour_statut(self.company, 'a_planifier').cle, 'etude_site')

    def test_effets_de_bord_gardent_leurs_gates(self):
        # Le statut qui consomme le stock (Installé) et celui qui remet la
        # garantie (Réceptionné) restent portés par les étapes mappées.
        installe = stage_pour_statut(
            self.company, Installation.Statut.INSTALLE)
        self.assertEqual(installe.statut_legacy, Installation.Statut.INSTALLE)
        receptionne = stage_pour_statut(
            self.company, Installation.Statut.RECEPTIONNE)
        self.assertEqual(receptionne.statut_legacy,
                         Installation.Statut.RECEPTIONNE)

    def test_etape_courante_derivee_pour_chantier_existant(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.MATERIEL_COMMANDE)
        self.assertIsNone(inst.etape)  # chantier d'avant CH1
        stage = etape_courante(inst)
        self.assertEqual(stage.cle, 'approvisionnement')

    def test_sync_etape_from_statut(self):
        inst = make_installation(self.company)
        inst.statut = Installation.Statut.INSTALLE
        inst.save(update_fields=['statut'])
        stage = sync_etape_from_statut(inst)
        inst.refresh_from_db()
        self.assertEqual(inst.etape_id, stage.id)
        self.assertEqual(inst.etape.cle, 'mise_en_service')

    def test_pointeur_inactif_retombe_sur_la_derivation(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        stage = StageModele.objects.get(
            company=self.company, cle='conception')
        inst.etape = stage
        inst.save(update_fields=['etape'])
        stage.actif = False
        stage.save(update_fields=['actif'])
        self.assertEqual(etape_courante(inst).cle, 'montage_mecanique')


class ConfigurationEtScopeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.autre = make_company()
        seed_stages(self.company)

    def test_ajout_retrait_reordonnancement(self):
        # Ajout d'une étape personnalisée intercalée.
        StageModele.objects.create(
            company=self.company, cle='controle_qualite',
            libelle='Contrôle qualité interne', ordre=6, bloquant=True)
        cles = [s.cle for s in stages_actifs(self.company)]
        self.assertIn('controle_qualite', cles)
        # Retrait (une étape non protégée se supprime ; une protégée se
        # désactive — même règle que les checklists, appliquée par la vue CH5).
        StageModele.objects.filter(
            company=self.company, cle='controle_qualite').delete()
        StageModele.objects.filter(
            company=self.company, cle='inspection_raccordement'
        ).update(actif=False)
        cles = [s.cle for s in stages_actifs(self.company)]
        self.assertNotIn('controle_qualite', cles)
        self.assertNotIn('inspection_raccordement', cles)
        # Réordonnancement : l'ordre édité pilote la liste.
        StageModele.objects.filter(
            company=self.company, cle='conception').update(ordre=99)
        self.assertEqual(stages_actifs(self.company)[-1].cle, 'conception')

    def test_scope_par_societe(self):
        # L'amorçage d'une société ne crée rien chez l'autre.
        self.assertFalse(
            StageModele.objects.filter(company=self.autre).exists())
        # La dérivation est scopée société (amorce à la volée pour l'autre).
        stage = stage_pour_statut(
            self.autre, Installation.Statut.SIGNE)
        self.assertIsNone(stage)  # pas d'amorçage implicite par la lecture
        seed_stages(self.autre)
        stage = stage_pour_statut(self.autre, Installation.Statut.SIGNE)
        self.assertEqual(stage.company_id, self.autre.id)
        # Les étapes des deux sociétés sont indépendantes.
        StageModele.objects.filter(
            company=self.autre, cle='conception').update(actif=False)
        self.assertIn('conception',
                      [s.cle for s in stages_actifs(self.company)])
