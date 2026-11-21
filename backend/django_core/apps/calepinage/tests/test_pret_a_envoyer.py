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

from .test_api_liste import BaseApiCalepinage, url_detail

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
        self.pk = 1
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
        self.assertEqual(approbation['valeur_texte'],
                         "Non évaluée tant que la visite n'est pas validée")

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


def _forme_du_contrat(test, controles):
    attendues = sorted(CONTRAT['exemple']['controles'][0])
    for controle in controles:
        test.assertEqual(sorted(controle), attendues)
        test.assertIn(controle['code'], CONTRAT['codes_produits'])
        test.assertIn(controle['etat'], ('ok', 'info', 'a_regler', 'bloquant'))


PUBLIABLE = 'apps.calepinage.services.electrique.verdict_publiable'
SERVI = 'apps.calepinage.selectors.resultat_servi'
TRONCONS = 'apps.calepinage.services.troncons.troncons_du_calepinage'


class ControlesElectriquesTest(SimpleTestCase):
    """ACAL858 — l'état d'ACAL934 et les lignes servies, LUS."""

    def _controles(self, *, motifs=(), etat='pret', points=0, verdicts=(),
                   ratio=None, troncons=None):
        from apps.calepinage.services.pret_a_envoyer import (
            controles_electriques,
        )

        publication = {'publiable': True, 'motifs': list(motifs),
                       'etat': etat, 'points': points}
        resultat = {'electrique': {'verdicts': list(verdicts)},
                    'ratio_dc_ac': ratio}
        with mock.patch(PUBLIABLE, return_value=publication), \
                mock.patch(SERVI, return_value=resultat), \
                mock.patch(TRONCONS, return_value=troncons or {}):
            controles = controles_electriques(_Calepinage())
        _forme_du_contrat(self, controles)
        return {c['code']: c for c in controles}

    def test_sans_materiel_a_regler_jamais_ok(self):
        motifs = [{'code': 'FICHE_INCOMPLETE', 'statut': 'non_verifiable',
                   'libelle': 'Onduleur : non désigné.', 'source': ''}]
        controles = self._controles(motifs=motifs, etat='a_completer',
                                    points=1)
        self.assertEqual(controles['materiel_designe']['etat'], 'a_regler')
        self.assertEqual(controles['materiel_designe']['valeur_texte'],
                         'Matériel non désigné')
        verdict = controles['verdict_electrique']
        self.assertEqual(verdict['etat'], 'a_regler')
        self.assertEqual(verdict['valeur_texte'], 'À compléter : 1 points')
        self.assertEqual(len(controles), 7)

    def test_etat_lu_jamais_recalcule(self):
        # Mutant : recalculer depuis les motifs ⇒ « pret » (aucun motif).
        controles = self._controles(etat='a_completer', points=3)
        self.assertEqual(controles['verdict_electrique']['valeur_texte'],
                         'À compléter : 3 points')

    def test_bloquant_avec_n(self):
        controles = self._controles(etat='bloquant', points=2)
        self.assertEqual(controles['verdict_electrique']['etat'], 'bloquant')
        self.assertEqual(controles['verdict_electrique']['valeur_texte'],
                         'Bloquant : 2')
        self.assertEqual(self._controles()['verdict_electrique']['etat'], 'ok')

    def test_ratio_sans_fourchette_info(self):
        ratio = {'valeur': 1.25, 'borne': 1.35, 'dans_bornes': True,
                 'borne_source': 'borne usuelle du noyau électrique'}
        controle = self._controles(ratio=ratio)['ratio_dc_ac']
        self.assertEqual(controle['etat'], 'info')
        self.assertEqual(controle['valeur_texte'], '1,25')
        hors = dict(ratio, valeur=1.5, dans_bornes=False,
                    borne_source='réglage de la société')
        controle = self._controles(ratio=hors)['ratio_dc_ac']
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['seuil_source'], 'réglage de la société')

    def test_tension_froid_valeur_et_temperature_servies(self):
        ligne = {'code': 'voc_cold_under_vmax', 'conforme': True,
                 'bloquant': True, 'source': 'fiche',
                 'detail': '343,0 V sous 600,0 V', 'temperature_c': -5.0,
                 'temperature_mention': ''}
        controle = self._controles(verdicts=[ligne])['tension_froid']
        self.assertEqual(controle['etat'], 'ok')
        self.assertIn('343,0 V sous 600,0 V', controle['valeur_texte'])
        self.assertIn('-5', controle['valeur_texte'])
        refuse = dict(ligne, conforme=False)
        self.assertEqual(self._controles(
            verdicts=[refuse])['tension_froid']['etat'], 'bloquant')

    def test_chutes_et_terre_lues(self):
        troncons = {'verdicts': [{'conforme': False, 'bloquant': False,
                                  'detail': 'Chute 3,2 % pour 3 %'}],
                    'omissions': []}
        terre = [{'code': 'TERRE_OMISE', 'statut': 'omis',
                  'libelle': 'Terre non saisie', 'source': ''}]
        controles = self._controles(troncons=troncons, motifs=terre)
        self.assertEqual(controles['chutes_tension']['etat'], 'a_regler')
        self.assertEqual(controles['chutes_tension']['cause'],
                         'Chute 3,2 % pour 3 %')
        self.assertEqual(controles['terre_protections']['etat'], 'a_regler')
        self.assertEqual(controles['orientation_mppt']['etat'], 'ok')


