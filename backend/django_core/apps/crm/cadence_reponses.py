"""Réponses de touche : replis, passation, opposition, veille, perdu (SPL4, extrait de crm/services.py : déplacement pur).

Module RACINE de la scission : il importe ``.services`` au niveau module ;
aucun module de type (a) ne l'importe et ``services`` ne le réexporte pas.
"""
import datetime
import logging

from django.utils import timezone

from core.dates import aujourd_hui_local

from apps.parametres import models_relance as gabarit_relance

from . import activity, cadence_config, stages
from .cadence_config import (
    CLE_CONFIRMATION,
    CLE_DEBRIEF,
    CLE_DECIDER_SUITE,
    CLE_DEVIS,
    CLE_DEVIS_MODIFIE,
    CLE_PLANIFIER,
    CLE_RAPPEL_CONVENU,
    cle_de,
    est_etape,
)
from .leads_socle import motif_refus_valide
from .models import Lead, LeadActivity, RelanceEtape
from .services import (
    CADENCE_DEUXIEME_AFFAIRE,
    CAUSE_RDV_NE_PLUS_CONTACTER,
    CadenceActiveConflit,
    _TAG_DECISION_A_PLUSIEURS,
    _config_visite,
    _debrief_ouvert,
    _lead_relancable,
    _poser_etape_de_filet,
    _poser_etape_visite,
    _prochaine_touche_a_faire,
    _recaler_file,
    _requalifier_debrief,
    _visite_a_venir,
    annuler_rendez_vous_du_lead,
    annuler_rendez_vous_sur_arret,
    arreter_cadence,
    assurer_prochaine_etape_apres_succes,
    avancer_stage_lead_vers,
    cause_rdv_perdu,
    demarrer_cadence_contact,
    deplacer_echeance_etape,
    initialiser_plan_relance,
    marquer_etape_relance,
    poser_tag_lead,
    prochain_palier_sans_reponse,
    reporter_prochaine_touche,
    retirer_tag_lead,
)
from .cadence_messages import ETIQUETTES_RAISON_ATTENTE, PREFIXE_LIEN_LOCATAIRE, RAISONS_ATTENTE
from .cadence_reperes import (
    FILET_JOINT_DELAI_JOURS,
    PASSATION_LIBELLE,
    PREFIXE_NOTE_VEILLE,
    QUESTION_PRIX_LIBELLE,
    VISITE_ORDRE_DEBRIEF,
    VISITE_ORDRE_FILET,
    _CANAL_VERS_KIND,
    _canal_configure,
    _lead_porte_tag,
    annuler_etapes_moteur_ouvertes,
    prefixe_activite_touche,
)
from .leads_consentement import _ecrire_registre_contact
from .leads_doublons import find_duplicates_by_contact, normalize_phone

logger = logging.getLogger(__name__)


# ── CAD-A ── CAD18 — l'étape de filet hérite d'un script ─────────────────────
#
#: CAD18 — clé de gabarit de message pour une étape de FILET, par libellé.
#:
#: LE TROU : en régime réactif, seule la touche 1 existe. Un lead qui RÉPOND
#: au message d'identité avant l'appel J0+3 min se fait marquer « joint », ce
#: qui arrête la prise de contact ; le filet pose alors « appeler le client —
#: il a répondu au message », et cette étape naissait SANS aucun gabarit. Le
#: dossier le plus chaud du portefeuille était le seul appel sans script.
#:
#: POURQUOI PAS ``appel_ouverture`` : ce script ouvre par « vous venez de
#: remplir notre formulaire », ce qui est FAUX pour quelqu'un qui vient de
#: répondre — il a déjà eu un échange. D'où une clé propre,
#: ``appel_apres_reponse``.
#:
#: Les autres étapes de filet n'ont PAS de gabarit : aucun texte validé
#: n'existe pour elles, et on n'en invente pas.
#:
#: PARAM-CADENCE (25/09/2026) — la clé de gabarit vit désormais SUR LE
#: BARREAU (« Après l'appel (avant devis) », ``template_cle``), réglable par
#: société : ce dictionnaire est la lecture des DÉFAUTS, plus jamais lue par
#: le moteur.
FILET_TEMPLATE_CLES = {
    e['libelle']: e['template_cle']
    for e in gabarit_relance.CADENCE_APRES_CONTACT_DEFAUT if e['template_cle']
}


def _palier_sans_reponse(touche_close, issue_touche_close, company=None):
    """CAD102 — le palier suivant de l'escalier « ne décroche pas », ou
    ``None`` si cette clôture n'en déclenche aucun.

    Rend ``(libelle, canal, delai_jours)`` — ceux du barreau de ``company``
    (Paramètres), ou les défauts livrés sans société. ``touche_close`` : la
    touche close, ou son libellé (reconnu s'il est un libellé par défaut)."""
    if isinstance(touche_close, str):
        touche_close = RelanceEtape(libelle=touche_close)
    if company is None:
        def _config(cle):
            defaut = gabarit_relance.barreau_par_defaut(
                cadence_config.CADENCE_DE_LA_CLE[cle], cle)
            return dict(defaut, actif=True)
    else:
        def _config(cle):
            return cadence_config.config_cle(company, cle)
    cle = prochain_palier_sans_reponse(
        cle_de(touche_close), issue_touche_close,
        lambda c: _config(c)['actif'])
    if cle is None:
        return None
    config = _config(cle)
    return (config['libelle'], _canal_configure(config),
            config['delai_jours'])


# ── CAD-D ── CAD54 — réattribuer un lead : la passation se dit ───────────────
#
# Ce que le round 2 a déjà vérifié SAIN, et qui n'est donc pas retouché ici :
# ``RelanceEtape`` n'a AUCUN champ responsable — les touches suivent le lead,
# donc elles « portent » le nouveau responsable par construction ; le digest du
# matin vise les owners ; le prénom du conseiller est recalculé à chaque rendu
# (jamais figé dans une touche) ; le changement est déjà journalisé.
#
# Ce qui manquait est côté CLIENT et côté NOUVEAU responsable : aucun gabarit
# de passation — tous les textes se présentent comme un premier contact, donc
# le prospect voyait changer de prénom sans un mot — et le nouveau responsable
# n'apprenait qu'il héritait d'une touche due demain que par une ligne
# d'historique.

#: CAD54 — clé du gabarit de passation. TEXTE LIBRE côté ``RelanceEtape``
#: (aucune valeur d'énumération ajoutée, donc aucune migration). Le texte
#: lui-même porte « {conseiller} » et « {ancien_conseiller} » en variables de
#: gabarit : AUCUN prénom n'est codé en dur (règle fondateur 08/09/2026).
PASSATION_TEMPLATE_CLE = 'passation'

#: Le libellé de la touche, lui, est déclaré plus haut avec ses sœurs de
#: FILET (``PASSATION_LIBELLE``) : `_LIBELLES_FILET` doit le connaître, et un
#: second littéral aurait dérivé au premier ajustement de la phrase.

#: Rang hors de la plage des gabarits (1-10), même précaution que les étapes
#: de visite : aucune matérialisation réactive ne peut le confondre avec un
#: barreau.
PASSATION_ORDRE = 93


def _poser_etape_passation(lead):
    """CAD54 — crée (ou DÉPLACE) l'unique touche de passation du lead.

    Cadence ``generique``, comme les étapes de FILET : c'en est une (posée par
    le moteur, hors protocole). Surtout PAS la cadence des gestes de visite —
    ``apres_devis`` — qui ferait d'une simple réattribution une « cadence
    active » capable de bloquer le démarrage d'une prise de contact (garde
    CADX) ou l'initialisation du suivi de proposition.

    IDEMPOTENTE par libellé : une passation déjà ouverte est déplacée à
    aujourd'hui, jamais dupliquée.
    """
    from core.dates import aujourd_hui_local

    from . import horaires

    vise = datetime.datetime.combine(
        aujourd_hui_local(), datetime.time(9, 0),
        tzinfo=horaires.CASABLANCA)
    echeance = horaires.prochain_creneau_appel(
        vise, lead.company, canal=RelanceEtape.Canal.WHATSAPP)
    ouverte = (lead.relance_etapes
               .filter(libelle=PASSATION_LIBELLE,
                       statut=RelanceEtape.Statut.A_FAIRE)
               .order_by('due_date', 'pk').first())
    if ouverte is not None:
        # COCKPIT-CONTRÔLE — déplacée par le MOTEUR : rien n'est compté.
        return deplacer_echeance_etape(ouverte, echeance)
    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='generique',
        ordre=PASSATION_ORDRE, canal=RelanceEtape.Canal.WHATSAPP,
        libelle=PASSATION_LIBELLE, template_cle=PASSATION_TEMPLATE_CLE,
        due_at=echeance,
        due_date=echeance.astimezone(horaires.CASABLANCA).date(),
        note='Posée automatiquement : le dossier change de conseiller.')


def poser_touche_passation(lead, user, ancien_responsable=None):
    """CAD54 — la touche qui DIT au client que son dossier change de mains.

    Posée seulement sur un lead DÉJÀ CONTACTÉ (``first_contacted_at``) : sur
    un lead jamais joint il n'y a rien à annoncer, et le premier message du
    protocole fait déjà les présentations.

    IDEMPOTENTE par libellé (``_poser_etape_visite``) : deux réattributions
    d'affilée déplacent la même touche, elles n'en empilent pas deux. Aucune
    touche n'est retirée ni réordonnée.

    Renvoie l'étape posée, ou ``None``.
    """
    if not _lead_relancable(lead):
        return None
    if not getattr(lead, 'first_contacted_at', None):
        return None
    if lead.stage in (stages.SIGNED,):
        return None
    etape = _poser_etape_passation(lead)
    if etape is not None and ancien_responsable is not None:
        # La trace dit DE QUI le dossier vient — l'écran et le gabarit, eux,
        # lisent le responsable courant, jamais un prénom figé.
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=('Passation à annoncer au client : le dossier change de '
                  'conseiller.'))
    return etape


