"""ALEA23 — garde de classe « liste blanche manuelle sans complétude ».

Les champs CONCRETS et INSCRIPTIBLES de ``LeadSerializer`` sont calculés par
INTROSPECTION : chacun doit être soit suivi au chatter (``TRACKED_FIELDS``),
soit exclu avec une raison (``CHAMPS_NON_SUIVIS``). Rouge sur 51f22174f
(``note``, ``contact_secondaire_nom``, ``contact_secondaire_telephone``,
``contact_preference``, ``structure_produit``, ``lien_maps``, ``tiers``,
``entite``), vert après ALEA16 + ALEA19.
"""
from django.test import SimpleTestCase

from apps.crm.activity import CHAMPS_NON_SUIVIS, TRACKED_FIELDS
from apps.crm.models import Lead
from apps.crm.serializers import LeadSerializer


def champs_inscriptibles_concrets():
    """Noms des champs inscriptibles du sérialiseur adossés à une colonne
    concrète de ``Lead`` (le nom DRF, ou sa ``source`` si elle diffère)."""
    concrets = {champ.name for champ in Lead._meta.concrete_fields}
    noms = set()
    for nom, champ in LeadSerializer().fields.items():
        if champ.read_only:
            continue
        source = champ.source if champ.source not in (None, '*') else nom
        if source in concrets:
            noms.add(source)
    return noms


class GardeChatterCompletTests(SimpleTestCase):
    def test_introspection_non_vide(self):
        """Anti-faux-vert : la garde voit bien les champs de la fiche."""
        noms = champs_inscriptibles_concrets()
        for attendu in ('nom', 'telephone', 'note', 'stage'):
            self.assertIn(attendu, noms)
        self.assertNotIn('company', noms)

    def test_tout_champ_inscriptible_est_suivi_ou_exclu(self):
        orphelins = sorted(
            champ for champ in champs_inscriptibles_concrets()
            if champ not in TRACKED_FIELDS and champ not in CHAMPS_NON_SUIVIS)
        self.assertEqual(
            orphelins, [],
            '\n'.join(f'Lead.{champ} inscriptible mais ni suivi au chatter '
                      'ni exclu (CHAMPS_NON_SUIVIS)' for champ in orphelins))

    def test_chaque_exclusion_porte_une_raison(self):
        for champ, raison in CHAMPS_NON_SUIVIS.items():
            with self.subTest(champ=champ):
                self.assertTrue(isinstance(raison, str) and raison.strip())

    def test_aucune_cle_perimee(self):
        concrets = {champ.name for champ in Lead._meta.concrete_fields}
        perimes = sorted(
            set(TRACKED_FIELDS) | set(CHAMPS_NON_SUIVIS))
        perimes = [cle for cle in perimes if cle not in concrets]
        self.assertEqual(perimes, [],
                         f'Clé(s) de suivi qui n’existent plus sur Lead : '
                         f'{perimes}')

    def test_suivi_et_exclusion_disjoints(self):
        self.assertFalse(set(TRACKED_FIELDS) & set(CHAMPS_NON_SUIVIS))