DOSSIERS = 'apps.calepinage.services.reglementaire.dossiers_du_calepinage'


class ControlesDuResultatTest(SimpleTestCase):
    """ACAL859 — écart PVGIS, ombrage, pièces : aucun seuil codé."""

    def _controles(self, *, validation=None, cascade=None, dossiers=(),
                   consommation=None):
        from apps.calepinage.services.pret_a_envoyer import (
            controles_du_resultat,
        )

        resultat = {'validation': validation, 'cascade': cascade,
                    'consommation': consommation}
        with mock.patch(SERVI, return_value=resultat), \
                mock.patch(DOSSIERS, return_value={'dossiers': list(dossiers)}):
            controles = controles_du_resultat(_Calepinage())
        _forme_du_contrat(self, controles)
        return {c['code']: c for c in controles}

    def test_ecart_hors_tolerance_saisie_a_regler(self):
        validation = {'ecart_pct': 7.2, 'verdict': 'hors_tolerance',
                      'tolerance_pct': 5.0, 'tolerance_source': 'société',
                      'avertissement': 'Écart de 7,2 % hors tolérance.'}
        ecart = self._controles(validation=validation)['ecart_pvgis']
        self.assertEqual(ecart['etat'], 'a_regler')
        self.assertIn('7,2', ecart['valeur_texte'])
        self.assertEqual(ecart['seuil_source'], 'société')
        dedans = dict(validation, verdict='dans_la_tolerance')
        self.assertEqual(self._controles(
            validation=dedans)['ecart_pvgis']['etat'], 'ok')

    def test_sans_tolerance_info(self):
        # Mutant : un seuil codé de 5 % rangerait 7,2 % en « à régler ».
        validation = {'ecart_pct': 7.2, 'verdict': None,
                      'tolerance_pct': None, 'motif': 'aucune tolérance'}
        ecart = self._controles(validation=validation)['ecart_pvgis']
        self.assertEqual(ecart['etat'], 'info')
        self.assertIsNone(ecart['seuil_source'])

    def test_dossier_incomplet_pieces_nommees(self):
        dossier = {'statut': 'incomplet', 'pieces': [
            {'intitule': 'Plan de masse', 'obligatoire': True,
             'etat': 'a_completer'},
            {'intitule': 'Photo', 'obligatoire': False, 'etat': 'manquante'},
            {'intitule': 'Schéma', 'obligatoire': True, 'etat': 'fournie'}]}
        pieces = self._controles(dossiers=[dossier])['dossier_pieces']
        self.assertEqual(pieces['etat'], 'a_regler')
        self.assertEqual(pieces['valeur_texte'], '1 pièce(s) à fournir')
        self.assertEqual(pieces['cause'], 'Plan de masse')
        self.assertEqual(self._controles()['dossier_pieces']['etat'], 'ok')

    def test_ombrage_omis_a_regler_avec_motif(self):
        cascade = {'etapes': [{'etape': 'ombrage_proche',
                               'motif_omission': 'Aucun obstacle relevé.'}]}
        ombrage = self._controles(cascade=cascade)['ombrage_chiffre']
        self.assertEqual(ombrage['etat'], 'a_regler')
        self.assertEqual(ombrage['cause'], 'Aucun obstacle relevé.')
        calcule = {'etapes': [{'etape': 'ombrage_proche',
                               'motif_omission': '', 'perte_pct': 2.1}]}
        self.assertEqual(self._controles(
            cascade=calcule)['ombrage_chiffre']['etat'], 'ok')
        self.assertEqual(self._controles()['ombrage_chiffre']['etat'], 'info')
        self.assertEqual(self._controles()['hypotheses_conso']['etat'], 'info')


