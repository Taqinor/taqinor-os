"""CAD17 — LA GARDE : chaque promesse d'écran a un effet serveur correspondant.

La cause commune de CAD1, CAD3, CAD16 et CAD97 : les phrases « suite » du
panneau « Fait » étaient écrites PAR CADENCE, à l'écran, alors que le moteur
se comporte selon le LIBELLÉ de la touche, son RANG et l'état du devis — et
aucun test ne confrontait une promesse à l'effet réel. La promesse est
désormais DÉRIVÉE du moteur (``apps/crm/suite_touche.py``) et servie avec la
touche (``suites`` du contrat ``relance_etape_v2``) ; l'écran ne fait que
traduire chaque code en une phrase (``suite_phrases.json``).

Ce module verrouille trois choses :

1. **le vocabulaire est UN** : les codes du serveur, les phrases de l'écran
   et les vérificateurs de ce test sont le même ensemble ;
2. **le contrat committé est ce que le moteur annonce** (PACT10 — le test
   front ``suite.test.jsx`` IMPORTE ce même exemple) ;
3. **LA GARDE** : pour chaque cadence, chaque nature et chaque rang de touche,
   chaque réponse annoncée est REJOUÉE par l'API réelle, et l'effet de chaque
   code est constaté en base. Les codes conditionnels (« si le suivi d'un devis
   envoyé n'est pas allé au bout… », « si c'était la dernière relance
   ouverte… », « au-delà d'un mois… ») sont rejoués dans CHACUNE de leurs
   branches.

Un code sans effet correspondant — le cinquième mensonge d'écran — casse ce
test au prochain drain.

Temps gelé : mercredi 23/09/2026, 10 h à Casablanca (jour ouvré, fenêtre
d'appel ouverte ; « demain » est le jeudi 24/09, la date de rappel choisie le
lundi 28/09 à 11 h).
"""
import datetime
import itertools
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm import suite_touche as st
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import (
    _LIBELLES_FILET, _LIBELLES_VISITE, FILET_APPEL_LIBELLE,
    FILET_DERNIER_APPEL_LIBELLE, FILET_JOINT_LIBELLE,
    FILET_MESSAGE_CRENEAU_LIBELLE, FILET_REFUS_LIBELLE, PASSATION_LIBELLE,
    PASSATION_ORDRE, QUESTION_PRIX_LIBELLE, REPONSES_TOUCHE,
    TAG_DECISION_A_PLUSIEURS, VISITE_CONFIRMATION_LIBELLE,
    VISITE_DEBRIEF_LIBELLE, VISITE_DEVIS_LIBELLE, VISITE_FILET_LIBELLE,
    VISITE_ORDRE_CONFIRMATION, VISITE_ORDRE_DEBRIEF, _lead_porte_tag)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca.
GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = datetime.date(2026, 9, 23)
DEMAIN = datetime.date(2026, 9, 24)
#: La date choisie dans « À rappeler le… » / « Plus tard » — un lundi, dans
#: la fenêtre d'appel : jamais recalée.
DATE_CHOISIE = datetime.date(2026, 9, 28)
HEURE_CHOISIE = '11:00'
#: « Plus tard » au-delà d'un mois (bascule en réveil daté) — un lundi.
DATE_LOINTAINE = datetime.date(2026, 11, 9)

RACINE = Path(__file__).resolve().parents[4]
TABLE_ECRAN = json.loads(
    (RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
     / 'suite_phrases.json').read_text(encoding='utf-8'))
PHRASES = TABLE_ECRAN['effets']
#: CAD15 — les effets d'une issue journalisée depuis la fiche, tels que
#: l'écran du journal d'appel les annonce.
JOURNAL_ECRAN = TABLE_ECRAN['journal']
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'relance_etape_v2.json').read_text(encoding='utf-8'))

A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
APPEL = RelanceEtape.Canal.APPEL
WHATSAPP = RelanceEtape.Canal.WHATSAPP

# ── La grille : chaque cadence, chaque nature, chaque rang ──────────────────

SIMPLE = 'simple'
#: Une touche posée À CÔTÉ du plan (visite, passation) : sa suite dépend de ce
#: qui reste ouvert à côté d'elle.
A_COTE = 'a_cote'


@dataclass(frozen=True)
class Scenario:
    nom: str
    cadence: str
    ordre: int
    canal: str
    libelle: str = ''         # '' : le libellé du barreau du gabarit
    devis: bool = False       # la touche porte-t-elle un devis ?
    stage: str = stages.CONTACTED
    famille: str = SIMPLE


