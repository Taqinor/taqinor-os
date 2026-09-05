"""AUD818 — garde : la corbeille transverse 30 jours DOIT avoir un émetteur.

Défaut corrigé : `apps.trash` était livrée complète (modèle `ElementSupprime`,
récepteur, rétention, endpoint `/api/django/trash/corbeille/`) mais AUCUN code
de production n'émettait `core.events.record_soft_deleted` — le seul canal qui
l'alimente. `core.event_coverage.NO_STATIC_EMITTER` réservait explicitement le
signal, ce qui rendait le trou INVISIBLE aux gardes existantes : un Directeur
ouvrant l'écran de gouvernance voyait une corbeille vide, non parce que rien
n'avait été supprimé, mais parce que rien ne parlait.

Cette garde ferme le trou dans les DEUX sens :
  * tant qu'`apps.trash` est installée, `record_soft_deleted` ne peut PAS
    retourner dormir dans `NO_STATIC_EMITTER` ;
  * un émetteur STATIQUE de production (hors tests, hors migrations) doit
    exister, et ses kwargs doivent correspondre exactement au contrat catalogué.

Test ROUGE d'abord : sur l'arbre d'avant AUD818, les trois assertions échouent
(réservation présente, zéro émetteur relevé). L'émetteur réel est
`core.models.SoftDeleteModel.soft_delete()`, donc TOUT adoptant du mixin
(`crm.Lead`, `mrp.OrdreFabrication`, `contrats.Contrat` — le premier objet à
valeur légale) alimente la corbeille sans jamais importer `apps.trash`.

Aucune app métier n'est importée ici : `core` reste une fondation (contrat
import-linter « The core foundation app imports downward only »). La preuve
fonctionnelle bout-en-bout vit côté app émettrice
(`apps/contrats/tests/test_aud818_corbeille.py`).
"""
from django.conf import settings
from django.test import SimpleTestCase

from core import event_catalog, event_coverage

SIGNAL = 'record_soft_deleted'


class CorbeilleEmetteurTests(SimpleTestCase):
    def test_signal_non_reserve_tant_que_la_corbeille_est_installee(self):
        """`record_soft_deleted` ne peut pas rester « sans émetteur » réservé."""
        if 'apps.trash' not in settings.INSTALLED_APPS:
            self.skipTest("apps.trash n'est pas installée sur cette édition.")
        self.assertNotIn(
            SIGNAL, event_coverage.NO_STATIC_EMITTER,
            "AUD818 — `apps.trash` est installée (corbeille 30 jours exposée "
            "aux Directeurs) mais `record_soft_deleted` est réservé dans "
            "core.event_coverage.NO_STATIC_EMITTER : la corbeille promet une "
            "rétention que personne n'alimente. Émettez le signal depuis un "
            "chemin de suppression de PRODUCTION (le mixin de fondation "
            "core.SoftDeleteModel.soft_delete() le fait déjà) au lieu de "
            "re-réserver le signal.",
        )

    def test_un_emetteur_de_production_existe(self):
        """Au moins un `.send()` hors tests/migrations porte le signal."""
        cles = event_coverage.emitter_payload_keys().get(SIGNAL, set())
        self.assertTrue(
            cles,
            "AUD818 — aucun émetteur statique de `record_soft_deleted` dans "
            "apps/ ou core/ (hors tests et migrations) : la corbeille "
            "transverse ne recevra jamais rien.",
        )

    def test_payload_conforme_au_catalogue(self):
        """Les kwargs réellement émis == le contrat catalogué du signal."""
        attendu = set(event_catalog.entry(SIGNAL)['payload'])
        reel = event_coverage.emitter_payload_keys().get(SIGNAL, set())
        self.assertEqual(
            reel, attendu,
            f"AUD818 — kwargs émis {sorted(reel)} ≠ contrat catalogué "
            f"{sorted(attendu)} : la corbeille perdrait un champ de son "
            "instantané d'affichage (type/libellé/données).",
        )

    def test_aucune_divergence_de_parite_signalee(self):
        """La garde WIR139 ne doit plus signaler ce signal."""
        mismatches = event_coverage.catalog_payload_mismatches()
        self.assertNotIn(
            SIGNAL, mismatches,
            f"AUD818 — divergence de parité sur `{SIGNAL}` : "
            f"{mismatches.get(SIGNAL)}",
        )