#: Un pan carré d'environ 9 m × 11 m (sommets [lng, lat]).
PAN_A = [[-7.5900, 33.5700], [-7.5899, 33.5700], [-7.5899, 33.5701],
         [-7.5900, 33.5701]]


class _Document:
    def __init__(self, zones):
        self.roof_layout = {'zones': zones}


class ObstacleHorsPanTest(SimpleTestCase):
    """ACAL863 — dedans ou dehors, aucune distance écrite."""

    def _controle(self, *obstacles, vertices=PAN_A):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_obstacle_hors_pan,
        )

        zone = {'id': 'a', 'label': 'A', 'vertices': vertices,
                'obstacles': list(obstacles)}
        controle = controle_obstacle_hors_pan(_Document([zone]))
        _forme_du_contrat(self, [controle])
        return controle

    def test_rectangle_dont_un_coin_depasse(self):
        # Centre DEDANS (1 m du bord nord), 4 m nord-sud : le coin sort.
        # Mutant « le seul centre » ⇒ ok, échec.
        cheminee = {'type': 'cheminee', 'centerLat': 33.57009,
                    'centerLng': -7.58995, 'lengthM': 4.0, 'widthM': 1.0}
        controle = self._controle(cheminee)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'],
                         'Cheminée / souche dépasse du pan A')
        self.assertEqual(controle['geste'], "Déplacer l'obstacle")
        self.assertNotRegex(controle['valeur_texte'], r'\d')

    def test_polygone_a_cheval_sur_la_rive(self):
        lucarne = {'type': 'chien_assis', 'forme': 'polygone', 'contour': [
            [-7.59002, 33.57003], [-7.58998, 33.57003],
            [-7.58998, 33.57006]]}
        controle = self._controle(lucarne)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertIn('lucarne dépasse du pan A', controle['valeur_texte'])

    def test_obstacle_dans_le_pan_ok(self):
        dedans = {'type': 'ventilation', 'centerLat': 33.57005,
                  'centerLng': -7.58995, 'lengthM': 2.0, 'widthM': 2.0}
        disque = {'type': 'antenne', 'forme': 'cercle', 'rayonM': 1.0,
                  'centerLat': 33.57005, 'centerLng': -7.58995}
        self.assertEqual(self._controle(dedans, disque)['etat'], 'ok')

    def test_contour_absent_info(self):
        dedans = {'type': 'ventilation', 'centerLat': 33.57005,
                  'centerLng': -7.58995, 'lengthM': 2.0, 'widthM': 2.0}
        self.assertEqual(self._controle(dedans, vertices=[])['etat'], 'info')
        sans_dimension = {'centerLat': 33.57005, 'centerLng': -7.58995}
        self.assertEqual(self._controle(sans_dimension)['etat'], 'info')


MESURES = 'apps.calepinage.services.mesures.mesures_du_document'


def _pan(nom, modules, motif='', kwc=None):
    return {'pan': nom, 'kind': 'toit', 'modules': modules, 'kwc': kwc,
            'motif': motif}


class PansVidesTest(SimpleTestCase):
    """ACAL864 — nom du pan et motif lus de ``mesures_du_document``."""

    def _controle(self, pans):
        from apps.calepinage.services.pret_a_envoyer import controle_pans_vides

        with mock.patch(MESURES, return_value={'pans': pans}):
            controle = controle_pans_vides(_Document([]))
        _forme_du_contrat(self, [controle])
        return controle

    def test_pan_vide_nomme_avec_son_motif(self):
        controle = self._controle([_pan('A', 8), _pan('B', 0, 'non pavé')])
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'],
                         'le pan B n’a aucun panneau : non pavé')
        self.assertEqual(controle['geste'], 'Remplir le pan')

    def test_deux_pans_vides_une_ligne(self):
        controle = self._controle([_pan('B', 0, 'non pavé'),
                                   _pan('C', 0, 'non pavé')])
        self.assertIn('pan B', controle['valeur_texte'])
        self.assertIn('pan C', controle['valeur_texte'])

    def test_tous_garnis_ok_et_sans_pan_info(self):
        self.assertEqual(self._controle([_pan('A', 8)])['etat'], 'ok')
        self.assertEqual(self._controle([])['etat'], 'info')