SCENARIOS = (
    # Prise de contact (11 barreaux) : message, appel, dernière touche.
    Scenario('contact_message', 'contact', 1, WHATSAPP),
    Scenario('contact_appel', 'contact', 2, APPEL),
    Scenario('contact_derniere_message', 'contact', 11, WHATSAPP),
    Scenario('contact_derniere_appel', 'contact', 11, APPEL),
    # Suivi de proposition (10 barreaux), avec et sans devis dans l'ERP.
    Scenario('apres_devis_message', 'apres_devis', 1, WHATSAPP,
             devis=True, stage=stages.QUOTE_SENT),
    Scenario('apres_devis_appel', 'apres_devis', 2, APPEL,
             devis=True, stage=stages.QUOTE_SENT),
    Scenario('apres_devis_derniere_message', 'apres_devis', 10, WHATSAPP,
             devis=True, stage=stages.QUOTE_SENT),
    Scenario('apres_devis_derniere_appel', 'apres_devis', 10, APPEL,
             devis=True, stage=stages.QUOTE_SENT),
    Scenario('apres_devis_sans_devis', 'apres_devis', 2, APPEL,
             stage=stages.QUOTE_SENT),
    Scenario('apres_devis_sans_devis_derniere', 'apres_devis', 10, WHATSAPP,
             stage=stages.QUOTE_SENT),
    # Les gestes de visite (cadence après-devis, hors protocole).
    Scenario('visite_confirmation', 'apres_devis', VISITE_ORDRE_CONFIRMATION,
             WHATSAPP, VISITE_CONFIRMATION_LIBELLE, devis=True,
             stage=stages.QUOTE_SENT, famille=A_COTE),
    Scenario('visite_debrief', 'apres_devis', VISITE_ORDRE_DEBRIEF, APPEL,
             VISITE_DEBRIEF_LIBELLE, devis=True, stage=stages.QUOTE_SENT,
             famille=A_COTE),
    # Réveils (2 barreaux, posés ensemble) : au Froid, et hors Froid (veille
    # de plus d'un mois basculée en réveil daté, CAD26).
    Scenario('reveil_appel', 'reveil', 1, APPEL, stage=stages.COLD),
    Scenario('reveil_dernier', 'reveil', 2, WHATSAPP, stage=stages.COLD),
    Scenario('reveil_dernier_hors_froid', 'reveil', 2, WHATSAPP),
    # Cadence générique : un barreau, le dernier, et les étapes de filet.
    Scenario('generique_barreau', 'generique', 1, APPEL),
    Scenario('generique_dernier', 'generique', 5, APPEL),
    Scenario('filet_envoi_devis', 'generique', 1, APPEL, FILET_JOINT_LIBELLE),
    Scenario('filet_appeler', 'generique', 1, APPEL, FILET_APPEL_LIBELLE),
    Scenario('filet_creneau', 'generique', 1, WHATSAPP,
             FILET_MESSAGE_CRENEAU_LIBELLE),
    Scenario('filet_decider', 'generique', 1, APPEL, FILET_REFUS_LIBELLE),
    Scenario('filet_question_prix', 'generique', 1, APPEL,
             QUESTION_PRIX_LIBELLE, stage=stages.QUOTE_SENT),
    Scenario('filet_passation', 'generique', PASSATION_ORDRE, WHATSAPP,
             PASSATION_LIBELLE, stage=stages.QUOTE_SENT, famille=A_COTE),
    # Deuxième affaire (2 barreaux) : un client déjà acquis qui revient.
    Scenario('deuxieme_message', 'deuxieme_affaire', 1, WHATSAPP,
             stage=stages.NEW),
    Scenario('deuxieme_appel', 'deuxieme_affaire', 2, APPEL,
             stage=stages.NEW),
)

#: Les branches rejouées pour chaque code CONDITIONNEL. Tout code absent ne
#: se rejoue qu'une fois (« base »).
BRANCHES_SUIVI = ('base', 'devis_ouvert', 'devis_epuise')
VARIANTES = {
    st.ETAPE_APPELER_SAUF_SUIVI: BRANCHES_SUIVI,
    st.ETAPE_DEVIS_DEMAIN_SAUF_SUIVI: BRANCHES_SUIVI,
    st.ETAPE_DEVIS_A_LA_DATE_SAUF_SUIVI: BRANCHES_SUIVI,
    st.VISITE_FROID_SI_SEULE: ('base', 'avec_autre'),
    st.SUITE_SI_PLUS_RIEN_OUVERT: ('base', 'avec_autre', 'seule_epuise'),
    st.PROCHAINE_RELANCE_A_LA_DATE: ('base', 'avec_autre'),
    st.VEILLE_MEME_TOUCHE: ('base', 'loin'),
    # CAD15 — le journal d'appel : la suite dépend de ce qui reste ouvert et
    # de l'étape du dossier (Froid ou non).
    st.JOURNAL_SUITE_SI_RIEN_OUVERT: ('base', 'avec_autre', 'froid'),
    st.JOURNAL_DECIDER_SI_RIEN_OUVERT: ('base', 'froid', 'generique_ouverte'),
}


def _ordres_defaut(cadence):
    return frozenset(e['ordre'] for e in CADENCES_DEFAUT.get(cadence, []))


def _libelle_du_gabarit(scenario):
    if scenario.libelle:
        return scenario.libelle
    for entree in CADENCES_DEFAUT.get(scenario.cadence, []):
        if entree['ordre'] == scenario.ordre:
            return entree['libelle']
    return ''


