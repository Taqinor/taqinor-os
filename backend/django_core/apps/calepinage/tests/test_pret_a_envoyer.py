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
#: Une part d'ombrage servie, de l'essai (ce que l'étape « ombrage proche » a calculé).
OMBRAGE_ESSAI_PCT = 2.1


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


#: H3 — ``verdict_publiable`` n'est que ``_rapport_publication(...)[0]`` : le
#: producteur lit le rapport entier (son matériel sert aussi ACAL906).
PUBLIABLE = 'apps.calepinage.services.electrique._rapport_publication'
SERVI = 'apps.calepinage.selectors.resultat_servi'
TRONCONS = 'apps.calepinage.services.troncons.troncons_du_calepinage'


class ControlesElectriquesTest(SimpleTestCase):
    """ACAL858 — l'état d'ACAL934 et les lignes servies, LUS."""

    def _controles(self, *, motifs=(), etat='pret', points=0, verdicts=(),
                   ratio=None, troncons=None, materiel=None):
        from apps.calepinage.services.pret_a_envoyer import (
            controles_electriques,
        )

        publication = {'publiable': True, 'motifs': list(motifs),
                       'etat': etat, 'points': points}
        resultat = {'electrique': {'verdicts': list(verdicts)},
                    'ratio_dc_ac': ratio}
        with mock.patch(PUBLIABLE, return_value=(publication, None, materiel)), \
                mock.patch(SERVI, return_value=resultat), \
                mock.patch(TRONCONS, return_value=troncons or {}):
            controles = controles_electriques(_Calepinage())
        _forme_du_contrat(self, controles)
        return {c['code']: c for c in controles}

    def test_sans_materiel_a_regler_jamais_ok(self):
        motifs = [{'code': 'FICHE_INCOMPLETE', 'statut': 'non_verifiable',
                   'libelle': 'onduleur : puissance AC', 'source': ''}]
        absent = "onduleur non désigné — désignez-le dans l'onglet Matériel électrique"
        controles = self._controles(motifs=motifs, etat='a_completer',
                                    points=1, materiel={'absents': (absent,)})
        self.assertEqual(controles['materiel_designe']['etat'], 'a_regler')
        # ACAL1704 — « Non désigné » : rien n'est choisi (le motif d'absence est la cause).
        self.assertEqual(controles['materiel_designe']['valeur_texte'],
                         'Non désigné')
        self.assertEqual(controles['materiel_designe']['cause'], absent)
        self.assertEqual(controles['ratio_dc_ac']['valeur_texte'],
                         'Non calculé : onduleur non désigné')
        verdict = controles['verdict_electrique']
        self.assertEqual(verdict['etat'], 'a_regler')
        # ACAL1539 : « À compléter » seul — le détail des motifs est au Verdict.
        self.assertEqual(verdict['valeur_texte'], 'À compléter')
        self.assertEqual(len(controles), 7)

    def test_materiel_choisi_fiche_incomplete_dit_la_vraie_cause(self):
        """ACAL1704 — panneau ET onduleur choisis, fiche du module sans Vmp :
        « Fiche incomplète : <champ> du module » et le geste « Compléter la fiche
        du module », jamais « Non désigné » ; le ratio dit « fiche du module
        incomplète » (mutant : remettre la valeur fixe ⇒ échec)."""
        motifs = [{'code': 'FICHE_INCOMPLETE', 'statut': 'non_verifiable',
                   'libelle': 'module : tension au point de puissance maximale (Vmp)',
                   'source': 'fiche technique du matériel retenu'}]
        controles = self._controles(motifs=motifs, etat='a_completer', points=1,
                                    materiel={'absents': ()})
        materiel = controles['materiel_designe']
        self.assertEqual(materiel['etat'], 'a_regler')
        self.assertEqual(materiel['valeur_texte'], 'Fiche incomplète : tension au '
                         'point de puissance maximale (Vmp) du module')
        self.assertEqual(materiel['geste'], 'Compléter la fiche du module')
        self.assertEqual(materiel['cause'],
                         'module : tension au point de puissance maximale (Vmp)')
        self.assertEqual(controles['ratio_dc_ac']['valeur_texte'],
                         'Non calculé : fiche du module incomplète')
        onduleur = [dict(motifs[0], libelle='onduleur : puissance AC')]
        controles = self._controles(motifs=onduleur, materiel={'absents': ()})
        self.assertEqual(controles['materiel_designe']['valeur_texte'],
                         'Fiche incomplète : puissance AC de l’onduleur')
        self.assertEqual(controles['materiel_designe']['geste'],
                         'Compléter la fiche de l’onduleur')
        self.assertEqual(controles['ratio_dc_ac']['valeur_texte'],
                         'Non calculé : fiche de l’onduleur incomplète')

    def test_resume_de_motifs_singulier_pluriel(self):
        # R3-10 : jamais « 1 point(s) » — « 1 point », « 2 points ».
        from apps.calepinage.services.pret_a_envoyer import _depuis_motifs

        un = [{'statut': 'alerte', 'libelle': 'Premier.'}]
        deux = un + [{'statut': 'alerte', 'libelle': 'Second.'}]
        self.assertEqual(_depuis_motifs('x', 'X', un, geste='g')['valeur_texte'], '1 point')
        self.assertEqual(_depuis_motifs('x', 'X', deux, geste='g')['valeur_texte'], '2 points')

    def test_etat_lu_jamais_recalcule(self):
        # Mutant : recalculer depuis les motifs ⇒ « pret » (aucun motif).
        controles = self._controles(etat='a_completer', points=3)
        self.assertEqual(controles['verdict_electrique']['etat'], 'a_regler')
        # ACAL1539 : aucun compte de motifs sur la ligne du dossier.
        self.assertEqual(controles['verdict_electrique']['valeur_texte'],
                         'À compléter')

    def test_bloquant_avec_n(self):
        controles = self._controles(etat='bloquant', points=2)
        self.assertEqual(controles['verdict_electrique']['etat'], 'bloquant')
        self.assertEqual(controles['verdict_electrique']['valeur_texte'],
                         'Bloquant : 2')
        self.assertEqual(self._controles()['verdict_electrique']['etat'], 'ok')

    def test_ratio_juge_par_la_regle_du_devis_jamais_bon_au_dessus(self):
        # ACAL1954 (D-ACAL-91) — 4,26 sur un onduleur réseau : « à régler », jamais « Bon ».
        ratio = {'valeur': 1.25, 'borne': 1.35, 'dans_bornes': True,
                 'borne_source': 'règle du devis', 'borne_reference': ''}
        controle = self._controles(ratio=ratio)['ratio_dc_ac']
        self.assertEqual(controle['etat'], 'ok')
        self.assertEqual(controle['valeur_texte'], '1,25 pour 1,35 au plus (règle du devis)')
        hors = dict(ratio, valeur=4.26, dans_bornes=False, borne_source='fourchette de la société')
        controle = self._controles(ratio=hors)['ratio_dc_ac']
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'], '4,26 pour 1,35 au plus (fourchette de la société)')
        self.assertEqual(controle['seuil_source'], 'fourchette de la société')

    def test_ratio_hors_devis_deja_envoye_est_une_information(self):
        from apps.calepinage.services.pret_a_envoyer import _ratio_dc_ac

        hors = {'valeur': 4.26, 'borne': 1.35, 'dans_bornes': False,
                'borne_source': 'règle du devis', 'borne_reference': ''}
        controle = _ratio_dc_ac(hors, devis_recu=True)
        self.assertEqual(controle['etat'], 'info')
        self.assertIn('Écart avec le devis', controle['cause'])

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

    def test_chaque_controle_a_regler_porte_l_onglet_qui_le_regle(self):
        # ACAL1506 — « Régler » ouvre l'écran où le point se saisit, plus le
        # Schéma (mutant : remettre ``schema`` par défaut ⇒ échec).
        troncons = {'verdicts': [], 'omissions': [
            {'motif': 'Longueur du tronçon non saisie'}]}
        terre = [{'code': 'TERRE_OMISE', 'statut': 'omis',
                  'libelle': 'Terre non saisie', 'source': ''}]
        controles = self._controles(troncons=troncons, motifs=terre,
                                    etat='a_completer', points=2)
        attendus = {'verdict_electrique': 'verdict-electrique',
                    'chutes_tension': 'cheminement-cables',
                    'terre_protections': 'decisions-electriques'}
        for code, onglet in attendus.items():
            self.assertNotEqual(controles[code]['etat'], 'ok', code)
            self.assertEqual(controles[code]['cible'],
                             {'etape': 'electrique', 'onglet': onglet,
                              'champ': ''}, code)
        # Les contrôles sans écran de saisie propre restent au Schéma.
        self.assertEqual(controles['tension_froid']['cible']['onglet'],
                         'schema')


