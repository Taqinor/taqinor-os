"""Services d'écriture/orchestration du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE pour les autres apps : une app métier qui doit tracer
une destruction/anonymisation appelle ``journaliser_destruction`` (import
FONCTION-LOCAL depuis son propre ``services``/``dsr_provider``) — jamais un
import des modèles de ``grc``.
"""
from __future__ import annotations

import hashlib
import logging
import secrets

from django.utils import timezone

logger = logging.getLogger(__name__)

#: NTGRC2/NTGRC3 — délai légal de réponse à une demande de droit (loi 09-08).
DELAI_LEGAL_JOURS = 30


def empreinte_avant(valeurs):
    """SHA-256 hexadécimal d'un instantané AVANT destruction (ou '').

    ``valeurs`` est un dict (ou toute valeur ``repr``-able) des champs
    personnels sur le point d'être effacés. On ne stocke JAMAIS la valeur
    elle-même — seulement son empreinte, qui permet de prouver a posteriori
    « c'est bien cette donnée-là qui a été détruite » sans la conserver.
    """
    if not valeurs:
        return ''
    if isinstance(valeurs, dict):
        canon = '|'.join(
            f'{cle}={valeurs[cle]}' for cle in sorted(valeurs) if valeurs[cle])
    else:
        canon = str(valeurs)
    if not canon:
        return ''
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def journaliser_destruction(company, *, type_objet, objet_ref, action,
                            politique_ref='', demande_droit_ref='',
                            executee_par='', motif='', empreinte=''):
    """Écrit UNE ligne immuable au journal de destruction (NTGRC5).

    Appelée par les fournisseurs DSR (NTGRC1) et par les politiques de
    rétention (NTGRC4) à CHAQUE purge/anonymisation réelle. Best-effort
    absolu : une erreur de journalisation ne doit JAMAIS faire échouer
    l'effacement légal lui-même (la demande resterait bloquée). Renvoie la
    ligne créée, ou ``None`` si la journalisation n'a pas pu avoir lieu.

    Aucune donnée personnelle n'est écrite : seuls un type d'objet, un
    identifiant technique, un motif et une EMPREINTE (SHA-256) sont tracés.
    """
    if company is None:
        return None
    from .models import JournalDestruction
    try:
        return JournalDestruction.objects.create(
            company=company,
            type_objet=(type_objet or '')[:60],
            objet_ref=str(objet_ref or '')[:64],
            action=action,
            politique_ref=str(politique_ref or '')[:64],
            demande_droit_ref=str(demande_droit_ref or '')[:64],
            executee_par=(executee_par or '')[:150],
            motif=motif or '',
            empreinte_avant=(empreinte or '')[:64],
        )
    except Exception:  # noqa: BLE001 - jamais bloquant pour l'effacement
        logger.exception(
            'grc: journalisation de destruction impossible (%s/%s)',
            type_objet, objet_ref)
        return None


# ── NTGRC2 — portail public de dépôt / suivi d'une demande de droit ─────────

def _nouveau_token_suivi():
    """Jeton de suivi OPAQUE (32 octets d'entropie, URL-safe).

    Distinct de l'identifiant réel : le déposant suit sa demande sans qu'aucun
    identifiant interne ne fuite et sans énumération possible.
    """
    return secrets.token_urlsafe(32)[:64]


def creer_demande_publique(slug_societe, identifiant, type_demande, *,
                           ip='', user_agent=''):
    """Crée une ``core.DataSubjectRequest`` déposée PUBLIQUEMENT.

    Renvoie ``(demande, None)`` en cas de succès, ``(None, {champ: message})``
    sinon — le message NOMME toujours le champ fautif, en français.

    La preuve (horodatage SERVEUR, IP, user-agent) est posée côté serveur et
    JAMAIS lue du corps de la requête. La société est résolue par son slug :
    la demande naît donc déjà bornée à un tenant.
    """
    from authentication.models import Company
    from core.models import DataSubjectRequest

    company = Company.objects.filter(slug=slug_societe).first()
    if company is None:
        return None, {'societe': 'Société inconnue.'}

    valides = {c for c, _ in DataSubjectRequest.KIND_CHOICES}
    if type_demande not in valides:
        return None, {
            'type': 'Type de demande invalide : choisissez « accès », '
                    '« rectification » ou « effacement ».'}

    maintenant = timezone.now()
    demande = DataSubjectRequest(
        company=company,
        subject_identifier=identifiant[:255],
        kind=type_demande,
        statut=DataSubjectRequest.STATUT_RECUE,
        token_suivi=_nouveau_token_suivi(),
        preuve={
            'depose_le': maintenant.isoformat(),
            'ip': ip or '',
            'user_agent': user_agent or '',
            'canal': 'portail_public',
        },
    )
    demande.save()
    return demande, None


