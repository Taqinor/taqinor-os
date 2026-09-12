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


# ── NTGRC17 — tests de contrôle : ouverture automatique d'un risque ─────────

def ouvrir_risque_sur_deficience(test):
    """Ouvre (une seule fois) un risque lié à un test de contrôle DÉFICIENT.

    Une déficience sans risque tracé disparaît au prochain comité : le test
    porte alors une preuve d'échec que personne ne suit. Idempotent — un test
    déjà relié à un risque n'en ouvre pas un second (un opérateur qui corrige
    la conclusion et ré-enregistre ne doit pas multiplier les risques).
    """
    from .models import RisqueEntreprise, TestControle

    if test.resultat != TestControle.RESULTAT_DEFICIENT:
        return None
    if test.risque_ouvert_id:
        return test.risque_ouvert

    controle = test.controle
    risque = creer_risque(
        test.company,
        titre=f'Contrôle {controle.code} déficient — {controle.intitule}',
        categorie='conformite',
        description=(test.conclusion or '').strip() or (
            f'Le test du contrôle {controle.code} a conclu à une '
            'déficience.'),
        proprietaire=controle.proprietaire,
        statut=RisqueEntreprise.STATUT_OUVERT,
    )
    test.risque_ouvert = risque
    test.save(update_fields=['risque_ouvert', 'updated_at'])
    return risque


def enregistrer_test_controle(company, controle, **champs):
    """Crée un ``TestControle`` et ouvre un risque si le résultat est déficient."""
    from django.db import transaction

    from .models import TestControle

    with transaction.atomic():
        test = TestControle.objects.create(
            company=company, controle=controle, **champs)
        ouvrir_risque_sur_deficience(test)
    return test


# ── NTGRC19 — politiques internes versionnées ───────────────────────────────

class PublicationImpossible(ValueError):
    """Publication refusée (politique obsolète, contenu vide…).

    Traduite en 400 par la vue — jamais 500, et le message dit POURQUOI.
    """


def publier_politique(politique, auteur=''):
    """Fige le contenu dans une version IMMUABLE et incrémente le numéro.

    Le numéro de version est calculé SERVEUR à partir du plus haut numéro déjà
    figé (+1) — jamais ``count() + 1``, qui se décale dès qu'une ligne manque,
    et jamais une valeur envoyée par le client.

    Publier une politique vide n'a pas de sens (personne ne peut attester
    avoir lu du vide) : c'est refusé, avec le motif.
    """
    from django.db import transaction
    from django.db.models import Max

    from .models import PolitiqueInterne, PolitiqueVersion

    if politique.statut == PolitiqueInterne.STATUT_OBSOLETE:
        raise PublicationImpossible(
            'Cette politique est obsolète : créez-en une nouvelle plutôt que '
            'de republier celle-ci.')
    if not (politique.contenu or '').strip():
        raise PublicationImpossible(
            'Le contenu de la politique est vide : rien à publier.')

    maintenant = timezone.now()
    with transaction.atomic():
        dernier = (PolitiqueVersion.objects
                   .filter(politique=politique)
                   .aggregate(maxi=Max('numero'))['maxi']) or 0
        numero = dernier + 1
        version = PolitiqueVersion.objects.create(
            company=politique.company, politique=politique, numero=numero,
            contenu=politique.contenu, auteur=(auteur or '')[:150],
            publiee_le=maintenant)
        politique.version = numero
        politique.statut = PolitiqueInterne.STATUT_PUBLIEE
        politique.date_publication = maintenant
        politique.save(update_fields=[
            'version', 'statut', 'date_publication', 'updated_at'])
    return version


# ── NTGRC20 — attestation de lecture d'une politique ────────────────────────

class AttestationImpossible(ValueError):
    """Attestation refusée (politique non publiée, nom manquant…).

    Traduite en 400 par la vue — jamais 500 — et le message NOMME le champ
    fautif, comme partout ailleurs dans le dépôt.
    """

    def __init__(self, message, champ='detail'):
        super().__init__(message)
        self.champ = champ


def preuve_requete(request):
    """Preuve technique d'un geste (IP + user-agent), posée CÔTÉ SERVEUR.

    Jamais lue du corps de la requête : une preuve que l'appelant fournit
    lui-même ne prouve rien. Best-effort — un en-tête manquant donne une
    chaîne vide, jamais une exception.
    """
    if request is None:
        return {}
    meta = getattr(request, 'META', {}) or {}
    transmis = meta.get('HTTP_X_FORWARDED_FOR', '')
    if transmis:
        ip = transmis.split(',')[0].strip()[:45]
    else:
        ip = (meta.get('REMOTE_ADDR') or '')[:45]
    return {
        'ip': ip,
        'user_agent': (meta.get('HTTP_USER_AGENT') or '')[:512],
        'atteste_le': timezone.now().isoformat(),
    }


