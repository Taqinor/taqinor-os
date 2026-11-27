"""ACAL992 / ADEV153 — la porte unique ``chiffrer_conception`` (contrat
``contract_samples/chiffrage_conception.json``, ACAL991).

ADEV153 : le chiffrage de l'atelier est une LECTURE de la conception rangée
(``ConceptionLead``) — aucun noyau (``calculer_etude_horaire``, ``etudier_ci``,
rendu du devis) n'est appelé ; la forme des clés ne change pas. Sans conception
rangée, UNE relance part en file (``conception_ou_calcul``). SimpleTestCase : la
version rangée est une doublure à la forme du contrat ``conception_lead.json`` ;
les noyaux sont surveillés (compteur à 0).
"""
import json
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import services
from apps.ventes.domain import chiffrage_conception as cc

CONTRAT = json.loads((Path(__file__).resolve().parents[1] / 'contract_samples'
                      / 'chiffrage_conception.json').read_text(encoding='utf-8'))
SOCIETE = N(id=7, pk=7)
LAYOUT = {'result': {'kwc': 5.0, 'panels': 10}}
FACTURES = {'facture_hiver': {'valeur': 900, 'source': 'lead'}}


def _v(valeur, unite=None, source='moteur'):
    return {'valeur': valeur, 'unite': unite, 'source': source}


def _conception(*, marche='residentiel', etat='complet', option='sans', sur_la_pose=True, entrees=None,
                nb=35, kwc=19.25, production=6047.0, economie=5100.0, autoconso=0.62, couverture=0.55):
    table = {'nb_panneaux': _v(nb, 'panneaux'), 'puissance_kwc': _v(kwc, 'kWc'),
             'production_annuelle': _v(production, 'kWh/an', 'pose' if sur_la_pose else 'moteur'),
             'autoconsommation': _v(autoconso, 'ratio'), 'couverture': _v(couverture, 'ratio'),
             'economies_annuelles': _v(economie, 'MAD/an')}
    return {'etat': etat, 'refus': None, 'marche': marche, 'option_retenue': option,
            'valeurs': {option: table}, 'niveau_regles': 15, 'version': 3, 'lead': 3,
            'entrees_utilisees': FACTURES if entrees is None else entrees}


def _calepinage(lead_id=3, devis_id=None):
    return N(pk=1, devis=None, devis_id=devis_id, lead_id=lead_id, roof_layout=LAYOUT)