def suivi_demande_publique(token):
    """État public d'une demande, résolu par son jeton OPAQUE.

    Renvoie un dict SANS aucune donnée personnelle d'autrui ni identifiant
    interne, ou ``None`` si le jeton ne correspond à rien.
    """
    from core.models import DataSubjectRequest

    if not token:
        return None
    demande = DataSubjectRequest.objects.filter(token_suivi=token).first()
    if demande is None:
        return None

    echeance = getattr(demande, 'date_echeance', None)
    if echeance is None:
        echeance = demande.created_at + timezone.timedelta(
            days=DELAI_LEGAL_JOURS)
    return {
        'statut': demande.statut,
        'type': demande.kind,
        'depose_le': demande.created_at.isoformat(),
        'echeance_legale': echeance.isoformat(),
        'delai_legal_jours': DELAI_LEGAL_JOURS,
        'traitee_le': (demande.traitee_le.isoformat()
                       if demande.traitee_le else None),
    }


# ── NTGRC6 — violations de données : numérotation + cycle de vie ────────────

class TransitionViolationInterdite(ValueError):
    """Transition de statut illégale sur une ``ViolationDonnees``.

    Traduite en 400 par la vue (jamais 500) ; le message NOMME les deux
    statuts, en français.
    """


def _transitions_violation(statut):
    from .models import ViolationDonnees

    table = {
        ViolationDonnees.STATUT_OUVERTE: {
            ViolationDonnees.STATUT_EN_ANALYSE,
            ViolationDonnees.STATUT_NOTIFIEE,
            ViolationDonnees.STATUT_CLOTUREE,
        },
        ViolationDonnees.STATUT_EN_ANALYSE: {
            ViolationDonnees.STATUT_NOTIFIEE,
            ViolationDonnees.STATUT_CLOTUREE,
        },
        ViolationDonnees.STATUT_NOTIFIEE: {
            ViolationDonnees.STATUT_CLOTUREE,
        },
        # Terminal : une violation clôturée ne se rouvre pas (on en ouvre une
        # nouvelle, qui repart avec sa propre échéance de 72 h).
        ViolationDonnees.STATUT_CLOTUREE: set(),
    }
    return table.get(statut, set())


def changer_statut_violation(violation, cible):
    """Fait avancer une violation dans son cycle de vie (garde de transition)."""
    from .models import ViolationDonnees

    libelles = dict(ViolationDonnees.STATUT_CHOICES)
    if cible not in libelles:
        raise TransitionViolationInterdite(
            f'Statut « {cible} » inconnu pour une violation de données.')
    if cible not in _transitions_violation(violation.statut):
        raise TransitionViolationInterdite(
            f'Transition impossible : une violation « '
            f'{libelles.get(violation.statut, violation.statut)} » ne peut '
            f'pas passer à « {libelles[cible]} ».')
    violation.statut = cible
    violation.save(update_fields=['statut', 'updated_at'])
    return violation


def notifier_cndp(violation, quand=None):
    """Enregistre la notification à la CNDP (date + statut, ensemble).

    Poser la date sans le statut (ou l'inverse) laisserait le registre mentir
    sur l'état réel du dossier : les deux bougent dans la même opération.
    """
    from .models import ViolationDonnees

    if violation.date_notification_cndp is not None:
        raise TransitionViolationInterdite(
            'Cette violation a déjà été notifiée à la CNDP le '
            f'{violation.date_notification_cndp:%d/%m/%Y}.')
    changer_statut_violation(violation, ViolationDonnees.STATUT_NOTIFIEE)
    violation.date_notification_cndp = quand or timezone.now()
    violation.save(update_fields=['date_notification_cndp', 'updated_at'])
    return violation


def creer_violation(company, **champs):
    """Crée une ``ViolationDonnees`` avec sa référence VD race-safe.

    Numérotation par ``core.numbering`` (plus-haut-utilisé + 1 par société et
    par mois, savepoint + retry) — JAMAIS ``count() + 1``, qui entre en
    collision dès qu'une ligne est supprimée.
    """
    from core.numbering import create_with_reference

    from .models import ViolationDonnees

    def _save(reference):
        return ViolationDonnees.objects.create(
            company=company, reference=reference, **champs)

    return create_with_reference(
        ViolationDonnees, ViolationDonnees.REFERENCE_PREFIX, company, _save)


# ── NTGRC7 — dossier de notification CNDP (PDF) ─────────────────────────────

