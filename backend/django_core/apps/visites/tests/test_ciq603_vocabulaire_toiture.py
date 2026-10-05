"""CIQ603 — un seul vocabulaire de type de toiture entre le lead et la visite.

Le test lit ``Lead.TypeToiture.choices`` : un code ajouté d'un seul côté
(visite OU lead) fait échouer la parité.
"""
from django.test import SimpleTestCase

from apps.crm.models import Lead
from apps.visites import visite_checklist as checklist


def _codes_visite():
    """Tous les codes de couverture que la visite sait saisir : la visite
    résidentielle (``toiture.type_couverture``) ET les zones du gabarit ci."""
    residentiel = set(
        checklist.mesure('toiture', 'type_couverture')['choix'])
    zones = checklist.mesure('toiture_ci', 'zones_toiture', 'ci')
    couverture = next(s for s in zones['forme'] if s['code'] == 'couverture')
    return residentiel, set(couverture['choix'])


class VocabulaireToitureTests(SimpleTestCase):
    def test_chaque_code_visite_a_exactement_un_code_lead(self):
        residentiel, zones = _codes_visite()
        self.assertEqual(residentiel, zones)
        self.assertEqual(set(checklist.CORRESPONDANCE_TOITURE_LEAD),
                         residentiel | zones)

    def test_chaque_code_lead_a_exactement_un_code_visite(self):
        codes_lead = {valeur for valeur, _ in Lead.TypeToiture.choices}
        cibles = list(checklist.CORRESPONDANCE_TOITURE_LEAD.values())
        self.assertEqual(set(cibles), codes_lead)
        # Bijection : aucun code lead visé par deux codes visite.
        self.assertEqual(len(cibles), len(set(cibles)))

    def test_la_table_se_lit_dans_les_deux_sens(self):
        for visite, lead in checklist.CORRESPONDANCE_TOITURE_LEAD.items():
            self.assertEqual(checklist.toiture_lead_depuis_visite(visite),
                             lead)
            self.assertEqual(checklist.toiture_visite_depuis_lead(lead),
                             visite)
        self.assertIsNone(checklist.toiture_lead_depuis_visite('inconnu'))
        self.assertIsNone(checklist.toiture_visite_depuis_lead('inconnu'))

    def test_les_valeurs_connues(self):
        self.assertEqual(checklist.toiture_lead_depuis_visite('beton'),
                         'terrasse_beton')
        self.assertEqual(checklist.toiture_lead_depuis_visite('tole'),
                         'tole_metal')
        self.assertEqual(checklist.toiture_lead_depuis_visite('tuile'),
                         'tuiles')

    def test_aucun_code_renomme(self):
        # Les codes de la visite et du lead gardent leur orthographe actuelle.
        residentiel, _ = _codes_visite()
        self.assertEqual(
            residentiel,
            {'tuile', 'tole', 'bac_acier', 'beton', 'fibrociment', 'autre'})
        self.assertEqual(
            {valeur for valeur, _ in Lead.TypeToiture.choices},
            {'tuiles', 'tole_metal', 'bac_acier', 'terrasse_beton',
             'fibrociment', 'autre'})