def notifier_touches_heritees(lead, nouveau_responsable):
    """CAD54 — le nouveau responsable apprend CE QU'IL HÉRITE, pas seulement
    qu'un lead lui est assigné.

    Une seule notification, sur l'événement EXISTANT ``LEAD_ASSIGNED``
    (aucune valeur d'énumération ajoutée) : le nombre de touches ouvertes et
    la date de la plus proche. Sans touche ouverte, rien n'est envoyé — la
    notification d'assignation ordinaire suffit et deux messages pour un seul
    geste rendraient la boîte illisible.

    Best-effort : ne lève jamais.
    """
    if nouveau_responsable is None:
        return None
    try:
        ouvertes = list(
            lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .order_by('due_date', 'ordre')[:3])
        total = lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).count()
        if not total:
            return None
        from apps.notifications.services import notify

        lignes = [
            f'{(e.libelle or e.get_canal_display())} — {e.due_date:%d/%m/%Y}'
            for e in ouvertes if e.due_date
        ]
        corps = f'{total} relance(s) déjà programmée(s) sur ce dossier.'
        if lignes:
            corps += ' ' + ' · '.join(lignes)
        return notify(
            user=nouveau_responsable,
            event_type='lead_assigned',
            title='Dossier repris — relances héritées',
            body=corps,
            link=f'/crm/leads?lead={lead.pk}',
            reason='assigne_a_vous',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant pour la réattribution
        logger.warning(
            'CAD54: notification des touches héritées échouée (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
        return None


def reattribuer_lead(lead, user, nouveau_responsable):
    """CAD54 — LE geste de réattribution, effets compris.

    Trois choses, dans cet ordre :

    1. le lead change d'``owner`` (les touches ouvertes suivent le lead — elles
       n'ont pas de responsable propre, et c'est ce qui rend l'ensemble
       cohérent sans rien migrer) ;
    2. le NOUVEAU responsable est notifié de ce qu'il HÉRITE ;
    3. sur un lead DÉJÀ contacté, la touche de passation est posée : le
       prospect ne doit pas voir changer de prénom sans un mot.

    L'ancien responsable ne reçoit plus rien : les notifications de relance
    visent les owners, et il ne l'est plus. Renvoie la touche de passation
    posée, ou ``None``.
    """
    if nouveau_responsable is None:
        return None
    ancien = getattr(lead, 'owner', None)
    if ancien is not None and ancien.pk == nouveau_responsable.pk:
        return None
    lead.owner = nouveau_responsable
    lead.save(update_fields=['owner'])
    notifier_touches_heritees(lead, nouveau_responsable)
    etape = poser_touche_passation(lead, user, ancien_responsable=ancien)
    _recaler_file(lead, user)
    return etape


#: CAD5 — « Ne plus me contacter ». Motif écrit sur chaque touche arrêtée :
#: le même que celui de la case de la fiche (``LeadViewSet.perform_update``),
#: pour que le KPI de cadence ne voie qu'UN motif d'opposition.
REPONSE_NE_PLUS_CONTACTER = 'ne_plus_contacter'
MOTIF_NE_PLUS_CONTACTER = 'ne plus contacter'
#: CAD6 — « Plus tard — pas maintenant » (la plus fréquente du résidentiel).
REPONSE_PLUS_TARD = 'plus_tard'
#: CAD7 — « Question de prix — veut négocier ».
REPONSE_QUESTION_PRIX = 'question_prix'
#: CAD8 — « Demande un devis modifié ».
REPONSE_DEVIS_MODIFIE = 'devis_modifie'
#: CAD9 — « Décision à plusieurs », en deux nuances que la note distingue.
REPONSE_DECISION_FAMILLE = 'decision_famille'
REPONSE_DECISION_PROPRIETAIRE = 'decision_proprietaire'
#: SUIVI E2 (30/09/2026) — « Perdu — clore le dossier », la décision prise
#: sur l'étape « Décider la suite » (et seulement là).
REPONSE_PERDU = 'perdu'
#: SUIVI E4 (30/09/2026) — « Ne veut plus de visite » / « Annule le
#: rendez-vous » : la VISITE est abandonnée, pas la proposition.
REPONSE_VISITE_ABANDONNEE = 'visite_abandonnee'
#: SUIVI E16 (30/09/2026) — « Client joint au téléphone » sur une touche
#: MESSAGE : la commerciale a appelé au lieu d'écrire, et le client a
#: décroché.
REPONSE_JOINT_TELEPHONE = 'joint_telephone'
#: L'étiquette posée — la forme AFFICHÉE de l'étiquette standard (seedée par
#: ``views.seed_tags``) ; la comparaison, elle, ignore casse et accents
#: (``_lead_porte_tag`` avec ``_TAG_DECISION_A_PLUSIEURS``).
TAG_DECISION_A_PLUSIEURS = 'Décision à plusieurs'
#: AGR520 (05/10/2026) — « En attente d'un accord (DPA / banque) » : le client
#: attend une décision ADMINISTRATIVE ou BANCAIRE (approbation préalable FDA —
#: Guide FDA 2024 p.22-23 —, accord de crédit). Même veille que « Plus tard »,
#: plus une étiquette ; jamais « je classe ? » ni le passage au Froid.
REPONSE_ATTENTE_ACCORD = 'attente_accord'


RAISONS_ATTENTE_VALEURS = tuple(r[0] for r in RAISONS_ATTENTE)


_RAISON_ATTENTE = {r[0]: r for r in RAISONS_ATTENTE}


def refus_raison_attente(raison):
    """CIQ508 — pourquoi ``raison`` n'est pas une raison d'attente valide, ou
    ``None``. Le message NOMME le champ et LISTE les valeurs (règle fondateur
    du 08/09/2026 : jamais un refus générique)."""
    if (raison or '').strip() in _RAISON_ATTENTE:
        return None
    return ("« Raison de l'attente » (raison_attente) : valeur requise "
            'parmi : ' + ', '.join(RAISONS_ATTENTE_VALEURS) + '.')


#: Les cadences de protocole (``None`` = toutes, filets et réveils compris).
_TOUTES_CADENCES = None
#: Les trois cadences NOMMÉES du protocole (MRY4) — pas les étapes de filet
#: (``generique``), dont « À rappeler le… » REPORTE déjà l'étape (CAD3).
_CADENCES_PROTOCOLE = ('contact', 'apres_devis', 'reveil')
#: SUIVI-PARCOURS (30/09/2026) — la table du parcours range la deuxième
#: affaire (CAD128, la prise de contact d'un client acquis) sous les mêmes
#: types d'étape que la prise de contact : ses touches sont des touches du
#: PROTOCOLE et reçoivent les mêmes réponses.
_CADENCES_PROTOCOLE_ET_DEUXIEME_AFFAIRE = (
    _CADENCES_PROTOCOLE + ('deuxieme_affaire',))

#: Table UNIQUE des réponses de touche. ``outcome`` est toujours une valeur
#: de ``LeadActivity.OUTCOMES`` ; ``cadences`` borne où la réponse a un sens ;
#: ``message`` nomme le texte d'accusé proposé à l'envoi (jamais envoyé seul).
#: SUIVI-PARCOURS — deux bornes optionnelles de plus, appliquées par
#: ``refus_reponse_touche`` : ``cles`` (les CLÉS d'étape moteur où la réponse
#: vaut — ``cadence_config.cle_de``, jamais un libellé) et ``canaux``.
REPONSES_TOUCHE = {
    REPONSE_NE_PLUS_CONTACTER: {
        'libelle': 'Ne plus me contacter',
        'outcome': 'refuse',
        'note': 'Ne plus me contacter — opposition du client',
        'cadences': _TOUTES_CADENCES,
        'message': 'stop_contact',
    },
    REPONSE_PLUS_TARD: {
        'libelle': 'Plus tard — pas maintenant',
        'outcome': 'rappel',
        'note': 'Plus tard — pas maintenant',
        # Protocole seulement (jamais une étape de filet ni de visite) — la
        # deuxième affaire comprise, que la table range avec la prise de
        # contact (SUIVI-PARCOURS).
        'cadences': _CADENCES_PROTOCOLE_ET_DEUXIEME_AFFAIRE,
        'message': 'rappel_plus_tard',
        # La date convenue avec le client est OBLIGATOIRE (« Rappeler le »).
        'date_requise': True,
    },
    # AGR520 — même place, mêmes cadences et même date OBLIGATOIRE que
    # « Plus tard » ; AUCUN texte proposé (aucun accusé n'est validé pour ce
    # cas) ; l'étiquette dit pourquoi le dossier dort.
    REPONSE_ATTENTE_ACCORD: {
        'libelle': "En attente d'un accord (DPA / banque)",
        'outcome': 'rappel',
        'note': "En attente d'un accord (DPA / banque)",
        'cadences': _CADENCES_PROTOCOLE_ET_DEUXIEME_AFFAIRE,
        'message': None,
        'date_requise': True,
        # CIQ508 — la RAISON de l'attente est obligatoire (liste fermée
        # `RAISONS_ATTENTE`) : sans elle, rien n'est mesurable.
        'raison_requise': True,
    },
    REPONSE_QUESTION_PRIX: {
        'libelle': 'Question de prix — veut négocier',
        # Version minimale, SANS nouvelle énumération : l'issue « à
        # rappeler » + la note typée (le client n'a dit ni oui ni non).
        'outcome': 'rappel',
        'note': 'Question de prix — veut négocier',
        'cadences': ('apres_devis',),
        # Aucun texte proposé : ni `annonce_appel_reda` ni `offre_reda` ne
        # partent avant la décision du fondateur (CAD60).
        'message': None,
    },
    REPONSE_DEVIS_MODIFIE: {
        'libelle': 'Demande un devis modifié',
        # « à rappeler » : l'étape posée dit « … — rappeler le client ».
        # Surtout PAS « joint » : son récepteur (MRY9) ferait naître le
        # barreau suivant du devis ÉCARTÉ avant que l'étape soit posée.
        'outcome': 'rappel',
        'note': 'Demande un devis modifié',
        'cadences': ('apres_devis',),
        'message': None,
    },
    # CAD9 — « à rappeler » : le client n'a pas tranché, il décide avec
    # d'autres. L'issue fait naître le barreau suivant du protocole — et
    # comme l'étiquette est posée AVANT, la partition recalculée réinjecte
    # le « dimanche famille » s'il n'est pas encore dépassé.
    REPONSE_DECISION_FAMILLE: {
        'libelle': 'Décision à plusieurs — en famille',
        'outcome': 'rappel',
        'note': ('Décision à plusieurs — en famille (un délai : la décision '
                 'se prend ensemble)'),
        'cadences': ('apres_devis',),
        'message': None,
    },
    REPONSE_DECISION_PROPRIETAIRE: {
        'libelle': 'Décision à plusieurs — le propriétaire',
        'outcome': 'rappel',
        'note': ('Décision à plusieurs — le propriétaire décide (un '
                 'interlocuteur à changer)'),
        'cadences': ('apres_devis',),
        'message': None,
    },
    # SUIVI E2 (30/09/2026) — la décision « perdu » se prend sur l'étape
    # « Décider la suite » (reconnue par sa CLÉ), avec un motif ACTIF de la
    # société, OBLIGATOIRE (``motif_perte``). L'issue dérivée est « refus » :
    # le client a dit non, et la décision de clore est humaine (MRY22).
    REPONSE_PERDU: {
        'libelle': 'Perdu — clore le dossier',
        'outcome': 'refuse',
        'note': 'Perdu',
        'cadences': _TOUTES_CADENCES,
        'cles': (CLE_DECIDER_SUITE,),
        'message': None,
        'motif_perte_requis': True,
    },
    # SUIVI E4 (30/09/2026) — refuser ou annuler la VISITE n'est pas refuser
    # la PROPOSITION : « refus » tuait tout le suivi. Issue « joint » (le
    # client a parlé), sur les trois gestes du rendez-vous seulement (jamais
    # « Préparer le devis modifié »).
    REPONSE_VISITE_ABANDONNEE: {
        'libelle': 'Ne veut plus de visite',
        'outcome': 'joint',
        'note': 'Visite abandonnée — le client ne veut plus de visite',
        'cadences': _TOUTES_CADENCES,
        'cles': (CLE_PLANIFIER, CLE_CONFIRMATION, CLE_DEBRIEF),
        'message': None,
    },
    # SUIVI E16 (30/09/2026) — la touche prévoyait un MESSAGE, la commerciale
    # a APPELÉ et le client a décroché. Issue « joint », mais la ligne de
    # chatter est un APPEL (``canal_reel``) : la suite est celle d'un appel
    # abouti (prise de contact / réveil : l'étape devis ; suivi de
    # proposition : le barreau suivant), jamais « Appeler le client — il a
    # répondu au message ». Sur les touches ÉCRITES du protocole seulement
    # (``barreaux_seulement`` : jamais un geste de visite, qui a sa clé).
    REPONSE_JOINT_TELEPHONE: {
        'libelle': 'Client joint au téléphone',
        'outcome': 'joint',
        'note': 'Client joint au téléphone',
        'cadences': _CADENCES_PROTOCOLE_ET_DEUXIEME_AFFAIRE,
        'canaux': (RelanceEtape.Canal.WHATSAPP, RelanceEtape.Canal.EMAIL),
        'barreaux_seulement': True,
        'message': None,
    },
}

#: Les textes de RÉPONSE qu'une touche peut proposer à l'envoi — le seul
#: vocabulaire accepté par ``?cle=`` sur ``relance-etapes/<id>/message/``.
#: CIQ503 — ``attente_accord_accuse`` : l'accusé quand la décision attend un
#: accord (comité, direction, banque), crochets à compléter (CAD69).
CLES_MESSAGE_REPONSE = ('stop_contact', 'rappel_plus_tard',
                        'attente_accord_accuse')


def reponse_touche(cle):
    """La définition de la réponse ``cle``, ou ``None`` si elle est inconnue."""
    return REPONSES_TOUCHE.get((cle or '').strip())


def refus_reponse_touche(etape, cle):
    """Pourquoi la réponse ``cle`` ne vaut PAS sur cette touche — ou ``None``.

    Le message NOMME la réponse et dit où elle vaut (règle fondateur du
    08/09/2026 : jamais un refus générique). L'appelant (la vue) le range sous
    le champ ``reponse``."""
    spec = reponse_touche(cle)
    if spec is None:
        return f'Réponse inconnue : « {cle} ».'
    if etape.statut != RelanceEtape.Statut.A_FAIRE:
        return ('Cette touche est déjà traitée : la réponse du client se '
                'saisit sur une touche encore à faire.')
    libelle = spec['libelle']
    cadences = spec.get('cadences')
    if cadences is not None and etape.cadence not in cadences:
        if tuple(cadences) == ('apres_devis',):
            return (f'« {libelle} » ne vaut que sur une touche du suivi de '
                    'proposition (après envoi du devis).')
        return (f'« {libelle} » ne vaut pas sur une touche de la cadence '
                f'« {etape.cadence} ».')
    # SUIVI-PARCOURS (30/09/2026) — une réponse peut ne valoir que sur
    # certaines ÉTAPES (reconnues par leur CLÉ, jamais leur libellé) ou sur
    # certains CANAUX : le message nomme la réponse et dit où elle vaut.
    cles = spec.get('cles')
    if cles is not None and cle_de(etape) not in cles:
        etapes = ' ou '.join(
            f'« {_libelle_par_defaut_de_la_cle(c)} »' for c in cles)
        return f'« {libelle} » ne vaut que sur l’étape {etapes}.'
    canaux = spec.get('canaux')
    if canaux is not None and etape.canal not in canaux:
        noms = ' ou '.join(RelanceEtape.Canal(c).label for c in canaux)
        return (f'« {libelle} » ne vaut que sur une touche écrite ({noms}) : '
                'sur un appel, choisissez « Client joint ».')
    # SUIVI E16 — une réponse réservée aux touches du PROTOCOLE : une étape
    # posée par le moteur (geste de visite, étape de filet) a sa CLÉ.
    if spec.get('barreaux_seulement') and cle_de(etape):
        return (f'« {libelle} » ne vaut que sur une touche du protocole '
                '(prise de contact, suivi de proposition, réveil).')
    return None


def _libelle_par_defaut_de_la_cle(cle):
    """Le libellé PAR DÉFAUT (gabarit livré) de l'étape moteur ``cle`` —
    pour NOMMER une étape dans un refus, sans requête."""
    defaut = gabarit_relance.barreau_par_defaut(
        cadence_config.CADENCE_DE_LA_CLE.get(cle), cle)
    return (defaut or {}).get('libelle') or cle


def _note_reponse(spec, note=''):
    """La note typée de la réponse, suivie de la note libre éventuelle."""
    note = (note or '').strip()
    return f'{spec["note"]} — {note}' if note else spec['note']


# ── CAD-I ── CAD91 — l'OPPOSITION est tracée au registre ─────────────────────
#
# Cocher « ne plus contacter » arrêtait bien les cadences et bloquait tout
# redémarrage — mais RIEN n'écrivait de ``ConsentRecord(granted=False)`` : le
# registre que CAD90 remplit était incapable de prouver qu'une opposition
# avait été honorée, ce qu'un contrôle vérifie en premier après une plainte.
# C'est ce registre qui prouve l'opposition devant l'art. 59 de la loi 09-08
# (3 mois à 1 an, 20 000 à 200 000 DH) ; l'art. 9 al. 2 n'exige AUCUN motif
# du client — rien ne conditionne donc l'écriture à une justification.

#: La base de l'opposition, sur texte primaire (round 2 de l'audit).
BASE_LEGALE_OPPOSITION = 'opposition : loi 09-08 art. 9 al. 2 (sans frais, ' \
                         'sans motif)'
#: Les deux gestes qui la recueillent — la case de la fiche, la réponse de
#: touche (CAD5). Le registre dit PAR OÙ elle est arrivée.
CONSENT_SOURCE_OPPOSITION_FICHE = 'case « Ne plus contacter » de la fiche'
CONSENT_SOURCE_OPPOSITION_TOUCHE = 'réponse « Ne plus me contacter »'


def tracer_opposition_registre(lead, *, source, occurred_at=None):
    """CAD91 — inscrit l'opposition au registre ``core.ConsentRecord``.

    ACRM59 — une entrée ``granted=False`` par FINALITÉ DE CONTACT
    (``FINALITES_CONTACT`` : prospection, WhatsApp, e-mail, SMS) et sous
    CHAQUE identifiant de la personne (e-mail ET téléphone) : la ligne
    WhatsApp « accordée » posée à l'intake n'est plus la dernière, et un
    lecteur qui interroge le téléphone voit l'opposition. Datée de
    l'instant où elle est recueillie ; la ``source`` porte le geste ET la
    base légale (une base légale CAD90 reste distincte par sa source). Le
    registre reste un historique append-only.

    Best-effort intégral : l'opposition elle-même (case cochée, cadences
    arrêtées) ne tombe jamais parce que le registre n'a pas pu être écrit.
    Renvoie la première entrée créée, ou ``None`` (lead sans e-mail ni
    téléphone, ou écriture impossible)."""
    try:
        return _ecrire_registre_contact(
            lead, granted=False,
            source=f'{source} — {BASE_LEGALE_OPPOSITION}',
            occurred_at=occurred_at)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD91 : opposition non écrite au registre pour le lead #%s',
            getattr(lead, 'pk', None), exc_info=True)
        return None


def marquer_lead_ne_plus_contacter(lead, user):
    """CAD5 — coche ``Lead.ne_plus_contacter`` et le JOURNALISE comme la
    fiche le ferait (ligne « modification » du chatter, ancien → nouveau).

    Idempotente : un lead déjà coché ne produit ni écriture ni ligne.
    Renvoie ``True`` si la case vient d'être cochée."""
    import copy

    if lead.ne_plus_contacter:
        return False
    avant = copy.copy(lead)
    lead.ne_plus_contacter = True
    lead.save(update_fields=['ne_plus_contacter'])
    activity.log_changes(avant, lead, user)
    return True


def repondre_ne_plus_contacter(etape, user, *, note='', body=''):
    """CAD5 — le client dit « ne me contactez plus » sur une touche.

    Base légale (round 2 de l'audit, texte primaire) : loi 09-08 art. 9 al.
    2 — l'opposition à la prospection s'exerce sans frais et SANS avoir à être
    motivée ; art. 59 — poursuivre malgré elle est puni de 3 mois à 1 an et de
    20 000 à 200 000 DH. C'est le seul risque pénal nommé de la cadence : la
    réponse agit donc TOUT DE SUITE, dans cet ordre —

      1. la case ``ne_plus_contacter`` est cochée (garde dure : plus aucune
         touche ne peut naître, et le redémarrage manuel est refusé) ;
      2. TOUTES les autres touches ouvertes, toutes cadences, sont arrêtées
         sous le motif « ne plus contacter » ;
      3. la touche est close avec l'issue « refus » et la note typée — SANS
         aucune étape de décision : il n'y a rien à décider, le client a
         tranché (``suite=False`` ; le filet du récepteur MRY9 est, lui,
         tenu par la case cochée en 1).

    L'accusé ``stop_contact`` est PROPOSÉ par l'écran (jamais envoyé seul).
    CAD91 — l'opposition est inscrite au REGISTRE au moment où elle est dite
    (``tracer_opposition_registre``), sans aucun motif exigé du client.
    Renvoie la touche close."""
    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_NE_PLUS_CONTACTER]
    marquer_lead_ne_plus_contacter(lead, user)
    tracer_opposition_registre(lead, source=CONSENT_SOURCE_OPPOSITION_TOUCHE)
    arreter_cadence(lead, user=user, motif=MOTIF_NE_PLUS_CONTACTER,
                    exclure=etape)
    # SUIVI E21 — le rendez-vous de visite en attente s'annule aussi (AVANT la
    # clôture : le récepteur « refus » qui la suit ne trouve plus rien).
    annuler_rendez_vous_sur_arret(lead, user,
                                  cause=CAUSE_RDV_NE_PLUS_CONTACTER)
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body, suite=False)
    # Ceinture : rien ne doit rester ouvert (idempotent — zéro touche, zéro
    # ligne de chatter).
    arreter_cadence(lead, user=user, motif=MOTIF_NE_PLUS_CONTACTER)
    return etape