def _etape_non_enregistree(scenario):
    """La touche du scénario, SANS base : pour les contrôles purs."""
    etape = RelanceEtape(
        cadence=scenario.cadence, ordre=scenario.ordre, canal=scenario.canal,
        libelle=_libelle_du_gabarit(scenario), statut=A_FAIRE,
        devis_id=903 if scenario.devis else None)
    etape.lead = Lead(nom='témoin', stage=scenario.stage)
    return etape


# ── Les vérificateurs : un par code ─────────────────────────────────────────


@dataclass
class Constat:
    """Ce que le test constate APRÈS avoir rejoué une réponse."""
    test: TestCase
    scenario: Scenario
    variante: str
    lead: Lead
    etape: RelanceEtape       # None pour le journal d'appel (aucune touche)
    avant: frozenset          # les touches ouvertes AVANT, hors la touche
    donnees: dict             # la réponse de l'API

    def ouvertes(self, **filtres):
        return self.lead.relance_etapes.filter(statut=A_FAIRE, **filtres)

    def nouvelles(self, **filtres):
        qs = self.ouvertes(**filtres).exclude(pk__in=self.avant)
        if self.etape is not None:
            qs = qs.exclude(pk=self.etape.pk)
        return qs

    def barreaux(self, qs):
        return (qs.filter(ordre__lt=90)
                .exclude(libelle__in=tuple(_LIBELLES_FILET | _LIBELLES_VISITE)))

    def vrai(self, condition, message):
        self.test.assertTrue(
            condition,
            f'{self.scenario.nom} [{self.variante}] : {message} — touches '
            f'ouvertes : {list(self.ouvertes().values_list("cadence", "ordre", "libelle", "due_date"))}, '
            f'étape du lead : {self.lead.stage}')


def _touche_suivante(c):
    c.vrai(c.barreaux(c.ouvertes(cadence=c.etape.cadence,
                                 ordre__gt=c.etape.ordre)).exists(),
           'aucune touche suivante ouverte dans la cadence')


def _touche_suivante_a_la_date(c):
    c.vrai(c.barreaux(c.ouvertes(cadence=c.etape.cadence,
                                 ordre__gt=c.etape.ordre,
                                 due_date=DATE_CHOISIE)).exists(),
           'la touche suivante n’est pas à la date choisie')


def _derniere_froid_reveils(c):
    c.vrai(c.lead.stage == stages.COLD, 'le dossier n’est pas au Froid')
    c.vrai(c.ouvertes(cadence='reveil').exists(), 'aucun réveil programmé')


def _dernier_reveil(c):
    c.vrai(c.lead.stage == stages.COLD, 'le dossier n’est plus au Froid')
    c.vrai(not c.ouvertes().exists(), 'une relance reste programmée')


def _dernier_reveil_date_perdue(c):
    _dernier_reveil(c)
    c.vrai(c.donnees.get('prochaine_touche') is None,
           'une prochaine touche est annoncée')


def _reste_au_froid(c):
    c.vrai(c.lead.stage == stages.COLD, 'le dossier n’est plus au Froid')


def _sort_du_froid(c):
    c.vrai(c.lead.stage != stages.COLD, 'le dossier est resté au Froid')


def _contact_arretee(c):
    c.vrai(not c.ouvertes(cadence='contact').exists(),
           'la prise de contact continue')


def _reveils_arretes(c):
    c.vrai(not c.ouvertes(cadence='reveil').exists(),
           'un réveil reste programmé')


def _relances_arretees(c):
    c.vrai(not c.ouvertes(
        cadence__in=('contact', 'apres_devis', 'reveil')).exists(),
        'une relance de contact, de proposition ou de réveil continue')


def _etape_appeler(c):
    c.vrai(c.ouvertes(libelle=FILET_APPEL_LIBELLE).exists(),
           'aucune étape « appeler le client »')


def _etape_devis_demain(c):
    c.vrai(c.ouvertes(libelle=FILET_JOINT_LIBELLE, due_date=DEMAIN).exists(),
           'aucune étape « préparer et envoyer le devis » demain')


def _suivi_repris(c):
    c.vrai(c.barreaux(c.nouvelles(cadence='apres_devis')).exists(),
           'le suivi de proposition n’a pas repris')


def _etape_appeler_sauf_suivi(c):
    if c.variante == 'devis_ouvert':
        _suivi_repris(c)
        c.vrai(not c.ouvertes(libelle=FILET_APPEL_LIBELLE).exists(),
               'une étape « appeler » est posée malgré le suivi repris')
    else:
        _etape_appeler(c)


def _etape_devis_demain_sauf_suivi(c):
    if c.variante == 'devis_ouvert':
        _suivi_repris(c)
        c.vrai(not c.ouvertes(libelle=FILET_JOINT_LIBELLE).exists(),
               'une étape « préparer le devis » est posée malgré le suivi')
    else:
        _etape_devis_demain(c)


def _etape_devis_a_la_date(c):
    c.vrai(c.ouvertes(libelle=FILET_JOINT_LIBELLE,
                      due_date=DATE_CHOISIE).exists(),
           'aucune étape « préparer et envoyer le devis » à la date choisie')


