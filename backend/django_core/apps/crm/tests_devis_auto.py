"""
Tests du gating « devis automatique » (devis_auto.py, champ sérialisé,
endpoint POST /leads/<id>/devis-auto/) et du mouvement automatique du
funnel quand le STATUT d'un devis change (envoye → QUOTE_SENT,
accepte → SIGNED) — clés d'étape scalaires, jamais de liste codée en dur
(STAGES.py canonique, CLAUDE.md règle #2).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_devis_auto -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.devis_auto import (
    champs_manquants, champs_manquants_detail, champs_requis,
    message_manquants, mode_pompe_du_lead, source_conso, visite_avant_devis,
    visite_point_eau_avant_devis)
from apps.crm.models import Lead, LeadActivity
from apps.ventes.models import Devis

User = get_user_model()

# AGR403 — libellés du contrat ``devis_auto_pret.json`` (exemple_agricole).
LIB_HMT = 'HMT (m)'  # AGQ9 (D-AGQ-5)
LIB_DEBIT = ('Débit souhaité, besoin en eau (m³/jour) ou débit de la pompe '
             'actuelle')
MSG_AGRICOLE = f'Manque : {LIB_HMT}, {LIB_DEBIT}'

CONTRAT_DEVIS_AUTO = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'devis_auto_pret.json').read_text(encoding='utf-8'))

# CIQ404 — libellés du groupe pro (industriel = exemple_industriel du contrat).
LIB_PRO = {
    'commercial': 'Consommation (kWh) ou facture mensuelle (MAD)',
    'industriel': CONTRAT_DEVIS_AUTO['exemple_industriel']['devis_auto'][
        'manquants'][0],
}


def _bloc_pro(lead):
    detail = champs_manquants_detail(lead)
    manquants = [e['label'] for e in detail]
    return {
        'pret': not manquants,
        'manquants': manquants,
        'manquants_detail': detail,
        'requis': champs_requis(lead),
        'source_conso': source_conso(lead),
        'visite_avant_devis': visite_avant_devis(lead),
    }


class TestDevisAutoProCIQ404(SimpleTestCase):
    """CIQ404 (D-CIQ-5, contrat CIQ1) — facture en MAD acceptée pour un BT,
    kWh exigés en MT, drapeau « visite avant devis ». Règle pure."""

    def _lead(self, **kw):
        # ADEV89 — la phase du site est un prérequis C&I ; ces cas testent
        # la consommation et le contrat, la phase est déclarée.
        if kw.get('type_installation') in ('commercial', 'industriel'):
            kw.setdefault('raccordement', 'triphase')
        return Lead(nom='Pro', **kw)

    def test_commercial_mad_sans_kwh_pret_source_facture(self):
        # ALEA47 — la facture en MAD ne compte qu'avec un contrat BT déclaré
        # (et le moteur exige aussi une activité : bureau = archétype).
        lead = self._lead(type_installation='commercial',
                          facture_hiver=Decimal('25000'),
                          contrat_electricite='bt_patente',
                          categorie_commerciale='bureau')
        self.assertEqual(champs_manquants(lead), [])
        self.assertEqual(source_conso(lead), 'facture_hiver')
        # ADEV125 (D-ACAL-92) — sans contrat, le moteur suppose la BT : la
        # facture compte toujours ; un contrat MT déclaré, non.
        lead.contrat_electricite = None
        self.assertEqual(source_conso(lead), 'facture_hiver')
        lead.contrat_electricite = 'mt_general'
        self.assertIsNone(source_conso(lead))

    def test_commercial_mt_et_mad_seul_pas_pret(self):
        lead = self._lead(type_installation='commercial',
                          tension_raccordement='mt',
                          facture_hiver=Decimal('25000'),
                          categorie_commerciale='bureau')
        self.assertEqual(champs_manquants(lead), [LIB_PRO['commercial']])
        self.assertIsNone(source_conso(lead))

    def test_industriel_mad_seul_tension_non_declaree_bt_supposee(self):
        # D-ACAL-92 (« supposer_bt », fondateur 23/11/2026, lead commercial OU
        # industriel) — tension non déclarée (vide, « ne sait pas », défaut
        # du site jamais touché) : basse tension supposée, la facture en MAD
        # compte ; la visite reste requise (« tension de raccordement inconnue »).
        for tension, source in ((None, None), ('ne_sait_pas', None),
                                ('bt', 'site_defaut_visible'),
                                ('mt', 'site_defaut_visible')):
            lead = self._lead(type_installation='industriel',
                              tension_raccordement=tension, tension_source=source,
                              facture_hiver=Decimal('40000'), regime_equipes='3x8')
            self.assertEqual(champs_manquants(lead), [], tension)
            self.assertEqual(source_conso(lead), 'facture_hiver', tension)
            self.assertTrue(visite_avant_devis(lead)['requise'], tension)
            if tension != 'mt':  # visite_avant_devis inchangée (lit la valeur brute)
                self.assertIn('tension de raccordement inconnue',
                              visite_avant_devis(lead)['motifs'], tension)
        # Sans rythme : seul le rythme manque (aucun archétype industriel).
        lead = self._lead(type_installation='industriel',
                          facture_hiver=Decimal('40000'))
        self.assertEqual([e['champ'] for e in champs_manquants_detail(lead)],
                         ['jours_ouverture'])

    def test_industriel_bt_declaree_et_mad_pret(self):
        lead = self._lead(type_installation='industriel',
                          tension_raccordement='bt', tension_source='declare',
                          facture_hiver=Decimal('40000'),
                          contrat_electricite='bt_force_motrice',
                          regime_equipes='continu',
                          jours_ouverture=[1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(champs_manquants(lead), [])
        # Une moyenne tension DÉCLARÉE garde sa règle : aucune facture en
        # dirhams convertie au tarif basse tension (prime fixe MT).
        lead.tension_raccordement, lead.contrat_electricite = 'mt', None
        detail = champs_manquants_detail(lead)
        self.assertEqual([e['champ'] for e in detail], ['conso_mensuelle_kwh'])
        self.assertEqual(detail[0]['label'], LIB_PRO['industriel'])
        self.assertIsNone(source_conso(lead))

    # ── Fondateur 24/11/2026 — la puissance maximale suffit (conso estimée) ──

    def _hasnaoui(self, **kw):
        """Lead « Karim Hasnaoui » : industriel MT, 1×8, lun→sam 8-18 h,
        380 kVA de puissance maximale, AUCUNE autre consommation."""
        champs = dict(type_installation='industriel', tension_raccordement='mt',
                      tension_source='facture', regime_equipes='1x8',
                      jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=8, heure_fin=18,
                      puissance_max_appelee_kva=Decimal('380'))
        champs.update(kw)
        return self._lead(**champs)

    def test_puissance_max_seule_pret_exemple_du_contrat(self):
        lead = self._hasnaoui()
        self.assertEqual(
            _bloc_pro(lead),
            CONTRAT_DEVIS_AUTO['exemple_industriel_puissance_max']['devis_auto'])
        self.assertEqual(source_conso(lead), 'puissance_max_appelee_kva')

    def test_puissance_max_sans_heures_les_heures_manquent(self):
        lead = self._hasnaoui(regime_equipes=None, heure_debut=None, heure_fin=None)
        detail = champs_manquants_detail(lead)
        self.assertEqual([e['champ'] for e in detail], ['heure_debut'])
        # Un commerce à archétype (bureau) : la forme de journée ne dit aucune
        # heure — l'estimation les exige quand même (la conso réelle, non).
        commerce = self._lead(type_installation='commercial', categorie_commerciale='bureau',
                              puissance_max_appelee_kva=Decimal('60'))
        self.assertEqual([e['champ'] for e in champs_manquants_detail(commerce)],
                         ['jours_ouverture'])
        commerce.conso_mensuelle_kwh = Decimal('4000')
        self.assertEqual(champs_manquants(commerce), [])

    def test_une_consommation_reelle_passe_devant_la_puissance(self):
        lead = self._hasnaoui(conso_mensuelle_kwh=Decimal('20000'))
        self.assertEqual(source_conso(lead), 'conso_mensuelle_kwh')
        self.assertEqual(champs_manquants(lead), [])

    def test_industriel_releve_seul_pret(self):
        lead = self._lead(type_installation='industriel', releve_conso={
            'mois': [{'mois': '2026-08', 'kwh': '40000.00'}],
            'source': 'lu_sur_facture'}, contrat_electricite='bt_patente',
            regime_equipes='3x8', jours_ouverture=[1, 2, 3, 4, 5, 6])
        self.assertEqual(champs_manquants(lead), [])
        self.assertEqual(source_conso(lead), 'releve_conso')

    def test_visite_avant_devis(self):
        mt = self._lead(type_installation='industriel',
                        tension_raccordement='mt')
        self.assertTrue(visite_avant_devis(mt)['requise'])
        self.assertIn('site en moyenne tension',
                      visite_avant_devis(mt)['motifs'])
        bt = self._lead(type_installation='commercial',
                        tension_raccordement='bt', tension_source='declare',
                        compteur_puissance_kva=Decimal('60'),
                        type_surface='toiture',
                        surface_toiture_m2=Decimal('300'))
        self.assertEqual(visite_avant_devis(bt),
                         {'requise': False, 'motifs': []})
        defaut = self._lead(type_installation='commercial',
                            tension_raccordement='bt',
                            tension_source='site_defaut_visible')
        self.assertIn('tension de raccordement inconnue',
                      visite_avant_devis(defaut)['motifs'])

    def test_residentiel_et_agricole_inchanges(self):
        for mode in ('residentiel', 'agricole', None):
            lead = self._lead(type_installation=mode)
            self.assertIsNone(visite_avant_devis(lead), mode)
            self.assertIsNone(source_conso(lead), mode)
        self.assertEqual(champs_requis(self._lead()),
                         [['facture_hiver', 'conso_mensuelle_kwh'], ['ville', 'gps_lat']])

    def test_exemples_commercial_et_industriel_du_contrat(self):
        # ALEA47 — contrat BT déclaré, rythme manquant (aucune activité).
        commercial = self._lead(
            type_installation='commercial', tension_raccordement='bt',
            tension_source='declare', facture_hiver=Decimal('4000'),
            type_surface='toiture', contrat_electricite='bt_patente')
        self.assertEqual(
            _bloc_pro(commercial),
            CONTRAT_DEVIS_AUTO['exemple_commercial']['devis_auto'])
        industriel = self._lead(
            type_installation='industriel', tension_raccordement='mt',
            tension_source='facture', facture_hiver=Decimal('40000'),
            compteur_puissance_kva=Decimal('250'), type_surface='toiture',
            surface_toiture_m2=Decimal('2000'))
        self.assertEqual(
            _bloc_pro(industriel),
            CONTRAT_DEVIS_AUTO['exemple_industriel']['devis_auto'])

    def test_questionnaire_energie_ferme_pour_le_commercial_en_mad(self):
        from unittest import mock
        from apps.crm import questionnaire
        lead = self._lead(type_installation='commercial',
                          facture_hiver=Decimal('25000'),
                          raccordement='triphase')
        with mock.patch.object(questionnaire, '_libelles_pieces_jointes',
                               return_value=[]):
            # CIQ412 — un pro ne reçoit plus la section énergie résidentielle
            # du tout (clé absente) : elle n'est donc jamais rouverte.
            self.assertFalse(
                questionnaire.manquantes(lead).get('energie', False))


class TestAgricoleSansCvAGR403(SimpleTestCase):
    """AGR403 (D-AGR-3, D-AGR-4) — « devis auto prêt » agricole sans le CV,
    et drapeau « visite du point d'eau avant devis ». Règle pure."""

    def _lead(self, **kwargs):
        kwargs.setdefault('raccordement', 'triphase')  # ALEA67 — la phase, exigée
        return Lead(nom='Ferme', type_installation='agricole', **kwargs)

    def test_hmt_et_debit_sans_cv_est_pret(self):
        lead = self._lead(pompe_hmt_m=Decimal('60'),
                          pompe_debit_m3h=Decimal('20'))
        self.assertEqual(champs_manquants(lead), [])

    def test_t4_u3_023_phase_lue_sur_la_plaque_ou_l_electricite_au_forage(self):
        # Pompe conservée (plaque 7,5 kW, 380 V, triphasée), « Raccordement »
        # vide : la phase déclarée ailleurs suffit, au devis comme au moteur.
        from apps.ventes.domain.taille import phase_et_isolement_du_lead
        phase = 'Phase du site (monophasé ou triphasé)'

        def lead(**kw):
            return self._lead(raccordement=kw.pop('raccordement', None), pompe_hmt_m=Decimal('60'),
                              pompe_debit_m3h=Decimal('20'), **kw)
        plaque = dict(mode_pompe='existante', pompe_actuelle_kw=Decimal('7.5'),
                      pompe_actuelle_tension_v=380, pompe_actuelle_phases='tri')
        self.assertEqual(champs_manquants(lead(**plaque)), [])
        self.assertEqual(phase_et_isolement_du_lead(lead(**plaque)), ('triphase', False))
        self.assertEqual(champs_manquants(lead(electricite_sur_place='triphase')), [])
        self.assertEqual(champs_manquants(lead(electricite_sur_place='triphase', **plaque)), [])
        # Site isolé : la plaque donne la phase, l'isolement reste dit.
        self.assertEqual(phase_et_isolement_du_lead(lead(raccordement='aucun', **plaque)),
                         ('triphase', True))
        # Ambigu (plaque triphasée, électricité monophasée) ou rien de déclaré :
        # le seul champ « Raccordement » est demandé.
        self.assertEqual(champs_manquants(lead(electricite_sur_place='monophase', **plaque)), [phase])
        self.assertEqual(champs_manquants(lead(electricite_sur_place='aucune')), [phase])
        # La plaque d'une pompe NEUVE ne compte pas ; « Raccordement » déclaré prime.
        self.assertEqual(champs_manquants(lead(**dict(plaque, mode_pompe='neuve'))), [phase])
        self.assertEqual(phase_et_isolement_du_lead(lead(raccordement='monophase', **plaque))[0],
                         'monophase')

    def test_hmt_et_besoin_m3j_est_pret(self):
        # AGQ9 (D-AGQ-5, réaligné) — la HMT saisie fait le groupe ; le niveau
        # d'eau seul ne suffit plus.
        lead = self._lead(pompe_hmt_m=Decimal('60'),
                          besoin_eau_m3j=Decimal('135'))
        self.assertEqual(champs_manquants(lead), [])
        lead = self._lead(niveau_statique_m=Decimal('32'),
                          besoin_eau_m3j=Decimal('135'))
        self.assertEqual(champs_manquants(lead), [LIB_HMT])

    def test_hmt_et_debit_actuel_avec_heures_est_pret(self):
        lead = self._lead(pompe_hmt_m=Decimal('60'),
                          pompe_actuelle_debit_m3h=Decimal('10'),
                          pompage_heures_jour=Decimal('7'))
        self.assertEqual(champs_manquants(lead), [])

    def test_debit_actuel_sans_heures_n_est_pas_pret(self):
        lead = self._lead(pompe_hmt_m=Decimal('60'),
                          pompe_actuelle_debit_m3h=Decimal('10'))
        self.assertEqual(champs_manquants(lead), [LIB_DEBIT])

    def test_cv_seul_n_est_pas_pret_et_nomme_les_deux_groupes(self):
        # Le CV de la pompe ACTUELLE n'est dans aucun groupe : un lead qui ne
        # porte que lui reste « pas prêt », les deux groupes nommés.
        lead = self._lead()
        self.assertEqual(
            [e['champ'] for e in champs_manquants_detail(lead)],
            ['pompe_hmt_m', 'pompe_debit_m3h'])
        self.assertEqual(champs_manquants(lead), [LIB_HMT, LIB_DEBIT])
        for groupe in champs_requis(lead):
            self.assertNotIn('pompe_cv', groupe)
            self.assertNotIn('pompe_actuelle_cv', groupe)

    def test_visite_point_eau_requise_tant_que_niveau_ou_debit_manque(self):
        lead = self._lead()
        # AGQ22 — chaque motif porte aussi son champ (``motifs_detail``).
        niveau = {'champ': 'niveau_statique_m',
                  'libelle': "niveau d'eau du forage (visite)"}
        debit = {'champ': 'debit_forage_m3h',
                 'libelle': 'débit du forage (visite)'}
        self.assertEqual(visite_point_eau_avant_devis(lead), {
            'requise': True,
            'motifs': ["niveau d'eau du forage inconnu",
                       'débit du forage inconnu'],
            'motifs_detail': [niveau, debit]})
        lead.niveau_statique_m = Decimal('32')
        self.assertEqual(visite_point_eau_avant_devis(lead), {
            'requise': True, 'motifs': ['débit du forage inconnu'],
            'motifs_detail': [debit]})
        lead.debit_forage_m3h = Decimal('36')
        self.assertEqual(visite_point_eau_avant_devis(lead),
                         {'requise': False, 'motifs': [], 'motifs_detail': []})

    def test_visite_point_eau_vaut_none_hors_agricole(self):
        for mode in (None, '', 'residentiel', 'industriel', 'commercial'):
            lead = Lead(nom='x', type_installation=mode)
            self.assertIsNone(visite_point_eau_avant_devis(lead), mode)

    def test_non_regression_residentiel_et_pro(self):
        self.assertEqual(champs_requis(Lead(nom='x')),
                         [['facture_hiver', 'conso_mensuelle_kwh'], ['ville', 'gps_lat']])
        self.assertEqual(
            champs_requis(Lead(nom='x', ete_differente=True)),
            [['facture_hiver', 'conso_mensuelle_kwh'], ['facture_ete'], ['ville', 'gps_lat']])
        for mode in ('industriel', 'commercial'):
            # CIQ404 — groupe pro du contrat CIQ1 ; ALEA47 — + le rythme que
            # le moteur exige (ici tout manque) ; ADEV125/ADEV126 — le contrat et
            # la phase absents sont supposés par le moteur, jamais exigés.
            # Fondateur 24/11/2026 — + la puissance maximale (conso estimée).
            self.assertEqual(champs_requis(Lead(nom='x', type_installation=mode)),
                             [['conso_mensuelle_kwh', 'bill_kwh',
                               'releve_conso', 'facture_hiver',
                               'puissance_max_appelee_kva'],
                              ['jours_ouverture'],
                              ['heure_debut', 'regime_equipes']])

    def test_sortie_reelle_egale_l_exemple_agricole_du_contrat(self):
        attendu = CONTRAT_DEVIS_AUTO['exemple_agricole']['devis_auto']
        lead = self._lead()
        detail = champs_manquants_detail(lead)
        manquants = [e['label'] for e in detail]
        self.assertEqual({
            'pret': not manquants,
            'manquants': manquants,
            'manquants_detail': detail,
            'requis': champs_requis(lead),
            'visite_point_eau_avant_devis': visite_point_eau_avant_devis(lead),
            # AGQ39 (D-AGQ-10) — le mode de pompe servi avec son drapeau.
            'mode_pompe': mode_pompe_du_lead(lead),
        }, attendu)