# ── CAD-B ── CAD26 — « rappelez-moi dans trois semaines » : une VEILLE ──────
#
# ``reporter_prochaine_touche`` décale la touche, toute la suite de sa cadence
# et l'ancre, du même écart, sans plafond ni bifurcation : « rappelez-moi dans
# trois semaines » envoyait la clôture J+14 à J+35, et un client qui avait
# fixé LA date où il voulait qu'on revienne ne la retrouvait nulle part.
#
# DEUX GESTES DISTINCTS désormais, au choix de la commerciale :
#
#   * « Décaler ce rappel » — le comportement historique, pour quelques
#     jours (``reporter_prochaine_touche`` inchangé) ;
#   * « Mettre en veille jusqu'au… » — la cadence SE TAIT jusqu'à la date du
#     client et reprend au MÊME barreau : rien n'est consommé, rien n'est
#     recréé (« décaler, jamais redémarrer ») ; au-delà d'un mois d'attente,
#     elle BASCULE en réveil daté — et le dit, parce que cette bascule
#     arrête la cadence en cours (CADX : une seule cadence à la fois).
#
# L'écran propose le second geste de lui-même au-delà de 7 jours.

#: Au-delà de cette attente (en jours calendaires, « un mois »), une veille
#: ne suspend plus la cadence : elle la remplace par un réveil daté.
VEILLE_BASCULE_REVEIL_JOURS = 30


