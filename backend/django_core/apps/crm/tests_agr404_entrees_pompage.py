"""AGR404 — ``entrees_pompage`` : UNE lecture lead → entrées du dimensionnement,
avec leur provenance et sans aucun défaut fabriqué.

Contrat partagé : ``apps/crm/contract_samples/lead_pompage.json`` (AGR1,
bloc ``entrees_pompage`` + ``regles.entrees_pompage.cibles``). Le contrat
fait foi sur deux points : ``source_eau`` et ``electricite_sur_place`` sont
des INFORMATIONS sans cible (« ne choisit jamais `alim` à la place du
vendeur ») — aucun type de pompe ni alimentation n'est donc déduit ici.

Run :
    python manage.py test apps.crm.tests_agr404_entrees_pompage -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import selectors
from apps.crm.models import Lead, LeadActivity

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pompage.json').read_text(encoding='utf-8'))

#: Clés v1 qu'une entrée ne doit JAMAIS viser (contrat AGR1).
CLES_V1 = ('current_fuel', 'fuel_spend_current', 'distance_m', 'hmt_static',
           'region', 'crop', 'surface_ha')


def _par_colonne(bloc):
    return {e['colonne']: e for e in bloc['entrees']}


class Provenance(TestCase):
    """AGQ29 (C-AGQ-027) — le débit du foreur ou d'un essai est une MESURE."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agq29-co', defaults={'nom': 'AGQ29 Co'})

    def _provenance_debit(self, source):
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole',
            debit_forage_m3h=Decimal('25'), debit_forage_source=source)
        bloc = selectors.entrees_pompage_du_lead(lead)
        return _par_colonne(bloc)['debit_forage_m3h']['provenance']

    def test_foreur_est_une_mesure(self):
        self.assertEqual(self._provenance_debit('foreur'), 'foreur')
        self.assertEqual(self._provenance_debit('essai'), 'essai')
        self.assertEqual(self._provenance_debit('client'), 'client')