def _etape_devis_a_la_date_sauf_suivi(c):
    if c.variante == 'devis_ouvert':
        c.vrai(c.barreaux(c.ouvertes(cadence='apres_devis',
                                     due_date=DATE_CHOISIE)).exists(),
               'le suivi repris n’est pas à la date choisie')
    else:
        _etape_devis_a_la_date(c)


def _etape_decider_suite(c):
    c.vrai(c.ouvertes(libelle=FILET_REFUS_LIBELLE).exists(),
           'aucune étape « décider la suite »')


def _etape_deplacee_a_la_date(c):
    c.vrai(c.etape.statut == A_FAIRE, 'l’étape a été consommée')
    c.vrai(c.etape.due_date == DATE_CHOISIE,
           'l’étape n’est pas à la date choisie')


def _suivi_proposition_demarre(c):
    c.vrai(c.ouvertes(cadence='apres_devis').exists(),
           'le suivi de proposition n’a pas démarré')
    c.vrai(c.lead.stage == stages.QUOTE_SENT,
           'le dossier n’est pas « Devis envoyé »')


def _etape_planifier_visite(c):
    c.vrai(c.ouvertes(libelle=VISITE_FILET_LIBELLE,
                      due_date=AUJOURDHUI).exists(),
           'aucune étape « planifier la visite » aujourd’hui')
    c.vrai(not c.barreaux(c.nouvelles(cadence='apres_devis')).exists(),
           'une relance du protocole a été posée')


def _etape_message_creneau(c):
    c.vrai(c.ouvertes(libelle=FILET_MESSAGE_CRENEAU_LIBELLE).exists(),
           'aucune étape « message pour convenir d’un créneau »')


def _etape_dernier_appel(c):
    c.vrai(c.ouvertes(libelle=FILET_DERNIER_APPEL_LIBELLE,
                      due_date=DEMAIN).exists(),
           'aucun dernier appel demain')


def _rien_de_nouveau(c):
    c.vrai(not c.nouvelles().exists(), 'une touche a été ajoutée')


def _visite_froid_si_seule(c):
    if c.variante == 'avec_autre':
        c.vrai(c.lead.stage != stages.COLD, 'le dossier est parti au Froid')
        _rien_de_nouveau(c)
    else:
        _derniere_froid_reveils(c)


def _suite_si_plus_rien_ouvert(c):
    if c.variante == 'avec_autre':
        _rien_de_nouveau(c)
    elif c.variante == 'seule_epuise':
        c.vrai(c.nouvelles(cadence='generique').exists(),
               'aucune étape de suite posée')
    else:
        _suivi_repris(c)


def _prochaine_relance_a_la_date(c):
    c.vrai(c.ouvertes(due_date=DATE_CHOISIE).exists(),
           'aucune relance à la date choisie')


def _etiquette_decision(c):
    c.vrai(_lead_porte_tag(c.lead, TAG_DECISION_A_PLUSIEURS),
           'l’étiquette « Décision à plusieurs » manque')


def _ne_plus_contacter(c):
    c.vrai(c.lead.ne_plus_contacter, 'la case « ne plus contacter » manque')
    c.vrai(not c.ouvertes().exists(), 'une relance reste programmée')


def _veille_meme_touche(c):
    if c.variante == 'loin':
        c.vrai(c.etape.statut == RelanceEtape.Statut.ANNULEE,
               'la cadence n’est pas arrêtée')
        c.vrai(c.ouvertes(cadence='reveil').exists(), 'aucun réveil daté')
        return
    c.vrai(c.etape.statut == A_FAIRE, 'la touche a été consommée')
    c.vrai(c.etape.due_date == DATE_CHOISIE,
           'la touche n’est pas à la date convenue')
    c.vrai(not c.ouvertes(due_date__lt=DATE_CHOISIE).exists(),
           'une relance part avant la date convenue')


def _question_prix(c):
    c.vrai(c.ouvertes(libelle=QUESTION_PRIX_LIBELLE, due_date=DEMAIN).exists(),
           'aucune étape « question de prix » demain')


def _question_prix_pause(c):
    _question_prix(c)
    c.vrai(set(c.nouvelles().values_list('libelle', flat=True))
           == {QUESTION_PRIX_LIBELLE}, 'une autre relance a été posée')


def _etape_devis_modifie(c):
    c.vrai(c.ouvertes(libelle=VISITE_DEVIS_LIBELLE, due_date=DEMAIN).exists(),
           'aucune étape « devis modifié » demain')
    c.vrai(set(c.nouvelles().values_list('libelle', flat=True))
           == {VISITE_DEVIS_LIBELLE}, 'une touche suivante est née')


# CAD15 — le journal d'appel de la fiche (aucune touche close).

def _journal_suite_si_rien_ouvert(c):
    c.vrai(c.lead.stage != stages.COLD, 'le dossier est resté au Froid')
    if c.variante == 'avec_autre':
        _rien_de_nouveau(c)
    else:
        c.vrai(c.nouvelles().exists(), 'aucune étape de suite posée')