def _instant_de_veille(quand):
    """``quand`` (date, datetime naïf ou aware) → datetime AWARE."""
    from . import horaires

    if not isinstance(quand, datetime.datetime):
        return datetime.datetime.combine(
            quand, datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
    if timezone.is_naive(quand):
        return timezone.make_aware(quand, datetime.timezone.utc)
    return quand


def mettre_en_veille(lead, user, quand, *, etape=None, journaliser=True):
    """CAD26 — met le dossier en VEILLE jusqu'à ``quand`` (date du client).

    * attente ≤ ``VEILLE_BASCULE_REVEIL_JOURS`` : la touche ``etape`` (sinon
      la prochaine à faire) N'EST PAS consommée — elle est déplacée à la date
      du client par la mécanique EXISTANTE (``reporter_prochaine_touche``),
      avec la suite de sa cadence et son ancre. Aucune touche intermédiaire
      ne part d'ici là, et la reprise se fait AU MÊME BARREAU ;
    * au-delà : bascule en RÉVEIL DATÉ (``_basculer_veille_en_reveil``).

    ``journaliser=False`` supprime la note de veille : l'appelant en écrit
    une qui dit la vraie raison (la réponse « Plus tard » de CAD6), jamais
    deux lignes pour un seul geste. Renvoie la touche qui portera la reprise
    (la même, déplacée — ou la première touche du réveil), ou ``None``."""
    from . import horaires

    cible = etape or _prochaine_touche_a_faire(lead)
    if cible is None:
        return None
    quand = _instant_de_veille(quand)
    jour = quand.astimezone(horaires.CASABLANCA).date()
    if (jour - aujourd_hui_local()).days > VEILLE_BASCULE_REVEIL_JOURS:
        return _basculer_veille_en_reveil(
            lead, user, cible, quand, journaliser=journaliser)
    return _veille_simple(lead, user, cible, quand, journaliser=journaliser)


def _veille_simple(lead, user, cible, quand, *, journaliser=True):
    """CAD26 — la VEILLE SIMPLE : ``cible`` n'est pas consommée, elle est
    déplacée à la date du client avec la suite de sa cadence et son ancre
    (``reporter_prochaine_touche``) ; la reprise se fait au MÊME barreau.
    Renvoie la touche déplacée, ou ``None``."""
    deplacee = reporter_prochaine_touche(
        lead, user, quand, etape=cible, journaliser=False)
    if deplacee is not None and journaliser:
        libelle = (deplacee.libelle or '').strip() \
            or deplacee.get_canal_display()
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(PREFIXE_NOTE_VEILLE
                  + f'jusqu’au {deplacee.due_date:%d/%m/%Y} à '
                  'la demande du client — la cadence reprendra à la touche '
                  f'« {libelle} », aucune touche ne part d’ici là.'))
    return deplacee


def _basculer_veille_en_reveil(lead, user, cible, quand, *, journaliser=True):
    """CAD26 — plus d'un mois d'attente : la cadence en cours s'ARRÊTE (motif
    tracé sur chaque touche + note) et un RÉVEIL est daté du jour demandé.

    La première touche du gabarit « réveil » tombe SUR la date du client :
    l'ancre est rétrodatée de son délai (même méthode que le placement MRY30,
    ``calculer_echeances_cadence`` garde l'ancre d'un réveil telle quelle).
    Rend la première touche du réveil, ou ``None`` (lead qu'on ne relance
    plus).

    SUIVI E20 (30/09/2026) — une société SANS barreau « réveil » actif
    (Paramètres) : la cadence était arrêtée AVANT de le découvrir, et le lead
    actif restait à ZÉRO touche. On regarde d'abord : sans réveil possible,
    rien n'est arrêté — la veille SIMPLE s'applique (la touche est déplacée
    à la date du client, ``_veille_simple``)."""
    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import horaires

    jour = quand.astimezone(horaires.CASABLANCA).date()
    gabarits = CadenceRelanceEtape.cadence_pour(lead.company, 'reveil')
    if not gabarits:
        return _veille_simple(lead, user, cible, quand,
                              journaliser=journaliser)
    arreter_cadence(
        lead, user=user,
        motif=(f'mise en veille jusqu’au {jour:%d/%m/%Y} — plus d’un mois '
               'd’attente : bascule en réveil daté'))
    premier = min(gabarits, key=lambda g: g.ordre)
    depart = quand - datetime.timedelta(days=premier.delai_jours or 0)
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=depart)
    except CadenceActiveConflit:
        etapes = []
    ouvertes = [e for e in etapes if e.statut == RelanceEtape.Statut.A_FAIRE]
    reveil = ouvertes[0] if ouvertes else None
    if journaliser:
        suite = (f'un réveil est daté du {reveil.due_date:%d/%m/%Y}'
                 if reveil is not None else 'aucun réveil n’a pu être daté')
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(PREFIXE_NOTE_VEILLE
                  + f'demandée jusqu’au {jour:%d/%m/%Y} : plus '
                  f'd’un mois d’attente, la cadence « {cible.cadence} » est '
                  f'arrêtée et {suite}.'))
    return reveil


# ── CAD-A ── CAD6 — « Plus tard — pas maintenant » ──────────────────────────

def repondre_plus_tard(etape, user, quand, *, note='', body=''):
    """CAD6 — « rappelez-moi après l'Aïd / après la rentrée / quand les
    travaux seront finis » : la réponse la plus fréquente du résidentiel.

    Avant, seule « À rappeler le… » existait : elle CONSOMMAIT un barreau et
    programmait le barreau scripté SUIVANT à la date donnée — reporter de six
    semaines faisait donc partir « Je classe ? » ou « Dernier message » à un
    client qui demandait simplement du temps.

    Ici, AUCUN barreau n'est consommé : le dossier est mis en VEILLE DATÉE
    (``mettre_en_veille``, la mécanique de CAD26) et reprend AU MÊME BARREAU
    à la date convenue — ou bascule en réveil daté au-delà d'un mois. La
    réponse du client est tracée par UNE ligne typée selon le canal (issue
    « à rappeler » — un vrai échange a eu lieu, il compte comme tel), qui dit
    aussi ce que la veille a fait. Le texte ``rappel_plus_tard`` est PROPOSÉ
    par l'écran ; ses crochets [jour] / [heure] se complètent à la main.

    Renvoie la touche qui portera la reprise."""
    from . import horaires

    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_PLUS_TARD]
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    quand = _instant_de_veille(quand)
    reprise = mettre_en_veille(lead, user, quand, etape=etape,
                               journaliser=False)
    if reprise is not None and reprise.pk == etape.pk:
        suite = (f'dossier en veille jusqu’au {reprise.due_date:%d/%m/%Y}, '
                 'reprise à cette même touche — aucun barreau consommé')
    elif reprise is not None:
        suite = (f'plus d’un mois d’attente : la cadence est arrêtée et un '
                 f'réveil est daté du {reprise.due_date:%d/%m/%Y}')
    else:
        jour = quand.astimezone(horaires.CASABLANCA).date()
        suite = (f'veille demandée jusqu’au {jour:%d/%m/%Y}, aucune touche à '
                 'reprendre')
    corps = (f'Réponse du client sur la touche « {libelle} » : « '
             f'{spec["note"]} » — {suite}.')
    if body:
        corps += f' {body}'
    if (note or '').strip():
        corps += f' Note : {note.strip()}'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=_CANAL_VERS_KIND.get(etape.canal, LeadActivity.Kind.NOTE),
        body=corps, outcome=spec['outcome'])
    if reprise is None:
        etape.refresh_from_db()
        return etape
    return reprise


