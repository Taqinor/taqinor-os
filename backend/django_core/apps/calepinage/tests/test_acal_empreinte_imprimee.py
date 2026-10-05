"""ACAL40 — ``layout_hash`` devient l'empreinte « IMPRIMÉE » (D-ACAL-4 +
D-ACAL-21) et les empreintes stockées sont recalculées par UNE migration.

Avant : deux documents ne différant que par le champ au sol (340 → 200
modules), les zones d'exclusion, les modules, l'ombrage dessiné ou l'horizon
avaient la MÊME empreinte (porte JUM-01 : 7bfcddcd2c8d avec et sans le champ
de 272 modules) — « Générer » rendait l'ancien brouillon et « Resynchroniser »
répondait « inchangé ».
"""
from __future__ import annotations

import copy
import importlib

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.services.devis import DevisRefuse, generer_devis
from apps.calepinage.services.layout import enregistrer_layout
from apps.ventes.domain.geometrie import CLES_IMPRIMEES, layout_hash
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_brouillon_pour_layout

from .test_api_liste import BaseApiCalepinage

MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0018_acal40_empreinte_imprimee')
APRES = ('calepinage', '0018_acal40_empreinte_imprimee')

TOIT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


def _champ_au_sol(modules):
    return dict(copy.deepcopy(TOIT), poseSurfaces=[{
        'kind': 'sol', 'id': 'sol-1', 'label': 'Champ au sol',
        # ACAL59 — une surface pavée sans ``moduleWc`` est refusée nommée :
        # le champ au sol déclare la puissance de son module.
        'moduleWc': 550,
        'engine': {'modules': modules}}])


class EmpreinteImprimeePureTest(SimpleTestCase):

    def test_cles_imprimees_publiques(self):
        for cle in ('poseSurfaces', 'exclusionZones', 'modules',
                    'shading12x24', 'environment', 'shadeObstructions',
                    'horizonProfile'):
            self.assertIn(cle, CLES_IMPRIMEES)

    def test_pose_surfaces_change_l_empreinte(self):
        self.assertNotEqual(layout_hash(_champ_au_sol(340)),
                            layout_hash(_champ_au_sol(200)))
        self.assertNotEqual(layout_hash(TOIT), layout_hash(_champ_au_sol(340)))
        for cle, valeur in (
                ('exclusionZones', [{'id': 'ex-1', 'vertices': [[0, 0]]}]),
                ('modules', [{'id': 'm-1', 'x': 1.0, 'y': 2.0}])):
            with self.subTest(cle=cle):
                self.assertNotEqual(layout_hash(TOIT),
                                    layout_hash(dict(TOIT, **{cle: valeur})))

    def test_ombrage_et_horizon_changent_l_empreinte(self):
        cas = {
            'shading12x24': [[1.0] * 24 for _ in range(12)],
            'environment': [{'kind': 'arbre', 'hauteurM': 6}],
            'shadeObstructions': [{'id': 'o-1', 'hauteurM': 3}],
            'horizonProfile': {'source': 'saisie', 'points': [
                {'azimuthDeg': 90, 'heightDeg': 8.0}]},
        }
        for cle, valeur in cas.items():
            with self.subTest(cle=cle):
                self.assertNotEqual(layout_hash(TOIT),
                                    layout_hash(dict(TOIT, **{cle: valeur})))
        with self.subTest(cle='zones[].obstacles'):
            avec = copy.deepcopy(TOIT)
            avec['areas'][0]['obstacles'] = [{'id': 'ch', 'hauteurM': 1.2}]
            plus_haut = copy.deepcopy(avec)
            plus_haut['areas'][0]['obstacles'][0]['hauteurM'] = 2.4
            self.assertNotEqual(layout_hash(TOIT), layout_hash(avec))
            self.assertNotEqual(layout_hash(avec), layout_hash(plus_haut))

    def test_document_toit_seul_empreinte_inchangee(self):
        """R3 — sans les clés ajoutées (ou vides), l'empreinte historique est
        conservée à l'octet : la formule d'AVANT est celle, figée, de la
        migration."""
        for document in (TOIT, dict(TOIT, poseSurfaces=[], modules=[],
                                    horizonProfile=None, environment={})):
            with self.subTest(document=sorted(document)):
                self.assertEqual(layout_hash(document),
                                 MIGRATION.ancienne_empreinte(document))
        self.assertEqual(layout_hash(_champ_au_sol(340)),
                         MIGRATION.nouvelle_empreinte(_champ_au_sol(340)))