#: ACAL1703 — le registre des onglets de l'atelier, LU (jamais recopié) : ``cle`` de
#: chaque entrée d'``ONGLETS`` ; ``reglages`` est la route nommée ``/calepinage/reglages``
#: (``production/lienManque.js``).
REGISTRE_ONGLETS = ('frontend', 'src', 'features', 'calepinage', 'atelier', 'onglets.js')
ROUTES_NOMMEES = {'reglages'}


def _registre_onglets():
    """Le fichier du registre, cherché en remontant depuis ce test : la racine du dépôt
    n'est pas à la même profondeur dans le checkout complet de la CI et dans un montage
    du seul ``django_core`` (où le front n'existe pas : ``None``)."""
    for parent in pathlib.Path(__file__).resolve().parents:
        candidat = parent.joinpath(*REGISTRE_ONGLETS)
        if candidat.is_file():
            return candidat
    return None


def _cles_du_registre():
    import re

    return set(re.findall(r"\{ cle: '([^']+)'", _registre_onglets().read_text(encoding='utf-8')))


def _onglets_servis():
    """Toutes les ``cible.onglet`` que le service peut servir : ses constantes
    ``CIBLE_*``, l'onglet de chaque contrôle électrique et son défaut, et les
    cibles de « Un seul chiffre »."""
    from apps.calepinage.services import pret_a_envoyer as service

    cibles = [v for nom, v in vars(service).items()
              if nom.startswith('CIBLE_') and isinstance(v, dict)]
    cibles += [c for *_x, c in service._MOTIFS_UN_SEUL_CHIFFRE if c]
    onglets = {c['onglet'] for c in cibles if c['onglet']}
    onglets |= set(service._ONGLET_DU_CONTROLE.values())
    onglets.add(service._elec('x', 'X', 'ok', '')['cible']['onglet'])
    return onglets


