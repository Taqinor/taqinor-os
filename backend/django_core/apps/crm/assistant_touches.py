"""COP-C3 / COP-C4 — UNE touche du suivi servie à l'assistant, en lecture.

``GET /api/django/crm/assistant/touches/<id>/`` (contrat
``contract_samples/assistant_touche.json``) :

* sans paramètre, tout ce qu'il faut à la carte « touche » : la ligne de la
  touche, le lead, puis le message VALIDÉ rendu par le MÊME code que l'écran
  Relances (``cadence_messages.message_pour_etape``) ou le script d'appel du
  panneau d'appel — jamais un texte écrit par le modèle ;
* avec ``?geste=fait|reporter|sauter`` et la réponse comprise, la CARTE-ÉCHO :
  le serveur VALIDE la réponse (mêmes règles que le geste réel) et rend
  ``proposition`` — le libellé en clair et le CORPS EXACT que la carte postera
  au geste existant quand la commerciale appuie. Rien n'est écrit ici, rien
  n'est envoyé, rien ne clôt une touche (RELANCE-WA).

Fichier à part : ``apps/crm/views.py`` et ``cadence_views.py`` sont des
fichiers-murs. Les validateurs du geste réel (``_parse_rappel``,
``_refus_date_passee``, les messages de refus…) sont IMPORTÉS de
``cadence_views`` ; ce qui n'est pas isolable (la suite exacte que le moteur
programmera, la présence d'une visite déjà calée…) n'est vérifié qu'au vrai
geste, qui garde son 409 nommé.
"""
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.roles.permissions import DroitDeLaGrille

from . import schema_docs as sd
from . import stages

GESTES = ('fait', 'reporter', 'sauter')

#: Paramètres de requête lus pour la proposition (les corps de ``fait``,
#: ``reporter`` et ``sauter`` — ``body`` reste réservé à l'écran). Jamais
#: ``due_at`` : l'écran ne poste un report qu'en ``rappel_le`` / ``rappel_heure``
#: (ancrés à Casablanca côté serveur), un ``due_at`` proposé y serait perdu.
PARAMETRES_PROPOSITION = (
    'geste', 'outcome', 'reponse', 'motif_refus', 'perdu_junk', 'motif_perte',
    'raison_attente', 'rappel_le', 'rappel_heure', 'note', 'langue', 'mode')

#: Refus de la carte-écho pour un compte qui ne passe pas la garde des vrais
#: gestes (``fait`` / ``reporter`` / ``sauter``).
MESSAGE_ROLE_SANS_ENREGISTREMENT = (
    "Votre rôle ne permet pas d'enregistrer la réponse d'une touche.")

#: Refus du rendu (``cadence_messages.refus_rendu_whatsapp``) -> (code, phrase).
_REFUS_RENDU = {
    'ne plus contacter': (
        'opposition', 'Ce contact a demandé à ne plus être contacté : '
        'aucun message ne peut être préparé.'),
    'perdu/archivé': (
        'perdu_ou_archive', 'Ce lead est perdu ou archivé : aucun message '
        'ne peut être préparé.'),
    'touche annulée': (
        'touche_annulee', 'Cette touche a été annulée par le moteur : '
        'rien à préparer.'),
}


class PropositionRefusee(Exception):
    """La réponse comprise ne vaut pas sur cette touche (message lisible)."""


def touche_en_portee(user, touche_id):
    """La touche de ``user`` (société + portée du lead, comme la file des
    relances) ou 404 — une touche d'une autre société ou hors portée est
    traitée comme ABSENTE."""
    from .models import RelanceEtape
    from .portee_selectors import leads_visibles

    visibles = leads_visibles(user, user.company).values('id')
    etape = (RelanceEtape.objects.select_related('lead', 'lead__owner')
             .filter(pk=touche_id, company=user.company, lead_id__in=visibles)
             .first())
    if etape is None:
        raise Http404
    return etape