def make_company(slug='devisauto-co', nom='DevisAuto Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestChampsManquants(TestCase):
    """Règle métier pure, par mode (type_installation)."""

    def setUp(self):
        self.company = make_company()

    def _lead(self, **kwargs):
        # ADEV89 — la phase du site est un prérequis C&I ; ces cas testent la
        # consommation, le contrat et le rythme : la phase est déclarée.
        if kwargs.get('type_installation') in ('commercial', 'industriel', 'agricole'):
            kwargs.setdefault('raccordement', 'triphase')
        else:  # ALEA67 — un chantier résidentiel situé (ville reconnue)
            kwargs.setdefault('ville', 'Casablanca')
        return Lead(company=self.company, nom='Gate', **kwargs)

    def test_agv5_visite_point_eau_validee_leve_la_garde(self):
        from apps.visites.models import VisiteTerrain

        lead = Lead.objects.create(
            company=self.company, nom='Fellah AGV5',
            type_installation='agricole')
        self.assertTrue(visite_point_eau_avant_devis(lead)['requise'])
        VisiteTerrain.objects.create(
            company=self.company, lead=lead, gabarit='point_eau',
            statut=VisiteTerrain.Statut.TERMINEE, mesures={})
        # Terminée mais pas validée (sans mesure) : la garde tient.
        self.assertTrue(visite_point_eau_avant_devis(lead)['requise'])
        VisiteTerrain.objects.create(
            company=self.company, lead=lead, gabarit='point_eau',
            statut=VisiteTerrain.Statut.VALIDEE,
            mesures={'point_eau': {'niveau_non_mesurable': True,
                                   'debit_non_mesurable': True}})
        self.assertEqual(visite_point_eau_avant_devis(lead),
                         {'requise': False, 'motifs': [], 'motifs_detail': []})

    def test_type_none_defaults_to_residentiel(self):
        self.assertEqual(champs_manquants(self._lead()), ['facture hiver'])
        self.assertEqual(champs_manquants(self._lead(type_installation='')),
                         ['facture hiver'])

    def test_residentiel_winter_only_when_toggle_off(self):
        lead = self._lead(type_installation='residentiel',
                          facture_hiver=650, ete_differente=False)
        # Été non différent : la facture hiver couvre toute l'année.
        self.assertEqual(champs_manquants(lead), [])

    def test_residentiel_summer_required_when_toggle_on(self):
        lead = self._lead(type_installation='residentiel',
                          facture_hiver=650, ete_differente=True)
        self.assertEqual(champs_manquants(lead), ['facture été'])
        lead.facture_ete = 900
        self.assertEqual(champs_manquants(lead), [])

    def test_residentiel_both_missing(self):
        lead = self._lead(type_installation='residentiel', ete_differente=True)
        self.assertEqual(champs_manquants(lead),
                         ['facture hiver', 'facture été'])

    def test_industriel_and_commercial_need_conso(self):
        # ALEA47 — kWh seul ≠ prêt : contrat + rythme exigés aussi.
        for mode in ('industriel', 'commercial'):
            lead = self._lead(type_installation=mode,
                              contrat_electricite='bt_patente',
                              regime_equipes='3x8',
                              jours_ouverture=[1, 2, 3, 4, 5, 6, 7])
            self.assertEqual(champs_manquants(lead),
                             [LIB_PRO[mode]], mode)
            lead.conso_mensuelle_kwh = 1234.5
            self.assertEqual(champs_manquants(lead), [], mode)
            # ADEV125 (D-ACAL-92) — contrat absent : BT supposé, toujours prêt.
            lead.contrat_electricite = None
            self.assertEqual(champs_manquants(lead), [], mode)

    def test_agricole_needs_the_two_hydraulic_groups(self):
        lead = self._lead(type_installation='agricole')
        self.assertEqual(champs_manquants(lead), [LIB_HMT, LIB_DEBIT])
        lead.pompe_hmt_m = 80
        self.assertEqual(champs_manquants(lead), [LIB_DEBIT])
        lead.pompe_debit_m3h = 12
        self.assertEqual(champs_manquants(lead), [])

    def test_alea67_pret_seulement_si_le_moteur_sait_situer_le_chantier(self):
        # ALEA67 — 29 leads « prêts » que le moteur refusait (localisation_inconnue).
        from apps.parametres.pvgis_profils import productible_mensuel

        inconnue = self._lead(type_installation='residentiel', facture_hiver=650, ville='Xyzzyville')
        self.assertIsNone(productible_mensuel(ville='Xyzzyville'))
        self.assertEqual(champs_manquants(inconnue), ['ville'])
        self.assertEqual(message_manquants(champs_manquants(inconnue)), 'Manque : ville')
        inconnue.gps_lat, inconnue.gps_lng = Decimal('33.57'), Decimal('-7.59')
        self.assertEqual(champs_manquants(inconnue), [])
        inconnue.gps_lng = None  # une seule coordonnée ne situe rien
        self.assertEqual(champs_manquants(inconnue), ['ville'])
        self.assertEqual(champs_manquants(self._lead(facture_hiver=650)), [])  # Casablanca reconnue

    def test_alea67_agricole_exige_la_phase_comme_le_moteur(self):
        for raccordement in (None, 'inconnu', 'aucun'):
            lead = self._lead(type_installation='agricole', pompe_hmt_m=80, pompe_debit_m3h=12,
                              raccordement=raccordement)
            self.assertEqual(champs_manquants(lead), ['Phase du site (monophasé ou triphasé)'], raccordement)
        self.assertEqual(champs_manquants(self._lead(type_installation='agricole', pompe_hmt_m=80,
                                                     pompe_debit_m3h=12, raccordement='monophase')), [])

    def test_message_format(self):
        self.assertEqual(message_manquants(['HMT', 'débit souhaité']),
                         'Manque : HMT, débit souhaité')


class TestDevisAutoSerializerField(TestCase):
    """Le champ lecture seule `devis_auto` est exposé sur l'API leads."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_ser', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)

    def test_field_in_list_payload(self):
        Lead.objects.create(company=self.company, nom='PasPrêt', ville='Casablanca')
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if 'results' in resp.data else resp.data
        row = [r for r in data if r['nom'] == 'PasPrêt'][0]
        self.assertIn('devis_auto', row)
        self.assertFalse(row['devis_auto']['pret'])
        self.assertEqual(row['devis_auto']['manquants'], ['facture hiver'])
        self.assertEqual(row['devis_auto']['message'],
                         'Manque : facture hiver')

    def test_field_when_ready(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prêt', facture_hiver=700, ville='Casablanca')
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['devis_auto']['pret'])
        self.assertEqual(resp.data['devis_auto']['manquants'], [])
        self.assertIsNone(resp.data['devis_auto']['message'])

    def test_alea67_ville_redevenue_reconnue_lead_de_nouveau_pret(self):
        # ALEA67 (rejeu T3-VAGUEC2, point 13) — la fiche nomme « ville » tant que
        # le moteur ne situe pas le chantier, puis le lead redevient prêt.
        lead = Lead.objects.create(company=self.company, nom='Situé ?', facture_hiver=700,
                                   ville='Xyzzyville')
        url = f'/api/django/crm/leads/{lead.id}/'
        bloc = self.api.get(url).data['devis_auto']
        self.assertEqual((bloc['pret'], bloc['message']), (False, 'Manque : ville'))
        self.assertEqual(bloc['manquants_detail'], [{'champ': 'ville', 'label': 'ville'}])
        resp = self.api.patch(url, {'ville': 'Casablanca'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        bloc = self.api.get(url).data['devis_auto']
        self.assertEqual((bloc['pret'], bloc['manquants'], bloc['message']), (True, [], None))


class TestCatalogueCiAlea50(TestCase):
    """ALEA50 (D-ACI-5=a / D-ACI-6=a) — « prêt » inclut le CATALOGUE : le bloc
    ``devis_auto.catalogue_ci`` = {pret, manquants} des postes fixes C&I sans
    prix (forfaits société, puis la liste du MOTEUR — ADEV157 : câbles DC / AC,
    coffrets, protection AC, structure, comptage, protections DC présentes)."""

    #: ADEV157 — les 7 postes fixes que le moteur compose toujours.
    POSTES = ('cable_dc', 'coffret_dc', 'coffret_ac', 'protection_ac',
              'cable_ac', 'structure_ci', 'compteur_injection')

    FORFAITS = ('etudes_ingenierie', 'pose_structure', 'pose_modules',
                'raccordement_ac', 'mise_en_service', 'dossier_raccordement',
                'levage_acces', 'transport_ci')

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.company = make_company(slug='alea50-co', nom='ALEA50 Co')
        self.user = User.objects.create_user(
            username='alea50_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)

    def _equiper(self, forfaits=None, roles=None):
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Produit
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'forfaits_ci': {
                cle: {'fixe_ht': '500', 'source': 'grille de test'}
                for cle in (self.FORFAITS if forfaits is None else forfaits)}})
        for role in (self.POSTES if roles is None else roles):
            Produit.objects.create(
                company=self.company, nom='Poste %s' % role, role_ci=role,
                prix_vente=Decimal('900'), prix_achat=Decimal('400'))

    def _articles_prestations(self, roles=None):
        from apps.stock.models import Produit
        for cle in self.FORFAITS if roles is None else roles:
            Produit.objects.create(
                company=self.company, nom='Prestation %s' % cle, role_ci=cle,
                prix_vente=Decimal('500'))

    def _bloc(self, **kw):
        lead = Lead.objects.create(company=self.company, nom='Usine',
                                   **{'type_installation': 'commercial', **kw})
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['devis_auto']['catalogue_ci']

    def test_liste_et_patch_servent_le_catalogue(self):
        """ALEA63 — liste et réponse du PATCH servent ``catalogue_ci`` (pas
        seulement le détail), pour que kanban, liste et autosave bloquent."""
        lead = Lead.objects.create(company=self.company, nom='Usine',
                                   type_installation='commercial')
        liste = self.api.get('/api/django/crm/leads/')
        self.assertEqual(liste.status_code, 200, liste.data)
        rows = (liste.data['results'] if isinstance(liste.data, dict)
                else liste.data)
        ligne = next(r for r in rows if r['id'] == lead.id)
        self.assertFalse(ligne['devis_auto']['catalogue_ci']['pret'])
        self.assertEqual(
            len(ligne['devis_auto']['catalogue_ci']['manquants']), 8 + 7)
        maj = self.api.patch(f'/api/django/crm/leads/{lead.id}/',
                             {'prenom': 'Karim'}, format='json')
        self.assertEqual(maj.status_code, 200, maj.data)
        self.assertFalse(maj.data['devis_auto']['catalogue_ci']['pret'])

    def test_catalogue_vide_nomme_les_postes_sans_prix(self):
        bloc = self._bloc()
        self.assertFalse(bloc['pret'])
        self.assertEqual(len(bloc['manquants']), 8 + 7)
        self.assertIn('Forfait « Pose des modules » (Paramètres › Devis › '
                      'Prestations C&I)', bloc['manquants'])
        self.assertIn('Coffret DC C&I (fiche produit)', bloc['manquants'])
        # ADEV157 — la désignation du moteur (« Comptage / limitation… »).
        self.assertIn("Comptage / limitation d'injection (fiche produit)",
                      bloc['manquants'])

    def test_prestation_sans_article_pas_pret(self):
        # ALEA56 : 8 forfaits réglés + 7 postes, mais aucun article de
        # prestation => le moteur refuserait (CORC6) ; « prêt » aussi.
        self._equiper()
        bloc = self._bloc(type_installation='industriel')
        self.assertFalse(bloc['pret'])
        self.assertEqual(len(bloc['manquants']), 8)
        self.assertIn('Article « Transport C&I » (fiche produit)',
                      bloc['manquants'])
        self._articles_prestations()
        self.assertEqual(self._bloc(), {'pret': True, 'manquants': []})

    def test_catalogue_complet_est_pret(self):
        self._equiper()
        self._articles_prestations()
        bloc = self._bloc(type_installation='industriel')
        self.assertEqual(bloc, {'pret': True, 'manquants': []})

    def test_un_controleur_tarife_vaut_le_compteur(self):
        self._equiper(roles=self.POSTES[:-1] + ('controleur_injection',))
        self._articles_prestations()
        self.assertTrue(self._bloc()['pret'])

    def test_article_sans_prix_ou_archive_ne_compte_pas(self):
        from apps.stock.models import Produit
        self._equiper(roles=[r for r in self.POSTES if r != 'coffret_dc'])
        self._articles_prestations()
        Produit.objects.create(company=self.company, nom='Coffret DC sans prix',
                               role_ci='coffret_dc', prix_vente=Decimal('0'))
        Produit.objects.create(company=self.company, nom='Coffret DC archivé',
                               role_ci='coffret_dc', prix_vente=Decimal('800'),
                               is_archived=True)
        bloc = self._bloc()
        # ADEV157 — l'article RETENU sans prix est nommé, comme au refus.
        self.assertEqual(bloc['manquants'], ['Coffret DC sans prix (fiche produit)'])

    def test_forfait_incomplet_manque(self):
        self._equiper(forfaits=self.FORFAITS[:7])
        self._articles_prestations()
        bloc = self._bloc()
        self.assertEqual(bloc['manquants'], [
            'Forfait « Transport C&I » (Paramètres › Devis › Prestations C&I)'])

    def test_null_hors_ci(self):
        lead = Lead.objects.create(company=self.company, nom='Villa',
                                   facture_hiver=700)
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertIsNone(resp.data['devis_auto']['catalogue_ci'])

    def test_cache_5_min_par_societe(self):
        from unittest import mock
        from apps.ventes import selectors
        self._equiper()
        self._articles_prestations()
        with mock.patch.object(selectors, '_calculer_catalogue_ci_pret',
                               wraps=selectors._calculer_catalogue_ci_pret
                               ) as calcul:
            self.assertTrue(self._bloc()['pret'])
            self.assertTrue(self._bloc()['pret'])
            self.assertEqual(calcul.call_count, 1)
            # Une lecture (même un nouveau lead) n'invalide rien ; la société
            # voisine a sa propre entrée.
            autre = make_company(slug='alea50-autre', nom='Autre')
            self.assertFalse(selectors.catalogue_ci_pret(autre.id)['pret'])
            self.assertEqual(calcul.call_count, 2)

    def test_tarifer_les_postes_vide_le_cache(self):
        """CAD177 (nocturne e2e CIQ127) — l'administrateur règle les forfaits
        puis tarife les articles : le bloc suivant est PRÊT, sans attendre les
        5 min du cache (le bouton restait désactivé, « 11 postes sans prix »)."""
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Produit
        self.assertFalse(self._bloc()['pret'])
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'forfaits_ci': {
                cle: {'fixe_ht': '500', 'source': 'grille de test'}
                for cle in self.FORFAITS}})
        self.assertEqual(len(self._bloc()['manquants']), 7 + 8)
        self._articles_prestations()
        self.assertEqual(len(self._bloc()['manquants']), 7)
        for role in self.POSTES:
            produit = Produit.objects.create(
                company=self.company, nom='Poste %s' % role, role_ci=role,
                prix_vente=Decimal('0'))
            produit.prix_vente = Decimal('900')
            produit.save(update_fields=['prix_vente'])
        self.assertEqual(self._bloc(), {'pret': True, 'manquants': []})

    def test_les_cinq_postes_que_le_moteur_refuse_sont_dits_manquants(self):
        """ADEV157 (T3-VAGUED-008) — forfaits et articles fixes tarifés, mais
        câble solaire, câble AC, structure lestée, protection et parafoudre DC
        à prix 0 : la garde les nomme (désignations du refus du moteur), puis,
        une fois tarifés, le lead est prêt et le moteur ne les refuse plus."""
        from apps.stock.models import FicheTechnique, Produit
        from apps.stock.selectors import produits_ci
        from apps.ventes.moteur_ci.composition import composer_ci
        self._equiper(roles=('coffret_dc', 'coffret_ac', 'protection_ac', 'compteur_injection'))
        self._articles_prestations()
        cinq = []
        for nom, role, fiche in (
                ('Câble solaire 4 mm²', 'cable_dc', None),
                ('Câble AC 5 × 10 mm²', 'cable_ac', {'type_fiche': 'cable', 'cable_cote': 'ac',
                                                     'cable_section_mm2': 10.0}),
                ('Structure toit plat lestée C&I', 'structure_ci', {
                    'type_fiche': 'structure', 'struct_type_pose': 'toit_plat_leste'}),
                ('Protection DC C&I', 'protection_dc', {'type_fiche': 'protection', 'prot_cote': 'dc'}),
                ('Parafoudre DC C&I', 'protection_dc', {
                    'type_fiche': 'protection', 'prot_type': 'parafoudre', 'prot_cote': 'dc'})):
            cinq.append(Produit.objects.create(company=self.company, nom=nom, role_ci=role,
                                               prix_vente=Decimal('0')))
            if fiche:
                FicheTechnique.objects.create(company=self.company, produit=cinq[-1], **fiche)
        attendus = ['Câble solaire 4 mm²', 'Câble AC 5 × 10 mm²', 'Structure toit plat lestée C&I',
                    'Protection DC par chaîne', 'Parafoudre DC par chaîne']
        self.assertEqual(self._bloc(), {'pret': False, 'manquants': [
            '%s (fiche produit)' % nom for nom in attendus]})

        def refus_du_moteur():  # 1 onduleur triphasé de 20 kW, 10 m de câble AC : section plancher
            compo = composer_ci(30, produits_ci(self.company), onduleurs={'combinaison': [
                {'produit': None, 'nom': 'Onduleur 20 kW', 'quantite': 1, 'kw_ac': 20}], 'chaines': None},
                entrees={'module': {'pmax_wc': 500, 'prix_connu': True}, 'phase': 'tri'}, forfaits={})
            return set(compo['prix_a_renseigner'])
        self.assertTrue(set(attendus) <= refus_du_moteur(), refus_du_moteur())
        Produit.objects.filter(pk__in=[p.pk for p in cinq]).update(prix_vente=Decimal('300'))
        from django.core.cache import cache
        cache.clear()  # ``update()`` ne déclenche pas les receivers (le save d'un article, si)
        self.assertEqual(self._bloc(), {'pret': True, 'manquants': []})
        self.assertFalse(set(attendus) & refus_du_moteur())

    def test_forme_du_contrat(self):
        exemple = CONTRAT_DEVIS_AUTO['exemple_catalogue_ci']['devis_auto']
        bloc = self._bloc()
        self.assertEqual(set(bloc), set(exemple['catalogue_ci']))
        self.assertIsInstance(bloc['pret'], bool)
        self.assertIsInstance(bloc['manquants'], list)


class TestDevisAutoEndpoint(TestCase):
    """Garde serveur POST /crm/leads/<id>/devis-auto/ — sans effet de bord."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_ep', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        # Lead agricole : HMT + débit manquants (AGR403 — le CV de la pompe
        # actuelle ne compte plus).
        self.lead = Lead.objects.create(
            company=self.company, nom='Agriculteur',
            type_installation='agricole', raccordement='triphase')

    def _post(self, lead_id=None, api=None):
        api = api or self.api
        lead_id = lead_id or self.lead.id
        return api.post(f'/api/django/crm/leads/{lead_id}/devis-auto/')

    def test_kwh_contredit_les_factures(self):
        """ACVI97 — 5 000 kWh pour 300 MAD : plus « prêt », valeur gardée."""
        lead = Lead.objects.create(
            company=self.company, nom='Maison', type_installation='residentiel',
            ville='Rabat', type_surface='toiture', facture_hiver=Decimal('300'))
        url = f'/api/django/crm/leads/{lead.id}/'
        patch = self.api.patch(url, {'conso_mensuelle_kwh': 5000}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertIn('kwh_factures', patch.data['avertissements'])
        refus = self._post(lead.id)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertIn('incohérent', refus.data['detail'])
        # 250 kWh ≈ 372 MAD au barème, ratio 1,24 dans la bande [0,5 ; 2].
        temoin = self.api.patch(url, {'conso_mensuelle_kwh': 250}, format='json')
        self.assertNotIn('avertissements', temoin.data)
        self.assertEqual(self._post(lead.id).status_code, 200)

    def test_409_with_exact_french_message(self):
        resp = self._post()
        # ERR-ENF11-FUZZ-CRM : champs manquants = refus d'état, 409.
        self.assertEqual(resp.status_code, 409, resp.data)
        # EXACTEMENT les champs manquants, même message que le sérialiseur.
        self.assertEqual(resp.data['detail'], MSG_AGRICOLE)
        ser = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        self.assertEqual(ser['devis_auto']['message'], resp.data['detail'])

    def test_200_once_fields_filled(self):
        self.lead.pompe_hmt_m = 80
        self.lead.pompe_debit_m3h = 12
        self.lead.save()
        resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['ok'])
        self.assertEqual(resp.data['detail'],
                         'Lead prêt pour le devis automatique.')

    def test_no_side_effects(self):
        self._post()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), 0)

    def test_company_scoped_404(self):
        other = make_company(slug='devisauto-other', nom='Other')
        intruder = User.objects.create_user(
            username='devisauto_intruder', password='x',
            role_legacy='responsable', company=other)
        resp = self._post(api=make_api(intruder))
        self.assertEqual(resp.status_code, 404)

    def test_granular_role_user_allowed(self):
        # Rôle fin façon « Commerciale » : permissions CRM seulement.
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commerciale DevisAuto',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'],
        )
        commerciale = User.objects.create_user(
            username='devisauto_commerciale', password='x',
            role=role, company=self.company,
        )
        resp = self._post(api=make_api(commerciale))
        # Autorisée (la règle métier répond 409 « manquants », pas 403).
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['detail'], MSG_AGRICOLE)


