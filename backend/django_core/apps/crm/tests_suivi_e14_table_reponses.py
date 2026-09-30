"""SUIVI E14 — les réponses servies suivent la TABLE du parcours, étape par
étape.

SUIVI-PARCOURS 30/09/2026 (ordre fondateur : « make sure we have the right set
of answers after each step »). ``suite_touche.cles_de_reponse`` ne
connaissait que la CADENCE : une étape « Décider la suite » recevait les
réponses d'un appel générique, un débrief de visite celles du suivi de
proposition. Désormais le TYPE d'étape est reconnu comme la table le
reconnaît (``type_etape`` : la clé moteur, puis le libellé, puis cadence +
canal) et les clés servies sont EXACTEMENT celles de la table
(``frontend/src/features/crm/relances/parcours_suivi.json``), dans son ordre,
suivies de « Sauter » hors des tâches.

Cette garde LIT la table et exige :

* chaque type de la table est reconnu (étape posée depuis la clé, étape
  posée avant la clé, libellés historiques, chaque cadence et chaque canal) ;
* ``cles_de_reponse`` == les clés de la table ;
* chaque clé a une promesse NON VIDE et chaque code sa phrase d'écran ;
* le serveur ACCEPTE chaque réponse qu'il sert (restrictions par cadence,
  par CLÉ d'étape et par CANAL de ``REPONSES_TOUCHE``).

Aucune base de données : ``SimpleTestCase``.
"""
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.crm import services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CADENCE_DE_LA_CLE
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, Cadence, barreau_par_defaut)

RACINE = Path(__file__).resolve().parents[4]
RELANCES = RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
TABLE = json.loads(
    (RELANCES / 'parcours_suivi.json').read_text(encoding='utf-8'))
PHRASES = json.loads(
    (RELANCES / 'suite_phrases.json').read_text(encoding='utf-8'))['effets']

_CANAUX_ECRITS = ('whatsapp', 'email')
_ISSUES = {cle for cle, _ in LeadActivity.OUTCOMES if cle}


def _cle_de_la_reponse(reponse):
    """La clé serveur d'une réponse de la table : sa ``reponse`` si elle en a
    une, sinon son issue (``''`` → ``sans_issue``) ; ``None`` pour un geste
    sans envoi (« la date est calée », « reportée à une autre date »)."""
    modele = dict(TABLE['modeles'][reponse['modele']])
    modele.update({k: v for k, v in reponse.items() if k != 'modele'})
    if modele.get('reponse'):
        return modele['reponse']
    if 'outcome' in modele:
        return modele['outcome'] or st.CLE_SANS_ISSUE
    return None


def _cles_de_la_table(etape_table, canal):
    cles = []
    reponses = list(etape_table['reponses'])
    if canal not in _CANAUX_ECRITS:
        reponses += [{'modele': m}
                     for m in etape_table.get('reponses_appel', ())]
    for reponse in reponses:
        cle = _cle_de_la_reponse(reponse)
        if cle is not None and cle not in cles:
            cles.append(cle)
    if not etape_table.get('tache'):
        cles.append(st.CLE_SAUTER)
    return cles


def _ordres(cadence):
    return sorted(e['ordre'] for e in CADENCES_DEFAUT.get(cadence, []))


def _stage(cadence, devis):
    if cadence == 'reveil':
        return stages.COLD
    return stages.QUOTE_SENT if devis else stages.CONTACTED


def _etape(cadence, ordre, canal, libelle, cle='', devis=False):
    etape = RelanceEtape(cadence=cadence, ordre=ordre, canal=canal,
                         libelle=libelle, cle=cle,
                         statut=RelanceEtape.Statut.A_FAIRE,
                         devis_id=903 if devis else None)
    etape.lead = Lead(nom='témoin', stage=_stage(cadence, devis))
    return etape


def _representants(etape_table):
    """Chaque forme réelle sous laquelle une étape de ce type existe."""
    reconnaissance = etape_table['reconnaissance']
    if 'cles' in reconnaissance:
        for cle in reconnaissance['cles']:
            gabarit = CADENCE_DE_LA_CLE[cle]
            defaut = barreau_par_defaut(gabarit, cle)
            visite = gabarit == Cadence.VISITE
            cadence = 'apres_devis' if visite else 'generique'
            ordre = services.VISITE_ORDRE_FILET if visite else 1
            canal = services._canal_configure(defaut)
            # Posée DEPUIS la clé, sous un libellé RENOMMÉ par la société…
            yield _etape(cadence, ordre, canal, 'Libellé renommé', cle=cle,
                         devis=visite)
            # … posée AVANT la clé, sous son libellé par défaut…
            yield _etape(cadence, ordre, canal, defaut['libelle'],
                         devis=visite)
            # … et sous chaque libellé historique que la table reconnaît.
            for libelle in reconnaissance.get('libelles', ()):
                yield _etape(cadence, ordre, canal, libelle, devis=visite)
        return
    if 'libelles' in reconnaissance:
        for libelle in reconnaissance['libelles']:
            yield _etape('generique', 1, 'appel', libelle, devis=True)
        return
    for cadence in reconnaissance['cadences']:
        canaux = reconnaissance.get('canaux') or ('appel', 'whatsapp')
        ordres = _ordres(cadence) or [1]
        for canal in canaux:
            # Une touche du milieu et la DERNIÈRE de la cadence.
            for ordre in sorted({ordres[0], ordres[-1]}):
                yield _etape(cadence, ordre, canal, 'Touche',
                             devis=cadence == 'apres_devis')