def nom_du_lead(lead):
    """« Prénom Nom » — la forme des lignes de la file de l'assistant."""
    return f'{lead.prenom or ""} {lead.nom}'.strip()


def _bloc_lead(lead):
    from .cadence_messages import langue_relance_du_lead

    return {'lead_id': lead.pk, 'nom': nom_du_lead(lead),
            'ville': lead.ville or '', 'etape': lead.stage,
            'langue': langue_relance_du_lead(lead)}


def _bloc_appel(request, etape):
    """Script et questions encore à poser (le MÊME code que le panneau
    d'appel) ; téléphone vide sans ``client_pii_voir``."""
    from .panneau_appel import _script_servi, questions_a_poser
    from .serializers import pii_masquee_pour

    lead = etape.lead
    masque = pii_masquee_pour(request.user)
    return {
        'telephone': '' if masque else (lead.telephone or lead.whatsapp or ''),
        'script': _script_servi(etape, request=request, user=request.user),
        'champs_a_poser': questions_a_poser(lead),
    }


def _refus_du_rendu(rendu, etape, user):
    """``{code, detail}`` quand le message rendu ne peut PAS être ouvert
    (preuve manquante, numéro inexploitable), sinon ``None``."""
    from .cadence_messages import REFUS_PREUVE_MANQUANTE
    from .models import RelanceEtape
    from .serializers import pii_masquee_pour

    if rendu.get('preuve_manquante'):
        return {'code': 'preuve_manquante', 'detail': REFUS_PREUVE_MANQUANTE}
    if etape.canal == RelanceEtape.Canal.WHATSAPP and not rendu.get('wa_url'):
        if pii_masquee_pour(user):
            return {'code': 'droit_manquant', 'detail': (
                "Votre rôle ne permet pas de voir le numéro du client : "
                'ouvrez la fiche pour préparer le message.')}
        return {'code': 'numero_invalide',
                'detail': 'Numéro de téléphone invalide.'}
    return None


def _refus_du_lead(etape):
    """Le refus du rendu pour CE lead et CETTE touche (opposition, perdu,
    archivé, touche annulée), ou ``None`` — la garde unique ACVI44."""
    from .cadence_messages import refus_rendu_whatsapp

    motif = refus_rendu_whatsapp(etape.lead, etape=etape)
    if not motif:
        return None
    code, detail = _REFUS_RENDU.get(motif, ('refuse', f'Refusé : {motif}.'))
    return {'code': code, 'detail': detail}


def touche_prete(request, etape):
    """Le corps de la carte « touche » : ``{touche, lead, message, appel,
    refus}`` — exactement un de ``message``/``appel``/``refus`` quand la
    touche est préparable (aucun pour une TÂCHE, qui se traite sans texte)."""
    from .models import RelanceEtape
    from .serializers_cadence import RelanceEtapeSerializer
    from .suite_touche import est_tache

    corps = {
        'touche': RelanceEtapeSerializer(
            etape, context={'request': request}).data,
        'lead': _bloc_lead(etape.lead),
        'message': None, 'appel': None, 'refus': _refus_du_lead(etape),
    }
    if corps['refus'] is not None or est_tache(etape):
        return corps
    if etape.canal == RelanceEtape.Canal.APPEL:
        corps['appel'] = _bloc_appel(request, etape)
    elif (etape.canal in (RelanceEtape.Canal.WHATSAPP,
                          RelanceEtape.Canal.EMAIL) or etape.template_cle):
        from .cadence_messages import message_pour_etape

        rendu = message_pour_etape(
            etape, request=request, user=request.user)
        corps['refus'] = _refus_du_rendu(rendu, etape, request.user)
        if corps['refus'] is None:
            corps['message'] = rendu
    return corps


# ── COP-C4 — la carte-écho d'une réponse ────────────────────────────────────

