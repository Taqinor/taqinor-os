"""L4 (21/08/2026, + extension fondateur) — questionnaire d'appel du lead :
présence en journée + équipements électriques.

Huit champs additifs sur ``Lead`` (occupation_jour ; piscine/pompe, véhicule
électrique/km-semaine, climatisation/pièces, chauffe-eau électrique) : ce
test vérifie la persistance tri-état (``None`` = pas encore posée, distinct
de ``False``), le chatter (``TRACKED_FIELDS``) et les sélecteurs cross-app
``apps.crm.selectors.equipements_pour_devis``/``occupation_jour_pour_devis``
consommés par ``apps.ventes.courbes_journalieres`` (jamais l'inverse — voir
``.importlinter``)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import equipements_pour_devis, occupation_jour_pour_devis

User = get_user_model()


def _company(slug='l4-co', nom='L4 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class LeadEquipementFieldsTests(TestCase):
    """Persistance tri-état : ``None`` (pas posée) ≠ ``False`` (Non)."""

    def setUp(self):
        self.company = _company()

    def test_defauts_a_la_creation_sont_inconnus_pas_non(self):
        lead = Lead.objects.create(company=self.company, nom='L4 Lead')
        self.assertIsNone(lead.occupation_jour)
        self.assertIsNone(lead.equip_piscine)
        self.assertIsNone(lead.equip_piscine_pompe_kw)
        self.assertIsNone(lead.equip_voiture_electrique)
        self.assertIsNone(lead.equip_ve_km_semaine)
        self.assertIsNone(lead.equip_clim)
        self.assertIsNone(lead.equip_clim_pieces)
        self.assertIsNone(lead.equip_chauffe_eau_electrique)

    def test_valeurs_reelles_persistees(self):
        lead = Lead.objects.create(
            company=self.company, nom='L4 Lead 2',
            occupation_jour=Lead.OccupationJour.PARTIEL,
            equip_piscine=True, equip_piscine_pompe_kw=Decimal('1.10'),
            equip_voiture_electrique=True, equip_ve_km_semaine=150,
            equip_clim=True, equip_clim_pieces=3,
            equip_chauffe_eau_electrique=False,
        )
        lead.refresh_from_db()
        self.assertEqual(lead.occupation_jour, 'partiel')
        self.assertTrue(lead.equip_piscine)
        self.assertEqual(lead.equip_piscine_pompe_kw, Decimal('1.10'))
        self.assertTrue(lead.equip_voiture_electrique)
        self.assertEqual(lead.equip_ve_km_semaine, 150)
        self.assertTrue(lead.equip_clim)
        self.assertEqual(lead.equip_clim_pieces, 3)
        self.assertFalse(lead.equip_chauffe_eau_electrique)


class LeadEquipementFieldsV2Tests(TestCase):
    """L-BACK (24/08/2026) — les 6 champs complémentaires (kW/créneau)."""

    def setUp(self):
        self.company = _company()

    def test_defauts_a_la_creation_sont_inconnus(self):
        lead = Lead.objects.create(company=self.company, nom='LB Lead')
        self.assertIsNone(lead.equip_chauffe_eau_kw)
        self.assertIsNone(lead.equip_chauffe_eau_creneau)
        self.assertIsNone(lead.equip_ve_chargeur_kw)
        self.assertIsNone(lead.equip_ve_creneau)
        self.assertIsNone(lead.equip_clim_kw)
        self.assertIsNone(lead.equip_piscine_heures_jour)

    def test_valeurs_reelles_persistees(self):
        lead = Lead.objects.create(
            company=self.company, nom='LB Lead 2',
            equip_chauffe_eau_kw=Decimal('2.20'),
            equip_chauffe_eau_creneau=Lead.CreneauChauffeEau.NUIT,
            equip_ve_chargeur_kw=Decimal('7.40'),
            equip_ve_creneau=Lead.CreneauVe.NUIT,
            equip_clim_kw=Decimal('3.50'),
            equip_piscine_heures_jour=Decimal('6.5'),
        )
        lead.refresh_from_db()
        self.assertEqual(lead.equip_chauffe_eau_kw, Decimal('2.20'))
        self.assertEqual(lead.equip_chauffe_eau_creneau, 'nuit')
        self.assertEqual(lead.equip_ve_chargeur_kw, Decimal('7.40'))
        self.assertEqual(lead.equip_ve_creneau, 'nuit')
        self.assertEqual(lead.equip_clim_kw, Decimal('3.50'))
        self.assertEqual(lead.equip_piscine_heures_jour, Decimal('6.5'))


class TrackedFieldsTests(TestCase):
    """Les 7 champs sont journalisés dans le chatter (activity.TRACKED_FIELDS)."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='l4_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='L4 Lead')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _patch(self, **body):
        return self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/', body, format='json')

    def _modifications(self, field):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION, field=field)

    def test_patch_occupation_jour_logs_choice_label(self):
        resp = self._patch(occupation_jour='partiel')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('occupation_jour')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().field_label, 'Présence en journée')
        self.assertEqual(acts.first().new_value,
                         'Présence partielle (télétravail/mi-temps)')

    def test_patch_equip_piscine_logs_one_modification(self):
        resp = self._patch(equip_piscine=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('equip_piscine')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().field_label, 'Piscine')
        self.assertEqual(acts.first().new_value, 'Oui')

    def test_patch_equip_ve_km_semaine_logs_one_modification(self):
        resp = self._patch(equip_ve_km_semaine=150)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('equip_ve_km_semaine')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().new_value, '150')

    def test_patch_equip_clim_pieces_logs_one_modification(self):
        resp = self._patch(equip_clim_pieces=3)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('equip_clim_pieces').count(), 1)

    def test_patch_equip_chauffe_eau_electrique_logs_choice_non(self):
        resp = self._patch(equip_chauffe_eau_electrique=False)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('equip_chauffe_eau_electrique')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().new_value, 'Non')

    def test_patch_equip_chauffe_eau_kw_logs_one_modification(self):
        resp = self._patch(equip_chauffe_eau_kw='2.20')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            self._modifications('equip_chauffe_eau_kw').count(), 1)

    def test_patch_equip_chauffe_eau_creneau_logs_choice_label(self):
        resp = self._patch(equip_chauffe_eau_creneau='nuit')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('equip_chauffe_eau_creneau')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().new_value, 'Nuit')

    def test_patch_equip_ve_chargeur_kw_logs_one_modification(self):
        resp = self._patch(equip_ve_chargeur_kw='7.40')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            self._modifications('equip_ve_chargeur_kw').count(), 1)

    def test_patch_equip_ve_creneau_logs_choice_label(self):
        resp = self._patch(equip_ve_creneau='soir')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('equip_ve_creneau')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().new_value, 'Soir')

    def test_patch_equip_clim_kw_logs_one_modification(self):
        resp = self._patch(equip_clim_kw='3.50')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('equip_clim_kw').count(), 1)

    def test_patch_equip_piscine_heures_jour_logs_one_modification(self):
        resp = self._patch(equip_piscine_heures_jour='6.5')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            self._modifications('equip_piscine_heures_jour').count(), 1)