def _journal_decider_si_rien_ouvert(c):
    if c.variante == 'base':
        _etape_decider_suite(c)
        return
    c.vrai(not c.ouvertes(libelle=FILET_REFUS_LIBELLE).exists(),
           'une étape « décider la suite » est posée malgré tout')
    if c.variante == 'froid':
        _reste_au_froid(c)
    else:
        _rien_de_nouveau(c)


def _journal_sans_effet(c):
    c.vrai(set(c.ouvertes().values_list('pk', flat=True)) == set(c.avant),
           'une relance a été ajoutée ou arrêtée')


VERIFICATEURS = {
    st.TOUCHE_SUIVANTE: _touche_suivante,
    st.TOUCHE_SUIVANTE_A_LA_DATE: _touche_suivante_a_la_date,
    st.DERNIERE_FROID_REVEILS: _derniere_froid_reveils,
    st.DERNIER_REVEIL: _dernier_reveil,
    st.DERNIER_REVEIL_DATE_PERDUE: _dernier_reveil_date_perdue,
    st.RESTE_AU_FROID: _reste_au_froid,
    st.SORT_DU_FROID: _sort_du_froid,
    st.CONTACT_ARRETEE: _contact_arretee,
    st.REVEILS_ARRETES: _reveils_arretes,
    st.RELANCES_ARRETEES: _relances_arretees,
    st.ETAPE_APPELER: _etape_appeler,
    st.ETAPE_DEVIS_DEMAIN: _etape_devis_demain,
    st.ETAPE_APPELER_SAUF_SUIVI: _etape_appeler_sauf_suivi,
    st.ETAPE_DEVIS_DEMAIN_SAUF_SUIVI: _etape_devis_demain_sauf_suivi,
    st.ETAPE_DEVIS_A_LA_DATE: _etape_devis_a_la_date,
    st.ETAPE_DEVIS_A_LA_DATE_SAUF_SUIVI: _etape_devis_a_la_date_sauf_suivi,
    st.ETAPE_DECIDER_SUITE: _etape_decider_suite,
    st.ETAPE_DEPLACEE_A_LA_DATE: _etape_deplacee_a_la_date,
    st.SUIVI_PROPOSITION_DEMARRE: _suivi_proposition_demarre,
    st.ETAPE_PLANIFIER_VISITE: _etape_planifier_visite,
    st.ETAPE_MESSAGE_CRENEAU: _etape_message_creneau,
    st.ETAPE_DERNIER_APPEL: _etape_dernier_appel,
    st.VISITE_FROID_SI_SEULE: _visite_froid_si_seule,
    st.SUITE_SI_PLUS_RIEN_OUVERT: _suite_si_plus_rien_ouvert,
    st.PROCHAINE_RELANCE_A_LA_DATE: _prochaine_relance_a_la_date,
    st.ETIQUETTE_DECISION: _etiquette_decision,
    st.NE_PLUS_CONTACTER: _ne_plus_contacter,
    st.VEILLE_MEME_TOUCHE: _veille_meme_touche,
    st.QUESTION_PRIX_PAUSE: _question_prix_pause,
    st.QUESTION_PRIX_ETAPE: _question_prix,
    st.ETAPE_DEVIS_MODIFIE: _etape_devis_modifie,
    st.JOURNAL_SUITE_SI_RIEN_OUVERT: _journal_suite_si_rien_ouvert,
    st.JOURNAL_DECIDER_SI_RIEN_OUVERT: _journal_decider_si_rien_ouvert,
    st.JOURNAL_SANS_EFFET: _journal_sans_effet,
}


# ── 1. Le vocabulaire est UN ────────────────────────────────────────────────

class VocabulaireTests(SimpleTestCase):

    def test_codes_phrases_et_verificateurs_sont_le_meme_ensemble(self):
        self.assertEqual(set(PHRASES), set(st.CODES),
                         'une phrase d’écran sans code serveur, ou l’inverse')
        self.assertEqual(set(VERIFICATEURS), set(st.CODES),
                         'un code sans vérificateur — une promesse non gardée')

    def test_chaque_code_est_produit_par_la_grille(self):
        # Un code que la grille ne produit jamais ne serait jamais rejoué :
        # sa promesse échapperait à la garde.
        produits = set()
        for scenario in SCENARIOS:
            promesses = st.promesses_touche(
                _etape_non_enregistree(scenario),
                ordres=_ordres_defaut(scenario.cadence))
            for codes in promesses.values():
                produits.update(codes)
        for codes in st.promesses_journal().values():
            produits.update(codes)
        self.assertEqual(produits, set(st.CODES))

    def test_le_journal_de_l_ecran_est_le_calcul_du_moteur(self):
        # CAD15 — la table committée côté écran (journal d'appel) est ÉGALE
        # à la dérivation serveur : jamais deux listes qui divergent.
        self.assertEqual(JOURNAL_ECRAN, st.promesses_journal())

    def test_chaque_reponse_proposee_a_sa_promesse(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.nom):
                promesses = st.promesses_touche(
                    _etape_non_enregistree(scenario),
                    ordres=_ordres_defaut(scenario.cadence))
                self.assertEqual(list(promesses),
                                 st.cles_de_reponse(scenario.cadence))
                for cle, codes in promesses.items():
                    self.assertTrue(codes, f'{scenario.nom} : « {cle} » '
                                           'n’annonce aucune suite')

    def test_une_touche_traitee_n_annonce_plus_rien(self):
        etape = _etape_non_enregistree(SCENARIOS[0])
        etape.statut = FAIT
        self.assertEqual(st.promesses_touche(etape, ordres=frozenset()), {})