#: Mot de la commerciale par issue (le libellé de la proposition).
_MOT_ISSUE = {
    'joint': 'client joint', 'non_joint': 'pas de réponse',
    'rappel': 'à rappeler', 'refuse': 'refus',
    'visite_acceptee': 'visite acceptée', 'sans_issue': 'fait',
    '': 'fait',
}


def _quand_en_clair(quand):
    """« jeudi 19 novembre à 11:00 » (date en toutes lettres, heure si elle
    a été donnée)."""
    from apps.crm import horaires

    from .cadence_messages import _date_visite_francais

    local = quand.astimezone(horaires.CASABLANCA)
    return _date_visite_francais(local.date())


def _lire_rappel(p, champ):
    """``(quand, fragment de corps)`` d'un rappel saisi, ``(None, {})`` sans
    date ; lève ``PropositionRefusee`` (format, puis date passée — CAD27)."""
    from .cadence_views import _parse_rappel, _refus_date_passee

    brut = p.get('rappel_le', '')
    if not brut:
        return None, {}
    quand = _parse_rappel(brut, p.get('rappel_heure', ''))
    if quand is None:
        raise PropositionRefusee(
            f'« {champ} » : date invalide (AAAA-MM-JJ attendu, heure HH:MM '
            'optionnelle).')
    refus = _refus_date_passee(quand, champ)
    if refus:
        raise PropositionRefusee(refus)
    fragment = {'rappel_le': brut}
    if p.get('rappel_heure'):
        fragment['rappel_heure'] = p['rappel_heure']
    return quand, fragment


def _avec_heure(quand, p):
    texte = _quand_en_clair(quand)
    return f'{texte} à {p["rappel_heure"]}' if p.get('rappel_heure') else texte


def _dernier_barreau(etape):
    """La touche est-elle la dernière de sa cadence (même lecture que le
    moteur) ? Alors « pas de réponse » parque le dossier au Froid."""
    from .suite_touche import (
        NATURE_BARREAU, est_derniere_touche, nature_touche,
        ordres_de_la_cadence)

    return (nature_touche(etape) == NATURE_BARREAU and est_derniere_touche(
        etape, ordres_de_la_cadence(etape.company_id, etape.cadence)))


def _effet_rappel(etape, quand_texte):
    """« À rappeler le… » : les MÊMES branches, dans le même ordre, que
    ``RelanceEtapeViewSet._marquer`` (SUIVI E10/E17/E23/E25, puis CAD3/E3)."""
    from .cadence_config import CLE_MESSAGE_CRENEAU, est_etape
    from .cadence_plan import est_etape_de_filet
    from .cadence_reperes import est_etape_de_visite
    from .cadence_reponses import (
        est_dernier_reveil, est_derniere_touche_de_contact,
        est_derniere_touche_du_suivi)

    if (est_etape(etape, CLE_MESSAGE_CRENEAU) or est_dernier_reveil(etape)
            or est_derniere_touche_de_contact(etape)
            or est_derniere_touche_du_suivi(etape)):
        return ('La touche est faite ; l\'appel « Rappeler le client — '
                f'rappel convenu » est posé pour {quand_texte}.')
    if est_etape_de_filet(etape) or est_etape_de_visite(etape):
        return (f'La touche est reportée au {quand_texte} : elle n\'est pas '
                'close et garde sa place dans le suivi.')
    return ('La touche est faite ; la touche suivante du suivi est placée au '
            f'{quand_texte}. Annulable 24 h.')