def prolonger_validite_attente_accord(lead, user=None):
    """CIQ510 — à la réponse « En attente d'un accord », le dernier devis
    ENVOYÉ du lead voit sa validité portée à ``max(validité actuelle,
    date_validite_credit(devis))`` par la façade de ventes
    ``prolonger_validite_devis`` ; une ligne d'historique par devis prolongé.
    Accepté, refusé, expiré : intouché. Best-effort (jamais bloquant). Rend
    la liste des ``(devis_id, date)`` prolongés."""
    prolonges = []
    try:
        from apps.ventes.selectors import dernier_devis_envoye_par_lead
        from apps.ventes.services import (
            date_validite_credit, prolonger_validite_devis,
        )
        envoyes = dernier_devis_envoye_par_lead(lead.company, [lead.pk])
        for devis in envoyes.values():
            nouvelle = prolonger_validite_devis(
                devis, date_validite_credit(devis))
            if nouvelle is None:
                continue
            prolonges.append((devis.pk, nouvelle))
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=(f'Validité prolongée au {nouvelle:%d/%m} — en attente '
                      "d'un accord (réglage société)."))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('CIQ510 : validité non prolongée (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
    return prolonges


#: CIQ512 — le libellé COURT de l'étape datée (≤ 150 car.) ; le texte complet
#: va dans la note.
LIBELLE_VALIDITE_A_RENOUVELER = 'Validité à renouveler — {reference}'

#: ACRM45 (jumeau) — la clé stable de l'étape « validité à renouveler ».
CLE_VALIDITE_A_RENOUVELER = 'validite_a_renouveler'


def texte_validite_a_renouveler(reference, validite, decision):
    """CIQ512 — le texte de l'étape « validité à renouveler »."""
    return (f'La proposition {reference} expire le {validite:%d/%m}, avant '
            f'la décision attendue le {decision:%d/%m} : prévenez le client '
            '; après expiration, « Renouveler » crée une nouvelle version '
            'que vous re-tarifez')


def poser_etape_validite_a_renouveler(lead, decision):
    """CIQ512 — la décision attendue (``decision``, une date) tombe APRÈS la
    validité effective du dernier devis ENVOYÉ du lead (après prolongation
    CIQ510) : une étape MANUELLE est posée au jour de la validité, hors
    gabarit (le mécanisme de l'étape datée d'AGR522 — jamais une touche de
    cadence, CAD124).

    Aucun statut de devis, aucune étape de lead ne change (règle #4,
    STAGES.py) : la bascule nocturne QJ5 reste seule à passer le devis en
    ``expire``. Idempotente (retrouvée par son libellé). Rend l'étape, ou
    ``None`` quand la décision tient dans la validité."""
    if lead is None or decision is None:
        return None
    try:
        from apps.ventes.selectors import (
            date_validite_effective, dernier_devis_envoye_par_lead,
        )
        devis = dernier_devis_envoye_par_lead(
            lead.company, [lead.pk]).get(lead.pk)
        validite = date_validite_effective(devis)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('CIQ512 : validité illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return None
    if devis is None or validite is None or decision <= validite:
        return None
    from . import horaires
    libelle = LIBELLE_VALIDITE_A_RENOUVELER.format(reference=devis.reference)
    # ACRM45 (jumeau) — retrouvée par sa CLÉ STABLE + la référence du devis
    # (libellé), ou par le libellé seul pour une étape d'avant la clé.
    from django.db.models import Q
    deja = lead.relance_etapes.filter(
        Q(cle=CLE_VALIDITE_A_RENOUVELER) | Q(cle=''),
        libelle=libelle).first()
    if deja is not None:
        return deja
    vise = datetime.datetime.combine(
        validite, datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
    etape = _poser_etape_de_filet(
        lead, libelle=libelle, canal=RelanceEtape.Canal.APPEL, vise=vise,
        note=texte_validite_a_renouveler(devis.reference, validite, decision))
    if etape.cle != CLE_VALIDITE_A_RENOUVELER:
        etape.cle = CLE_VALIDITE_A_RENOUVELER
        etape.save(update_fields=['cle'])
    return etape


# ── AGR520 — « En attente d'un accord (DPA / banque) » ─────────────────────

def repondre_attente_accord(etape, user, quand, *, raison=None, note='',
                            body=''):
    """AGR520 — le client attend une décision administrative ou bancaire
    (approbation préalable du dossier FDA par la DPA, accord de crédit) : il
    n'a dit ni oui ni non, et le relancer « je classe ? » (J7), « dernier
    message » (J13) puis le mettre en pause (J14) serait faux.

    CIQ508 — la réponse est étendue au B2B (comité, banque, bailleur des
    murs, exercice budgétaire, consultation) par une RAISON typée
    (``RAISONS_ATTENTE``, validée par la vue) : l'étiquette posée est celle de
    la raison (``administration`` pose celle d'AGR520), l'historique la dit,
    et au-delà d'un mois la première touche du réveil daté porte en note
    « Rappel convenu — <raison> ».

    1. l'étiquette de la RAISON (``TAG_ATTENTE_ACCORD`` pour
       ``administration``) est posée (``poser_tag_lead``, idempotent) ;
    2. EXACTEMENT la veille de « Plus tard » (``mettre_en_veille``) : aucun
       barreau consommé, la même touche revient à la date convenue — au-delà
       de ``VEILLE_BASCULE_REVEIL_JOURS``, la cadence s'arrête et un réveil
       est daté de ce jour-là (sa première touche est un APPEL). Jamais de
       passage au Froid par cette réponse : l'étape du dossier ne bouge pas ;
    3. UNE ligne d'historique typée selon le canal (issue « à rappeler »).

    Aucun texte n'est proposé. La date est OBLIGATOIRE (la vue la refuse en
    400 nommant ``rappel_le`` sinon). Renvoie la touche qui portera la
    reprise."""
    from . import horaires

    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_ATTENTE_ACCORD]
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    # CIQ508 — sans raison (appel interne), le comportement d'AGR520 :
    # « administration ».
    _valeur, raison_libelle, etiquette = _RAISON_ATTENTE[
        (raison or '').strip() or 'administration']
    # Changer de raison remplace l'étiquette de la précédente : le dossier
    # n'attend qu'une chose à la fois.
    for autre in ETIQUETTES_RAISON_ATTENTE:
        if autre != etiquette and _lead_porte_tag(lead, autre):
            retirer_tag_lead(lead, user, autre)
    poser_tag_lead(lead, user, etiquette)
    quand = _instant_de_veille(quand)
    reprise = mettre_en_veille(lead, user, quand, etape=etape,
                               journaliser=False)
    jour = quand.astimezone(horaires.CASABLANCA).date()
    if reprise is not None and reprise.pk == etape.pk:
        suite = (f'dossier en veille jusqu’au {reprise.due_date:%d/%m/%Y}, '
                 'reprise à cette même touche — aucun barreau consommé')
    elif reprise is not None:
        suite = (f'plus d’un mois d’attente : la cadence est arrêtée et un '
                 f'réveil est daté du {reprise.due_date:%d/%m/%Y}')
        # CIQ508 — la première touche du réveil daté dit POURQUOI on rappelle
        # (le script `reveil_a1` ne parle plus de « nouveau », CIQ501).
        reprise.note = f'Rappel convenu — {raison_libelle}'
        reprise.save(update_fields=['note'])
    else:
        suite = (f'veille demandée jusqu’au {jour:%d/%m/%Y}, aucune touche à '
                 'reprendre')
    corps = (f'Réponse du client sur la touche « {libelle} » : « '
             f"En attente d'un accord — {raison_libelle} — rappel le "
             f'{jour:%d/%m} » — étiquette « {etiquette} » posée, {suite}.')
    if body:
        corps += f' {body}'
    if (note or '').strip():
        corps += f' Note : {note.strip()}'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=_CANAL_VERS_KIND.get(etape.canal, LeadActivity.Kind.NOTE),
        body=corps, outcome=spec['outcome'])
    # CIQ510 — l'attente déclarée APRÈS l'envoi allonge la validité du
    # devis ENVOYÉ du lead (réglage société), jamais ne la raccourcit.
    prolonger_validite_attente_accord(lead, user)
    # CIQ512 — une décision attendue APRÈS la validité (même prolongée) :
    # une étape MANUELLE datée au jour de la validité, jamais un statut.
    poser_etape_validite_a_renouveler(lead, jour)
    if reprise is None:
        etape.refresh_from_db()
        return etape
    return reprise


def repondre_question_prix(etape, user, *, note='', body=''):
    """CAD7 — le client NÉGOCIE le prix, sur une touche du suivi de
    proposition.

    Avant, la réponse la plus fréquente sur une proposition n'avait pas de
    bouton : « Intéressé » était faux (il n'a pas dit oui), « Refuse la
    proposition » aussi (il négocie), et la négociation ne laissait aucune
    trace. Version minimale, SANS nouvelle énumération :

      1. la touche est close avec l'issue « à rappeler » et la note typée
         « Question de prix » — sans barreau suivant (``suite=False``) ;
      2. le TAMBOUR DE MESSAGES SE MET EN PAUSE : une étape de filet
         « Question de prix — préparer l'appel du fondateur » est posée pour
         le prochain jour ouvré, et AUCUNE touche du suivi de proposition ne
         reste ouverte tant qu'elle n'est pas traitée. La traiter rouvre le
         suivi au barreau SUIVANT (CAD1, jamais un redémarrage) ; annuler la
         touche (RLC1) la rouvre elle-même.

    Garde-fou : RIEN n'est envoyé — ni ``annonce_appel_reda`` ni
    ``offre_reda`` : l'offre du fondateur ne part jamais avant sa décision
    (CAD60). Renvoie la touche close."""
    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_QUESTION_PRIX]
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body, suite=False)
    pause = _poser_etape_de_filet(
        lead, libelle=QUESTION_PRIX_LIBELLE, canal=RelanceEtape.Canal.APPEL,
        vise=timezone.now() + datetime.timedelta(days=FILET_JOINT_DELAI_JOURS),
        note='Posée automatiquement : question de prix — le suivi de '
             'proposition est en pause.')
    _recaler_file(lead, user)
    # Note SYSTÈME (``user=None``) : poser une étape n'est pas un contact.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'Suivi de proposition en pause (question de prix) : étape « '
              f'{QUESTION_PRIX_LIBELLE} » posée pour le '
              f'{pause.due_date:%d/%m/%Y}. Aucun message de relance ne part '
              'tant qu’elle n’est pas traitée.'))
    return etape


# ── CAD-A ── CAD8 — « Demande un devis modifié », atteignable au téléphone ──

def repondre_devis_modifie(etape, user, *, note='', body=''):
    """CAD8 — le client demande une VARIANTE du devis, sur une touche du suivi
    de proposition.

    Le libellé existait déjà (``VISITE_DEVIS_LIBELLE``, « Préparer le devis
    modifié — rappeler le client ») mais n'était posé que depuis la
    qualification rapportée par une visite : au téléphone, « Intéressé »
    relançait le protocole sur un devis déjà écarté. Zéro nouveau concept :

      1. la touche est close (issue « à rappeler » + note typée), SANS
         barreau suivant — le protocole du devis écarté se tait ;
      2. l'étape « Préparer le devis modifié » est posée pour demain par la
         mécanique EXISTANTE des gestes de visite (``_poser_etape_visite``,
         idempotente par libellé) ; un débrief déjà ouvert est RENOMMÉ plutôt
         que doublé — c'est la même étape, dont la nature vient de changer
         (même règle qu'``appliquer_retour_visite``).

    L'ENVOI du nouveau devis démarre son propre suivi de proposition, par la
    mécanique existante — rien n'est câblé ici pour ça. Renvoie la touche
    close."""
    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_DEVIS_MODIFIE]
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body, suite=False)
    config = _config_visite(lead, CLE_DEVIS_MODIFIE)
    existante = _debrief_ouvert(lead)
    if existante is not None:
        _requalifier_debrief(existante, CLE_DEVIS_MODIFIE, config)
    _poser_etape_visite(
        lead, cle=CLE_DEVIS_MODIFIE, ordre=VISITE_ORDRE_DEBRIEF,
        quand=aujourd_hui_local() + datetime.timedelta(
            days=config['delai_jours']),
        devis_id=etape.devis_id, config=config)
    _recaler_file(lead, user)
    return etape


# ── CAD-A ── CAD9 — « Décision à plusieurs (famille / propriétaire) » ───────

#: CIQ508 — les segments dont la décision « à plusieurs » se lit en B2B, et
#: les notes neutres correspondantes (jamais « en famille » pour une usine).
NOTES_DECISION_B2B_SEGMENTS = ('commercial', 'industriel')
NOTES_DECISION_B2B = {
    REPONSE_DECISION_FAMILLE: (
        'Décision à plusieurs — direction / associés (un délai : la décision '
        'se prend ensemble)'),
    REPONSE_DECISION_PROPRIETAIRE: (
        'Décision à plusieurs — le bailleur des murs décide (un '
        'interlocuteur à changer)'),
}


