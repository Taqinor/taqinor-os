"""QJR246 — Champs enrichment du diagnostic enrichi atteignent la fiche lead.

`apps/web/src/lib/enrichment.ts` (cleanEnrichment) normalise 4 champs
FACULTATIFS du diagnostic enrichi (preview privé) : type d'alimentation
(mono/tri), surface de toiture, orientation, kWc estimé. Quand au moins un
est rempli, `preview-lead.ts` les pose dans un sous-objet `record.enrichment`
du lead transmis au webhook CRM (même convention que `band`/`utm`, jamais
top-level).

`_map_payload_to_fields` (apps/crm/webhooks.py) lit ce sous-objet et mappe
chaque clé vers une colonne `crm.Lead` EXISTANTE (aucune migration) :
supplyType -> raccordement, roofAreaM2 -> surface_toiture_m2,
orientation -> orientation, estimatedKwc -> taille_souhaitee_kwc. Le
vocabulaire du site diffère de celui du CRM (mono/tri, sud-est) et est
apparié explicitement, jamais un passthrough aveugle. Style tolérant du
webhook : une valeur invalide/hors bornes est ignorée, jamais une erreur ;
sans le sous-objet `enrichment`, la sortie reste byte-identique à avant
QJR246.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qjr246_enrichment -v 2
"""
from django.test import SimpleTestCase

from .models import Lead
from .webhooks import _map_payload_to_fields


BASE_PAYLOAD = {'fullName': 'Amina', 'phoneE164': '+212661850410'}


class TestEnrichmentPresentAndValid(SimpleTestCase):
    def test_all_four_fields_mapped(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD,
            'enrichment': {
                'supplyType': 'tri',
                'roofAreaM2': 45.5,
                'orientation': 'sud-est',
                'estimatedKwc': 6.2,
            },
        })
        self.assertEqual(fields['raccordement'], Lead.Raccordement.TRIPHASE)
        self.assertEqual(fields['surface_toiture_m2'], 45.5)
        self.assertEqual(fields['orientation'], Lead.Orientation.SUD_EST)
        self.assertEqual(fields['taille_souhaitee_kwc'], 6.2)

    def test_supply_type_mono(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'supplyType': 'mono'},
        })
        self.assertEqual(fields['raccordement'], Lead.Raccordement.MONOPHASE)

    def test_supply_type_inconnu(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'supplyType': 'inconnu'},
        })
        self.assertEqual(fields['raccordement'], Lead.Raccordement.INCONNU)

    def test_orientation_cardinal_mapped(self):
        for site_value, crm_value in (
                ('sud', Lead.Orientation.SUD),
                ('sud-ouest', Lead.Orientation.SUD_OUEST),
                ('est', Lead.Orientation.EST),
                ('ouest', Lead.Orientation.OUEST),
        ):
            fields = _map_payload_to_fields({
                **BASE_PAYLOAD, 'enrichment': {'orientation': site_value},
            })
            self.assertEqual(fields['orientation'], crm_value)

    def test_orientation_nord_and_inconnu_map_to_autre(self):
        # `Lead.Orientation` n'a pas de bucket Nord/Inconnu dédié — rapproché
        # d'AUTRE (même convention que distributeur 'inconnu' -> AUTRE),
        # jamais silencieusement jeté.
        for site_value in ('nord', 'inconnu'):
            fields = _map_payload_to_fields({
                **BASE_PAYLOAD, 'enrichment': {'orientation': site_value},
            })
            self.assertEqual(fields['orientation'], Lead.Orientation.AUTRE)

    def test_partial_enrichment_only_maps_whats_present(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'roofAreaM2': 30},
        })
        self.assertEqual(fields['surface_toiture_m2'], 30.0)
        self.assertNotIn('raccordement', fields)
        self.assertNotIn('orientation', fields)
        self.assertNotIn('taille_souhaitee_kwc', fields)


class TestEnrichmentInvalidOrOutOfBounds(SimpleTestCase):
    def test_unknown_supply_type_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'supplyType': 'quadriphase'},
        })
        self.assertNotIn('raccordement', fields)

    def test_unknown_orientation_string_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'orientation': 'nord-est-bis'},
        })
        self.assertNotIn('orientation', fields)

    def test_negative_roof_area_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'roofAreaM2': -10},
        })
        self.assertNotIn('surface_toiture_m2', fields)

    def test_roof_area_over_ceiling_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'roofAreaM2': 999999},
        })
        self.assertNotIn('surface_toiture_m2', fields)

    def test_non_numeric_kwc_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'estimatedKwc': 'beaucoup'},
        })
        self.assertNotIn('taille_souhaitee_kwc', fields)

    def test_kwc_over_ceiling_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {'estimatedKwc': 999999},
        })
        self.assertNotIn('taille_souhaitee_kwc', fields)

    def test_enrichment_not_a_dict_ignored(self):
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': 'oops',
        })
        self.assertNotIn('raccordement', fields)
        self.assertNotIn('surface_toiture_m2', fields)
        self.assertNotIn('orientation', fields)
        self.assertNotIn('taille_souhaitee_kwc', fields)

    def test_empty_enrichment_object_changes_nothing(self):
        with_empty = _map_payload_to_fields({
            **BASE_PAYLOAD, 'enrichment': {},
        })
        without_key = _map_payload_to_fields(dict(BASE_PAYLOAD))
        self.assertEqual(with_empty, without_key)


class TestByteIdenticalWithoutEnrichment(SimpleTestCase):
    def test_payload_without_enrichment_key_unchanged(self):
        # Garde-fou central QJR246 : un lead sans le sous-objet `enrichment`
        # (100 % des soumissions avant la promotion QJW16) ne voit apparaître
        # AUCUNE des 4 clés.
        fields = _map_payload_to_fields(dict(BASE_PAYLOAD))
        self.assertNotIn('raccordement', fields)
        self.assertNotIn('surface_toiture_m2', fields)
        self.assertNotIn('orientation', fields)
        self.assertNotIn('taille_souhaitee_kwc', fields)

    def test_does_not_override_field_already_set_by_another_source(self):
        # `raccordement` peut déjà être posé directement (vocabulaire CRM,
        # bloc historique) — l'enrichment ne doit jamais l'écraser.
        fields = _map_payload_to_fields({
            **BASE_PAYLOAD,
            'raccordement': Lead.Raccordement.MONOPHASE,
            'enrichment': {'supplyType': 'tri'},
        })
        self.assertEqual(fields['raccordement'], Lead.Raccordement.MONOPHASE)