class ChiffrerConceptionTest(SimpleTestCase):
    def _chiffrer(self, conception, *, en_cours=False, calepinage=None):
        """Chiffre contre la conception rangée ``conception`` ; rend ``(bloc, noyaux)`` où
        ``noyaux`` = les trois noyaux surveillés (aucun ne doit être appelé)."""
        with ExitStack() as pile:
            lecture = pile.enter_context(mock.patch(
                'apps.ventes.conception.service.conception_ou_calcul', return_value=(conception, en_cours)))
            noyaux = [pile.enter_context(mock.patch(cible)) for cible in (
                'apps.ventes.etude_horaire.calculer_etude_horaire', 'apps.ventes.domain.etude_ci.etudier_ci',
                'apps.ventes.quote_engine.builder.build_quote_data')]
            pile.enter_context(mock.patch('apps.crm.selectors.get_company_lead',
                                          return_value=N(type_installation=None)))
            bloc = services.chiffrer_conception(calepinage=calepinage or _calepinage(), company=SOCIETE)
        self.last_lecture = lecture
        return bloc, noyaux

    def test_chiffrage_egale_la_conception_rangee_sans_aucun_noyau(self):
        """ADEV153 — 35 panneaux, 6 047 kWh/an rangés : le chiffrage les rend, aucun noyau n'est
        appelé ; mutant : rappeler ``etudier_ci`` / le moteur horaire ⇒ un compteur monte."""
        bloc, noyaux = self._chiffrer(_conception())
        self.assertEqual([n.call_count for n in noyaux], [0, 0, 0])
        self.assertEqual(set(bloc), set(CONTRAT['exemple']))
        self.assertEqual(bloc['production_annuelle_kwh'],
                         {'valeur': 6047.0, 'unite': 'kWh/an', 'source': cc.SOURCE_POSE, 'etat': 'servi'})
        self.assertEqual(bloc['kwc']['valeur'], 19.25)
        economie = bloc['economie_annee1_mad']
        self.assertEqual((economie['valeur'], economie['option'], economie['etat']), (5100.0, 'sans_batterie', 'servi'))
        self.assertEqual(bloc['autoconsommation_pct']['valeur'], 62.0)
        # ACAL2022/2023 — la part production ÷ consommation de la conception est SERVIE (une seule, pour tous)
        self.assertEqual(bloc['couverture_pct'],
                         {'valeur': 55.0, 'unite': '%', 'source': 'conception', 'etat': 'servi'})
        self.assertEqual((bloc['marche'], bloc['regles_calcul'], bloc['omissions']), ('residentiel', 15, []))
        self.last_lecture.assert_called_once_with(SOCIETE, 3)

    def test_deux_appels_rendent_la_meme_reponse(self):
        un, _ = self._chiffrer(_conception())
        deux, _ = self._chiffrer(_conception())
        self.assertEqual(un, deux)

    def test_option_avec_batterie_et_production_de_la_ville(self):
        bloc, _ = self._chiffrer(_conception(option='avec', sur_la_pose=False))
        self.assertEqual(bloc['economie_annee1_mad']['option'], 'avec_batterie')
        self.assertEqual(bloc['production_annuelle_kwh']['source'], cc.SOURCE_VILLE)

    def test_adev155_production_du_plan_par_defaut_jamais_dite_de_la_ville(self):
        """ADEV155 (niveau 15) — la conception rangée d'un lead sans toit tracé reste servie quand
        un calepinage SANS pose est ouvert (empreinte inchangée : ``calepinage_du_lead`` ne pose
        de toit qu'avec un ``layout_hash``) ; sa production vient du plan par défaut : le chiffrage
        le dit, jamais « standard_ville ». Mutant « pose sinon ville » : rouge."""
        conception = _conception(sur_la_pose=False)
        conception['valeurs']['sans']['production_annuelle']['source'] = 'plan_par_defaut'
        bloc, _ = self._chiffrer(conception)
        self.assertEqual(bloc['production_annuelle_kwh']['source'], cc.SOURCE_PLAN_PAR_DEFAUT)
        self.assertEqual(cc.SOURCE_PLAN_PAR_DEFAUT, 'plan_par_defaut')

    def test_sans_conception_une_relance_part_une_fois(self):
        """ADEV153 — sans version rangée, ``conception_ou_calcul`` met UNE relance en file
        (jamais un calcul dans la requête) ; le bloc dit « premier calcul en cours », jamais un zéro."""
        with ExitStack() as pile:
            pile.enter_context(mock.patch('apps.ventes.selectors_conception.conception_courante', return_value=None))
            file = pile.enter_context(mock.patch('apps.ventes.conception.receivers.mettre_en_file',
                                                 return_value='lancee'))
            noyaux = [pile.enter_context(mock.patch(cible)) for cible in (
                'apps.ventes.etude_horaire.calculer_etude_horaire', 'apps.ventes.domain.etude_ci.etudier_ci')]
            pile.enter_context(mock.patch('apps.crm.selectors.get_company_lead',
                                          return_value=N(type_installation=None)))
            bloc = services.chiffrer_conception(calepinage=_calepinage(), company=SOCIETE)
        file.assert_called_once()
        self.assertEqual(file.call_args.kwargs['origine'], 'remplissage')
        self.assertEqual([n.call_count for n in noyaux], [0, 0])
        self.assertEqual({bloc[c]['etat'] for c in cc.UNITES}, {'omis'})
        self.assertEqual({bloc[c]['valeur'] for c in cc.UNITES}, {None})
        self.assertEqual({o['motif'] for o in bloc['omissions']}, {cc.MOTIF_EN_COURS})
        self.assertEqual(set(bloc), set(CONTRAT['exemple']))

    def test_sans_facture_economie_omise(self):
        """D-ACAL-40 : une conception bâtie sans consommation connue sert la production, jamais
        une économie ni une autoconsommation de profil supposé."""
        bloc, _ = self._chiffrer(_conception(entrees={'ville': {'valeur': 'Rabat', 'source': 'lead'}}))
        self.assertEqual(set(bloc), set(CONTRAT['exemple_sans_facture']))
        self.assertEqual(bloc['production_annuelle_kwh']['etat'], 'servi')
        self.assertEqual(bloc['economie_annee1_mad'], CONTRAT['exemple_sans_facture']['economie_annee1_mad'])
        self.assertEqual(bloc['omissions'], CONTRAT['exemple_sans_facture']['omissions'])

    def test_refus_non_servi_agricole_et_sans_lead(self):
        refusee = dict(_conception(), etat='refus',
                       refus={'code': 'localisation_inconnue', 'message': 'Ville inconnue'})
        bloc, _ = self._chiffrer(refusee)
        self.assertEqual({bloc[c]['etat'] for c in cc.UNITES}, {'indisponible'})
        self.assertEqual(bloc['omissions'][0]['motif'], 'Ville inconnue')
        agricole, _ = self._chiffrer(_conception(marche='agricole'))
        attendu = dict(CONTRAT['exemple_agricole'], regles_calcul=agricole['regles_calcul'])
        self.assertEqual(agricole, attendu)
        sans, noyaux = self._chiffrer(None, calepinage=_calepinage(lead_id=None))
        self.assertEqual({sans[c]['etat'] for c in cc.UNITES}, {'non_servi'})
        self.assertEqual(sans['omissions'][0]['motif'], cc.MOTIF_SANS_LEAD)

    def test_acal1239_sans_devis_puis_avec_devis_meme_economie(self):
        """ACAL1239 — 8 panneaux, un bloc horaire : l'économie année 1 de l'atelier (conception rangée,
        ``conception/valeurs._bilan``), sans puis avec devis lié, égale celle du PDF
        (``pricing.calculate_savings_roi`` sur le MÊME bloc) à l'arrondi près du PDF."""
        from apps.ventes.conception.valeurs import _bilan
        from apps.ventes.quote_engine.pricing import calculate_savings_roi

        mois = [{'production_kwh': 400.0, 'economie_sans_mad': 425.37, 'economie_avec_mad': 470.12}] * 12
        bloc = {'kwc': 5.68, 'mois': mois, 'annuel': {
            'production_kwh': 4800.0, 'consommation_kwh': 5200.0, 'economie_sans_mad': 5104.44,
            'economie_avec_mad': 5641.44, 'taux_autoconso_sans': 0.61, 'taux_autoconso_avec': 0.74}}
        economie = _bilan(N(marche='residentiel', etude_params={'etude_horaire': bloc}), 'sans')[4]
        atelier = [self._chiffrer(_conception(nb=8, kwc=5.68, economie=economie), calepinage=_calepinage(
            devis_id=devis))[0]['economie_annee1_mad']['valeur'] for devis in (None, 42)]
        pdf = calculate_savings_roi(5.68, 60000.0, 80000.0, etude_horaire=bloc)['eco_s_ann']
        self.assertEqual([round(a) for a in atelier], [pdf, pdf])

    def test_une_lecture_en_echec_est_indisponible_jamais_une_exception(self):
        with mock.patch('apps.ventes.conception.service.conception_ou_calcul', side_effect=RuntimeError('panne')), \
                mock.patch('apps.crm.selectors.get_company_lead', return_value=N(type_installation=None)):
            echec = services.chiffrer_conception(calepinage=_calepinage(), company=SOCIETE)
        self.assertEqual({echec[c]['etat'] for c in cc.UNITES}, {'indisponible'})
        self.assertEqual(echec['omissions'][0]['motif'], cc.MOTIF_ECHEC)