class CiblesDuReglerTest(SimpleTestCase):
    """ACAL1703 — « Régler » mène toujours vers un écran qui existe."""

    def test_toute_cible_servie_est_un_onglet_du_registre_ou_une_route(self):
        # Mutant : remettre « materiel », « obstacles » ⇒ échec (clés absentes).
        # Aucun saut (ENF23) : sans le front (montage du seul ``django_core``) ce cas échoue et le dit.
        self.assertIsNotNone(_registre_onglets(), 'registre des onglets introuvable : front absent de ce montage')
        cles = _cles_du_registre()
        self.assertGreater(len(cles), 30)  # le registre est bien lu
        self.assertEqual(_onglets_servis() - cles - ROUTES_NOMMEES, set())

    def test_les_trois_cibles_menent_a_l_ecran_qui_porte_le_champ(self):
        from apps.calepinage.services import pret_a_envoyer as service

        self.assertEqual(service.CIBLE_MATERIEL['onglet'], 'materiel-electrique')
        self.assertEqual((service.CIBLE_OBSTACLES['etape'], service.CIBLE_OBSTACLES['onglet']),
                         ('toit', 'pente'))
        self.assertEqual(service.CIBLE_PERTES['onglet'], 'reglages')


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
        cascade = {'etapes': [{
            'etape': 'ombrage_proche',
            'motif_omission': 'Omis. Champ manquant : « ombrage.shading12x24 ».'}]}
        cause = self._controles(cascade=cascade)['ombrage_chiffre']['cause']
        self.assertNotIn('ombrage.shading12x24', cause)
        self.assertIn("matrice d'ombrage", cause)
        calcule = {'etapes': [{'etape': 'ombrage_proche',
                               'motif_omission': '',
                               'perte_pct': OMBRAGE_ESSAI_PCT}]}
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

    def test_sans_facture_ni_taille_aucun_balayage_reponse_identique(self):
        """ACAL1342 — un lead résidentiel sans facture ni taille souhaitée : la réponse
        est celle du moteur (« facture absente »), sans lancer ``cible_depuis_lead`` ;
        dès qu'un champ dimensionnant est rempli, le moteur tranche comme avant."""
        from types import SimpleNamespace

        from apps.calepinage.services.pret_a_envoyer import controle_taille_sans_facture

        attendu = self._controle(_cible('facture_absente', 'Facture absente.'))
        vide = dict(type_installation='residentiel', facture_hiver=None, facture_ete='',
                    conso_mensuelle_kwh=None, taille_souhaitee_kwc=None)
        for lead, appels in ((SimpleNamespace(**vide), 0),
                             (SimpleNamespace(**dict(vide, facture_hiver=900)), 1),
                             (SimpleNamespace(**dict(vide, type_installation='commercial')), 1)):
            calepinage = _Calepinage(lead_id=3)
            calepinage.roof_layout = {'zones': []}
            with mock.patch(LEAD, return_value=lead), \
                    mock.patch(CIBLE, return_value=_cible('facture_absente', 'Facture absente.')) as balayage, \
                    mock.patch(MESURES, return_value={'kwc': 131.04, 'pans': []}):
                controle = controle_taille_sans_facture(calepinage)
            self.assertEqual(balayage.call_count, appels, lead)
            self.assertEqual(controle, attendu)

    def test_puissance_inconnue_info_et_sans_lead(self):
        self.assertEqual(self._controle(_cible('facture_absente', 'x'),
                                        kwc=None)['etat'], 'info')
        self.assertEqual(self._controle(None, lead_id=None)['etat'],
                         'a_regler')


