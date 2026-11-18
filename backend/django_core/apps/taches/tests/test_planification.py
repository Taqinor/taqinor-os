"""TCH34 — `planifier()`, le seul chemin d'un jour (invariants 4, 14, 15 ; 409 `conflit_version`).

Base requise (`TestCase`) : joué par la CI. `planifier` lit l'horloge à sa frontière
(`timezone.localdate()`) : les jours des tests sont donc RELATIFS à aujourd'hui (`J`).
"""
import datetime

from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers

from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.journee import LignePlanJour
from apps.taches.models.taches import Tache
from apps.taches.services.gestes import annuler_geste
from apps.taches.services.journee import alleger, cloturer
from apps.taches.services.planification import planifier
from apps.taches.services.projets import decaler_projet
from apps.taches.services.taches import lot_taches, trancher_tache
from apps.taches.tests import fabriques
from core.verrou_optimiste import ConflitVersion


def _j(delta):
    return timezone.localdate() + datetime.timedelta(days=delta)


def _prochain_dimanche():
    jour = _j(1)
    while jour.weekday() != 6:
        jour += datetime.timedelta(days=1)
    return jour


class PlanifierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _reports(self, ancien, nouveau=None, **options):
        tache = fabriques.tache(self.u1, jour_prevu=ancien)
        planifier(tache, acteur=self.u1, jour_prevu=nouveau, **options)
        return Tache.objects.get(pk=tache.pk).reports

    # --- Invariant 4 : ce qui compte un report ----------------------------------------

    def test_aujourdhui_vers_plus_tard_compte(self):
        self.assertEqual(self._reports(_j(0), _j(2)), 1)

    def test_retard_garde_aujourdhui_compte(self):
        self.assertEqual(self._reports(_j(-3), _j(0)), 1)

    def test_en_reserve_depuis_aujourdhui_compte(self):
        self.assertEqual(self._reports(_j(0), quelque_jour=True), 1)

    def test_futur_vers_futur_ne_compte_pas(self):
        self.assertEqual(self._reports(_j(2), _j(5)), 0)

    def test_avancer_ne_compte_pas(self):
        self.assertEqual(self._reports(_j(0), _j(-1)), 0)

    def test_premier_jour_pose_ne_compte_pas(self):
        self.assertEqual(self._reports(None, _j(0)), 0)

    def test_meme_jour_autre_heure_ne_compte_pas(self):
        self.assertEqual(self._reports(_j(0), _j(0), heure_debut=datetime.time(15, 0)), 0)

    def test_compter_report_faux(self):
        self.assertEqual(self._reports(_j(0), None, compter_report=False), 0)
        self.assertEqual(self._reports(_j(-1), _j(3), compter_report=False), 0)

    def test_retirer_le_jour_n_est_pas_un_report(self):
        self.assertEqual(self._reports(_j(0), None), 0)

    def test_report_par_f_puis_relu(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0), reports=2)
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(1))
        self.assertEqual(resultat.tache.reports, 3)
        self.assertEqual(Tache.objects.get(pk=tache.pk).reports, 3)

    # --- Invariants 14 et 15 : heure murale, moment dérivé, heure sans jour ------------

    def test_heure_murale_et_moment_derive(self):
        tache = fabriques.tache(self.u1)
        planifier(tache, acteur=self.u1, jour_prevu=_j(1), heure_debut=datetime.time(10, 0))
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual((tache.jour_prevu, tache.heure_debut, tache.moment),
                         (_j(1), datetime.time(10, 0), 'matin'))
        planifier(tache, acteur=self.u1, jour_prevu=_j(1), heure_debut='19:30')
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual((tache.heure_debut, tache.moment), (datetime.time(19, 30), 'soir'))

    def test_heure_sans_jour_refusee(self):
        tache = fabriques.tache(self.u1)
        with self.assertRaises(serializers.ValidationError) as ctx:
            planifier(tache, acteur=self.u1, jour_prevu=None, heure_debut=datetime.time(10, 0))
        self.assertEqual(ctx.exception.detail, {'heure_debut': ['Une heure demande un jour prévu.']})
        self.assertIsNone(Tache.objects.get(pk=tache.pk).heure_debut)

    def test_en_reserve_efface_jour_heure_moment(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(1), heure_debut=datetime.time(9, 0), moment='matin')
        planifier(tache, acteur=self.u1, jour_prevu=_j(1), quelque_jour=True)
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual((tache.jour_prevu, tache.heure_debut, tache.moment, tache.quelque_jour),
                         (None, None, '', True))

    def test_moment_sans_heure(self):
        tache = fabriques.tache(self.u1)
        planifier(tache, acteur=self.u1, jour_prevu=_j(0), moment='soir')
        self.assertEqual(Tache.objects.get(pk=tache.pk).moment, 'soir')
        with self.assertRaises(serializers.ValidationError):
            planifier(tache, acteur=self.u1, jour_prevu=_j(0), moment='nuit')

    def test_premier_jour_pose_une_fois_et_triee_le(self):
        tache = fabriques.tache(self.u1)
        self.assertIsNone(tache.triee_le)
        planifier(tache, acteur=self.u1, jour_prevu=_j(2))
        planifier(tache, acteur=self.u1, jour_prevu=_j(4))
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual(tache.premier_jour_prevu, _j(2))
        self.assertIsNotNone(tache.triee_le)

    def test_changer_de_jour_oublie_le_rang_du_jour(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0), rang_jour=2048)
        planifier(tache, acteur=self.u1, jour_prevu=_j(0), moment='soir')
        self.assertEqual(Tache.objects.get(pk=tache.pk).rang_jour, 2048)
        planifier(tache, acteur=self.u1, jour_prevu=_j(1))
        self.assertIsNone(Tache.objects.get(pk=tache.pk).rang_jour)

    # --- Verrou 409 ---------------------------------------------------------------------

    def test_version_perimee_409_rien_ecrit(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        Tache.objects.get(pk=tache.pk).save()  # un autre appareil : lock_version 1
        with self.assertRaises(ConflitVersion) as ctx:
            planifier(tache, acteur=self.u1, jour_prevu=_j(3), version=0)
        exc = ctx.exception
        self.assertEqual(exc.status_code, 409)
        self.assertEqual((exc.detail['code'], exc.detail['lock_version']), ('conflit_version', 1))
        self.assertEqual((exc.detail['actuel']['id'], exc.tache.pk), (tache.pk, tache.pk))
        self.assertNotIn('titre', exc.detail['actuel'])
        relue = Tache.objects.get(pk=tache.pk)
        self.assertEqual((relue.jour_prevu, relue.reports), (_j(0), 0))

    def test_version_a_jour_passe(self):
        tache = fabriques.tache(self.u1)
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(1), version=tache.lock_version)
        self.assertEqual(resultat.tache.lock_version, tache.lock_version + 1)

    # --- Propriétaire ---------------------------------------------------------------------

    def test_tache_d_un_autre_404(self):
        a_lui = fabriques.tache(self.voisin)
        for acteur in (self.u1, self.ailleurs):
            with self.assertRaises(Http404):
                planifier(a_lui, acteur=acteur, jour_prevu=_j(1))
        self.assertIsNone(Tache.objects.get(pk=a_lui.pk).jour_prevu)

    def test_tache_supprimee_404(self):
        tache = fabriques.tache(self.u1)
        tache.soft_delete(self.u1, record=False)
        with self.assertRaises(Http404):
            planifier(tache.pk, acteur=self.u1, jour_prevu=_j(1))

    # --- Geste et collecte ------------------------------------------------------------------

    def test_geste_propre_puis_annulation(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(1))
        geste = resultat.geste
        self.assertEqual((geste.type, geste.message), ('planification', 'Reportée à demain'))
        annuler_geste(self.u1, geste.pk)
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual((tache.jour_prevu, tache.reports), (_j(0), 0))

    def test_collecte_ajoute_sans_creer_de_geste(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        collecte = [{'op': 'creation', 'objet': 'tache', 'id': 1}]
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(2), collecte=collecte)
        self.assertIsNone(resultat.geste)
        self.assertFalse(GesteAnnulable.objects.exists())
        champs = {op['champ'] for op in collecte[1:]}
        self.assertIn('jour_prevu', champs)
        self.assertIn('reports', champs)
        self.assertEqual(collecte[0], {'op': 'creation', 'objet': 'tache', 'id': 1})

    def test_rien_change_aucun_geste(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(1), triee_le=timezone.now(), premier_jour_prevu=_j(1))
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(1))
        self.assertIsNone(resultat.geste)

    # --- Avertissements ---------------------------------------------------------------------

    def test_prevue_apres_echeance(self):
        tache = fabriques.tache(self.u1, echeance=_j(1))
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(3))
        self.assertIn({'code': 'prevue_apres_echeance', 'message': "Prévue après l'échéance."},
                      resultat.avertissements)

    def test_jour_non_travaille(self):
        tache = fabriques.tache(self.u1)
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_prochain_dimanche())
        codes = [a['code'] for a in resultat.avertissements]
        self.assertEqual(codes, ['jour_non_travaille'])
        self.assertTrue(resultat.avertissements[0]['message'].endswith("n'est pas un jour travaillé."))