def attester_politique(company, politique, *, employe_ref='', nom_saisi='',
                       attestant_nom='', preuve=None):
    """Enregistre l'attestation de lecture de la VERSION COURANTE.

    Renvoie ``(attestation, creee)``. IDEMPOTENT : ré-attester la même version
    renvoie la ligne existante sans en créer une seconde (un double clic ne
    doit pas gonfler le taux d'attestation — c'est le genre d'écart qu'un
    auditeur repère immédiatement).

    Refus explicites, chacun nommant son champ :
      * politique non publiée (``version`` = 0) — on n'atteste pas un
        brouillon, qui peut encore changer sous les yeux du lecteur ;
      * ``nom_saisi`` vide — c'est le geste de signature (loi 53-05) ; sans
        lui il n'y a qu'un clic anonyme.
    """
    from .models import AttestationPolitique, PolitiqueInterne

    version = int(getattr(politique, 'version', 0) or 0)
    if politique.statut != PolitiqueInterne.STATUT_PUBLIEE or version < 1:
        raise AttestationImpossible(
            'Cette politique n\'est pas publiée : il n\'y a pas encore de '
            'version figée à attester.', champ='politique')
    nom_saisi = (nom_saisi or '').strip()
    if not nom_saisi:
        raise AttestationImpossible(
            'Saisissez votre nom pour attester avoir lu cette politique '
            '(loi 53-05).', champ='nom_saisi')

    employe_ref = str(employe_ref or '').strip()[:64]
    if employe_ref:
        existante = AttestationPolitique.objects.filter(
            company=company, politique=politique, version_attestee=version,
            employe_ref=employe_ref).first()
        if existante is not None:
            return existante, False

    attestation = AttestationPolitique.objects.create(
        company=company,
        politique=politique,
        version_attestee=version,
        employe_ref=employe_ref,
        attestant_nom=(attestant_nom or nom_saisi)[:160],
        nom_saisi=nom_saisi[:160],
        preuve=preuve or {},
    )
    return attestation, True


# ── NTGRC22 — questionnaires de conformité fournisseurs ─────────────────────

class TransitionQuestionnaireInterdite(ValueError):
    """Transition de statut illégale sur un ``QuestionnaireFournisseur``.

    Traduite en 400 par la vue (jamais 500) ; le message NOMME les deux
    statuts, en français.
    """


def _transitions_questionnaire(statut):
    from .models import QuestionnaireFournisseur as Q

    table = {
        Q.STATUT_ENVOYE: {Q.STATUT_EN_COURS, Q.STATUT_COMPLETE,
                          Q.STATUT_REFUSE},
        Q.STATUT_EN_COURS: {Q.STATUT_COMPLETE, Q.STATUT_REFUSE},
        # On ne valide/refuse qu'un questionnaire COMPLET : juger sur des
        # réponses manquantes, c'est juger sur rien.
        Q.STATUT_COMPLETE: {Q.STATUT_VALIDE, Q.STATUT_REFUSE},
        # Terminaux : on renvoie un NOUVEAU questionnaire, on ne rouvre pas
        # celui sur lequel un avis a déjà été rendu.
        Q.STATUT_VALIDE: set(),
        Q.STATUT_REFUSE: set(),
    }
    return table.get(statut, set())


def changer_statut_questionnaire(questionnaire, cible):
    """Fait avancer un questionnaire fournisseur (garde de transition)."""
    from .models import QuestionnaireFournisseur

    libelles = dict(QuestionnaireFournisseur.STATUT_CHOICES)
    if cible not in libelles:
        raise TransitionQuestionnaireInterdite(
            f'Statut « {cible} » inconnu pour un questionnaire fournisseur.')
    if cible not in _transitions_questionnaire(questionnaire.statut):
        raise TransitionQuestionnaireInterdite(
            'Transition impossible : un questionnaire « '
            f'{libelles.get(questionnaire.statut, questionnaire.statut)} » ne '
            f'peut pas passer à « {libelles[cible]} ».')
    questionnaire.statut = cible
    questionnaire.save(update_fields=['statut', 'updated_at'])
    return questionnaire


def recalculer_questionnaire(questionnaire):
    """Recalcule le SCORE et, s'il y a lieu, fait passer le questionnaire à
    « complété ».

    * score = part des réponses CONFORMES sur le TOTAL des questions (0-100).
      Le dénominateur est le total, pas le nombre de questions évaluées :
      sinon une seule question conforme sur trente afficherait 100 %.
    * « complété » dès que toutes les questions OBLIGATOIRES portent une
      réponse non vide. Un questionnaire déjà validé ou refusé n'est jamais
      rétrogradé — un avis rendu ne se défait pas parce qu'on a retouché une
      ligne.

    Renvoie le questionnaire rafraîchi.
    """
    from .models import QuestionnaireFournisseur

    reponses = list(questionnaire.reponses.all())
    total = len(reponses)
    conformes = sum(1 for r in reponses if r.conforme is True)
    score = int(round(100.0 * conformes / total)) if total else 0

    champs = []
    if questionnaire.score != score:
        questionnaire.score = score
        champs.append('score')

    obligatoires = [r for r in reponses if r.obligatoire]
    a_repondre = obligatoires or reponses
    complet = bool(a_repondre) and all(r.est_repondue for r in a_repondre)
    if complet and questionnaire.statut in (
            QuestionnaireFournisseur.STATUT_ENVOYE,
            QuestionnaireFournisseur.STATUT_EN_COURS):
        questionnaire.statut = QuestionnaireFournisseur.STATUT_COMPLETE
        champs.append('statut')
    elif (not complet
            and questionnaire.statut == QuestionnaireFournisseur.STATUT_ENVOYE
            and any(r.est_repondue for r in reponses)):
        questionnaire.statut = QuestionnaireFournisseur.STATUT_EN_COURS
        champs.append('statut')

    if champs:
        questionnaire.save(update_fields=champs + ['updated_at'])
    return questionnaire