def _effet_issue(etape, issue, quand_texte):
    """La conséquence réelle, en français clair, d'une issue enregistrée ;
    ``quand_texte`` (date saisie) avec une autre issue que « À rappeler »
    PLACE la touche suivante à cette date (``_marquer``, placement final)."""
    froid = stages.STAGE_LABELS[stages.COLD]
    if issue == 'rappel':
        return _effet_rappel(etape, quand_texte)
    from .cadence_config import CLE_PLANIFIER, est_etape
    if issue == 'non_joint' and est_etape(etape, CLE_PLANIFIER):
        # SUIVI E12 — ``_marquer`` : l'appel compte, l'étape est REPOSÉE (demain,
        # ou à la date donnée) ; jamais « la touche suivante du protocole ».
        return ("L'appel est compté ; l'étape « Planifier la visite » est "
                'reposée ' + (f'au {quand_texte}.' if quand_texte else 'pour demain.'))
    if issue in ('non_joint', '') and _dernier_barreau(etape):
        return ("C'est la dernière touche de la cadence : aucune suite n'est "
                f'programmée et le dossier part à « {froid} » s\'il n\'y est '
                'pas déjà (annulation impossible).')
    effets = {
        'joint': ("La touche est faite et la prise de contact s'arrête ; "
                  "le suivi pose l'étape suivante."),
        'non_joint': ('La touche est faite ; la touche suivante du protocole '
                      'est programmée à son délai. Annulable 24 h.'),
        'refuse': ('La touche est faite avec l\'issue « Refus » : le suivi '
                   "s'arrête pour ce lead."),
        'visite_acceptee': ('La touche est faite ; la visite technique est à '
                            'planifier (étape posée par le suivi).'),
    }
    effet = effets.get(issue, 'La touche est faite ; le suivi pose '
                       "l'étape suivante. Annulable 24 h.")
    if quand_texte:
        # ``reporter_prochaine_touche`` ne place rien s'il ne reste aucune
        # touche ouverte : la phrase ne promet pas plus que le geste.
        effet += (' La touche suivante, s\'il en reste une, est placée au '
                  f'{quand_texte}.')
    return effet


def _effet_reponse(cle, spec, quand_texte, motif):
    """La conséquence d'une réponse du client (``REPONSES_TOUCHE``)."""
    effets = {
        'ne_plus_contacter': (
            'Le lead est marqué « ne plus contacter » : toutes ses relances '
            "s'arrêtent et aucun message ne pourra plus être préparé "
            '(annulation impossible).'),
        'plus_tard': (f'La touche est faite ; le dossier est mis en veille '
                      f'jusqu\'au {quand_texte}.'),
        'attente_accord': (f'La touche est faite ; une étiquette « en attente '
                           f'd\'un accord » et un réveil le {quand_texte} '
                           'sont posés.'),
        'question_prix': ("Une tâche « Question de prix » est créée pour le "
                          'fondateur ; rien n\'est envoyé au client avant sa '
                          'décision.'),
        'devis_modifie': 'Une tâche « devis modifié » est créée.',
        'decision_famille': ('Le suivi tient compte d\'une décision prise à '
                             'plusieurs (en famille).'),
        'decision_proprietaire': ('Une note « joindre le propriétaire » est '
                                  'posée.'),
        'perdu': (f'Le lead passe à « Perdu » (motif : {motif}) et toutes ses '
                  'relances s\'arrêtent (annulation impossible).'),
        'visite_abandonnee': 'La visite en attente est annulée.',
        'joint_telephone': ('Le client est joint par téléphone : la réponse '
                            'compte comme un appel abouti.'),
    }
    return effets.get(cle, f'Réponse enregistrée : « {spec["libelle"]} ».')


