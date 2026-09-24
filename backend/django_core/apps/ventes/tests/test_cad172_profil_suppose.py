"""CAD172 — occupation non posée : présence SUPPOSÉE, et la proposition le dit.

Décision fondateur du 21/09/2026 (Q5) : quand ``occupation_jour`` n'a pas été
posée, on garde le défaut (présence en journée en résidentiel) ET la
proposition porte le bandeau « Profil supposé, à confirmer ». Le bandeau
disparaît dès la réponse, et c'est LE MÊME drapeau qui fait remonter la
question en tête du panneau d'appel.

Done de la tâche, tenu ici côté serveur : une étude sans ``occupation_jour``
porte le drapeau « profil supposé » et la proposition (le bloc
``courbes_journalieres`` de sa charge utile) porte le bandeau ; avec la
réponse, ni l'un ni l'autre. La moitié écran vit dans
``PanneauScriptAppel.test.jsx``.

Aucune base : même patron que ``test_courbes_journalieres`` (lecteurs CRM
simulés, table PVGIS de référence, aucun réseau).
"""
from unittest import mock

from django.core.cache import cache as django_cache
from django.test import SimpleTestCase

from apps.crm import panneau_appel
from apps.crm.models import Lead
from apps.ventes import courbes_journalieres as cj
from apps.ventes import etude_horaire as EH

CASA_CONSO = [900, 880, 860, 840, 900, 1100,
              1300, 1350, 1100, 900, 870, 910]


def _data(**extra):
    base = {'puissance_kwc': 10.0, 'client_city': 'Casablanca',
            'mode_installation': 'residentiel', 'sans_ok': True,
            'avec_ok': True, 'deux_options': True,
            'batterie_kwh_total': 10.0}
    base.update(extra)
    return base


class LeDrapeauEstUnDefautNonUneReponse(SimpleTestCase):
    def test_les_deux_defauts_sont_supposes(self):
        self.assertTrue(cj.profil_suppose(cj.DEFAUT_RESIDENTIEL[1]))
        self.assertTrue(cj.profil_suppose(cj.SOURCE_DEFAUT_NON_RESIDENTIEL))

    def test_une_reponse_un_profil_pro_ou_une_variante_ne_le_sont_pas(self):
        for source in ('lead_occupation_jour:present',
                       'lead_occupation_jour:absent',
                       'lead_profil_activite:day',
                       'variante_demandee:absence_jour'):
            self.assertFalse(cj.profil_suppose(source), source)

    def test_sur_un_lead_seul_meme_traducteur(self):
        self.assertTrue(cj.profil_suppose_du_lead(Lead(nom='P')))
        self.assertFalse(cj.profil_suppose_du_lead(
            Lead(nom='P', occupation_jour='present')))

    def test_le_bandeau_est_la_decision_mot_pour_mot(self):
        self.assertEqual(cj.BANDEAU_PROFIL_SUPPOSE,
                         'Profil supposé, à confirmer')


class LaPropositionPorteLeBandeau(SimpleTestCase):
    """Le bloc ``courbes_journalieres`` servi à la proposition."""

    def setUp(self):
        django_cache.clear()
        for cible, valeur in (
                ('apps.crm.selectors.site_location_for_devis',
                 {'site_adresse': None, 'site_ville': None,
                  'gps_lat': None, 'gps_lng': None}),
                ('apps.crm.selectors.profil_activite_pour_devis', None)):
            patch = mock.patch(cible, return_value=valeur)
            patch.start()
            self.addCleanup(patch.stop)

    def _bloc(self, occupation_jour=None, data=None):
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value=occupation_jour):
            return cj.construire_courbes_journalieres(
                object(), data or _data(), monthly_consumption=CASA_CONSO)

    def test_sans_occupation_jour_le_drapeau_et_le_bandeau_sont_servis(self):
        bloc = self._bloc()
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertIs(bloc['profil_suppose'], True)
        self.assertEqual(bloc['bandeau_profil'], 'Profil supposé, à confirmer')

    def test_avec_la_reponse_ni_drapeau_ni_bandeau(self):
        for reponse in ('present', 'absent', 'partiel'):
            bloc = self._bloc(occupation_jour=reponse)
            self.assertNotIn('profil_suppose', bloc, reponse)
            self.assertNotIn('bandeau_profil', bloc, reponse)

    def test_pro_sans_profil_d_activite_est_aussi_un_profil_suppose(self):
        bloc = self._bloc(data=_data(mode_installation='industriel'))
        self.assertEqual(bloc['occupation_source'],
                         cj.SOURCE_DEFAUT_NON_RESIDENTIEL)
        self.assertIs(bloc['profil_suppose'], True)


class LEtudeDuDevisPorteLeDrapeau(SimpleTestCase):
    """``etude_horaire_pour_devis`` : lecteurs et moteur simulés (même patron
    que CAD168) — on ne vérifie que le drapeau posé à côté de l'étude."""

    def _etude(self, occupation_source):
        patches = [
            mock.patch('apps.crm.selectors.lead_bills_for_devis',
                       return_value={'facture_hiver': 600.0}),
            mock.patch('apps.crm.selectors.site_location_for_devis',
                       return_value={'site_ville': 'Casablanca'}),
            mock.patch('apps.crm.selectors.conso_mensuelle_kwh_pour_devis',
                       return_value=None),
            mock.patch.object(EH, '_reglages_tarifaires',
                              return_value=(None, None)),
            mock.patch.object(EH, 'profil_depuis_factures',
                              return_value=([300.0] * 12, 'factures', {})),
            mock.patch.object(EH, 'occupation_du_devis',
                              return_value=('presence_jour',
                                            occupation_source)),
            mock.patch.object(EH, 'equipements_du_devis', return_value={}),
            mock.patch.object(EH, 'capacite_batterie_du_devis',
                              return_value=None),
            mock.patch.object(EH, 'puissance_batterie_du_devis',
                              return_value={'packs_decharge_kw': None,
                                            'ond_decharge_kw': None,
                                            'charge_kw': None}),
            mock.patch.object(EH, 'rendement_batterie_du_devis',
                              return_value={'rendement': None,
                                            'source': None}),
            mock.patch.object(EH, 'calculer_etude_horaire',
                              return_value={'annuel': {}}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        devis = mock.Mock(company=None, etude_params={},
                          mode_installation='residentiel')
        return EH.etude_horaire_pour_devis(devis, kwc=5.0, data={})

    def test_une_etude_sans_occupation_jour_porte_le_drapeau(self):
        etude = self._etude(cj.DEFAUT_RESIDENTIEL[1])
        self.assertIs(etude['profil_suppose'], True)
        self.assertEqual(etude['bandeau_profil'], cj.BANDEAU_PROFIL_SUPPOSE)

    def test_avec_la_reponse_l_etude_ne_le_porte_pas(self):
        etude = self._etude('lead_occupation_jour:present')
        self.assertNotIn('profil_suppose', etude)
        self.assertNotIn('bandeau_profil', etude)


class LePanneauDAppelLitLeMemeDrapeau(SimpleTestCase):
    def test_vierge_vrai_repondu_faux(self):
        self.assertIs(panneau_appel.profil_suppose_servi(Lead(nom='P')), True)
        self.assertIs(panneau_appel.profil_suppose_servi(
            Lead(nom='P', occupation_jour='absent')), False)