class EntreesPompage(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr404-co', defaults={'nom': 'AGR404 Co'})

    def _lead(self, **kwargs):
        kwargs.setdefault('type_installation', 'agricole')
        return Lead.objects.create(company=self.company, nom='Ferme',
                                   **kwargs)

    def test_lead_vide_aucune_valeur_tout_manquant(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead())
        self.assertEqual(bloc['entrees'], [])
        attendus = [c for c, _k, _p in selectors.ENTREES_POMPAGE_CIBLES]
        self.assertEqual(bloc['manquants'], attendus)

    def test_sans_distance_pas_de_distance_et_listee_manquante(self):
        bloc = selectors.entrees_pompage_du_lead(
            self._lead(niveau_statique_m=Decimal('20')))
        self.assertNotIn('distance_forage_champ_m', _par_colonne(bloc))
        self.assertIn('distance_forage_champ_m', bloc['manquants'])
        self.assertNotIn('distance_champ_m',
                         {e['cle_etude'] for e in bloc['entrees']})

    def test_aucun_defaut_fabrique_type_ou_alimentation(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            source_eau='bassin', raccordement='monophase',
            electricite_sur_place='monophase'))
        cles = {e['cle_etude'] for e in bloc['entrees']}
        colonnes = set(_par_colonne(bloc))
        self.assertNotIn('type_pompe', cles)
        self.assertNotIn('alim', cles)
        self.assertNotIn('source_eau', colonnes)
        self.assertNotIn('electricite_sur_place', colonnes)

    def test_volume_declare_derive_du_debit_et_des_heures_actuels(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            pompe_actuelle_debit_m3h=Decimal('10'),
            pompage_heures_jour=Decimal('7')))
        derive = [e for e in bloc['entrees']
                  if e['colonne'] == 'besoin_eau_m3j']
        self.assertEqual(len(derive), 1)
        self.assertEqual(derive[0]['valeur'], 70)
        self.assertEqual(derive[0]['provenance'], 'derive')
        self.assertEqual(derive[0]['formule'],
                         selectors.FORMULE_VOLUME_DECLARE)
        heures = _par_colonne(bloc)['pompage_heures_jour']
        self.assertEqual(heures['libelle'], 'heures de la pompe actuelle')
        self.assertEqual(heures['chemin'], 'besoin.heures_actuelles_jour')

    def test_le_besoin_declare_prime_sur_le_volume_derive(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            besoin_eau_m3j=Decimal('135'), besoin_eau_source='client',
            pompe_actuelle_debit_m3h=Decimal('10'),
            pompage_heures_jour=Decimal('7')))
        besoins = [e for e in bloc['entrees']
                   if e['colonne'] == 'besoin_eau_m3j']
        self.assertEqual([(e['valeur'], e['provenance']) for e in besoins],
                         [(135, 'client')])

    def test_pompe_actuelle_marquee_information_et_ne_sait_pas_omis(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            pompe_actuelle_cv=Decimal('7.5'), pompe_actuelle_type='ne_sait_pas'))
        par = _par_colonne(bloc)
        self.assertTrue(par['pompe_actuelle_cv']['information'])
        self.assertEqual(par['pompe_actuelle_cv']['chemin'], 'plaque.cv')
        self.assertNotIn('pompe_actuelle_type', par)

    def test_aucune_cible_v1(self):
        lead = self._lead(
            niveau_statique_m=Decimal('32'), distance_forage_champ_m=25,
            region_agricole='souss-massa', culture='agrumes',
            surface_irriguee_ha=4, pompe_alim_actuelle='butane',
            butane_bouteilles_jour=Decimal('4'), mois_irrigation=[4, 5])
        for entree in selectors.entrees_pompage_du_lead(lead)['entrees']:
            self.assertNotIn(entree['cle_etude'], CLES_V1, entree)

    def test_la_sortie_egale_l_exemple_du_contrat(self):
        exemple = CONTRAT['exemple']
        champs = {c['nom'] for c in CONTRAT['colonnes']}
        valeurs = {k: v for k, v in exemple.items()
                   if k in champs and v is not None}
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', source=Lead.Source.SITE_WEB,
            type_installation='agricole', **valeurs)
        # Relire depuis la base : l'exemple JSON porte des dates en chaînes
        # (``carburant_prix_declare_le``), le sélecteur reçoit toujours un
        # lead chargé de la base (dates typées).
        lead.refresh_from_db()
        # Les colonnes que l'exemple dit « client » ont été saisies par un
        # humain dans l'ERP (une ligne de chatter avec un utilisateur).
        user = User.objects.create_user(
            username='agr404_user', password='x', role_legacy='responsable',
            company=self.company)
        attendues = exemple['entrees_pompage']['entrees']
        for entree in attendues:
            if entree['provenance'] == 'client':
                LeadActivity.objects.create(
                    company=self.company, lead=lead, user=user,
                    kind=LeadActivity.Kind.MODIFICATION,
                    field=entree['colonne'], field_label=entree['colonne'])
        servies = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        for entree in attendues:
            servie = servies.get(entree['colonne'])
            self.assertIsNotNone(servie, entree['colonne'])
            self.assertTrue(set(entree) <= set(servie), entree['colonne'])
            for cle in ('valeur', 'provenance', 'cle_etude', 'chemin'):
                self.assertEqual(servie[cle], entree[cle],
                                 f"{entree['colonne']}.{cle}")

    def test_jours_irrigation_semaine_servis_au_bloc_economie(self):
        """AGQ10 (D-AGQ-6) — les jours d'irrigation par semaine du lead sont
        servis vers ``saisies_economie_pompage.consommation`` : sans eux une
        conso butane « par jour d'irrigation » laisse « Votre argent » omis."""
        lead = self._lead(
            pompe_alim_actuelle='butane', butane_bouteilles_jour=Decimal('2'),
            jours_irrigation_semaine=Decimal('5'))
        servies = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        jours = servies['jours_irrigation_semaine']
        self.assertEqual(jours['valeur'], 5)
        self.assertEqual(jours['cle_etude'], 'saisies_economie_pompage')
        self.assertEqual(
            jours['chemin'],
            'saisies_economie_pompage.consommation.jours_irrigation_par_semaine')
        # Champ vide : listé manquant, jamais un défaut.
        vide = selectors.entrees_pompage_du_lead(self._lead())
        self.assertIn('jours_irrigation_semaine', vide['manquants'])

    def test_une_seule_colonne_de_consommation_par_energie(self):
        """AGQ19 (C-AGQ-018) — ``butane_bouteilles_jour`` ET
        ``carburant_litres_mois`` visent ``consommation.quantite`` : seule la
        colonne de l'énergie du lead est servie telle quelle, l'autre porte
        ``ignoree`` (le moteur la saute). Table unique : ``apps.ventes``."""
        from apps.ventes.selectors import unite_par_energie
        self.assertEqual(unite_par_energie(),
                         {'butane': 'bouteille_12kg', 'diesel': 'litre'})
        lead = self._lead(
            pompe_alim_actuelle='butane', butane_bouteilles_jour=Decimal('2'),
            carburant_litres_mois=Decimal('100'))
        par = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        self.assertNotIn('ignoree', par['butane_bouteilles_jour'])
        self.assertEqual(par['carburant_litres_mois']['ignoree'],
                         'énergie butane')
        lead = self._lead(
            pompe_alim_actuelle='diesel', butane_bouteilles_jour=Decimal('2'),
            carburant_litres_mois=Decimal('100'))
        par = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        self.assertEqual(par['butane_bouteilles_jour']['ignoree'],
                         'énergie diesel')
        self.assertNotIn('ignoree', par['carburant_litres_mois'])

    def test_mode_pompe_et_plaque_servis_au_moteur(self):
        """AGQ39 (D-AGQ-10) — le mode et la plaque de la pompe actuelle
        sont servis vers ``mode_pompe`` et ``plaque.*`` ; les phases en 1/3."""
        lead = self._lead(
            mode_pompe='existante', pompe_actuelle_kw=Decimal('5.5'),
            pompe_actuelle_tension_v=380, pompe_actuelle_phases='tri')
        par = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        self.assertEqual(par['mode_pompe']['chemin'], 'mode_pompe')
        self.assertEqual(par['mode_pompe']['valeur'], 'existante')
        self.assertEqual(par['pompe_actuelle_kw']['chemin'], 'plaque.kw')
        self.assertEqual(par['pompe_actuelle_kw']['valeur'], 5.5)
        self.assertEqual(par['pompe_actuelle_tension_v']['valeur'], 380)
        self.assertEqual(par['pompe_actuelle_phases']['chemin'],
                         'plaque.phases')
        self.assertEqual(par['pompe_actuelle_phases']['valeur'], 3)
        self.assertTrue(par['pompe_actuelle_kw']['information'])
        vide = selectors.entrees_pompage_du_lead(self._lead())
        self.assertIn('mode_pompe', vide['manquants'])

    def test_facture_electricite_pompage_servie_seulement_si_electrique(self):
        """AGV8 — la facture d'électricité du pompage et sa part fixe visent
        ``facture_reseau.*`` ; servies seulement pour une pompe actuelle
        électrique, sinon MARQUÉES ``ignoree`` ; le moteur lit alors la
        périodicité mensuelle posée par le serveur."""
        from apps.ventes.domain.pompage import saisies_economie_pompage_du_lead
        lead = self._lead(
            pompe_alim_actuelle='electrique',
            depense_electricite_pompe_mad_mois=Decimal('900'),
            depense_electricite_pompe_part_fixe_mad_mois=Decimal('60'))
        par = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        self.assertEqual(
            par['depense_electricite_pompe_mad_mois']['chemin'],
            'saisies_economie_pompage.facture_reseau.montant_mad')
        self.assertEqual(
            par['depense_electricite_pompe_part_fixe_mad_mois']['chemin'],
            'saisies_economie_pompage.facture_reseau.part_fixe_mad_mois')
        self.assertNotIn('ignoree', par['depense_electricite_pompe_mad_mois'])
        facture = saisies_economie_pompage_du_lead(lead)['facture_reseau']
        self.assertEqual(facture['montant_mad'], 900)
        self.assertEqual(facture['part_fixe_mad_mois'], 60)
        self.assertEqual(facture['periodicite'], 'mensuelle')
        self.assertTrue(facture['saisi_le'])  # date de la déclaration
        for energie in ('butane', 'diesel'):
            lead = self._lead(
                pompe_alim_actuelle=energie,
                depense_electricite_pompe_mad_mois=Decimal('900'))
            par = _par_colonne(selectors.entrees_pompage_du_lead(lead))
            self.assertEqual(
                par['depense_electricite_pompe_mad_mois']['ignoree'],
                f'énergie {energie}')
            self.assertNotIn(
                'facture_reseau',
                saisies_economie_pompage_du_lead(lead) or {})

    def test_part_fixe_non_declaree_jamais_supposee_zero(self):
        """AGV8 — facture sans part fixe : la part fixe reste absente (le
        moteur omet alors l'économie en nommant le champ) ; part fixe sans
        facture : aucun bloc ``facture_reseau``."""
        from apps.ventes import economie_pompage as E
        from apps.ventes.domain.pompage import saisies_economie_pompage_du_lead
        lead = self._lead(
            pompe_alim_actuelle='electrique',
            depense_electricite_pompe_mad_mois=Decimal('900'))
        saisies = saisies_economie_pompage_du_lead(lead)
        self.assertNotIn('part_fixe_mad_mois', saisies['facture_reseau'])
        saisies['mois_irrigation'] = {'mois': [6, 7]}
        dep = E.depense_actuelle(saisies)
        self.assertEqual(dep['statut'], 'omis')
        self.assertTrue(any('part fixe de la facture électricité du pompage'
                            in m for m in dep['motifs']))
        lead = self._lead(
            pompe_alim_actuelle='electrique',
            depense_electricite_pompe_part_fixe_mad_mois=Decimal('60'))
        self.assertNotIn('facture_reseau',
                         saisies_economie_pompage_du_lead(lead) or {})

    def test_lecture_filtree_par_societe(self):
        lead = self._lead(niveau_statique_m=Decimal('20'))
        autre, _ = Company.objects.get_or_create(
            slug='agr404-autre', defaults={'nom': 'AGR404 Autre'})
        self.assertIsNone(
            selectors.entrees_pompage_pour_lead_id(lead.pk, autre))
        bloc = selectors.entrees_pompage_pour_lead_id(lead.pk, self.company)
        self.assertIn('niveau_statique_m', _par_colonne(bloc))