class TestAvancerStagePourDevis(TestCase):
    """Mouvement automatique du funnel quand le statut d'un devis change.

    QJR541 — ``statut`` n'est plus écrivable au PATCH/POST : l'envoi passe par
    sa porte (``mark_devis_sent`` → événement ``devis_sent`` → récepteur crm),
    jamais par un corps brut. Un PATCH ``statut`` est IGNORÉ (200)."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_stage', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(company=self.company, nom='Funnel')

    def _create_devis(self, lead=None, extra=None):
        payload = {'taux_tva': '20.00', 'remise_globale': '0'}
        if lead is not None:
            payload['lead'] = lead.id
        payload.update(extra or {})
        resp = self.api.post('/api/django/ventes/devis/', payload,
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # La référence n'est pas exposée par le sérialiseur d'écriture.
        devis = Devis.objects.get(pk=resp.data['id'])
        return devis.id, devis.reference

    def _patch_statut(self, devis_id, statut):
        return self.api.patch(f'/api/django/ventes/devis/{devis_id}/',
                              {'statut': statut}, format='json')

    def _envoyer(self, devis_id):
        """La VRAIE porte d'envoi (lien / courriel / WhatsApp)."""
        from apps.ventes.services import mark_devis_sent
        mark_devis_sent(devis=Devis.objects.get(pk=devis_id), user=self.user)

    def _stage_acts(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind='modification', field='stage')

    def test_envoye_moves_new_to_quote_sent_and_logs(self):
        devis_id, ref = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        acts = self._stage_acts()
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Étape')
        self.assertEqual(act.old_value, stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(act.old_value, 'Nouveau')
        self.assertEqual(act.new_value, stages.STAGE_LABELS['QUOTE_SENT'])
        self.assertEqual(act.new_value, 'Devis envoyé')
        self.assertIn('auto — devis', act.body)
        self.assertIn(ref, act.body)
        self.assertIn('envoyé', act.body)
        self.assertEqual(act.user_id, self.user.id)
        self.assertEqual(act.company_id, self.company.id)

    def test_patch_statut_accepte_ignored_lead_not_advanced(self):
        """AUD505 / QJR541 — un PATCH brut vers « accepte » ne fait rien :
        seul POST /devis/<id>/accepter/ (accept_devis) fait avancer le statut
        ET le lead. Depuis QJR541 le champ est en lecture seule : 200, statut
        inchangé (plus un 400)."""
        devis_id, ref = self._create_devis(self.lead)
        self._envoyer(devis_id)
        resp = self._patch_statut(devis_id, 'accepte')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis = Devis.objects.get(pk=devis_id)
        self.assertEqual(devis.statut, 'envoye')
        self.lead.refresh_from_db()
        # Le lead reste où l'envoi l'a amené (QUOTE_SENT) — jamais SIGNED
        # via un PATCH brut.
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)  # seul l'envoi a loggé

    def test_create_with_statut_envoye_stays_brouillon_stage_unmoved(self):
        """QJR541 — un POST ``statut: envoye`` crée un BROUILLON ; le lead
        n'avance pas (aucun envoi réel)."""
        devis_id, _ = self._create_devis(self.lead, {'statut': 'envoye'})
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'brouillon')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(self._stage_acts().count(), 0)

    def test_patch_statut_envoye_is_ignored(self):
        devis_id, _ = self._create_devis(self.lead)
        resp = self._patch_statut(devis_id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'brouillon')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_same_statut_send_does_not_duplicate(self):
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self._envoyer(devis_id)  # idempotent
        self.assertEqual(self._stage_acts().count(), 1)

    def test_never_backwards_from_signed(self):
        self.lead.stage = 'SIGNED'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'SIGNED')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_never_backwards_from_follow_up(self):
        # FOLLOW_UP est APRÈS QUOTE_SENT dans le funnel — pas de recul.
        self.lead.stage = 'FOLLOW_UP'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'FOLLOW_UP')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_cold_lead_is_reactivated(self):
        # COLD = parking, pas « plus avancé » : un devis envoyé le réactive.
        self.lead.stage = 'COLD'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        acts = self._stage_acts()
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().old_value, stages.STAGE_LABELS['COLD'])

    def test_lost_lead_untouched(self):
        # Marqué Perdu via le DRAPEAU (sans motif) — le funnel l'ignore.
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        devis_id, _ = self._create_devis(self.lead)
        # AMSG35 — l'envoi même d'un devis de lead perdu est refusé (409).
        from core.conflit_etat import ConflitEtat
        with self.assertRaises(ConflitEtat):
            self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(self._stage_acts().count(), 0)

    def test_stale_motif_but_not_perdu_still_advances(self):
        # Texte de motif résiduel mais perdu=False : ce n'est PAS perdu, le
        # funnel doit avancer normalement (le texte seul ne signale plus rien).
        self.lead.motif_perte = 'Trop cher'
        self.lead.perdu = False
        self.lead.save(update_fields=['motif_perte', 'perdu'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)

    def test_devis_without_lead_no_crash(self):
        from apps.crm.models import Client
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@devisauto.com')
        devis_id, _ = self._create_devis(extra={'client': client.id})
        self._envoyer(devis_id)
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'envoye')
        self.assertEqual(LeadActivity.objects.count(), 0)