#: Les 8 rubriques exigées par une notification de violation (loi 09-08 /
#: RGPD art. 33). L'ordre est celui du formulaire : il ne change pas.
RUBRIQUES_NOTIFICATION = (
    'Responsable du traitement',
    'Nature de la violation',
    'Chronologie',
    'Catégories et nombre de personnes concernées',
    'Catégories de données concernées',
    'Conséquences probables pour les personnes',
    'Mesures prises ou proposées',
    'Point de contact (DPO)',
)

_NON_RENSEIGNE = '— non renseigné'


def contact_responsable(company):
    """Coordonnées du responsable de traitement (profil société, best-effort).

    Résolution PAR CHAÎNE (jamais un import de ``apps.parametres.models``).
    Aucune valeur n'est inventée : un champ vide reste vide.
    """
    from django.apps import apps as django_apps

    try:
        CompanyProfile = django_apps.get_model('parametres', 'CompanyProfile')
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 - profil indisponible ⇒ dossier quand même
        profil = None
    if profil is None:
        return {'nom': getattr(company, 'nom', '') or '', 'email': '',
                'telephone': '', 'adresse': ''}
    return {
        'nom': getattr(profil, 'nom', '') or getattr(company, 'nom', '') or '',
        'email': getattr(profil, 'email', '') or '',
        'telephone': getattr(profil, 'telephone', '') or '',
        'adresse': getattr(profil, 'adresse', '') or '',
    }


def contexte_dossier_notification(violation, now=None):
    """Contenu structuré du dossier CNDP — les 8 rubriques, dans l'ordre.

    Séparé du rendu : le contenu est testable sans WeasyPrint, et un futur
    format (XML de téléservice, export) réutilisera exactement la même source.
    """
    now = now or timezone.now()
    contact = contact_responsable(violation.company)

    def _ou_vide(valeur):
        return valeur if (valeur or '').strip() else _NON_RENSEIGNE

    categories = violation.categories_donnees or []
    if isinstance(categories, (list, tuple)):
        categories_txt = ', '.join(str(c) for c in categories)
    else:
        categories_txt = str(categories)

    chronologie = [
        ('Incident', violation.date_incident),
        ('Détection', violation.date_detection),
        ('Échéance de notification (72 h)', violation.date_echeance_72h),
        ('Notification CNDP', violation.date_notification_cndp),
    ]

    return {
        'reference': violation.reference,
        'genere_le': now,
        'rubriques': [
            {
                'titre': 'Responsable du traitement',
                'contenu': _ou_vide(
                    ' — '.join(p for p in [contact['nom'], contact['adresse']]
                               if p)),
            },
            {
                'titre': 'Nature de la violation',
                'contenu': (f"{violation.get_nature_display()} "
                            f"(gravité : {violation.get_gravite_display()})"),
            },
            {
                'titre': 'Chronologie',
                'contenu': ' | '.join(
                    f'{libelle} : '
                    + (f'{quand:%d/%m/%Y %H:%M}' if quand else _NON_RENSEIGNE)
                    for libelle, quand in chronologie),
            },
            {
                'titre': 'Catégories et nombre de personnes concernées',
                'contenu': (f'{violation.nombre_personnes_estime} personne(s) '
                            'concernée(s), estimation'),
            },
            {
                'titre': 'Catégories de données concernées',
                'contenu': _ou_vide(categories_txt),
            },
            {
                'titre': 'Conséquences probables pour les personnes',
                'contenu': _ou_vide(violation.risque_personnes),
            },
            {
                'titre': 'Mesures prises ou proposées',
                'contenu': _ou_vide(violation.mesures_prises),
            },
            {
                'titre': 'Point de contact (DPO)',
                'contenu': _ou_vide(
                    ' — '.join(p for p in [contact['email'],
                                           contact['telephone']] if p)),
            },
        ],
    }


def _html_dossier_notification(contexte):
    """Gabarit HTML du dossier (inline : un seul consommateur, aucun gabarit
    partagé à maintenir)."""
    from html import escape

    lignes = ''.join(
        '<tr><th style="text-align:left;vertical-align:top;width:34%;'
        'padding:6px 10px;border:1px solid #999;background:#f3f3f3;">'
        + escape(r['titre'])
        + '</th><td style="padding:6px 10px;border:1px solid #999;">'
        + escape(r['contenu']) + '</td></tr>'
        for r in contexte['rubriques'])
    return (
        '<html><head><meta charset="utf-8"><style>'
        'body{font-family:sans-serif;font-size:11pt;}'
        'h1{font-size:15pt;margin-bottom:2px;}'
        'table{width:100%;border-collapse:collapse;margin-top:14px;}'
        '.meta{color:#555;font-size:9pt;}'
        '</style></head><body>'
        '<h1>Notification de violation de données personnelles</h1>'
        '<div class="meta">Référence '
        + escape(contexte['reference'] or '—')
        + ' — dossier généré le '
        + contexte['genere_le'].strftime('%d/%m/%Y à %H:%M')
        + ' (loi 09-08, notification sous 72 heures)</div>'
        '<table>' + lignes + '</table>'
        '</body></html>'
    )