class LigneDuPlanTests(TestCase):
    """Acceptation F2, défaut 6 — LA règle d'une gardée qui change de jour (`_suivre_les_lignes_du_plan`,
    appelée par `planifier`, seul écrivain du jour) : sa ligne du plan du jour qu'elle quitte RESTE (une
    gardée non tenue, comptée dans « x des y gardées » ; seul Alléger retire une ligne) et passe
    `reportee` comme au bilan (regles.md §4.6, §4.9). Prouvée sur chaque chemin qui change le jour."""

    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.projet = fabriques.projet(cls.u1, nom='Chantier')

    def setUp(self):
        self.J = timezone.localdate()
        self.plan = fabriques.plan(self.u1, self.J, planifie_le=timezone.now())
        self.tache = fabriques.tache(self.u1, projet=self.projet, jour_prevu=self.J, triee_le=timezone.now())
        LignePlanJour.objects.create(company=self.a, plan=self.plan, tache=self.tache, prevue_au_plan=True)

    def ligne(self):
        lignes = list(LignePlanJour.objects.filter(plan=self.plan, tache=self.tache))
        self.assertEqual(len(lignes), 1, 'la gardée reste une ligne du plan du jour')
        return lignes[0]

    def gardees(self):
        return LignePlanJour.objects.filter(plan=self.plan, prevue_au_plan=True).count()

    def assertReportee(self, reportee=True):
        self.assertEqual((self.ligne().reportee, self.ligne().prevue_au_plan, self.gardees()), (reportee, True, 1))

    def test_choisir_un_jour_garde_la_ligne_et_la_marque_reportee(self):
        planifier(self.tache, acteur=self.u1, jour_prevu=self.J + datetime.timedelta(days=2))
        self.assertReportee()

    def test_en_reserve_garde_la_ligne_et_la_marque_reportee(self):
        planifier(self.tache, acteur=self.u1, jour_prevu=None, quelque_jour=True)
        self.assertReportee()

    def test_annuler_rend_la_ligne_d_avant(self):
        geste = planifier(self.tache, acteur=self.u1, jour_prevu=self.J + datetime.timedelta(days=1)).geste
        annuler_geste(self.u1, geste.pk)
        self.assertReportee(False)

    def test_revenue_au_jour_la_ligne_n_est_plus_reportee(self):
        planifier(self.tache, acteur=self.u1, jour_prevu=self.J + datetime.timedelta(days=1))
        planifier(self.tache, acteur=self.u1, jour_prevu=self.J)
        self.assertReportee(False)

    def test_placer_a_une_heure_le_meme_jour_ne_touche_pas_la_ligne(self):
        planifier(self.tache, acteur=self.u1, jour_prevu=self.J, heure_debut=datetime.time(10, 0))
        self.assertReportee(False)

    def test_gardee_par_son_echeance_n_est_pas_reportee(self):
        Tache.objects.filter(pk=self.tache.pk).update(echeance=self.J)
        planifier(self.tache, acteur=self.u1, jour_prevu=self.J + datetime.timedelta(days=1))
        self.assertReportee(False)

    def test_trancher_un_jour(self):
        trancher_tache(self.u1, self.tache.pk, 'jour', self.J + datetime.timedelta(days=3))
        self.assertReportee()

    def test_lot_planifier(self):
        lot_taches(self.u1, [self.tache.pk], 'planifier',
                   {'jour_prevu': (self.J + datetime.timedelta(days=1)).isoformat()})
        self.assertReportee()

    def test_decaler_le_projet(self):
        decaler_projet(self.u1, self.projet.pk, 2, apercu=False)
        self.assertReportee()

    def test_bilan_tout_reporter(self):
        cloturer(self.u1, self.J, timezone.now(), le_reste=True)
        self.assertReportee()

    def test_alleger_retire_la_ligne(self):
        alleger(self.u1, self.J, timezone.now(), garder=[])
        self.assertFalse(LignePlanJour.objects.filter(plan=self.plan, tache=self.tache).exists())