class EntreesPompageServiesAuDetail(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr404-api', defaults={'nom': 'AGR404 API'})
        self.user = User.objects.create_user(
            username='agr404_api', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole',
            niveau_statique_m=Decimal('32'))

    def test_detail_sert_le_bloc_et_la_liste_non(self):
        detail = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        self.assertEqual(set(detail['entrees_pompage']),
                         {'entrees', 'manquants'})
        self.assertIn('niveau_statique_m',
                      _par_colonne(detail['entrees_pompage']))
        liste = self.api.get('/api/django/crm/leads/').data
        lignes = liste['results'] if 'results' in liste else liste
        self.assertNotIn('entrees_pompage', lignes[0])

    def test_jours_irrigation_semaine_persiste_et_journalise(self):
        """AGQ10 — enregistrer → rouvrir : valeur identique, chatter old→new ;
        une valeur hors 0-7 est refusée en la nommant."""
        url = f'/api/django/crm/leads/{self.lead.id}/'
        rep = self.api.patch(url, {'jours_irrigation_semaine': '5'},
                             format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        relu = self.api.get(url).data
        self.assertEqual(Decimal(str(relu['jours_irrigation_semaine'])),
                         Decimal('5'))
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='jours_irrigation_semaine').exists())
        trop = self.api.patch(url, {'jours_irrigation_semaine': '8'},
                              format='json')
        self.assertEqual(trop.status_code, 400, trop.data)
        self.assertIn('jours_irrigation_semaine', trop.data)

    def test_mode_pompe_et_plaque_persistent_et_journalisent(self):
        """AGQ39 — enregistrer → rouvrir : identique, chatter old→new."""
        url = f'/api/django/crm/leads/{self.lead.id}/'
        corps = {'mode_pompe': 'existante', 'pompe_actuelle_kw': '5.50',
                 'pompe_actuelle_tension_v': 380,
                 'pompe_actuelle_phases': 'tri'}
        rep = self.api.patch(url, corps, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        relu = self.api.get(url).data
        for cle, valeur in corps.items():
            self.assertEqual(relu[cle], valeur, cle)
        self.assertEqual(relu['devis_auto']['mode_pompe'],
                         {'valeur': 'existante', 'par_defaut': False})
        for champ in corps:
            self.assertTrue(LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
                field=champ).exists(), champ)


class MotifJoursIrrigationTests(TestCase):
    """api-fuzz (24/10/2026) — la branche « chaîne » du schéma refuse ce que
    le serveur refuse : « 0 », négatif, > 7 ; accepte 0,1 … 7."""

    def test_motif_aligne_sur_les_bornes(self):
        import re
        from apps.crm.serializers import MOTIF_JOURS_IRRIGATION
        motif = re.compile(MOTIF_JOURS_IRRIGATION)
        for ok in ('0.1', '0.5', '1', '3.5', '6.9', '7', '7.0'):
            self.assertIsNotNone(motif.match(ok), ok)
        for ko in ('0', '0.0', '-1', '7.1', '7.5', '8', '12', 'abc', ''):
            self.assertIsNone(motif.match(ko), ko)