# ── 2. Le contrat committé est ce que le moteur annonce ─────────────────────

#: Les touches committées dans le contrat : l'exemple principal ET l'état
#: « dernier réveil » (CAD16), que l'écran importe tous deux.
TOUCHES_DU_CONTRAT = (CONTRAT['exemple']['results']
                      + CONTRAT['exemple_dernier_reveil']['results'])


def _stage_du_contrat(resultat):
    """L'étape du dossier de chaque touche committée : un réveil vit au Froid,
    un suivi de proposition après un envoi, le reste en prise de contact."""
    if resultat['cadence'] == 'reveil':
        return stages.COLD
    if resultat['devis'] is not None:
        return stages.QUOTE_SENT
    return stages.CONTACTED


class ContratTests(SimpleTestCase):

    def test_l_exemple_committe_est_ce_que_le_moteur_annonce(self):
        for resultat in TOUCHES_DU_CONTRAT:
            with self.subTest(touche=resultat['id']):
                etape = RelanceEtape(
                    cadence=resultat['cadence'], ordre=resultat['ordre'],
                    canal=resultat['canal'], libelle=resultat['libelle'],
                    statut=resultat['statut'], devis_id=resultat['devis'])
                etape.lead = Lead(nom=resultat['lead_nom'],
                                  stage=_stage_du_contrat(resultat))
                self.assertEqual(
                    st.promesses_touche(
                        etape, ordres=_ordres_defaut(resultat['cadence'])),
                    resultat['suites'])

    def test_chaque_code_de_l_exemple_a_sa_phrase(self):
        for resultat in TOUCHES_DU_CONTRAT:
            for codes in resultat['suites'].values():
                self.assertTrue(set(codes) <= set(PHRASES))

    def test_l_etat_dernier_reveil_a_la_forme_de_l_exemple(self):
        # Un AUTRE état du serveur, jamais une autre forme (PACT10).
        forme = set(CONTRAT['exemple']['results'][0])
        for resultat in CONTRAT['exemple_dernier_reveil']['results']:
            self.assertEqual(set(resultat), forme)

    def test_cad16_le_dernier_reveil_annonce_la_fin(self):
        # CAD16 — sur la touche de rang 2 du réveil, « Pas de réponse »
        # n'annonce plus de réveil suivant : la fin, et le Froid.
        [dernier] = CONTRAT['exemple_dernier_reveil']['results']
        self.assertEqual(dernier['ordre'], max(_ordres_defaut('reveil')))
        self.assertEqual(dernier['suites']['non_joint'], [st.DERNIER_REVEIL])
        self.assertNotIn(st.TOUCHE_SUIVANTE, dernier['suites']['non_joint'])


# ── 3. LA GARDE : chaque promesse est rejouée et son effet constaté ────────

_compteur = itertools.count(1)


