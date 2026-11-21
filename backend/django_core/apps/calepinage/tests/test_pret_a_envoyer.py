"""ACAL857 — les contrôles de PORTE du « prêt à envoyer ? ».

Ce qui est prouvé ici (sans base : la VRAIE porte
``services/feu_vert.py::verifier_avant_publication`` est appelée, seules ses
lectures de base — option société, feu vert de la visite, approbation — sont
remplacées) :

* sans feu vert ⇒ ``visite_validee`` bloquant avec le message de la porte et
  ``approbation_a_jour`` « non évaluée » (jamais ``ok``) ;
* feu vert, approbation exigée et absente ⇒ ``approbation_a_jour`` bloquant ;
* options éteintes ⇒ ``ok`` « non exigé par votre société » ;
* ni lead ni devis ⇒ ``info`` ;
* simulation périmée ou jamais lancée ⇒ ``simulation_fraiche`` à régler ;
* devis lié : conception périmée à régler, kWh déclaré contredit bloquant ;
* chaque contrôle a la forme du contrat ``calepinage_pret_a_envoyer.json`` et
  son code est dans ``codes_produits`` ; la fonction ne lève jamais.

Run :
    python manage.py test apps.calepinage.tests.test_pret_a_envoyer -v2
"""
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.feu_vert import (
    MESSAGES_APPROBATION, MESSAGES_FEU_VERT,
)
from apps.calepinage.services.pret_a_envoyer import controles_de_porte

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_pret_a_envoyer.json').read_text(encoding='utf-8'))

FEU_VERT = 'apps.calepinage.services.feu_vert._option_active'
VISITE = 'apps.visites.selectors.visite_feu_vert'
EXIGEE = 'apps.calepinage.services.approbation.approbation_exigee'
APPROUVE = 'apps.calepinage.services.approbation.est_approuve'
PERIMEE = ('apps.calepinage.services.comparaison.'
           'simulation_perimee_du_calepinage')
PEREMPTION = 'apps.calepinage.serializers.peremption_du_calepinage'
KWH = 'apps.ventes.selectors_calepinage.refus_kwh_declare_du_devis'

SIMULATION = {'simulation': {'hash_entree': 'abc'}}


class _Societe:
    id = 7


class _Calepinage:
    def __init__(self, *, lead_id=3, devis=None, resultat=SIMULATION):
        self.company = _Societe()
        self.lead_id = lead_id
        self.devis = devis
        self.resultat = resultat


class _Devis:
    lead_id = 3


class ControlesDePorteTest(SimpleTestCase):

    def _controles(self, calepinage, *, option=True, feu_vert=True,
                   exigee=True, approuve=True, perimee=False):
        with mock.patch(FEU_VERT, return_value=option), \
                mock.patch(VISITE, return_value=object() if feu_vert
                           else None), \
                mock.patch(EXIGEE, return_value=exigee), \
                mock.patch(APPROUVE, return_value=approuve), \
                mock.patch(PERIMEE, return_value=perimee):
            controles = controles_de_porte(calepinage)
        return {c['code']: c for c in controles}

    def test_forme_du_contrat_et_codes_produits(self):
        attendues = sorted(CONTRAT['exemple']['controles'][0])
        for controle in self._controles(_Calepinage()).values():
            self.assertEqual(sorted(controle), attendues)
            self.assertIn(controle['code'], CONTRAT['codes_produits'])
            self.assertIn(controle['etat'],
                          ('ok', 'info', 'a_regler', 'bloquant'))
            self.assertEqual(sorted(controle['cible']),
                             ['champ', 'etape', 'onglet'])

    def test_sans_feu_vert_bloquant_et_approbation_non_evaluee(self):
        controles = self._controles(_Calepinage(), feu_vert=False,
                                    approuve=False)
        visite = controles['visite_validee']
        self.assertEqual(visite['etat'], 'bloquant')
        self.assertEqual(visite['cause'], MESSAGES_FEU_VERT['devis'])
        self.assertEqual(visite['geste'], 'Faire valider la visite')
        approbation = controles['approbation_a_jour']
        self.assertEqual(approbation['etat'], 'info')
        self.assertIn('non évaluée tant que la visite n’est pas validée',
                      approbation['valeur_texte'])

    def test_feu_vert_sans_approbation_bloquant(self):
        controles = self._controles(_Calepinage(), approuve=False)
        self.assertEqual(controles['visite_validee']['etat'], 'ok')
        approbation = controles['approbation_a_jour']
        self.assertEqual(approbation['etat'], 'bloquant')
        self.assertEqual(approbation['cause'], MESSAGES_APPROBATION['devis'])

    def test_options_eteintes_ok_non_exige(self):
        controles = self._controles(_Calepinage(), option=False,
                                    feu_vert=False, exigee=False,
                                    approuve=False)
        for code in ('visite_validee', 'approbation_a_jour'):
            self.assertEqual(controles[code]['etat'], 'ok', code)
            self.assertEqual(controles[code]['valeur_texte'],
                             'Non exigé par votre société', code)

    def test_sans_lead_ni_devis_info(self):
        controles = self._controles(_Calepinage(lead_id=None),
                                    feu_vert=False, approuve=False)
        for code in ('visite_validee', 'approbation_a_jour'):
            self.assertEqual(controles[code]['etat'], 'info', code)
            self.assertEqual(controles[code]['valeur_texte'],
                             'Sans lead : non applicable', code)

    def test_simulation_perimee_ou_jamais_lancee_a_regler(self):
        perimee = self._controles(_Calepinage(), perimee=True)
        self.assertEqual(perimee['simulation_fraiche']['etat'], 'a_regler')
        jamais = self._controles(_Calepinage(resultat=None))
        self.assertEqual(jamais['simulation_fraiche']['etat'], 'a_regler')
        fraiche = self._controles(_Calepinage())
        self.assertEqual(fraiche['simulation_fraiche']['etat'], 'ok')

    def test_sans_devis_lie_verifie_a_la_creation(self):
        controles = self._controles(_Calepinage())
        for code in ('conception_perimee', 'kwh_declare'):
            self.assertEqual(controles[code]['etat'], 'info', code)
            self.assertEqual(controles[code]['valeur_texte'],
                             'Vérifié à la création du devis', code)

    def test_devis_lie_perime_et_kwh_contredit(self):
        refus = {'detail': 'Le kWh déclaré contredit les factures.',
                 'code': 'kwh_incoherent'}
        with mock.patch(PEREMPTION, return_value={'layout_stale': True}), \
                mock.patch(KWH, return_value=refus):
            controles = self._controles(_Calepinage(devis=_Devis()))
        self.assertEqual(controles['conception_perimee']['etat'], 'a_regler')
        self.assertEqual(controles['kwh_declare']['etat'], 'bloquant')
        self.assertEqual(controles['kwh_declare']['cause'], refus['detail'])

    def test_devis_lie_a_jour(self):
        with mock.patch(PEREMPTION, return_value={'layout_stale': False}), \
                mock.patch(KWH, return_value=None):
            controles = self._controles(_Calepinage(devis=_Devis()))
        self.assertEqual(controles['conception_perimee']['etat'], 'ok')
        self.assertEqual(controles['kwh_declare']['etat'], 'ok')