class GenererApresChangementDuChampTest(BaseApiCalepinage):

    def test_generer_apres_changement_du_champ_ne_rend_pas_l_ancien_brouillon(
            self):
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        seed_catalogue(self.company)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-SOL')
        enregistrer_layout(calepinage, _champ_au_sol(340), user=self.user)
        brouillon, cree = generer_devis(calepinage, user=self.user)
        self.assertTrue(cree)
        enregistrer_layout(calepinage, _champ_au_sol(200), user=self.user)
        calepinage.refresh_from_db()
        self.assertNotEqual(calepinage.layout_hash, brouillon.layout_hash)
        self.assertIsNone(devis_brouillon_pour_layout(
            self.company, self.lead.pk, calepinage.layout_hash))
        with self.assertRaises(DevisRefuse) as refus:
            generer_devis(calepinage, user=self.user)
        self.assertEqual(refus.exception.statut, 409)
        self.assertIn('Resynchroniser', str(refus.exception))


class MigrationRecalculTest(BaseApiCalepinage):
    """La migration 0018 rejouée par le CHARGEUR de migrations : ses deux
    fonctions (``recalculer`` / ``revenir``) reçoivent le registre HISTORIQUE
    de l'état 0018 — exactement ce que ``MigrationExecutor`` leur passe —
    sans dé-appliquer de schéma sous une transaction de test (les migrations
    calepinage suivantes altèrent la table)."""

    def _apps_historiques(self):
        executor = MigrationExecutor(connection)
        return executor.loader.project_state(APRES).apps

    def test_migration_recalcule_et_reverse(self):
        apps = self._apps_historiques()
        sol = _champ_au_sol(340)
        ancienne = MIGRATION.ancienne_empreinte(sol)
        nouvelle = MIGRATION.nouvelle_empreinte(sol)
        self.assertNotEqual(ancienne, nouvelle)
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-4040', layout_hash=ancienne)
        cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sol',
            roof_layout=sol, layout_hash=ancienne, devis=devis)
        version = CalepinageVersion.objects.create(
            company=self.company, calepinage=cal, roof_layout=sol,
            layout_hash=ancienne)
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=cal, nom='A', roof_layout=sol,
            layout_hash=ancienne)
        toit = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit',
            roof_layout=TOIT, layout_hash=layout_hash(TOIT))
        etrangere = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Étrangère',
            roof_layout=sol, layout_hash='f' * 64)
        statut = devis.statut

        def relire():
            def lu(modele, pk):
                return modele.objects.filter(pk=pk).values_list(
                    'layout_hash', flat=True).get()
            return {
                'cal': lu(Calepinage, cal.pk),
                'version': lu(CalepinageVersion, version.pk),
                'variante': lu(CalepinageVariante, variante.pk),
                'devis': lu(Devis, devis.pk),
                'toit': lu(Calepinage, toit.pk),
                'etrangere': lu(Calepinage, etrangere.pk),
            }

        MIGRATION.recalculer(apps, None)
        apres = relire()
        for cle in ('cal', 'version', 'variante', 'devis'):
            self.assertEqual(apres[cle], nouvelle, cle)
        self.assertEqual(apres['toit'], layout_hash(TOIT))
        self.assertEqual(apres['etrangere'], 'f' * 64)
        # Idempotente : rejouée, elle ne trouve plus rien à écrire.
        self.assertEqual(MIGRATION.plan_de_recalcul(apps), [])

        MIGRATION.revenir(apps, None)
        arriere = relire()
        for cle in ('cal', 'version', 'variante', 'devis'):
            self.assertEqual(arriere[cle], ancienne, cle)
        self.assertEqual(arriere['toit'], layout_hash(TOIT))
        self.assertEqual(arriere['etrangere'], 'f' * 64)
        self.assertEqual(Devis.objects.get(pk=devis.pk).statut, statut)

    def test_devis_sans_document_suit_son_calepinage(self):
        apps = self._apps_historiques()
        sol = _champ_au_sol(272)
        ancienne = MIGRATION.ancienne_empreinte(sol)
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-4041', layout_hash=ancienne)
        Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sol 272',
            roof_layout=sol, layout_hash=ancienne, devis=devis)
        MIGRATION.recalculer(apps, None)
        devis.refresh_from_db()
        self.assertEqual(devis.layout_hash, MIGRATION.nouvelle_empreinte(sol))


class DryRunTest(BaseApiCalepinage):

    def test_dry_run_n_ecrit_rien_et_nomme_le_devis(self):
        import io

        from django.core.management import call_command

        sol = _champ_au_sol(340)
        ancienne = MIGRATION.ancienne_empreinte(sol)
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-4042', layout_hash=ancienne,
            statut='envoye')
        Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sol',
            roof_layout=sol, layout_hash=ancienne, devis=devis)
        sortie = io.StringIO()
        call_command('acal_empreintes_dry_run', stdout=sortie)
        texte = sortie.getvalue()
        self.assertIn('DEV-202610-4042', texte)
        self.assertIn('AUCUNE écriture', texte)
        devis.refresh_from_db()
        self.assertEqual(devis.layout_hash, ancienne)