class _DevisAvecLead:
    """Stand-in minimal pour un ``ventes.Devis`` — jamais le vrai modèle
    importé ici (le sélecteur est lu depuis ``apps.ventes``, jamais l'inverse
    — un import ``apps.ventes.models`` dans ``apps.crm`` casserait
    ``.importlinter``)."""

    def __init__(self, lead=None):
        self.lead = lead


class EquipementsPourDevisSelectorTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_aucun_lead_renvoie_dict_vide(self):
        self.assertEqual(equipements_pour_devis(_DevisAvecLead(None)), {})

    def test_lead_sans_devis_attribut_ne_casse_pas(self):
        # object() n'a pas d'attribut .lead — même filet que
        # site_location_for_devis/profil_activite_pour_devis.
        self.assertEqual(equipements_pour_devis(object()), {})

    def test_valeurs_du_lead_relues_telles_quelles(self):
        lead = Lead.objects.create(
            company=self.company, nom='L4 Lead 3',
            equip_piscine=True, equip_piscine_pompe_kw=Decimal('0.75'),
            equip_voiture_electrique=True, equip_ve_km_semaine=200,
            equip_clim=False, equip_clim_pieces=None,
            equip_chauffe_eau_electrique=None,
        )
        out = equipements_pour_devis(_DevisAvecLead(lead))
        self.assertEqual(out, {
            'piscine': True,
            'piscine_pompe_kw': Decimal('0.75'),
            'voiture_electrique': True,
            've_km_semaine': 200,
            'clim': False,
            'clim_pieces': None,
            'chauffe_eau_electrique': None,
            'chauffe_eau_kw': None,
            'chauffe_eau_creneau': None,
            've_chargeur_kw': None,
            've_creneau': None,
            'clim_kw': None,
            'piscine_heures_jour': None,
        })


class OccupationJourPourDevisSelectorTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_aucun_lead_renvoie_none(self):
        self.assertIsNone(occupation_jour_pour_devis(_DevisAvecLead(None)))

    def test_lead_sans_devis_attribut_ne_casse_pas(self):
        self.assertIsNone(occupation_jour_pour_devis(object()))

    def test_valeur_pas_encore_posee_renvoie_none(self):
        lead = Lead.objects.create(company=self.company, nom='L4 Lead 4')
        self.assertIsNone(occupation_jour_pour_devis(_DevisAvecLead(lead)))

    def test_valeur_reelle_relue_telle_quelle(self):
        lead = Lead.objects.create(
            company=self.company, nom='L4 Lead 5',
            occupation_jour=Lead.OccupationJour.ABSENT)
        self.assertEqual(
            occupation_jour_pour_devis(_DevisAvecLead(lead)), 'absent')