#: CIQ513 — les valeurs de ``Lead.decideur`` qui disent « pas seul ».
DECIDEURS_A_PLUSIEURS = ('conjoint_famille', 'associe_direction',
                         'proprietaire_tiers')


def poser_decision_a_plusieurs_depuis_decideur(lead, user):
    """CIQ513 — « Qui décide » noté sur le lead (``conjoint_famille``,
    ``associe_direction``, ``proprietaire_tiers``) pose l'étiquette « Décision
    à plusieurs » par ``poser_tag_lead`` (idempotent, ligne d'historique) —
    même effet que les deux réponses de touche (CAD9). La partition réactive
    réinjecte alors la touche « dimanche famille » si son jour n'est pas
    passé ; elle n'est jamais inventée. ``seul`` ne retire rien (geste
    humain). Aucun barreau créé. Rend True si l'étiquette vient d'être
    posée."""
    if (getattr(lead, 'decideur', None) or '') not in DECIDEURS_A_PLUSIEURS:
        return False
    if _lead_porte_tag(lead, _TAG_DECISION_A_PLUSIEURS):
        return False
    poser_tag_lead(lead, user, TAG_DECISION_A_PLUSIEURS)
    return True


def repondre_decision_a_plusieurs(etape, user, cle, *, note='', body=''):
    """CAD9 — le client dit qu'il ne décide pas SEUL, sur une touche du
    suivi de proposition.

    Le barreau « dimanche famille » n'était posé que si le lead portait DÉJÀ
    l'étiquette « Décision à plusieurs » au démarrage du plan, et aucune
    réponse ne la posait : le lead moyen recevait 9 touches après-devis, pas
    10. Ici l'étiquette est posée AU MOMENT où le client le dit, PUIS la
    touche est close — dans cet ordre, parce que ``materialiser_touche_
    suivante`` recalcule la partition à chaque touche (filtre d'étiquette de
    ``calculer_echeances_cadence``) : le dimanche famille est RÉINJECTÉ s'il
    n'est pas encore dépassé, jamais inventé s'il l'est.

    La note distingue « en famille » (un DÉLAI) de « le propriétaire décide »
    (un INTERLOCUTEUR à changer). Renvoie la touche close.

    SUIVI E25 (30/09/2026, même règle que la décision fondateur E22) — sur la
    DERNIÈRE touche du suivi de proposition, aucune touche ne suit : le filet
    posait « Préparer et envoyer le devis » alors que le devis est déjà
    parti. L'étiquette est posée comme partout, la touche est close sans
    autre suite, puis « Décider la suite » est posée pour demain (même pose
    qu'après un client joint sur cette touche, E22)."""
    lead = etape.lead
    spec = REPONSES_TOUCHE[cle]
    # CIQ508 — sur un lead commercial ou industriel, la note est NEUTRE
    # (« en famille » n'a pas de sens pour une entreprise) ; résidentiel,
    # agricole et segment vide : la note de REPONSES_TOUCHE, inchangée.
    if (getattr(lead, 'type_installation', '') or '') in NOTES_DECISION_B2B_SEGMENTS:
        spec = {**spec, 'note': NOTES_DECISION_B2B[cle]}
    if not _lead_porte_tag(lead, _TAG_DECISION_A_PLUSIEURS):
        poser_tag_lead(lead, user, TAG_DECISION_A_PLUSIEURS)
    derniere = est_derniere_touche_du_suivi(etape)
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body, suite=not derniere)
    if derniere:
        assurer_prochaine_etape_apres_succes(
            lead, user, cle=CLE_DECIDER_SUITE, avec_plan_devis=False)
    return etape


# ── SUIVI E4 — « Ne veut plus de visite » : la VISITE s'arrête, pas le suivi ─

#: La note des gestes de visite retirés quand la visite est abandonnée.
NOTE_VISITE_ABANDONNEE = 'visite abandonnée'


def repondre_visite_abandonnee(etape, user, *, note='', body=''):
    """SUIVI E4 (30/09/2026) — le client ne veut plus de la visite (étape
    « Planifier la visite », « Confirmer la visite » ou « Débrief visite »).

    Avant, « Ne veut plus de visite » / « Annule le rendez-vous » envoyaient
    « refus » : TOUT le suivi mourait, proposition comprise. Ici, dans
    l'ordre :

      1. la touche est close : FAIT, issue « joint » (le client a parlé),
         note typée + note libre, sans aucune suite (``suite=False``) ;
      2. le rendez-vous éventuel est ANNULÉ côté visites (le technicien est
         prévenu) et ``Lead.visite_prevue_le`` vidé
         (``annuler_rendez_vous_du_lead``) ;
      3. les AUTRES gestes de visite ouverts (planifier, confirmer, débrief —
         jamais « Préparer le devis modifié ») sont annulés (statut moteur) ;
      4. UNE note système dit ce qui s'est passé ;
      5. le filet d'invariant, sans jamais DÉMARRER le suivi de proposition :
         un suivi pendant continue seul, sinon « Préparer et envoyer le
         devis » est posée.

    Renvoie la touche close."""
    lead = etape.lead
    spec = REPONSES_TOUCHE[REPONSE_VISITE_ABANDONNEE]
    jour = lead.visite_prevue_le
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body, suite=False)
    annules = annuler_rendez_vous_du_lead(lead, user)
    retirees = annuler_etapes_moteur_ouvertes(
        lead, CLE_PLANIFIER, CLE_CONFIRMATION, CLE_DEBRIEF,
        note=NOTE_VISITE_ABANDONNEE)
    morceaux = ['Visite abandonnée à la demande du client']
    if annules and jour is not None:
        morceaux.append(f'rendez-vous du {jour:%d/%m/%Y} annulé (le '
                        'technicien est prévenu)')
    elif annules:
        morceaux.append('rendez-vous annulé (le technicien est prévenu)')
    if retirees:
        morceaux.append(f'{retirees} étape(s) de visite retirée(s)')
    # Note SYSTÈME (``user=None``) : dire ce que le moteur a fait n'est pas
    # un contact (garde QJ7).
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=' — '.join(morceaux) + ' : le suivi continue sans visite.')
    assurer_prochaine_etape_apres_succes(
        lead, user, libelle_touche_close=(etape.libelle or ''),
        cle_touche_close=cle_de(etape),
        issue_touche_close=spec['outcome'], demarrer_plan=False)
    _recaler_file(lead, user)
    return etape


# ── SUIVI E16 — « Client joint au téléphone » sur une touche MESSAGE ────────

def repondre_joint_telephone(etape, user, *, note='', body=''):
    """SUIVI E16 (30/09/2026) — la touche prévoyait un message (WhatsApp,
    e-mail), la commerciale a APPELÉ et le client a décroché.

    Avant, la seule réponse était « Le client a répondu » (issue « joint »
    sur une ligne de chatter WhatsApp) : le récepteur MRY9 lisait un MESSAGE
    répondu et posait « Appeler le client — il a répondu au message » — un
    second appel pour un client qu'on venait d'avoir au téléphone.

    Ici, la touche est close « joint » par la machinerie ORDINAIRE
    (``marquer_etape_relance``, suite comprise), mais avec le canal RÉEL :
    la ligne de chatter est un APPEL abouti. La suite est donc celle d'un
    appel : prise de contact (et deuxième affaire) arrêtée → « Préparer et
    envoyer le devis » ; réveil → le dossier sort du Froid, un suivi pendant
    reprend, sinon l'étape devis ; suivi de proposition → le barreau
    suivant. Renvoie la touche close."""
    spec = REPONSES_TOUCHE[REPONSE_JOINT_TELEPHONE]
    return marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=_note_reponse(spec, note),
        outcome=spec['outcome'], body=body,
        canal_reel=RelanceEtape.Canal.APPEL)


# ── SUIVI E12 — « Planifier la visite » sans réponse : on réessaie demain ──

def repondre_planifier_sans_reponse(etape, user, *, note='', body=''):
    """SUIVI E12 (30/09/2026) — l'appel pour caler la date de la visite n'a
    pas abouti. Le client a ACCEPTÉ la visite : on réessaie, jamais « Préparer
    et envoyer le devis » à la place.

    L'appel compte (touche close FAIT, issue « non joint », sans autre
    suite) et une NOUVELLE étape « Planifier la visite technique convenue »
    est posée pour DEMAIN (même devis rattaché). Si un rendez-vous a été calé
    entre-temps, ou que le lead n'est plus relançable, le filet ordinaire
    décide (jamais un lead actif sans suite). Renvoie ``(touche close,
    nouvelle étape ou None)``."""
    lead = etape.lead
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=note,
        outcome='non_joint', body=body, suite=False)
    nouvelle = None
    if _lead_relancable(lead) and not _visite_a_venir(lead):
        nouvelle = _poser_etape_visite(
            lead, cle=CLE_PLANIFIER, ordre=VISITE_ORDRE_FILET,
            quand=aujourd_hui_local() + datetime.timedelta(days=1),
            devis_id=etape.devis_id)
        # Note SYSTÈME (``user=None``) : poser une étape n'est pas un contact.
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Pas de réponse pour caler la visite : étape « '
                  f'{nouvelle.libelle} » reposée pour le '
                  f'{nouvelle.due_date:%d/%m/%Y}.'))
    else:
        assurer_prochaine_etape_apres_succes(
            lead, user, libelle_touche_close=(etape.libelle or ''),
            cle_touche_close=cle_de(etape), issue_touche_close='non_joint',
            demarrer_plan=False)
    _recaler_file(lead, user)
    return etape, nouvelle


# ── SUIVI E22 / E23 — la DERNIÈRE touche d'un protocole ────────────────────

def _est_dernier_barreau(etape, cadence):
    """SUIVI E22 / E23 (30/09/2026) — ``etape`` est-elle le DERNIER barreau du
    protocole ``cadence``, celui après lequel aucune touche suivante ne naît
    (``materialiser_touche_suivante``) ?

    MÊME critère que la promesse servie à l'écran : un BARREAU
    (``suite_touche.nature_touche`` — jamais une étape de visite ou de
    filet, qui porte la cadence sans être du protocole) et
    ``suite_touche.est_derniere_touche`` sur les barreaux ACTIFS de la
    société (le plus grand rang, ou une touche dont le rang n'est plus un
    barreau actif). Lecture pure (une requête, aucune écriture) ; une touche
    absente (``None``) n'est la dernière de rien."""
    if etape is None or etape.cadence != cadence:
        return False
    from .suite_touche import (
        NATURE_BARREAU, est_derniere_touche, nature_touche,
        ordres_de_la_cadence)

    return (nature_touche(etape) == NATURE_BARREAU
            and est_derniere_touche(
                etape, ordres_de_la_cadence(etape.company_id, cadence)))