HYPOTHESES = 'apps.calepinage.services.hypotheses_toit.avertissements_hypotheses'


def _ctrl(code, etat):
    from apps.calepinage.services.pret_a_envoyer import _controle

    return _controle(code, code, etat, '')


ANNONCEE = 'apps.ventes.selectors_calepinage.production_annoncee_du_devis'


class _DevisPose:
    pk = 41


class UnSeulChiffreTest(SimpleTestCase):
    """ACAL1171 — le chiffre que le PDF du devis imprimera : la pose ou la ville."""

    def _controle(self, lu, *, devis=_DevisPose()):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_un_seul_chiffre)

        with mock.patch(ANNONCEE, return_value=lu) as lecture:
            controle = controle_un_seul_chiffre(_Calepinage(devis=devis))
        _forme_du_contrat(self, [controle])
        self.assertNotEqual(controle['etat'], 'bloquant')
        return controle, lecture

    @staticmethod
    def _lu(motif='', *, servie=False, regles=True):
        return {'regles_a_jour': regles, 'servie': servie, 'motif': motif}

    def test_base_servie_ok_et_lecture_bornee_societe(self):
        controle, lecture = self._controle(self._lu(servie=True))
        self.assertEqual(controle['etat'], 'ok')
        self.assertEqual(controle['valeur_texte'],
                         'Le devis imprimera la production de cette pose')
        lecture.assert_called_once()
        self.assertEqual(lecture.call_args.args[0], 41)
        self.assertEqual(lecture.call_args.args[1].id, 7)

    def test_simulation_absente_a_lancer(self):
        for motif in ('aucune simulation du calepinage',
                      'aucun calepinage lié'):
            controle, _ = self._controle(self._lu(motif))
            self.assertEqual(controle['etat'], 'a_regler', motif)
            self.assertEqual(controle['geste'], 'Lancer la simulation')
            self.assertEqual(controle['cause'], motif)

    def test_simulation_perimee_a_relancer(self):
        motif = 'la conception a changé depuis la simulation'
        controle, _ = self._controle(self._lu(motif))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['geste'], 'Relancer la simulation')
        self.assertEqual(controle['cause'], motif)

    def test_resultat_incomplet_nomme_les_pertes_a_renseigner(self):
        controle, _ = self._controle(self._lu(
            'résultat incomplet : 3 pertes non renseignées'))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['geste'], 'Renseigner les 3 pertes manquantes')
        self.assertEqual(controle['cible']['onglet'], 'reglages')
        controle, _ = self._controle(self._lu(
            'résultat du calepinage incomplet'))
        self.assertEqual(controle['geste'], 'Renseigner les pertes manquantes')

    def test_kwc_du_devis_different_a_resynchroniser(self):
        for motif in ('lignes du devis différentes du calepinage',
                      'Conception modifiée depuis le devis : '
                      'resynchronisez le devis.'):
            controle, _ = self._controle(self._lu(motif))
            self.assertEqual(controle['etat'], 'a_regler', motif)
            self.assertEqual(controle['geste'], 'Resynchroniser le devis')

    def test_agricole_le_motif_du_resolveur_est_rendu_tel_quel(self):
        motif = 'un pan sans inclinaison ou orientation lisible'
        controle, _ = self._controle(self._lu(motif))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['cause'], motif)

    def test_info_sans_verdict_ni_geste(self):
        cas = (self._lu('règles d’avant le 21/11', regles=False),
               self._lu('marché non résidentiel'),
               self._lu('aucune base rangée au bloc horaire'),
               self._lu('calepinage illisible'), None)
        for lu in cas:
            controle, _ = self._controle(lu)
            self.assertEqual(controle['etat'], 'info', lu)
            self.assertEqual(controle['geste'], '', lu)

    def test_sans_devis_lie_info_et_aucune_lecture(self):
        controle, lecture = self._controle(self._lu(servie=True), devis=None)
        self.assertEqual(controle['etat'], 'info')
        lecture.assert_not_called()