def _tous():
    for etape_table in TABLE['etapes']:
        for etape in _representants(etape_table):
            yield etape_table, etape


class TableEtMoteurTests(SimpleTestCase):

    def test_le_moteur_connait_chaque_type_de_la_table(self):
        ids = {e['id'] for e in TABLE['etapes']}
        self.assertEqual(set(st.REPONSES_PAR_TYPE), ids)
        self.assertEqual(
            set(st.TYPES_TACHE),
            {e['id'] for e in TABLE['etapes'] if e.get('tache')})

    def test_chaque_type_de_la_table_est_reconnu(self):
        for etape_table, etape in _tous():
            with self.subTest(type=etape_table['id'], cadence=etape.cadence,
                              canal=etape.canal, libelle=etape.libelle,
                              cle=etape.cle):
                self.assertEqual(st.type_etape(etape), etape_table['id'])

    def test_les_cles_servies_sont_celles_de_la_table(self):
        for etape_table, etape in _tous():
            with self.subTest(type=etape_table['id'], cadence=etape.cadence,
                              canal=etape.canal, ordre=etape.ordre):
                self.assertEqual(st.cles_de_reponse(etape),
                                 _cles_de_la_table(etape_table, etape.canal))

    def test_chaque_cle_a_une_promesse_et_chaque_code_sa_phrase(self):
        for etape_table, etape in _tous():
            promesses = st.promesses_touche(
                etape, ordres=frozenset(_ordres(etape.cadence)),
                est_actif=lambda cle: True)
            self.assertEqual(list(promesses), st.cles_de_reponse(etape))
            for cle, codes in promesses.items():
                with self.subTest(type=etape_table['id'], ordre=etape.ordre,
                                  canal=etape.canal, reponse=cle):
                    self.assertTrue(codes, 'réponse sans suite annoncée')
                    self.assertTrue(set(codes) <= set(PHRASES),
                                    f'code sans phrase : {codes}')

    def test_le_serveur_accepte_chaque_reponse_qu_il_sert(self):
        for etape_table, etape in _tous():
            for cle in st.cles_de_reponse(etape):
                with self.subTest(type=etape_table['id'], canal=etape.canal,
                                  reponse=cle):
                    if cle in services.REPONSES_TOUCHE:
                        self.assertIsNone(
                            services.refus_reponse_touche(etape, cle))
                    elif cle not in (st.CLE_SANS_ISSUE, st.CLE_SAUTER):
                        self.assertIn(cle, _ISSUES)

    def test_une_cadence_passee_en_chaine_reste_toleree(self):
        for cadence in ('contact', 'apres_devis', 'reveil', 'generique',
                        'deuxieme_affaire'):
            with self.subTest(cadence=cadence):
                self.assertEqual(
                    st.cles_de_reponse(cadence),
                    st.cles_de_reponse(RelanceEtape(
                        cadence=cadence, canal=RelanceEtape.Canal.APPEL)))


_SPEC_TEST = {'libelle': 'Réponse témoin', 'outcome': 'joint',
              'note': 'Réponse témoin', 'cadences': None, 'message': None}


class RestrictionsParCleEtParCanalTests(SimpleTestCase):
    """``refus_reponse_touche`` applique les deux bornes optionnelles de
    ``REPONSES_TOUCHE`` et son message NOMME la réponse (règle fondateur du
    08/09/2026 : jamais un refus générique)."""

    def test_une_reponse_bornee_a_une_cle_d_etape(self):
        spec = dict(_SPEC_TEST, cles=('decider_suite',))
        with mock.patch.dict(services.REPONSES_TOUCHE, {'temoin': spec}):
            decider = _etape('generique', 1, 'appel', '', cle='decider_suite')
            self.assertIsNone(services.refus_reponse_touche(decider, 'temoin'))
            devis = _etape('generique', 1, 'appel', '', cle='devis')
            refus = services.refus_reponse_touche(devis, 'temoin')
        self.assertIn('« Réponse témoin »', refus)
        self.assertIn('Décider la suite', refus)

    def test_une_reponse_bornee_a_des_canaux(self):
        spec = dict(_SPEC_TEST, canaux=('whatsapp', 'email'))
        with mock.patch.dict(services.REPONSES_TOUCHE, {'temoin': spec}):
            message = _etape('contact', 1, 'whatsapp', 'Touche')
            self.assertIsNone(services.refus_reponse_touche(message, 'temoin'))
            appel = _etape('contact', 2, 'appel', 'Touche')
            refus = services.refus_reponse_touche(appel, 'temoin')
        self.assertIn('« Réponse témoin »', refus)
        self.assertIn('WhatsApp', refus)