class _Layout:
    def __init__(self, kwc):
        self.roof_layout = {'result': {'kwc': kwc}, 'panelWatt': 720}


class KwcCoherentTest(SimpleTestCase):
    """ACAL862 — ``result.kwc`` contre « modules × Wc de la fiche »."""

    def _controle(self, annonce, fiche):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_kwc_coherent,
        )

        with mock.patch(MESURES, return_value={'kwc': fiche, 'pans': []}):
            controle = controle_kwc_coherent(_Layout(annonce))
        _forme_du_contrat(self, [controle])
        return controle

    def test_ecart_nomme_les_deux_valeurs(self):
        # 182 × 710 Wc = 129,22 kWc ; le document garde 182 × 720 Wc.
        controle = self._controle(131.04, 182 * 710 / 1000)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'],
                         'le document annonce 131,04 kWc, la fiche des '
                         'modules donne 129,22 kWc')
        self.assertEqual(controle['geste'], 'Enregistrer le calepinage')

    def test_egalite_ok(self):
        self.assertEqual(self._controle(129.22, 129.2200001)['etat'], 'ok')

    def test_module_sans_puissance_info(self):
        self.assertEqual(self._controle(131.04, None)['etat'], 'info')
        self.assertEqual(self._controle(None, 129.22)['etat'], 'info')


LEAD = 'apps.crm.selectors.get_company_lead'
CIBLE = 'apps.ventes.selectors.cible_depuis_lead'


def _cible(motif_code=None, refus=None):
    return {'panneaux': None if refus else 10, 'panel_watt': 710, 'kwc': None,
            'source': 'factures', 'refus': refus, 'motif_code': motif_code}


class TailleSansFactureTest(SimpleTestCase):
    """ACAL861 — la condition de ``devis.taille_non_dimensionnee``, lue."""

    def _controle(self, cible, *, kwc=131.04, lead_id=3):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_taille_sans_facture,
        )

        calepinage = _Calepinage(lead_id=lead_id)
        # Le document n'a AUCUN bloc ``consumption`` (lead avec facture).
        calepinage.roof_layout = {'zones': []}
        with mock.patch(LEAD, return_value=object()), \
                mock.patch(CIBLE, return_value=cible), \
                mock.patch(MESURES, return_value={'kwc': kwc, 'pans': []}):
            controle = controle_taille_sans_facture(calepinage)
        _forme_du_contrat(self, [controle])
        return controle

    def test_lead_sans_facture_ni_taille_a_regler(self):
        controle = self._controle(_cible('facture_absente', 'Facture absente.'))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'], 'le toit est rempli : 131 kWc')
        self.assertEqual(controle['geste'], 'Saisir la facture')
        self.assertEqual(controle['cible']['champ'], 'facture')

    def test_lead_avec_facture_sans_consumption_ok(self):
        # Mutant « absence de consumption.courbe24 » ⇒ orange ici, échec.
        self.assertEqual(self._controle(_cible())['etat'], 'ok')

    def test_autre_refus_ne_pose_pas_la_question(self):
        ci = _cible(None, 'Lead commercial/industriel : étude C&I.')
        self.assertEqual(self._controle(ci)['etat'], 'ok')

    def test_puissance_inconnue_info_et_sans_lead(self):
        self.assertEqual(self._controle(_cible('facture_absente', 'x'),
                                        kwc=None)['etat'], 'info')
        self.assertEqual(self._controle(None, lead_id=None)['etat'],
                         'a_regler')


HYPOTHESES = 'apps.calepinage.services.hypotheses_toit.avertissements_hypotheses'


def _ctrl(code, etat):
    from apps.calepinage.services.pret_a_envoyer import _controle

    return _controle(code, code, etat, '')