COMPATIBILITE = 'apps.ventes.selectors.compatibilite_du_materiel'
MATERIEL = 'apps.calepinage.services.electrique.resoudre_materiel'


class CompatibiliteTest(SimpleTestCase):
    """ACAL906 — le verdict de ventes (ACAL901), relayé : le pire des deux."""

    def _controle(self, servi, *, produits=None, batterie=None):
        from apps.calepinage.services.pret_a_envoyer import (
            controle_compatibilite)

        calepinage = _Calepinage()
        calepinage.resultat = {'entree_electrique': {
            'batterie': {'produit': batterie}} if batterie else {}}
        materiel = {'produits': produits or {'module': 11, 'onduleur': 12},
                    'absents': ('onduleur non désigné',)}
        with mock.patch(MATERIEL, return_value=materiel):
            with mock.patch(COMPATIBILITE, return_value=servi) as lecture:
                controle = controle_compatibilite(calepinage)
        _forme_du_contrat(self, [controle])
        return controle, lecture

    @staticmethod
    def _servi(statut, raisons=(), batterie=None):
        return {'panneau_onduleur': {'statut': statut,
                                     'raisons': list(raisons)},
                'batterie_onduleur': batterie}

    def test_incompatible_a_regler_avec_les_raisons_servies(self):
        controle, lecture = self._controle(self._servi(
            'incompatible', ['Voc à froid au-dessus du maximum']))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'], 'Incompatible')
        self.assertEqual(controle['cause'], 'Voc à froid au-dessus du maximum')
        self.assertEqual(controle['geste'], 'Revoir le choix du matériel')
        self.assertEqual(lecture.call_args.args[:2], (11, 12))

    def test_reserve_a_regler_avec_les_raisons_d_alerte(self):
        controle, _ = self._controle(self._servi('reserve', ['écrêtage']))
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['cause'], 'écrêtage')

    def test_compatible_ok(self):
        controle, _ = self._controle(self._servi('compatible'))
        self.assertEqual(controle['etat'], 'ok')
        self.assertEqual(controle['geste'], '')

    def test_inconnu_info_avec_les_champs_manquants(self):
        controle, _ = self._controle(self._servi(
            'inconnu', ['complétez la fiche : Vmax onduleur']))
        self.assertEqual(controle['etat'], 'info')
        self.assertEqual(controle['valeur_texte'], 'Non vérifiable')
        self.assertIn('Vmax onduleur', controle['cause'])

    def test_le_pire_des_deux_verdicts_l_emporte(self):
        batterie = {'statut': 'incompatible', 'raisons': ['tension hors plage']}
        controle, lecture = self._controle(
            self._servi('compatible', batterie=batterie), batterie=21)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['cause'], 'tension hors plage')
        self.assertEqual(lecture.call_args.args[3], 21)
        controle, _ = self._controle(self._servi(
            'inconnu', ['fiche vide'],
            batterie={'statut': 'compatible', 'raisons': []}))
        self.assertEqual(controle['etat'], 'info')

    def test_materiel_non_designe_info_sans_lecture(self):
        controle, lecture = self._controle(
            self._servi('compatible'), produits={'module': 11})
        self.assertEqual(controle['etat'], 'info')
        self.assertEqual(controle['cause'], 'onduleur non désigné')
        lecture.assert_not_called()


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

    @staticmethod
    def _lectures_remplacees(materiel=None):
        """Les lectures de base de tous les producteurs, remplacées."""
        from contextlib import ExitStack

        publication = {'publiable': True, 'motifs': [], 'etat': 'pret',
                       'points': 0}
        pile = ExitStack()
        for cible, valeur in (
                (FEU_VERT, False), (VISITE, None), (APPROUVE, False),
                (EXIGEE, False), (PERIMEE, False),
                (PUBLIABLE, (publication, None, materiel)), (SERVI, {}),
                (TRONCONS, {}), (DOSSIERS, {'dossiers': []}),
                (MESURES, {'kwc': None, 'pans': []}), (LEAD, object()),
                (CIBLE, _cible()), (HYPOTHESES, [])):
            pile.enter_context(mock.patch(cible, return_value=valeur))
        return pile

    def test_codes_produits_exactement_ceux_du_contrat(self):
        from apps.calepinage.views.pret_a_envoyer import PRODUCTEURS
        from apps.calepinage.services.pret_a_envoyer import agreger

        calepinage = _Calepinage()
        calepinage.roof_layout = {'zones': []}
        with self._lectures_remplacees():
            servi = agreger(calepinage, PRODUCTEURS)
        _forme_du_contrat(self, servi['controles'])
        codes = [c['code'] for c in servi['controles']]
        self.assertEqual(sorted(codes), sorted(CONTRAT['codes_produits']))
        self.assertFalse(set(codes) & set(CONTRAT['codes_reserves']))

    def test_une_lecture_calcule_une_fois_les_entrees_partagees(self):
        # H3 — mutant : retirer ``_partage`` ⇒ ``resultat_servi`` lu deux fois
        # (électrique + résultat) et le matériel résolu deux fois : échec.
        from apps.calepinage import selectors
        from apps.calepinage.services import electrique
        from apps.calepinage.services import pret_a_envoyer as service
        from apps.calepinage.views.pret_a_envoyer import PRODUCTEURS

        calepinage = _Calepinage()
        calepinage.roof_layout = {'zones': []}
        materiel = {'produits': {}, 'absents': ('module non désigné',)}
        with self._lectures_remplacees(materiel), \
                mock.patch(MATERIEL) as resolution:
            servi = service.agreger(calepinage, PRODUCTEURS)
            self.assertEqual(selectors.resultat_servi.call_count, 1)
            self.assertEqual(electrique._rapport_publication.call_count, 1)
            resolution.assert_not_called()
            compat = next(c for c in servi['controles']
                          if c['code'] == 'compatibilite_equipements')
            self.assertEqual(compat['cause'], 'module non désigné')
            # Hors ``agreger`` : aucune mémoire, chaque appel relit.
            service.controles_du_resultat(calepinage)
            service.controles_du_resultat(calepinage)
            self.assertEqual(selectors.resultat_servi.call_count, 3)
        self.assertIsNone(service._LECTURE.get())

    def test_filtre_par_etape_couvre_le_rangement_de_l_ecran(self):
        # H3 — ``?etape=`` : chaque code que l'écran range dans une étape
        # (``etape_du_code`` du contrat, que ``PretAEnvoyer.helpers.js`` doit
        # égaler : ``PretAEnvoyer.test.jsx``) est produit par un producteur de
        # CETTE étape ; l'Électrique ne paie ni porte ni taille.
        from apps.calepinage.services.pret_a_envoyer import (
            agreger, controle_taille_sans_facture, controles_de_porte,
        )
        from apps.calepinage.views.pret_a_envoyer import (
            PRODUCTEURS, PRODUCTEURS_PAR_ETAPE,
        )

        self.assertFalse({controle_taille_sans_facture, controles_de_porte}
                         & set(PRODUCTEURS_PAR_ETAPE['electrique']))
        ecran = CONTRAT['etape_du_code']
        self.assertEqual(sorted(ecran), sorted(CONTRAT['codes_produits']))
        calepinage = _Calepinage()
        calepinage.roof_layout = {'zones': []}
        with self._lectures_remplacees():
            for etape, producteurs in PRODUCTEURS_PAR_ETAPE.items():
                self.assertTrue(set(producteurs) <= set(PRODUCTEURS))
                rendus = {c['code'] for c in agreger(
                    calepinage, producteurs)['controles']}
                attendus = {c for c, e in ecran.items() if e == etape}
                self.assertTrue(attendus <= rendus, (etape, attendus - rendus))