def generer_dossier_notification(violation, now=None):
    """Rend le dossier de notification CNDP en PDF (octets).

    Passe par ``core.pdf.render_pdf`` (ARC11) — JAMAIS un import direct de
    WeasyPrint, et surtout JAMAIS le moteur de devis (règle #4 : `/proposal`
    est l'unique chemin des PDF de devis client).
    """
    from core.pdf import render_pdf

    contexte = contexte_dossier_notification(violation, now=now)
    pdf = render_pdf(
        html=_html_dossier_notification(contexte),
        company=violation.company, header=True, footer=True)
    return pdf, contexte


# ── NTGRC8 — legal hold transverse : garde d'effacement + garde de purge ────

def motif_hold_pour_personne(company, subject_identifier):
    """Motif de blocage si CETTE personne est couverte par un séquestre actif.

    Renvoie une chaîne (le motif, qui devient le corps du 409) ou ``''``.
    Consultée par ``core.dsr`` AVANT tout effacement — un dossier gelé pour
    contentieux ne s'anonymise pas, même sur demande légale : la preuve prime
    tant que le séquestre est actif (il faut le lever d'abord).
    """
    from .models import LEGAL_HOLD_TRANSVERSE_MESSAGE
    from .selectors import objets_sous_hold

    if company is None or not (subject_identifier or '').strip():
        return ''
    couverture = objets_sous_hold(company)
    if not couverture:
        return ''

    from apps.crm.selectors import (
        client_ids_par_identifiant, lead_ids_par_identifiant,
    )

    cibles = {
        'crm_client': set(client_ids_par_identifiant(
            company, subject_identifier)),
        'crm_lead': set(lead_ids_par_identifiant(
            company, subject_identifier)),
    }
    for type_objet, ids in cibles.items():
        if ids & couverture.get(type_objet, set()):
            return LEGAL_HOLD_TRANSVERSE_MESSAGE
    return ''


def ids_geles(company, type_objet):
    """Ids gelés pour ce type d'objet (raccourci pour les balayages)."""
    from .selectors import objets_sous_hold

    return objets_sous_hold(company).get(type_objet, set())


def register_erasure_guard():
    """Branche la garde de séquestre sur ``core.dsr`` (idempotent, ready())."""
    from core import dsr

    dsr.register_erasure_guard('grc_legal_hold', motif_hold_pour_personne)


# ── NTGRC13 — registre des risques d'entreprise ─────────────────────────────

def creer_risque(company, **champs):
    """Crée un ``RisqueEntreprise`` avec sa référence RQ race-safe."""
    from core.numbering import create_with_reference

    from .models import RisqueEntreprise

    def _save(reference):
        return RisqueEntreprise.objects.create(
            company=company, reference=reference, **champs)

    return create_with_reference(
        RisqueEntreprise, RisqueEntreprise.REFERENCE_PREFIX, company, _save)


# ── NTGRC15 — revues périodiques du risque ──────────────────────────────────

def enregistrer_revue(company, risque, **champs):
    """Enregistre une ``RevueRisque`` et AVANCE la cadence sur le risque.

    La prochaine date de revue est poussée sur ``RisqueEntreprise`` par CE
    service, jamais par l'appelant : la cadence vit à un seul endroit, sinon
    la date du risque et celle de sa dernière revue finissent par diverger.
    Une décision « clos » clôt aussi le risque — c'est ce que le mot veut
    dire ; laisser un risque « ouvert » après l'avoir déclaré clos en revue
    est exactement le genre d'écart qu'un auditeur relève.
    """
    from django.db import transaction

    from .models import RevueRisque, RisqueEntreprise

    with transaction.atomic():
        revue = RevueRisque.objects.create(
            company=company, risque=risque, **champs)
        champs_maj = []
        if revue.prochaine_revue:
            risque.date_revue_prevue = revue.prochaine_revue
            champs_maj.append('date_revue_prevue')
        if revue.decision == RevueRisque.DECISION_CLOS:
            risque.statut = RisqueEntreprise.STATUT_CLOS
            champs_maj.append('statut')
        if champs_maj:
            risque.save(update_fields=champs_maj + ['updated_at'])
    return revue