def _valider_reponse(etape, p, corps):
    """``reponse`` : mêmes refus que ``_repondre`` (réponse valable sur CETTE
    touche, motif de perte, date, raison d'attente) ; ``(mot, effet)``."""
    from .cadence_reponses import (
        refus_motif_perte, refus_raison_attente, refus_reponse_touche,
        reponse_touche)
    from .suite_touche import cles_de_reponse

    cle = p['reponse']
    refus = refus_reponse_touche(etape, cle)
    if refus:
        raise PropositionRefusee(refus)
    spec = reponse_touche(cle)
    if cle not in cles_de_reponse(etape):
        raise PropositionRefusee(
            f'« {spec["libelle"]} » n\'est pas proposée sur cette touche.')
    corps['reponse'] = cle
    motif = ''
    if spec.get('motif_perte_requis'):
        motif, refus = refus_motif_perte(etape.company, p.get('motif_perte'))
        if refus:
            raise PropositionRefusee(refus)
        corps['motif_perte'] = motif
    if spec.get('raison_requise'):
        refus = refus_raison_attente(p.get('raison_attente', ''))
        if refus:
            raise PropositionRefusee(refus)
        corps['raison_attente'] = p['raison_attente']
    quand, fragment = _lire_rappel(p, 'Rappeler le')
    if spec.get('date_requise') and quand is None:
        raise PropositionRefusee(
            '« Rappeler le » : la date convenue avec le client est '
            f'obligatoire pour « {spec["libelle"]} ».')
    corps.update(fragment)
    texte = _avec_heure(quand, p) if quand else ''
    return spec['libelle'], _effet_reponse(cle, spec, texte, motif)


def _verifier_issue_appel(etape, outcome):
    """Une touche d'APPEL ne se clôt pas sans issue (CKP2) — mêmes
    exceptions que ``_marquer`` : filets « generique », devis modifié,
    message déjà ouvert depuis l'ERP (CAD45)."""
    from .cadence_config import CLE_DEVIS_MODIFIE, est_etape
    from .cadence_views import (
        MESSAGE_ISSUE_APPEL_OBLIGATOIRE, _message_ouvert_sur_touche)
    from .models import RelanceEtape

    if (not outcome and etape.canal == RelanceEtape.Canal.APPEL
            and etape.cadence != 'generique'
            and not est_etape(etape, CLE_DEVIS_MODIFIE)
            and not _message_ouvert_sur_touche(etape)):
        raise PropositionRefusee(MESSAGE_ISSUE_APPEL_OBLIGATOIRE)


def _valider_motifs(etape, p, outcome, corps):
    """``motif_refus`` (seulement avec « refus ») et ``perdu_junk``
    (seulement avec « pas de réponse »), motifs de la liste de la société."""
    from .cadence_reponses import motif_junk_valide
    from .leads_socle import motif_refus_valide

    if p.get('motif_refus'):
        nom = motif_refus_valide(etape.company, p['motif_refus'])
        if outcome != 'refuse' or nom is None:
            raise PropositionRefusee(
                '« Motif du refus » : valable seulement avec « Refus » et '
                f'pour un motif de la liste (Paramètres → CRM) — « '
                f'{p["motif_refus"]} » ne convient pas.')
        corps['motif_refus'] = nom
    if p.get('perdu_junk'):
        nom = motif_junk_valide(etape.company, p['perdu_junk'])
        if outcome != 'non_joint' or nom is None:
            raise PropositionRefusee(
                '« Marquer perdu (junk) » : valable seulement avec « Pas de '
                f'réponse » et pour un motif junk de la liste — « '
                f'{p["perdu_junk"]} » ne convient pas.')
        corps['perdu_junk'] = nom