class UneFoisParLectureTest(SimpleTestCase):
    """H5 — ``une_fois_par_lecture`` : calculé une fois PAR LECTURE, jamais hors."""

    def _decoree(self, appels):
        from apps.calepinage.services.pret_a_envoyer import une_fois_par_lecture

        @une_fois_par_lecture('essai')
        def calcul(calepinage, *, layout=None):
            appels.append((calepinage, layout))
            if getattr(calepinage, 'leve', False):
                raise ValueError('refus')
            return {'pk': calepinage.pk, 'layout': layout}
        return calcul

    def test_hors_lecture_chaque_appel_calcule(self):
        appels = []
        calcul = self._decoree(appels)
        calepinage = _Calepinage()
        calcul(calepinage)
        calcul(calepinage)
        self.assertEqual(len(appels), 2)

    def test_dans_une_lecture_une_fois_par_cle_puis_memoire_retiree(self):
        # Mutant : retirer la mémoire ⇒ 4 calculs pour la même instance, échec.
        from apps.calepinage.services import pret_a_envoyer as service

        appels = []
        calcul = self._decoree(appels)
        meme, autre_instance = _Calepinage(), _Calepinage()  # même pk
        rendus = []

        def producteur(calepinage):
            rendus.append(calcul(calepinage))
            rendus.append(calcul(calepinage))
            calcul(autre_instance)  # autre instance ⇒ autre clé
            calcul(calepinage, layout={'zones': []})  # option ⇒ recalcul
            calcul(calepinage, layout={'zones': []})
            return _ctrl('pans_vides', 'ok')

        service.agreger(meme, [producteur, producteur])
        self.assertIs(rendus[0], rendus[1])
        self.assertIs(rendus[0], rendus[2])
        self.assertEqual([a[0] for a in appels].count(meme), 5)  # 1 + 2×2 à options
        self.assertEqual([a[0] for a in appels].count(autre_instance), 1)
        self.assertIsNone(service._LECTURE.get())
        calcul(meme)  # après la lecture : plus rien de gardé
        self.assertEqual([a[0] for a in appels].count(meme), 6)

    def test_document_rebranche_change_la_cle_et_refus_releve_chaque_fois(self):
        from apps.calepinage.services import pret_a_envoyer as service

        appels = []
        calcul = self._decoree(appels)
        calepinage = _Calepinage()
        calepinage.roof_layout = {'zones': []}
        leve = _Calepinage()
        leve.leve = True

        def producteur(c):
            calcul(c)
            c.roof_layout = {'zones': [{'id': 'A'}]}  # rebranché en mémoire
            calcul(c)
            for _ in range(2):
                with self.assertRaises(ValueError):
                    calcul(leve)
            return _ctrl('pans_vides', 'ok')

        service.agreger(calepinage, [producteur])
        self.assertEqual([a[0] for a in appels].count(calepinage), 2)
        self.assertEqual([a[0] for a in appels].count(leve), 1)  # relevé 2×

    def test_les_deux_fonctions_chaudes_sont_decorees(self):
        from apps.calepinage.services import electrique, equipements

        for fonction in (electrique.conception_du_calepinage,
                         equipements.equipements_du_calepinage):
            self.assertTrue(hasattr(fonction, '__wrapped__'), fonction)


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
        self.assertIsNone(reponse.data['etape'])
        self.assertEqual(Calepinage.objects.get(pk=calepinage.pk)
                         .updated_at, avant)

    def test_filtre_etape_et_etape_inconnue_400(self):
        # H3 — ``?etape=electrique`` : les seuls contrôles électriques.
        from apps.calepinage.models import Calepinage

        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-H3-ETAPE')
        url = f'{url_detail(calepinage.pk)}pret-a-envoyer/'
        reponse = self.api.get(url, {'etape': 'electrique'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etape'], 'electrique')
        codes = {c['code'] for c in reponse.data['controles']}
        self.assertIn('verdict_electrique', codes)
        self.assertNotIn('taille_sans_facture', codes)
        self.assertNotIn('visite_validee', codes)
        self.assertEqual(self.api.get(url, {'etape': 'plafond'}).status_code,
                         400)

    def test_conception_et_equipements_calcules_une_fois_par_lecture(self):
        # H5 — mutant : retirer ``une_fois_par_lecture`` ⇒ la conception
        # calculée 4-5 fois et les équipements 5-7 fois par lecture : échec.
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services import electrique, equipements

        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-H5-UNE-FOIS')
        url = f'{url_detail(calepinage.pk)}pret-a-envoyer/'
        conception = electrique.conception_du_calepinage
        agregat = equipements.equipements_du_calepinage
        with mock.patch.object(conception, '__wrapped__',
                               wraps=conception.__wrapped__) as calculs, \
                mock.patch.object(agregat, '__wrapped__',
                                  wraps=agregat.__wrapped__) as lectures:
            self.assertEqual(self.api.get(url).status_code, 200)
            premiere = (calculs.call_count, lectures.call_count)
            self.assertLessEqual(max(premiere), 1)
            self.assertEqual(self.api.get(url).status_code, 200)
            # une lecture neuve recalcule : rien n'est gardé d'une requête à l'autre
            self.assertEqual((calculs.call_count, lectures.call_count),
                             (2 * premiere[0], 2 * premiere[1]))

    def test_la_lecture_complete_range_son_verdict_le_filtre_non(self):
        """ACAL1333 — verdict rangé par la lecture complète seule, idempotent,
        sans toucher ``updated_at``."""
        from apps.calepinage.models import Calepinage

        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL1333',
            layout_hash='a' * 64)
        url = f'{url_detail(calepinage.pk)}pret-a-envoyer/'
        avant = calepinage.updated_at
        self.assertEqual(self.api.get(url, {'etape': 'electrique'}).status_code, 200)
        self.assertIsNone(Calepinage.objects.get(pk=calepinage.pk).dernier_verdict)

        reponse = self.api.get(url)

        self.assertEqual(reponse.status_code, 200, reponse.data)
        rangee = Calepinage.objects.get(pk=calepinage.pk)
        verdict = rangee.dernier_verdict
        self.assertEqual(
            (verdict['a_regler'], verdict['bloquants'], verdict['empreinte']),
            (reponse.data['nombre_a_regler'], reponse.data['nombre_bloquants'], 'a' * 64))
        self.assertTrue(verdict['lu_le'])
        self.assertEqual(rangee.updated_at, avant)
        # Relire le même document : aucune réécriture (même date de lecture).
        self.assertEqual(self.api.get(url).status_code, 200)
        self.assertEqual(Calepinage.objects.get(pk=calepinage.pk).dernier_verdict, verdict)