class PariteBase(TestCase):
    slug = 'cad17'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        # Comme en production : les gabarits existent (seedés au premier
        # usage) — la lecture des barreaux actifs lit donc la vraie table.
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)

    # ── fabrique ──

    def _lead(self, scenario):
        n = next(_compteur)
        return Lead.objects.create(
            company=self.company, nom=f'CAD17 {scenario.nom} {n}',
            stage=scenario.stage, owner=self.acteur,
            telephone=f'+21266{n:07d}')

    def _devis(self, lead):
        n = next(_compteur)
        client = Client.objects.create(
            company=self.company, nom=f'Client CAD17 {n}',
            email=f'cad17-{n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-CAD17-{n:05d}',
            client=client, lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=7))

    def _touche(self, lead, *, cadence, ordre, canal, libelle, devis=None,
                statut=A_FAIRE, due=None, depart=None):
        due = due or GEL
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=canal, libelle=libelle, devis=devis, statut=statut,
            due_at=due, due_date=due.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=depart,
            traite_par=None if statut == A_FAIRE else self.acteur,
            traite_le=None if statut == A_FAIRE else due)

    def _suivi_consomme(self, lead, devis, ordre):
        """Un suivi de proposition dont le barreau ``ordre`` est CONSOMMÉ."""
        gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                       if e['ordre'] == ordre)
        self._touche(lead, cadence='apres_devis', ordre=ordre,
                     canal=gabarit['canal'], libelle=gabarit['libelle'],
                     devis=devis, statut=FAIT,
                     due=GEL - datetime.timedelta(days=5),
                     depart=GEL - datetime.timedelta(days=7))

    def _fabriquer(self, scenario, variante):
        """Le lead et la touche du scénario, dans la branche ``variante``."""
        lead = self._lead(scenario)
        devis = None
        if scenario.devis or scenario.famille == A_COTE or variante in (
                'devis_ouvert', 'devis_epuise'):
            devis = self._devis(lead)
        if scenario.famille == A_COTE:
            self._suivi_consomme(
                lead, devis, 10 if variante == 'seule_epuise' else 2)
            if variante == 'avec_autre':
                # Le plan suspendu pendant la visite : une touche ouverte.
                gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                               if e['ordre'] == 4)
                self._touche(lead, cadence='apres_devis', ordre=4,
                             canal=gabarit['canal'],
                             libelle=gabarit['libelle'], devis=devis,
                             due=GEL + datetime.timedelta(days=2),
                             depart=GEL - datetime.timedelta(days=7))
        elif variante == 'devis_ouvert':
            self._suivi_consomme(lead, devis, 2)
        elif variante == 'devis_epuise':
            self._suivi_consomme(lead, devis, 10)

        barreau = st.nature_touche(RelanceEtape(
            cadence=scenario.cadence,
            libelle=_libelle_du_gabarit(scenario))) == st.NATURE_BARREAU
        depart = None
        if barreau:
            depart = (GEL - datetime.timedelta(days=30)
                      if scenario.cadence == 'reveil' else GEL)
        if scenario.cadence == 'reveil':
            # Les deux réveils naissent ENSEMBLE (cadence non réactive) : la
            # touche 1 ouverte a sa sœur ouverte ; la touche 2, sa sœur close.
            autre = 2 if scenario.ordre == 1 else 1
            gabarit = next(e for e in CADENCES_DEFAUT['reveil']
                           if e['ordre'] == autre)
            self._touche(
                lead, cadence='reveil', ordre=autre, canal=gabarit['canal'],
                libelle=gabarit['libelle'],
                statut=A_FAIRE if autre == 2 else FAIT,
                due=(GEL + datetime.timedelta(days=30) if autre == 2
                     else GEL - datetime.timedelta(days=30)),
                depart=depart)
        etape = self._touche(
            lead, cadence=scenario.cadence, ordre=scenario.ordre,
            canal=scenario.canal, libelle=_libelle_du_gabarit(scenario),
            devis=devis if (scenario.devis or scenario.famille == A_COTE
                            and scenario.cadence == 'apres_devis') else None,
            depart=depart)
        return lead, etape

    # ── rejeu ──

    def _promesses_servies(self, scenario):
        """Ce que l'écran LIT pour ce scénario : ``suites`` servie par l'API."""
        lead, etape = self._fabriquer(scenario, 'base')
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/?lead={lead.pk}')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(r for r in resp.data['results'] if r['id'] == etape.pk)
        self.assertEqual(list(ligne['suites']),
                         st.cles_de_reponse(scenario.cadence), scenario.nom)
        return ligne['suites']

    def _rejouer(self, etape, cle, variante):
        corps = {}
        if cle in REPONSES_TOUCHE:
            corps['reponse'] = cle
        elif cle != st.CLE_SANS_ISSUE:
            corps['outcome'] = cle
        if cle == 'rappel':
            corps['rappel_le'] = DATE_CHOISIE.isoformat()
            corps['rappel_heure'] = HEURE_CHOISIE
        if cle == 'plus_tard':
            corps['rappel_le'] = (DATE_LOINTAINE if variante == 'loin'
                                  else DATE_CHOISIE).isoformat()
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _garder(self, *noms):
        for scenario in SCENARIOS:
            if scenario.nom not in noms:
                continue
            promesses = self._promesses_servies(scenario)
            for cle, codes in promesses.items():
                variantes = []
                for code in codes:
                    for variante in VARIANTES.get(code, ('base',)):
                        if variante not in variantes:
                            variantes.append(variante)
                for variante in variantes:
                    with self.subTest(scenario=scenario.nom, reponse=cle,
                                      variante=variante):
                        lead, etape = self._fabriquer(scenario, variante)
                        avant = frozenset(
                            lead.relance_etapes.filter(statut=A_FAIRE)
                            .exclude(pk=etape.pk).values_list('pk', flat=True))
                        resp = self._rejouer(etape, cle, variante)
                        self.assertEqual(resp.status_code, 200, resp.data)
                        lead.refresh_from_db()
                        etape.refresh_from_db()
                        constat = Constat(
                            test=self, scenario=scenario, variante=variante,
                            lead=lead, etape=etape, avant=avant,
                            donnees=resp.data)
                        for code in codes:
                            if variante in VARIANTES.get(code, ('base',)):
                                VERIFICATEURS[code](constat)


class PariteContactTests(PariteBase):
    slug = 'cad17-contact'

    def test_prise_de_contact(self):
        self._garder('contact_message', 'contact_appel',
                     'contact_derniere_message', 'contact_derniere_appel')


class PariteSuiviPropositionTests(PariteBase):
    slug = 'cad17-proposition'

    def test_suivi_de_proposition(self):
        self._garder('apres_devis_message', 'apres_devis_appel',
                     'apres_devis_derniere_message',
                     'apres_devis_derniere_appel', 'apres_devis_sans_devis',
                     'apres_devis_sans_devis_derniere')


