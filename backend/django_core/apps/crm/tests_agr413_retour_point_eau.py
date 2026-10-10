"""AGR413 — à la validation, les mesures du point d'eau remontent au lead (la
mesure remplace la déclaration).

Contrats partagés : ``apps/visites/contract_samples/visite_terrain.json``
(``retour_lead_point_eau``) et ``apps/crm/contract_samples/lead_pompage.json``
(colonnes cibles et provenance « mesure_visite »).

Run :
    python manage.py test apps.crm.tests_agr413_retour_point_eau -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm import visites_retour_lead
from apps.crm.models import Lead, LeadActivity
from apps.visites import selectors as visites_selectors
from apps.visites import services as visites_services
from apps.visites.models import VisiteTerrain

User = get_user_model()

RACINE = Path(__file__).resolve().parent.parent
CONTRAT_VISITE = json.loads(
    (RACINE / 'visites' / 'contract_samples' / 'visite_terrain.json')
    .read_text(encoding='utf-8'))
CONTRAT_LEAD = json.loads(
    (RACINE / 'crm' / 'contract_samples' / 'lead_pompage.json')
    .read_text(encoding='utf-8'))

COLONNES_POMPAGE = [c['nom'] for c in CONTRAT_LEAD['colonnes']]


class TableDuContrat(SimpleTestCase):
    def test_la_table_crm_est_celle_du_contrat(self):
        attendu = []
        for ligne in CONTRAT_VISITE['retour_lead_point_eau']:
            categorie, code = ligne['mesure'].split('.')
            provenance = ligne.get('provenance')
            attendu.append((
                categorie, code, ligne['colonne_lead'],
                (provenance['colonne_lead'], provenance['valeur'])
                if provenance else None))
        self.assertEqual(list(visites_retour_lead.RETOUR_LEAD_POINT_EAU), attendu)

    def test_chaque_colonne_cible_est_une_colonne_du_contrat_lead(self):
        for _cat, _code, colonne, provenance in visites_retour_lead.RETOUR_LEAD_POINT_EAU:
            self.assertIn(colonne, COLONNES_POMPAGE)
            if provenance:
                self.assertIn(provenance[0], COLONNES_POMPAGE)

    def test_une_visite_toiture_ne_transporte_aucune_mesure(self):
        visite = VisiteTerrain(gabarit='toiture', mesures={
            'toiture': {'longueur_m': 12}})
        self.assertEqual(
            visites_selectors.mesures_point_eau_pour_lead(visite), {})

    def test_seules_les_valeurs_saisies_voyagent(self):
        visite = VisiteTerrain(gabarit='point_eau', mesures={
            'point_eau': {'niveau_statique_m': 42, 'debit_mesure_m3h': None,
                          'niveau_dynamique_m': 50},
            'administratif': {'autorisation_numero': '',
                              'compteur_eau': False}})
        self.assertEqual(
            visites_selectors.mesures_point_eau_pour_lead(visite),
            {'point_eau': {'niveau_statique_m': 42, 'niveau_dynamique_m': 50},
             'administratif': {'compteur_eau': False}})


class RetourPointEauALaValidation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AGR413 Co', slug='agr413-co')
        self.bureau = User.objects.create_user(
            username='agr413_bureau', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Fellah', type_installation='agricole',
            niveau_statique_m=Decimal('30'), niveau_statique_source='declare',
            debit_forage_m3h=Decimal('20'), debit_forage_source='client',
            source_eau='puits')

    def _visite(self, gabarit='point_eau', mesures=None):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit=gabarit,
            statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures or {})

    def _lignes(self, champ):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION, field=champ)

    def test_valider_un_niveau_a_42_remonte_au_lead(self):
        visite = self._visite(mesures={
            'point_eau': {'source_eau': 'forage', 'niveau_statique_m': 42}})
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.niveau_statique_m, Decimal('42'))
        self.assertEqual(self.lead.niveau_statique_source, 'mesure_visite')
        self.assertEqual(self.lead.source_eau, 'forage')
        lignes = self._lignes('niveau_statique_m')
        self.assertEqual(lignes.count(), 1)
        self.assertEqual(lignes.get().user, self.bureau)

    def test_une_mesure_absente_laisse_la_valeur_declaree(self):
        visite = self._visite(mesures={
            'point_eau': {'niveau_statique_m': 42}})
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.debit_forage_m3h, Decimal('20'))
        self.assertEqual(self.lead.debit_forage_source, 'client')
        self.assertEqual(self.lead.source_eau, 'puits')

    def test_une_visite_toiture_ne_touche_aucune_colonne_de_pompage(self):
        avant = {c: getattr(self.lead, c) for c in COLONNES_POMPAGE}
        visite = self._visite(gabarit='toiture', mesures={
            'toiture': {'longueur_m': 12, 'largeur_m': 8}})
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual({c: getattr(self.lead, c) for c in COLONNES_POMPAGE},
                         avant)

    def test_revalider_ne_change_rien(self):
        visite = self._visite(mesures={
            'point_eau': {'niveau_statique_m': 42},
            'administratif': {'compteur_eau': True}})
        visites_services.valider_visite(visite, self.bureau)
        nb = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count()
        mesures = visites_selectors.mesures_point_eau_pour_lead(visite)
        self.lead.refresh_from_db()
        self.assertEqual(
            visites_retour_lead.appliquer_mesures_point_eau(
                self.lead, mesures, self.bureau), [])
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count(),
            nb)