def _valider_issue(etape, p, corps):
    """``outcome`` (ou fait sans issue) : mêmes refus que ``_marquer`` ;
    ``(mot, effet)``."""
    from .cadence_config import CLE_DECIDER_SUITE, est_etape
    from .cadence_views import MESSAGE_REFUS_SUR_DECIDER_SUITE
    from .models import LeadActivity
    from .suite_touche import cles_de_reponse

    outcome = p.get('outcome', '')
    # Une ISSUE du chatter (ce que ``_marquer`` accepte) ET proposée sur cette
    # touche : ``cles_de_reponse`` mêle issues, réponses du client et
    # « sauter », que ``fait`` refuserait en 400 « Issue inconnue ».
    issues = {k for k, _libelle in LeadActivity.OUTCOMES if k}
    if outcome and (outcome not in issues
                    or outcome not in cles_de_reponse(etape)):
        raise PropositionRefusee(
            f'« {_MOT_ISSUE.get(outcome, outcome)} » n\'est pas proposée sur '
            'cette touche (réponses possibles : '
            + ', '.join(c for c in cles_de_reponse(etape)
                        if c in _MOT_ISSUE) + ').')
    if outcome == 'refuse' and est_etape(etape, CLE_DECIDER_SUITE):
        raise PropositionRefusee(MESSAGE_REFUS_SUR_DECIDER_SUITE)
    _verifier_issue_appel(etape, outcome)
    quand, fragment = _lire_rappel(p, 'Rappeler le')
    if outcome == 'rappel' and quand is None:
        raise PropositionRefusee(
            '« Rappeler le » : la date convenue avec le client est '
            'obligatoire pour « À rappeler ».')
    _valider_motifs(etape, p, outcome, corps)
    if outcome:
        corps['outcome'] = outcome
    corps.update(fragment)
    mot = _MOT_ISSUE.get(outcome, outcome)
    texte = _avec_heure(quand, p) if quand else ''
    if outcome == 'rappel':
        mot = f'rappel {texte}'
    return mot, _effet_issue(etape, outcome, texte)


def _valider_fait(etape, p):
    """Le geste « Fait » : ``(corps, mot, effet)``."""
    from .cadence_messages import refus_langue_relance

    corps = {}
    if p.get('langue'):
        refus = refus_langue_relance(p['langue'])
        if refus:
            raise PropositionRefusee(refus)
        corps['langue'] = p['langue']
    if p.get('reponse'):
        mot, effet = _valider_reponse(etape, p, corps)
    else:
        mot, effet = _valider_issue(etape, p, corps)
    if p.get('note'):
        corps['note'] = p['note']
    return corps, mot, effet


def _valider_sauter(etape, p):
    """Le geste « Sauter » : refusé sur une tâche (COCKPIT-CONTRÔLE B4)."""
    from .cadence_views import MESSAGE_TACHE_NON_SAUTABLE
    from .suite_touche import est_tache

    if est_tache(etape):
        raise PropositionRefusee(MESSAGE_TACHE_NON_SAUTABLE)
    corps = {'note': p['note']} if p.get('note') else {}
    froid = stages.STAGE_LABELS[stages.COLD]
    suite = (f"C'est la dernière touche : le dossier part à « {froid} »."
             if _dernier_barreau(etape) else
             'La touche suivante du protocole est programmée. Annulable 24 h.')
    return corps, 'sautée', f'La touche est sautée. {suite}'


def _quand_du_report(p):
    """L'instant du report (``rappel_le`` + heure facultative, Casablanca),
    refusé comme ``reporter`` : illisible, trop ancien, passé."""
    from .cadence_temps import instant_utc
    from .cadence_views import _parse_rappel, _refus_date_passee

    quand = _parse_rappel(p.get('rappel_le', ''), p.get('rappel_heure', ''))
    if quand is None:
        raise PropositionRefusee(
            '« Reporter au » : date invalide (rappel_le AAAA-MM-JJ, heure '
            'HH:MM optionnelle).')
    quand, trop_ancien = instant_utc(quand)
    refus = ('« Reporter au » : cette date est déjà passée — choisissez '
             'aujourd’hui ou une date à venir.' if trop_ancien
             else _refus_date_passee(quand, 'Reporter au'))
    if refus:
        raise PropositionRefusee(refus)
    return quand