class PariteVisiteTests(PariteBase):
    slug = 'cad17-visite'

    def test_gestes_de_visite(self):
        self._garder('visite_confirmation', 'visite_debrief')


class PariteReveilTests(PariteBase):
    slug = 'cad17-reveil'

    def test_reveils(self):
        self._garder('reveil_appel', 'reveil_dernier',
                     'reveil_dernier_hors_froid')


class PariteGeneriqueTests(PariteBase):
    slug = 'cad17-generique'

    def test_cadence_generique_et_filets(self):
        self._garder('generique_barreau', 'generique_dernier',
                     'filet_envoi_devis', 'filet_appeler', 'filet_creneau',
                     'filet_decider', 'filet_question_prix',
                     'filet_passation')


class PariteDeuxiemeAffaireTests(PariteBase):
    slug = 'cad17-deuxieme'

    def test_deuxieme_affaire(self):
        self._garder('deuxieme_message', 'deuxieme_appel')


class PariteJournalTests(PariteBase):
    """CAD15 — le journal d'appel de la fiche : chaque issue est rejouée par
    l'API réelle (``log-interaction``) et l'effet de chaque code annoncé à
    l'écran est constaté, dans chacune de ses branches."""
    slug = 'cad17-journal'

    JOURNAL = Scenario('journal', 'contact', 2, APPEL)

    def _fabriquer_journal(self, variante):
        froid = variante == 'froid'
        lead = self._lead(Scenario(
            'journal', 'contact', 2, APPEL,
            stage=stages.COLD if froid else stages.CONTACTED))
        if froid:
            # Un dormant : ses deux réveils ouverts, rien d'autre.
            for entree in CADENCES_DEFAUT['reveil']:
                self._touche(lead, cadence='reveil', ordre=entree['ordre'],
                             canal=entree['canal'], libelle=entree['libelle'],
                             due=GEL + datetime.timedelta(
                                 days=entree['delai_jours']),
                             depart=GEL)
            return lead
        # La prise de contact en cours : une touche ouverte.
        self._touche(lead, cadence='contact', ordre=2, canal=APPEL,
                     libelle="Appel d'ouverture", depart=GEL)
        if variante == 'avec_autre':
            devis = self._devis(lead)
            self._touche(lead, cadence='apres_devis', ordre=4,
                         canal=WHATSAPP, libelle='Preuve — chantier comparable',
                         devis=devis, due=GEL + datetime.timedelta(days=2),
                         depart=GEL - datetime.timedelta(days=7))
        elif variante == 'generique_ouverte':
            self._touche(lead, cadence='generique', ordre=2, canal=WHATSAPP,
                         libelle='Relance WhatsApp',
                         due=GEL + datetime.timedelta(days=3), depart=GEL)
        return lead

    def test_journal_d_appel(self):
        for issue, codes in JOURNAL_ECRAN.items():
            variantes = []
            for code in codes:
                for variante in VARIANTES.get(code, ('base',)):
                    if variante not in variantes:
                        variantes.append(variante)
            for variante in variantes:
                with self.subTest(issue=issue, variante=variante):
                    lead = self._fabriquer_journal(variante)
                    avant = frozenset(
                        lead.relance_etapes.filter(statut=A_FAIRE)
                        .values_list('pk', flat=True))
                    resp = self.api.post(
                        f'/api/django/crm/leads/{lead.pk}/log-interaction/',
                        {'kind': 'appel', 'outcome': issue}, format='json')
                    self.assertIn(resp.status_code, (200, 201), resp.data)
                    lead.refresh_from_db()
                    constat = Constat(
                        test=self, scenario=self.JOURNAL, variante=variante,
                        lead=lead, etape=None, avant=avant, donnees=resp.data)
                    for code in codes:
                        if variante in VARIANTES.get(code, ('base',)):
                            VERIFICATEURS[code](constat)


class ContratServiTests(PariteBase):
    """Le sérialiseur RÉEL (liste de la file) sert l'exemple committé."""
    slug = 'cad17-contrat'

    def test_la_file_sert_les_suites_de_l_exemple(self):
        for resultat in TOUCHES_DU_CONTRAT:
            with self.subTest(touche=resultat['id']):
                scenario = Scenario(
                    'contrat', resultat['cadence'], resultat['ordre'],
                    resultat['canal'], resultat['libelle'],
                    devis=resultat['devis'] is not None,
                    stage=_stage_du_contrat(resultat))
                self.assertEqual(self._promesses_servies(scenario),
                                 resultat['suites'])

    def test_une_lecture_ne_seede_rien(self):
        # Une société sans gabarit : la lecture rejoue le seed À BLANC et
        # annonce les mêmes promesses, sans créer un seul barreau.
        vierge = Company.objects.create(nom='CAD17 vierge', slug='cad17-v')
        self.assertEqual(st.ordres_de_la_cadence(vierge.pk, 'contact'),
                         _ordres_defaut('contact'))
        self.assertFalse(CadenceRelanceEtape.objects.filter(
            company=vierge).exists())