class AgregatTest(SimpleTestCase):
    """ACAL860 — l'agrégat : forme du contrat, tri, ``pret``, codes."""

    def test_tout_vert_pret_vrai(self):
        from apps.calepinage.services.pret_a_envoyer import agreger

        servi = agreger(_Calepinage(), [
            lambda c: [_ctrl('visite_validee', 'ok')],
            lambda c: _ctrl('pans_vides', 'ok')])
        self.assertEqual(sorted(servi), sorted(CONTRAT['exemple_vide']))
        self.assertEqual((servi['pret'], servi['nombre_bloquants'],
                          servi['nombre_a_regler']), (True, 0, 0))

    def test_bloquant_en_tete_et_pret_faux(self):
        # Mutant : retirer le tri ⇒ « ok » reste en tête, échec.
        from apps.calepinage.services.pret_a_envoyer import agreger

        servi = agreger(_Calepinage(), [
            lambda c: [_ctrl('visite_validee', 'ok'),
                       _ctrl('ratio_dc_ac', 'info')],
            lambda c: _ctrl('pans_vides', 'a_regler'),
            lambda c: _ctrl('kwh_declare', 'bloquant')])
        self.assertFalse(servi['pret'])
        self.assertEqual([c['etat'] for c in servi['controles']],
                         ['bloquant', 'a_regler', 'info', 'ok'])
        self.assertEqual((servi['nombre_bloquants'],
                          servi['nombre_a_regler']), (1, 1))

    def test_pente_non_confirmee_a_regler(self):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_pentes_confirmees,
        )

        message = "Pan « A » : la pente (22°) n'a jamais été confirmée."
        with mock.patch(HYPOTHESES, return_value=[message]):
            controle = controle_pentes_confirmees(_Document([]))
        _forme_du_contrat(self, [controle])
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['cause'], message)
        self.assertEqual(controle['cible']['onglet'], 'pente')
        with mock.patch(HYPOTHESES, return_value=[]):
            self.assertEqual(controle_pentes_confirmees(
                _Document([]))['etat'], 'ok')

    def test_codes_produits_exactement_ceux_du_contrat(self):
        from apps.calepinage.views.pret_a_envoyer import PRODUCTEURS
        from apps.calepinage.services.pret_a_envoyer import agreger

        calepinage = _Calepinage()
        calepinage.roof_layout = {'zones': []}
        publication = {'publiable': True, 'motifs': [], 'etat': 'pret',
                       'points': 0}
        with mock.patch(FEU_VERT, return_value=False), \
                mock.patch(VISITE, return_value=None), \
                mock.patch(APPROUVE, return_value=False), \
                mock.patch(EXIGEE, return_value=False), \
                mock.patch(PERIMEE, return_value=False), \
                mock.patch(PUBLIABLE, return_value=publication), \
                mock.patch(SERVI, return_value={}), \
                mock.patch(TRONCONS, return_value={}), \
                mock.patch(DOSSIERS, return_value={'dossiers': []}), \
                mock.patch(MESURES, return_value={'kwc': None, 'pans': []}), \
                mock.patch(LEAD, return_value=object()), \
                mock.patch(CIBLE, return_value=_cible()), \
                mock.patch(HYPOTHESES, return_value=[]):
            servi = agreger(calepinage, PRODUCTEURS)
        _forme_du_contrat(self, servi['controles'])
        codes = [c['code'] for c in servi['controles']]
        self.assertEqual(sorted(codes), sorted(CONTRAT['codes_produits']))
        self.assertFalse(set(codes) & set(CONTRAT['codes_reserves']))


class PretAEnvoyerRouteTest(BaseApiCalepinage):
    """ACAL860 — la route : société bornée, lecture seule (base requise)."""

    def test_autre_societe_404_et_lecture_sans_ecriture(self):
        from apps.calepinage.models import Calepinage

        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL860')
        url = f'{url_detail(calepinage.pk)}pret-a-envoyer/'
        self.assertEqual(self.api_autre.get(url).status_code, 404)
        avant = Calepinage.objects.get(pk=calepinage.pk).updated_at
        reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertEqual(Calepinage.objects.get(pk=calepinage.pk)
                         .updated_at, avant)