def est_derniere_touche_du_suivi(etape):
    """SUIVI E22 (décision fondateur du 30/09/2026) — ``etape`` est-elle la
    DERNIÈRE touche du SUIVI DE PROPOSITION (cadence ``apres_devis``) ?

    Relue par le récepteur d'issue MRY9 sur la touche close
    (``touche_close_de``) : un client JOINT sur elle (appel abouti, message
    répondu, client joint au téléphone) ne fait plus poser « Préparer et
    envoyer le devis » — le devis est déjà parti — mais « Décider la suite »,
    pour demain. Sur toute autre touche du suivi, rien ne change : le
    barreau suivant naît."""
    return _est_dernier_barreau(etape, 'apres_devis')


#: SUIVI E24 — les deux PRISES DE CONTACT : celle d'un prospect (``contact``)
#: et celle d'un client déjà acquis qui revient (``deuxieme_affaire``, CAD128)
#: — la table du parcours les range sous les mêmes types d'étape (même
#: couple que ``suite_touche._CADENCES_PRISE_DE_CONTACT``, SUIVI E15).
CADENCES_PRISE_DE_CONTACT = ('contact', CADENCE_DEUXIEME_AFFAIRE)


def est_derniere_touche_de_contact(etape):
    """SUIVI E23 / E24 (décisions fondateur du 30/09/2026) — ``etape``
    est-elle la DERNIÈRE touche d'une PRISE DE CONTACT : celle d'un prospect
    (cadence ``contact``, E23) ou d'un client acquis qui revient (cadence
    ``deuxieme_affaire``, E24) — chacune lue sur les barreaux actifs de SA
    cadence ?

    Lue par la vue « Fait » : « À rappeler le… » sur elle ne pose plus
    « Préparer et envoyer le devis » à la date choisie (aucune touche
    suivante ne pouvait porter la date) mais l'APPEL « Rappeler le client —
    rappel convenu », à la date et à l'heure convenues
    (``repondre_rappel_convenu``, E10/E17). Sur toute autre touche de la
    prise de contact, rien ne change : la touche suivante est datée."""
    return (etape is not None
            and etape.cadence in CADENCES_PRISE_DE_CONTACT
            and _est_dernier_barreau(etape, etape.cadence))


# ── SUIVI E10 / E17 — un créneau CONVENU devient un APPEL à cette date ──────

def est_dernier_reveil(etape):
    """SUIVI E17 (30/09/2026) — ``etape`` est-elle la DERNIÈRE touche de la
    cadence réveil, celle après laquelle aucun réveil suivant ne peut porter
    la date d'un « À rappeler le… » ?

    MÊME critère que la promesse servie à l'écran
    (``suite_touche.est_derniere_touche`` sur les barreaux ACTIFS de la
    société — le plus grand rang, ou une touche hors gabarit comme un réveil
    saisonnier) : ce que l'écran annonce et ce que le moteur fait ne peuvent
    pas diverger. Lecture pure (une requête, aucune écriture)."""
    if etape.cadence != 'reveil':
        return False
    from .suite_touche import est_derniere_touche, ordres_de_la_cadence

    return est_derniere_touche(
        etape, ordres_de_la_cadence(etape.company_id, 'reveil'))


def repondre_rappel_convenu(etape, user, quand, *, note='', body='',
                            sortir_du_froid=False):
    """SUIVI E10 / E17 (30/09/2026) — le client a convenu d'un moment pour
    être APPELÉ : la touche est close (FAIT, issue « à rappeler »), et
    l'étape « Rappeler le client — rappel convenu » (clé ``rappel_convenu``,
    un appel) est posée À LA DATE ET À L'HEURE convenues, recalées sur la
    fenêtre d'appel de la société.

    Deux touches y mènent :

    * « Message — proposer un créneau pour l'appel » (E10) : l'étape message
      était déplacée telle quelle, et « rappel convenu » restait
      inatteignable depuis l'écran ;
    * le DERNIER réveil (E17) : la date choisie n'était reportée sur rien.
      Avec ``sortir_du_froid``, un dossier au Froid en sort d'abord
      (→ Contacté) : un client qui fixe une date de rappel est réactivé — et
      un réveil resté ouvert (réveil saisonnier, barreau réordonné) s'arrête
      avec lui : le rendez-vous convenu le remplace.

    Aucune autre suite (``suite=False``) ; UNE note système dit l'étape posée.
    Renvoie ``(touche close, étape « rappel convenu »)``."""
    from . import horaires

    lead = etape.lead
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=note, outcome='rappel',
        body=body, suite=False)
    if sortir_du_froid:
        arreter_cadence(lead, user=user, cadences=['reveil'],
                        motif='rappel convenu avec le client')
        lead.refresh_from_db(fields=['stage'])
        if lead.stage == stages.COLD:
            avancer_stage_lead_vers(lead, user, stages.CONTACTED)
    rappel = _poser_etape_de_filet(
        lead, cle=CLE_RAPPEL_CONVENU, a_la_date=quand,
        note='Posée : créneau d’appel convenu avec le client.')
    _recaler_file(lead, user)
    quand_local = rappel.due_at.astimezone(horaires.CASABLANCA)
    quand_lisible = quand_local.strftime('%d/%m/%Y à %H:%M')
    # Note SYSTÈME (``user=None``) : poser une étape n'est pas un contact.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'Créneau convenu avec le client : étape « {rappel.libelle} » '
              f'posée pour le {quand_lisible}.'))
    return etape, rappel


# ── CAD-A ── CAD101 — « pièce reçue » : le geste pour l'enregistrer ─────────
#
# Le client envoie sa facture, son adresse ou sa localisation sur WhatsApp :
# c'est l'événement commercial le plus important du parcours, et le seul qui
# ne s'enregistrait pas en un clic. Le raccordement WhatsApp entrant ne lit que
# le texte, et un message entrant est une note SYSTÈME (``user=None``) que les
# récepteurs d'arrêt ignorent — volontairement : un « merci » ne doit jamais
# tuer une cadence (décision confirmée au round 2, CAD61). Le geste reste donc
# HUMAIN : Meryem dit « pièce reçue » sur la touche ouverte.

#: Les pièces qu'un client envoie spontanément, et leur libellé.
TYPES_PIECE_RECUE = {
    'facture': 'Facture',
    'adresse': 'Adresse',
    'localisation': 'Localisation',
}


def refus_piece_recue(etape, type_piece):
    """CAD101 — ``(champ, message)`` si le geste ne vaut pas, sinon ``None``.
    Le message NOMME le champ tel que l'écran l'affiche."""
    if etape.statut != RelanceEtape.Statut.A_FAIRE:
        return ('etape', '« Pièce reçue » : cette touche est déjà traitée — '
                'le geste se fait sur une touche encore à faire.')
    if (type_piece or '').strip() not in TYPES_PIECE_RECUE:
        choix = ', '.join(v.lower() for v in TYPES_PIECE_RECUE.values())
        return ('type_piece', f'« Pièce reçue » : choisissez la pièce ({choix}).')
    return None


def enregistrer_piece_recue(etape, user, *, type_piece, attachment=None,
                            note=''):
    """CAD101 — le client a ENVOYÉ une pièce : un geste, trois effets.

      1. l'étape « Préparer et envoyer le devis (ou fixer un rappel) » est
         posée (filet existant, même délai que le filet « joint ») — AVANT la
         clôture, pour que le filet du récepteur « joint » la trouve ouverte et
         n'en pose pas une seconde ;
      2. la touche est CLOSE, issue « joint » (le client a répondu : la prise
         de contact a atteint son but, récepteur MRY9 inchangé) avec la note
         typée « Pièce reçue — facture », SANS barreau suivant ;
      3. le document éventuel est ATTACHÉ à la ligne de chatter de la touche
         (magasin ``records.Attachment`` existant, déposé par la vue).

    Aucun arrêt n'est jamais déclenché par un message ENTRANT : ce geste est
    humain. Renvoie ``(touche close, étape « préparer le devis »)``."""
    lead = etape.lead
    libelle_piece = TYPES_PIECE_RECUE[type_piece]
    if est_etape(etape, CLE_DEVIS):
        # La touche ouverte EST déjà « préparer le devis » : la clore pour la
        # reposer à l'identique n'aurait aucun sens. La pièce est tracée (et
        # attachée) sur la fiche, l'étape reste ouverte — son « Fait » vaudra
        # toujours « devis parti » (QJ-FUNNEL).
        ligne = LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Pièce reçue du client : {libelle_piece.lower()} — '
                  f'l’étape « {etape.libelle} » reste ouverte.'
                  + (f' Note : {note.strip()}' if (note or '').strip()
                     else '')))
        if attachment is not None:
            ligne.attachment = attachment
            ligne.save(update_fields=['attachment'])
        return etape, etape
    etape_devis = _poser_etape_de_filet(
        lead, cle=CLE_DEVIS,
        note=f'Posée : pièce reçue du client ({libelle_piece.lower()}).')
    note_typee = f'Pièce reçue — {libelle_piece.lower()}'
    if (note or '').strip():
        note_typee = f'{note_typee} — {note.strip()}'
    corps = f'Pièce reçue du client : {libelle_piece.lower()}'
    corps += ' (fichier joint).' if attachment is not None else '.'
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=note_typee,
        outcome='joint', body=corps, suite=False)
    if attachment is not None:
        ligne = (LeadActivity.objects
                 .filter(company=lead.company, lead=lead, user=user,
                         body__startswith=prefixe_activite_touche(etape))
                 .order_by('-pk').first())
        if ligne is not None:
            ligne.attachment = attachment
            ligne.save(update_fields=['attachment'])
    _recaler_file(lead, user)
    etape_devis.refresh_from_db()
    return etape, etape_devis


# ── CAD-A ── CAD10 — le motif de refus, FACULTATIF, au moment où il est dit ─
#
# « Refus » posait l'étape « Décider la suite » sans demander pourquoi ; le
# motif n'était exigé que bien plus tard, à la mise en « perdu », quand
# personne ne se souvient de ce que le client a dit. Ici le motif est PROPOSÉ
# dans le panneau de réponse, parmi la liste déjà paramétrée (Paramètres →
# CRM, ``MotifPerte``) — FACULTATIF (MRY22 : « perdu » reste une décision
# humaine) et journalisé sur la ligne de chatter de la touche, JAMAIS sur
# ``Lead.motif_perte``.


def mention_motif_refus(nom):
    """La phrase ajoutée à la ligne de chatter de la touche refusée."""
    return f'Motif de refus : {nom}.'


# ── CAD-A ── CAD11 — « Numéro invalide / a bloqué » : junk en un clic ───────
#
# Un numéro mort épuisait les six tentatives du protocole : Répondeur et
# Occupé retombaient sur « non joint » avec une note, et le drapeau
# ``MotifPerte.est_junk`` vivait au niveau du lead, à trois écrans de la
# touche. Le raccourci suit le patron Répondeur/Occupé (issue ``non_joint`` +
# note typée, AUCUNE nouvelle valeur d'énumération, aucune migration) et
# PROPOSE « perdu, motif junk » en un clic — une proposition : c'est le clic
# humain qui décide (MRY22), jamais le moteur.

