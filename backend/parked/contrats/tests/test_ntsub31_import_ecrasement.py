"""Garde-fou anti-écrasement — import CSV des compteurs d'usage (NTSUB31).

``services.importer_compteurs_usage_csv`` rapproche chaque ligne par
``(company, type_cible, cible_id, code_compteur, periode_debut,
periode_fin)`` et METTAIT À JOUR une fiche ``CompteurUsage`` existante sans
aperçu ni trace de l'ancienne valeur (``update_or_create`` inconditionnel) —
un fichier périmé pouvait donc silencieusement remplacer un relevé réel
(potentiellement saisi à la main, ``source='manuel'``).

Ces tests couvrent les trois protections réutilisées TELLES QUELLES depuis la
primitive plateforme ``apps.dataimport.services`` (jamais un diff, une règle
remplissage-seul ou un journal maison) :

  * ``apercu=True`` — aperçu lecture seule des écrasements (champ/ancienne/
    nouvelle valeur), n'écrit rien ;
  * ``ecraser=False`` (défaut) — remplissage seul, la valeur bloquée revient
    dans ``refuses`` ;
  * ``ecraser=True`` — opt-in explicite, applique le remplacement et
    conserve la valeur précédente (``modifications`` / ``ImportJobRow`` /
    ``AuditLog``) ;

ainsi qu'une cellule vide qui ne peut jamais écraser/vider un champ existant,
la mise à jour de masse légitime (créations en nombre) qui reste possible
sans opt-in, et l'isolation multi-société du rapprochement.
"""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.audit.models import AuditLog
from apps.contrats import services
from apps.contrats.models import CompteurUsage
from apps.dataimport.models import ImportJob, ImportJobRow

CSV_HEADER = "cible_id,code_compteur,periode_debut,periode_fin,quantite\n"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


class AjoutGardeFouEcrasementTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub31-ecr", "Ntsub31Ecr")
        # Relevé RÉEL, saisi à la main (comme via l'écran, jamais un import).
        # type_cible='contrat' : défaut appliqué par l'import quand la
        # colonne est absente du CSV (voir CSV_HEADER, comme le fichier
        # existant `test_ntsub31_import_compteurs.py`).
        self.existant = CompteurUsage.objects.create(
            company=self.co, type_cible="contrat",
            cible_id=1, code_compteur="interventions",
            periode_debut="2026-01-01", periode_fin="2026-01-31",
            quantite=Decimal("5"), source=CompteurUsage.Source.MANUEL,
        )

    def _csv_ecrasant(self, quantite="99"):
        return CSV_HEADER + (
            f"1,interventions,2026-01-01,2026-01-31,{quantite}\n"
        )

    # ------------------------------------------------------------------
    # 1) Aperçu : surface l'écrasement, n'écrit rien.
    # ------------------------------------------------------------------
    def test_apercu_surface_ecrasement_sans_rien_ecrire(self):
        rapport = services.importer_compteurs_usage_csv(
            self.co, self._csv_ecrasant(), apercu=True)

        self.assertTrue(rapport["apercu"])
        self.assertEqual(len(rapport["conflits"]), 1)
        conflit = rapport["conflits"][0]
        self.assertEqual(conflit["cible_id"], self.existant.pk)
        [ecr] = conflit["ecrasements"]
        self.assertEqual(ecr["champ"], "quantite")
        self.assertEqual(ecr["ancienne"], "5.0000")
        self.assertEqual(ecr["nouvelle"], "99.0000")

        # Rien n'a été écrit : ni la fiche, ni un ImportJob.
        self.existant.refresh_from_db()
        self.assertEqual(self.existant.quantite, Decimal("5"))
        self.assertEqual(self.existant.source, CompteurUsage.Source.MANUEL)
        self.assertFalse(ImportJob.objects.filter(company=self.co).exists())

    # ------------------------------------------------------------------
    # 2) Remplissage seul (défaut) : préserve, remonte dans « refuses ».
    # ------------------------------------------------------------------
    def test_remplissage_seul_preserve_le_champ_et_le_signale_dans_refuses(self):
        rapport = services.importer_compteurs_usage_csv(
            self.co, self._csv_ecrasant())

        self.assertFalse(rapport["ecraser"])
        self.existant.refresh_from_db()
        self.assertEqual(self.existant.quantite, Decimal("5"))  # intact

        self.assertEqual(len(rapport["refuses"]), 1)
        refus_ligne = rapport["refuses"][0]
        self.assertEqual(refus_ligne["cible_id"], self.existant.pk)
        [refus] = refus_ligne["refuses"]
        self.assertEqual(refus["champ"], "quantite")
        self.assertEqual(refus["ancienne"], "5.0000")
        self.assertEqual(refus["nouvelle"], "99.0000")

        # Une ligne entièrement refusée n'a rien changé : pas comptée à tort.
        self.assertEqual(rapport["mises_a_jour"], 0)
        self.assertEqual(rapport["inserees"], 0)

    # ------------------------------------------------------------------
    # 3) ecraser=True : applique ET conserve l'ancienne valeur (réversible).
    # ------------------------------------------------------------------
    def test_ecraser_true_applique_et_journalise_ancienne_valeur(self):
        rapport = services.importer_compteurs_usage_csv(
            self.co, self._csv_ecrasant(), ecraser=True,
            filename="releves-janvier.csv")

        self.existant.refresh_from_db()
        self.assertEqual(self.existant.quantite, Decimal("99"))
        self.assertEqual(rapport["mises_a_jour"], 1)
        self.assertEqual(rapport["ecrasements"], 1)
        self.assertEqual(rapport["refuses"], [])

        # ImportJob/ImportJobRow réversible.
        job = ImportJob.objects.get(company=self.co, target="compteurs_contrat")
        self.assertEqual(job.pk, rapport["job_id"])
        self.assertTrue(job.ecraser)
        self.assertEqual(job.ecrasement_count, 1)
        row = ImportJobRow.objects.get(job=job)
        [mod] = row.modifications
        self.assertEqual(mod["champ"], "quantite")
        self.assertEqual(mod["ancienne"], "5.0000")
        self.assertEqual(mod["nouvelle"], "99.0000")
        self.assertTrue(mod["ecrasement"])

        # Ligne d'audit plateforme (jamais un journal maison).
        ct = ContentType.objects.get_for_model(CompteurUsage)
        log = AuditLog.objects.get(
            company=self.co, content_type=ct, object_id=str(self.existant.pk),
            action=AuditLog.Action.UPDATE)
        self.assertIn("5.0000", log.detail)
        self.assertIn("99.0000", log.detail)

    # ------------------------------------------------------------------
    # 4) Mise à jour de masse légitime : créer de NOUVELLES lignes marche
    #    sans opt-in (rien n'existe encore, donc rien à écraser).
    # ------------------------------------------------------------------
    def test_import_masse_de_nouvelles_lignes_sans_opt_in(self):
        csv_content = CSV_HEADER + "\n".join(
            f"{n},compteur-{n},2026-02-01,2026-02-28,{n * 10}"
            for n in range(2, 12)
        ) + "\n"
        rapport = services.importer_compteurs_usage_csv(self.co, csv_content)

        self.assertEqual(rapport["inserees"], 10)
        self.assertEqual(rapport["erreurs"], [])
        self.assertEqual(rapport["refuses"], [])
        self.assertEqual(
            CompteurUsage.objects.filter(
                company=self.co, periode_debut="2026-02-01").count(),
            10)

    # ------------------------------------------------------------------
    # 5) Cellule vide : jamais un écrasement/vidage silencieux.
    # ------------------------------------------------------------------
    def test_quantite_vide_ne_vide_jamais_la_valeur_existante(self):
        csv_content = CSV_HEADER + "1,interventions,2026-01-01,2026-01-31,\n"
        rapport = services.importer_compteurs_usage_csv(
            self.co, csv_content, ecraser=True)  # même avec l'opt-in

        self.assertEqual(len(rapport["erreurs"]), 1)
        self.assertEqual(rapport["mises_a_jour"], 0)
        self.existant.refresh_from_db()
        self.assertEqual(self.existant.quantite, Decimal("5"))  # inchangé

    # ------------------------------------------------------------------
    # 6) Isolation multi-société : le rapprochement ne traverse jamais
    #    la frontière société, même avec une clé identique.
    # ------------------------------------------------------------------
    def test_rapprochement_ne_traverse_jamais_les_societes(self):
        autre_co = make_company("ntsub31-ecr-autre", "Autre")
        autre_releve = CompteurUsage.objects.create(
            company=autre_co, type_cible="contrat", cible_id=1,
            code_compteur="interventions", periode_debut="2026-01-01",
            periode_fin="2026-01-31", quantite=Decimal("777"),
            source=CompteurUsage.Source.MANUEL)

        # Import sur self.co seulement — même clé (1, interventions, ...).
        rapport = services.importer_compteurs_usage_csv(
            self.co, self._csv_ecrasant(), ecraser=True)

        # La fiche de self.co a bien été mise à jour (rapprochement correct),
        # UNE seule ligne touchée — jamais deux (une par société).
        self.existant.refresh_from_db()
        self.assertEqual(self.existant.quantite, Decimal("99"))
        self.assertEqual(rapport["mises_a_jour"], 1)
        self.assertEqual(rapport["inserees"], 0)

        # La fiche de l'AUTRE société n'a jamais été vue ni touchée.
        autre_releve.refresh_from_db()
        self.assertEqual(autre_releve.quantite, Decimal("777"))
        self.assertEqual(
            CompteurUsage.objects.filter(company=autre_co).count(), 1)
        job = ImportJob.objects.get(company=self.co, target="compteurs_contrat")
        [row] = ImportJobRow.objects.filter(job=job)
        self.assertEqual(row.cible_id, self.existant.pk)
        self.assertNotEqual(row.cible_id, autre_releve.pk)
