"""CIQ607 — à la validation, le relevé C&I remonte au lead : la mesure
remplace la déclaration, avec sa provenance.

Contrats partagés : ``apps/visites/contract_samples/visite_terrain.json``
(``retour_lead_ci``, ``releve_ci``) et ``apps/crm/contract_samples/
lead_pro.json`` (colonnes cibles, provenance « mesure_visite »). Le sélecteur
du relevé n'est jamais mocké : la visite est validée par le vrai service.
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
    (RACINE / 'crm' / 'contract_samples' / 'lead_pro.json')
    .read_text(encoding='utf-8'))

COLONNES_CI = [c for _cle, c, _s in visites_retour_lead.RETOUR_LEAD_CI]

ZONE = {'id': 'z1', 'libelle': 'Atelier nord', 'longueur_m': 40,
        'largeur_m': 18, 'pente_deg': 8, 'orientation': 'sud',
        'couverture': 'bac_acier', 'structure': 'portique',
        'surface_utile_m2': None}


class TableDuContrat(SimpleTestCase):
    def test_chaque_ligne_est_dans_retour_lead_ci(self):
        contrat = {ligne['colonne_lead']: ligne
                   for ligne in CONTRAT_VISITE['retour_lead_ci']}
        for _cle, colonne, source in visites_retour_lead.RETOUR_LEAD_CI:
            with self.subTest(colonne=colonne):
                self.assertIn(colonne, contrat)
                provenance = contrat[colonne].get('provenance')
                if source:
                    self.assertEqual(provenance, {
                        'colonne_lead': source,
                        'valeur': visites_retour_lead.ORIGINE_MESURE_VISITE})
                else:
                    self.assertIsNone(provenance)

    def test_les_cles_du_releve_sont_celles_du_contrat(self):
        releve = CONTRAT_VISITE['exemple_ci']['releve_ci']
        for cle, _colonne, _source in visites_retour_lead.RETOUR_LEAD_CI:
            self.assertIn(cle, releve)


class RetourReleveCiALaValidation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ607 Co', slug='ciq607-co')
        self.bureau = User.objects.create_user(
            username='ciq607_bureau', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Usine', type_installation='industriel',
            tension_raccordement='bt', tension_source='declare',
            compteur_puissance_kva=Decimal('80'),
            puissance_souscrite_source='declare',
            type_toiture='terrasse_beton',
            surface_toiture_m2=Decimal('650'), surface_source='declare')

    def _visite(self, gabarit='ci', mesures=None):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit=gabarit,
            statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures or {})

    def _mesures_ci(self, **comptage):
        bloc = {'type_compteur': 'triphasé',
                'niveau_tension_constate': 'mt',
                'puissance_souscrite_kva_constatee': 100}
        bloc.update(comptage)
        return {'comptage': bloc, 'toiture_ci': {'zones_toiture': [ZONE]}}

    def _lignes(self, champ):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION, field=champ)

    def test_ci_100_kva_remonte_avec_provenance_et_journal(self):
        visite = self._visite(mesures=self._mesures_ci())
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.compteur_puissance_kva, Decimal('100'))
        self.assertEqual(self.lead.puissance_souscrite_source,
                         'mesure_visite')
        self.assertEqual(self.lead.tension_raccordement, 'mt')
        self.assertEqual(self.lead.tension_source, 'mesure_visite')
        self.assertEqual(self.lead.type_toiture, 'bac_acier')
        self.assertEqual(self.lead.surface_toiture_m2, Decimal('720'))
        self.assertEqual(self.lead.surface_source, 'mesure_visite')
        lignes = self._lignes('compteur_puissance_kva')
        self.assertEqual(lignes.count(), 1)
        self.assertEqual(lignes.get().user, self.bureau)
        # Le type du lead n'est JAMAIS changé (convention 20).
        self.assertEqual(self.lead.type_installation, 'industriel')

    def test_provenance_mesure_visite_detail_et_date(self):
        visite = self._visite(mesures=self._mesures_ci())
        visites_services.valider_visite(visite, self.bureau)
        visite.refresh_from_db()
        Lead.objects.filter(pk=self.lead.pk).update(
            compteur_puissance_kva=Decimal('80'))
        self.lead.refresh_from_db()
        rendu = visites_retour_lead.appliquer_releve_ci(
            self.lead, visites_selectors.releve_ci_de_visite(visite),
            self.bureau)
        self.assertEqual(rendu['compteur_puissance_kva']['provenance'], {
            'origine': 'mesure_visite', 'detail': f'visite {visite.id}',
            'date': visite.validee_le.isoformat()})

    def test_mesure_non_relevee_laisse_la_valeur_declaree(self):
        mesures = self._mesures_ci(puissance_souscrite_kva_constatee=None)
        mesures['comptage']['_non_releves'] = {
            'puissance_souscrite_kva_constatee': 'a_faire_par_electricien'}
        visites_services.valider_visite(
            self._visite(mesures=mesures), self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.compteur_puissance_kva, Decimal('80'))
        self.assertEqual(self.lead.puissance_souscrite_source, 'declare')

    def test_visite_toiture_ne_touche_aucune_colonne_ci(self):
        avant = {c: getattr(self.lead, c) for c in COLONNES_CI}
        visites_services.valider_visite(
            self._visite(gabarit='toiture', mesures={
                'toiture': {'longueur_m': 12, 'largeur_m': 8}}), self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual({c: getattr(self.lead, c) for c in COLONNES_CI},
                         avant)

    def test_revalider_est_idempotent(self):
        visite = self._visite(mesures=self._mesures_ci())
        visites_services.valider_visite(visite, self.bureau)
        nb = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count()
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(
            visites_retour_lead.appliquer_releve_ci(
                self.lead, visites_selectors.releve_ci_de_visite(visite),
                self.bureau), {})
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count(),
            nb)


class SupplementCosPhiGroupe(TestCase):
    """CIQ5 (lignes ``factures_mt.cos_phi_constate`` → ``cos_phi`` et
    ``reactif_secours.groupe_kva`` → ``groupe_kva`` de ``retour_lead_ci``) —
    constat CAD177 (nocturne e2e CIQ665) : le cos φ relevé à la visite MT ne
    remontait jamais sur le lead."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ607b Co', slug='ciq607b-co')
        self.bureau = User.objects.create_user(
            username='ciq607b_bureau', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Usine MT',
            type_installation='industriel')

    def test_les_lignes_supplement_sont_dans_le_contrat(self):
        contrat = {ligne['colonne_lead']: ligne
                   for ligne in CONTRAT_VISITE['retour_lead_ci']}
        for _cle, colonne, source in visites_retour_lead.RETOUR_LEAD_CI_SUPPLEMENT:
            with self.subTest(colonne=colonne):
                self.assertIn(colonne, contrat)
                attendu = ({'colonne_lead': source,
                            'valeur': visites_retour_lead.ORIGINE_MESURE_VISITE}
                           if source else None)
                self.assertEqual(contrat[colonne].get('provenance'), attendu)

    def _valider(self, factures_mt=None, reactif=None):
        mesures = {'comptage': {'niveau_tension_constate': 'mt'}}
        if factures_mt is not None:
            mesures['factures_mt'] = factures_mt
        if reactif is not None:
            mesures['reactif_secours'] = reactif
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='ci',
            statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures)
        visites_services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()

    def test_cos_phi_source_connue_remonte_avec_provenance(self):
        self._valider(factures_mt={'cos_phi_constate': 0.92,
                                   'source_cos_phi': 'facture'})
        self.assertEqual(self.lead.cos_phi, Decimal('0.920'))
        self.assertEqual(self.lead.cos_phi_source, 'mesure_visite')

    def test_cos_phi_source_inconnue_nest_pas_recopie(self):
        self._valider(factures_mt={'cos_phi_constate': 0.92,
                                   'source_cos_phi': 'inconnu'})
        self.assertIsNone(self.lead.cos_phi)
        self.assertIsNone(self.lead.cos_phi_source)

    def test_cos_phi_hors_bornes_nest_jamais_recopie(self):
        self._valider(factures_mt={'cos_phi_constate': 1.4,
                                   'source_cos_phi': 'mesure'})
        self.assertIsNone(self.lead.cos_phi)

    def test_groupe_kva_remonte(self):
        self._valider(reactif={'groupe_kva': 150})
        self.assertEqual(self.lead.groupe_kva, Decimal('150.00'))