def motif_junk_valide(company, nom):
    """Le libellé EXACT du motif JUNK (``est_junk``, actif) ``nom`` de
    ``company`` (comparaison sans casse), ou ``None``."""
    from .models import MotifPerte

    nom = (nom or '').strip()
    if not nom or company is None:
        return None
    return (MotifPerte.objects
            .filter(company=company, archived=False, est_junk=True,
                    nom__iexact=nom)
            .values_list('nom', flat=True).first())


def marquer_lead_perdu(lead, user, motif, *, exclure=None):
    """SUIVI E2 (30/09/2026) — LE geste « le lead passe PERDU » depuis une
    touche : ``motif`` (déjà validé) posé sur ``Lead.motif_perte``,
    journalisé comme la fiche le ferait (lignes « modification » ancien →
    nouveau), et TOUTES ses touches ouvertes sont arrêtées sous ce motif —
    la même conséquence que la bascule « perdu » de la fiche
    (``LeadViewSet.perform_update``, MRY9). ``exclure`` (une touche) la
    laisse ouverte : l'appelant la clôt lui-même avec son issue (même patron
    que « Ne plus me contacter »).

    Idempotente : un lead déjà perdu n'est pas réécrit. Renvoie ``True`` si
    le lead vient de passer perdu. Généralise ``marquer_lead_perdu_junk``
    (CAD11), qui en reste un alias mince."""
    import copy

    if lead.perdu:
        return False
    avant = copy.copy(lead)
    lead.perdu = True
    lead.motif_perte = motif
    lead.save(update_fields=['perdu', 'motif_perte'])
    activity.log_changes(avant, lead, user)
    arreter_cadence(lead, user=user, motif=motif, exclure=exclure)
    # SUIVI E21 — le rendez-vous de visite en attente s'annule aussi.
    annuler_rendez_vous_sur_arret(lead, user, cause=cause_rdv_perdu(motif))
    return True


def marquer_lead_perdu_junk(lead, user, motif):
    """CAD11 — le lead passe PERDU avec le motif junk ``motif`` (déjà
    validé) : alias mince de ``marquer_lead_perdu`` (SUIVI E2)."""
    return marquer_lead_perdu(lead, user, motif)


def refus_motif_perte(company, motif):
    """SUIVI E2 — ``(motif exact, None)`` si ``motif`` est un motif de perte
    ACTIF de la société (comparaison sans casse — ``motif_refus_valide``),
    sinon ``(None, message)`` : le message NOMME le champ « Motif de perte »,
    qu'il soit absent ou hors liste (règle fondateur du 08/09/2026)."""
    brut = str(motif or '').strip()
    libelle = REPONSES_TOUCHE[REPONSE_PERDU]['libelle']
    if not brut:
        return None, (f'« Motif de perte » : obligatoire pour « {libelle} » — '
                      'choisissez le motif dans la liste.')
    nom = motif_refus_valide(company, brut)
    if nom is None:
        return None, (f'« Motif de perte » : « {brut} » n’est pas un motif '
                      'de la liste (Paramètres → CRM).')
    return nom, None


def repondre_perdu(etape, user, motif, *, note='', body=''):
    """SUIVI E2 — « Perdu — clore le dossier » sur l'étape « Décider la
    suite ». Dans cet ordre :

      1. le lead passe PERDU avec ``motif`` (déjà validé,
         ``refus_motif_perte``) et toutes ses AUTRES touches ouvertes sont
         arrêtées (``marquer_lead_perdu``, la touche exclue) — AVANT la
         clôture, pour que le filet du récepteur « refus » (MRY9) trouve un
         lead perdu et ne pose aucune étape ;
      2. la touche est close : FAIT, issue « refus », note typée « Perdu —
         <motif> » suivie de la note libre, sans aucune suite
         (``suite=False``) ;
      3. ceinture : plus rien ne reste ouvert (idempotent).

    Aucune étape n'est posée ensuite : le lead sort des files, il reste
    rouvrable depuis sa fiche (CAD107). Renvoie la touche close."""
    lead = etape.lead
    marquer_lead_perdu(lead, user, motif, exclure=etape)
    note_typee = f'{REPONSES_TOUCHE[REPONSE_PERDU]["note"]} — {motif}'
    if (note or '').strip():
        note_typee = f'{note_typee} — {note.strip()}'
    etape = marquer_etape_relance(
        etape, user, RelanceEtape.Statut.FAIT, note=note_typee,
        outcome=REPONSES_TOUCHE[REPONSE_PERDU]['outcome'], body=body,
        suite=False)
    arreter_cadence(lead, user=user, motif=motif)
    return etape


#: Le motif de perte d'un locataire sans propriétaire joignable (existant).
MOTIF_PERTE_LOCATAIRE = 'Locataire'


#: Les deux suites que l'écran propose quand la réponse est « locataire ».
SUITES_LOCATAIRE = ('creer_proprietaire', 'perdu_locataire')

#: Ce que la fiche du propriétaire reprend de celle du locataire : c'est le
#: MÊME logement (l'adresse, le repère, le segment) — jamais l'identité ni la
#: consommation, qui sont celles du locataire.
_CHAMPS_LOGEMENT = ('adresse', 'ville', 'gps_lat', 'gps_lng', 'lien_maps',
                    'type_installation')


def proposition_locataire(lead):
    """CAD164 — ce que l'écran propose pour ce lead : les deux suites quand
    la réponse « propriétaire ou locataire » est « locataire », rien sinon."""
    locataire = (getattr(lead, 'ownership', None)
                 == Lead.Ownership.LOCATAIRE)
    return {
        'locataire': locataire,
        'propose': list(SUITES_LOCATAIRE) if locataire else [],
        'motif_perte': MOTIF_PERTE_LOCATAIRE,
    }


def refus_proprietaire(donnees):
    """CAD164 — ``{champ: [message]}`` si les coordonnées du propriétaire ne
    permettent pas de créer sa fiche, sinon ``None``. Chaque message NOMME le
    champ tel que l'écran l'affiche."""
    if not isinstance(donnees, dict):
        return {'proprietaire': ['« Propriétaire » : coordonnées attendues '
                                 '(nom et téléphone).']}
    erreurs = {}
    if not (donnees.get('nom') or '').strip():
        erreurs['nom'] = ['« Nom du propriétaire » : obligatoire.']
    numero = (donnees.get('telephone') or donnees.get('whatsapp') or '')
    if not normalize_phone(numero):
        erreurs['telephone'] = ['« Téléphone du propriétaire » : un numéro '
                                'joignable est obligatoire.']
    return erreurs or None


def _marquer_locataire(lead, user):
    """La réponse « locataire » est posée sur la fiche (journalisée) si elle
    ne l'était pas déjà."""
    import copy

    if lead.ownership == Lead.Ownership.LOCATAIRE:
        return
    avant = copy.copy(lead)
    lead.ownership = Lead.Ownership.LOCATAIRE
    lead.save(update_fields=['ownership'])
    activity.log_changes(avant, lead, user)


def creer_lead_proprietaire(locataire, user, donnees, *, queryset=None):
    """CAD164 — le propriétaire est joignable : SA fiche, liée au locataire.

    Un propriétaire DÉJÀ connu (même téléphone, même société) est RELIÉ, jamais
    dupliqué. Sinon sa fiche naît au canal « Référence » (le texte d'origine
    « recommandation » de CAD127 s'applique à sa première touche), avec le
    logement du locataire (adresse, repère, segment) et le même responsable,
    puis sa cadence de prise de contact démarre par le chemin ordinaire.

    ACRM7 (D-ACRM-1) — ``queryset`` borne le rapprochement aux leads de la
    PORTÉE de l'appelant (la vue passe ses leads en portée) : un propriétaire
    connu d'un collègue hors portée est traité comme ABSENT (fiche neuve,
    aucune note ni identité chez le collègue). ``None`` (chemins système) =
    toute la société, comportement historique.

    Renvoie ``(fiche du propriétaire, créée ?)``."""
    from django.db import transaction

    nom = (donnees.get('nom') or '').strip()
    prenom = (donnees.get('prenom') or '').strip()
    telephone = (donnees.get('telephone') or '').strip()
    whatsapp = (donnees.get('whatsapp') or '').strip()
    with transaction.atomic():
        _marquer_locataire(locataire, user)
        existant = next(iter(find_duplicates_by_contact(
            locataire.company, phone=telephone or whatsapp,
            exclude_pk=locataire.pk, queryset=queryset)), None)
        cree = existant is None
        if cree:
            proprietaire = Lead(
                company=locataire.company, nom=nom, prenom=prenom or None,
                telephone=telephone or None, whatsapp=whatsapp or None,
                ownership=Lead.Ownership.PROPRIETAIRE,
                canal=Lead.Canal.REFERENCE, owner=locataire.owner)
            for champ in _CHAMPS_LOGEMENT:
                setattr(proprietaire, champ, getattr(locataire, champ, None))
            proprietaire.save()
            activity.log_creation(proprietaire, user)
        else:
            proprietaire = existant
        nom_locataire = ' '.join(
            p for p in ((locataire.prenom or '').strip(),
                        (locataire.nom or '').strip()) if p)
        LeadActivity.objects.create(
            company=proprietaire.company, lead=proprietaire, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'{PREFIXE_LIEN_LOCATAIRE}{locataire.pk} ({nom_locataire}) '
                  ': le locataire du logement nous a donné les coordonnées du '
                  'propriétaire.'))
        LeadActivity.objects.create(
            company=locataire.company, lead=locataire, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Locataire — propriétaire du logement : fiche '
                  f'#{proprietaire.pk} '
                  + ('créée' if cree else 'déjà connue, reliée')
                  + f' ({proprietaire.nom}).'))
    if cree:
        demarrer_cadence_contact(proprietaire, user=user,
                                 origine='recommandation (locataire)')
    return proprietaire, cree


def clore_locataire_sans_proprietaire(lead, user):
    """CAD164 — le locataire ne communique pas son propriétaire (ou il est
    injoignable) : « Perdu — Locataire », motif EXISTANT, et toutes ses
    touches s'arrêtent (même conséquence que la bascule « perdu » de la
    fiche, MRY9). Idempotente. Renvoie ``True`` si le lead vient de passer
    perdu."""
    import copy

    _marquer_locataire(lead, user)
    if lead.perdu:
        return False
    motif = (motif_refus_valide(lead.company, MOTIF_PERTE_LOCATAIRE)
             or MOTIF_PERTE_LOCATAIRE)
    avant = copy.copy(lead)
    lead.perdu = True
    lead.motif_perte = motif
    lead.save(update_fields=['perdu', 'motif_perte'])
    activity.log_changes(avant, lead, user)
    arreter_cadence(lead, user=user, motif=motif)
    return True