def _valider_reporter(etape, p):
    """Le geste « Reporter » (décaler, ou mettre en veille) :
    ``(corps, mot, effet)``. Le corps est TOUJOURS ``rappel_le`` +
    ``rappel_heure`` (jour et heure de Casablanca) — la forme que l'écran
    poste à ``reporter`` (``crmApi.reporterRelanceEtape``), jamais ``due_at``."""
    from apps.crm import horaires

    mode = p.get('mode', '')
    if mode not in ('', 'decaler', 'veille'):
        raise PropositionRefusee(
            f'Geste inconnu : « {mode} ». Choisir « decaler » ou « veille ».')
    local = _quand_du_report(p).astimezone(horaires.CASABLANCA)
    corps = {'rappel_le': local.date().isoformat(),
             'rappel_heure': local.strftime('%H:%M')}
    if mode:
        corps['mode'] = mode
    texte = _avec_heure(local, p)
    if mode == 'veille':
        return (corps, f'mise en veille jusqu\'au {texte}',
                'Le suivi se tait jusqu\'à cette date puis reprend au même '
                'barreau.')
    return (corps, f'reportée au {texte}',
            'La touche est reportée et les suivantes glissent du même '
            'délai.')


def proposition_pour(etape, p):
    """``(proposition, refus)`` : la carte-écho d'une réponse comprise. Le
    serveur VALIDE sans rien écrire ; un refus est un texte lisible."""
    from .cadence_views import MESSAGE_ETAPE_DEJA_TRAITEE
    from .models import RelanceEtape

    geste = p.get('geste', '')
    if geste not in GESTES:
        return None, ('Geste inconnu : « ' + geste + ' ». Gestes : '
                      + ', '.join(GESTES) + '.')
    try:
        if etape.statut != RelanceEtape.Statut.A_FAIRE:
            raise PropositionRefusee(MESSAGE_ETAPE_DEJA_TRAITEE)
        valider = {'fait': _valider_fait, 'reporter': _valider_reporter,
                   'sauter': _valider_sauter}[geste]
        corps, mot, effet = valider(etape, p)
    except PropositionRefusee as refus:
        return None, str(refus)
    libelle = f'{nom_du_lead(etape.lead)} — {etape.libelle} : {mot}'
    return {'geste': geste, 'libelle': libelle, 'effet': effet,
            'corps': corps}, None


def _peut_enregistrer(request):
    """Le compte passe-t-il la garde des VRAIS gestes (``fait`` /
    ``reporter`` / ``sauter``) ? Lue sur ``RelanceEtapeViewSet.get_permissions``
    pour un POST de geste — jamais une seconde règle ici."""
    from types import SimpleNamespace

    from .cadence_views import RelanceEtapeViewSet

    vue = RelanceEtapeViewSet(action='fait')
    geste = SimpleNamespace(user=request.user, method='POST')
    return all(garde.has_permission(geste, vue)
               for garde in vue.get_permissions())


@extend_schema(
    parameters=[sd.param(nom, description=(
        'Réponse comprise (carte-écho) : voir la description de '
        'crm.suivi.proposer_reponse.')) for nom in PARAMETRES_PROPOSITION],
    responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([DroitDeLaGrille('crm_voir')])
def touche_assistant(request, touche_id):
    """COP-C3/COP-C4 — ``GET /api/django/crm/assistant/touches/<id>/`` : la
    touche prête (message validé ou script d'appel) et, avec ``?geste=``, la
    proposition validée par le serveur. LECTURE : rien n'est écrit, rien n'est
    envoyé, aucune touche n'est close (le geste reste celui de l'écran)."""
    etape = touche_en_portee(request.user, touche_id)
    corps = touche_prete(request, etape)
    proposition, refus = None, None
    if request.query_params.get('geste') is not None:
        # COP-C4 — la carte ne propose que ce que le compte pourra poster.
        if not _peut_enregistrer(request):
            refus = MESSAGE_ROLE_SANS_ENREGISTREMENT
        else:
            p = {cle: (request.query_params.get(cle) or '').strip()
                 for cle in PARAMETRES_PROPOSITION}
            proposition, refus = proposition_pour(etape, p)
    corps['proposition'] = proposition
    corps['proposition_refus'] = refus
    return Response(corps)
