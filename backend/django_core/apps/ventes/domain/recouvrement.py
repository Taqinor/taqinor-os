"""Recouvrement — relances, rejets, contentieux, expiration.

Le versant « la facture n'est pas payée / le devis n'a pas abouti » du
domaine ventes : cadence de relance (nudges FR/AR), rejet d'un paiement,
abandon de solde, anomalies d'émission, blocage crédit, avertissements de
vente, dossier contentieux, contestation portail, et l'expiration
automatique des devis avec son hygiène de funnel.

QJR69 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


# Note des relances automatiques programmées (chemin scheduler). La séquence de
# relance compte ces traces pour reprendre au bon niveau ; on les neutralise au
# paiement intégral (U10) pour remettre l'escalade à zéro.
RELANCE_AUTO_NOTE = 'Relance automatique programmée (email).'
RELANCE_AUTO_NOTE_RESOLUE = (
    'Relance automatique programmée (email). [résolue — facture soldée]')


def reset_relance_escalation(facture):
    """U10 — remet à zéro l'escalade de relance d'une facture soldée.

    Quand un paiement amène ``montant_du <= 0`` et que la facture passe
    « Payée », l'escalade de recouvrement doit s'arrêter : sinon la facture
    continue d'afficher un ancien niveau de relance en retard et le scheduler
    (``relance_reminders``) pourrait reprendre la séquence là où elle s'était
    arrêtée. On efface donc ``prochaine_relance`` ET on neutralise les traces
    de relance AUTOMATIQUE consignées (le compteur qui pilote le niveau
    courant) — sans détruire l'historique : les ``RelanceLog`` sont conservés,
    leur note est seulement marquée « résolue » pour qu'ils ne soient plus
    comptés dans l'escalade. Idempotent : rien à faire si aucune escalade n'est
    en cours. Renvoie True si quelque chose a été réinitialisé."""
    changed = False
    if facture.prochaine_relance is not None:
        facture.prochaine_relance = None
        facture.save(update_fields=['prochaine_relance'])
        changed = True
    autos = facture.relances.filter(note=RELANCE_AUTO_NOTE)
    n = autos.update(note=RELANCE_AUTO_NOTE_RESOLUE)
    if n:
        changed = True
    # XFAC5 — une facture soldée referme toute promesse de paiement encore
    # « en_cours » (tenue) et lève l'exclusion de relance expirante posée par
    # la promesse.
    from ..models import PromessePaiement
    tenues = facture.promesses_paiement.filter(
        statut=PromessePaiement.Statut.EN_COURS,
    ).update(statut=PromessePaiement.Statut.TENUE)
    if tenues:
        changed = True
    if facture.exclu_relances_jusquau is not None:
        facture.exclu_relances_jusquau = None
        facture.save(update_fields=['exclu_relances_jusquau'])
        changed = True
    return changed


class PaiementRejectError(Exception):
    """YLEDG5 — erreur métier au rejet d'un paiement (message + conflict)."""

    def __init__(self, message, conflict=False):
        super().__init__(message)
        self.message = message
        self.conflict = conflict


def rejeter_paiement(*, paiement, motif, frais=None, date_rejet=None, user=None):
    """YLEDG5 — chemin d'exception « paiement rejeté » (chèque impayé /
    virement rejeté).

    Le paiement N'EST JAMAIS supprimé (piste d'audit) : il passe
    ``statut=rejete`` et sort du calcul ``Facture.montant_paye``/``statut`` —
    la facture redevient ouverte/en retard (recalculée : émise si l'échéance
    n'est pas dépassée, sinon en retard) et les relances existantes sont
    ré-armées (symétrique de ``reset_relance_escalation``). Émet
    ``paiement_rejete`` sur le bus core pour que compta contre-passe
    l'écriture d'encaissement (YLEDG4) et délettre (YLEDG6). Idempotent côté
    garde : rejeter un paiement déjà rejeté est refusé (jamais un double
    rejet)."""
    from django.utils import timezone
    from django.db import transaction
    from ..models import Facture, Paiement
    from core.events import paiement_rejete

    motif = (motif or '').strip()
    if not motif:
        raise PaiementRejectError('Le motif du rejet est obligatoire.')
    if paiement.statut == Paiement.Statut.REJETE:
        raise PaiementRejectError(
            'Ce paiement est déjà marqué rejeté.', conflict=True)

    with transaction.atomic():
        paiement.statut = Paiement.Statut.REJETE
        paiement.motif_rejet = motif[:255]
        paiement.frais_rejet = frais
        paiement.date_rejet = date_rejet or timezone.now().date()
        paiement.save(update_fields=[
            'statut', 'motif_rejet', 'frais_rejet', 'date_rejet'])

        facture = paiement.facture
        if facture is not None:
            facture.refresh_from_db()
            # Rouvre la facture : reste dû > 0 → repasse émise (ou en
            # retard si l'échéance est déjà dépassée), jamais « payée » ni
            # « annulée » (états terminaux préservés à part la réouverture).
            if facture.statut not in (
                    Facture.Statut.ANNULEE,) and facture.montant_du > 0:
                today = timezone.now().date()
                if facture.date_echeance and facture.date_echeance < today:
                    facture.statut = Facture.Statut.EN_RETARD
                else:
                    facture.statut = Facture.Statut.EMISE
                facture.save(update_fields=['statut'])
            from .. import activity
            activity.log_facture_paiement_rejete(facture, user, paiement, motif)

        paiement_rejete.send(
            sender=Paiement, paiement=paiement, facture=facture,
            montant=paiement.montant, company=paiement.company)
    return paiement


def abandonner_solde_facture(facture, *, motif, user=None, auto=False,
                             date_abandon=None):
    """XFAC13 — abandonne le résiduel dû sur une facture (write-off).

    Passe la facture ``payee``, trace l'abandon (motif + montant + auteur +
    auto/manuel), délègue l'écriture comptable (6585/créance + reprise de
    provision FG152 le cas échéant) à ``apps.compta.services`` (jamais
    d'import direct de ses modèles) et consigne le chatter. Idempotent : ne
    fait rien si le résiduel est déjà nul. Renvoie le montant abandonné
    (``Decimal('0')`` si rien à faire)."""
    from decimal import Decimal
    from django.utils import timezone
    from ..models import Facture
    reste = facture.montant_du
    if reste <= 0:
        return Decimal('0')
    from apps.compta import services as compta_services
    compta_services.abandonner_creance(
        facture.company, montant=reste, date_abandon=date_abandon,
        tiers_type='client', tiers_id=facture.client_id,
        tiers_nom=getattr(facture.client, 'nom', '') or '',
        libelle=f'Abandon créance facture {facture.reference}',
        user=user,
    )
    facture.abandon_motif = motif
    facture.abandon_montant = reste
    facture.abandon_date = timezone.now()
    facture.abandon_auto = bool(auto)
    facture.abandon_par = user if (
        user and getattr(user, 'is_authenticated', False)) else None
    facture.statut = Facture.Statut.PAYEE
    facture.save(update_fields=[
        'abandon_motif', 'abandon_montant', 'abandon_date', 'abandon_auto',
        'abandon_par', 'statut',
    ])
    from .. import activity
    motif_label = dict(Facture.MotifAbandon.choices).get(motif, motif)
    activity.log_facture_abandon(facture, user, reste, motif_label, auto=auto)
    reset_relance_escalation(facture)
    return reste


def anomalies_emission_facture(facture):
    """XFAC18 — anomalies à contrôler avant l'émission d'une facture.

    Liste (jamais bloquante — informative pour le valideur) :
      * doublon probable (même client + montant TTC à ±1 % sous 15 jours) ;
      * remise globale au-delà de ``remise_max_pct`` (réglage société) ;
      * client au-delà du plafond d'encours FG41.

    Renvoie une liste de dicts ``{'code', 'message'}`` (vide si rien à
    signaler)."""
    from datetime import timedelta
    from decimal import Decimal
    from django.utils import timezone
    from ..models import Facture

    anomalies = []

    # Doublon probable : même client, montant TTC proche, facture récente.
    montant = facture.total_ttc
    if montant and facture.client_id:
        seuil_jours = timezone.now().date() - timedelta(days=15)
        marge = montant * Decimal('0.01')
        doublons = Facture.objects.filter(
            client_id=facture.client_id, company=facture.company,
            date_emission__gte=seuil_jours,
        ).exclude(pk=facture.pk).exclude(
            statut=Facture.Statut.ANNULEE)
        for autre in doublons:
            if abs(autre.total_ttc - montant) <= marge:
                anomalies.append({
                    'code': 'doublon_probable',
                    'message': (
                        f'Doublon probable : facture {autre.reference} '
                        f'({autre.total_ttc} MAD) du même client, émise le '
                        f'{autre.date_emission}.'),
                })
                break

    # Remise globale au-delà du seuil société.
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=facture.company)
    remise_max = getattr(profile, 'remise_max_pct', None)
    if remise_max is not None and (facture.remise_globale or 0) > remise_max:
        anomalies.append({
            'code': 'remise_excessive',
            'message': (
                f'Remise globale ({facture.remise_globale} %) supérieure au '
                f'seuil société ({remise_max} %).'),
        })

    # Client au-delà de son plafond d'encours (FG41).
    if facture.client_id:
        from apps.crm.selectors import client_credit_warning
        warning = client_credit_warning(facture.client)
        if warning['depasse']:
            anomalies.append({
                'code': 'plafond_credit_depasse',
                'message': (
                    f"Encours client ({warning['encours']} MAD) au-delà du "
                    f"plafond ({warning['plafond']} MAD)."),
            })

    return anomalies


class CreditHoldError(Exception):
    """XFAC28 — levée quand un client est en hold crédit dur (sans override).

    Porte le détail chiffré (``motif``) pour un message 403 explicite."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def verifier_credit_hold(client, *, override=False, user=None,
                         chatter_target=None, contexte=''):
    """XFAC28 — vérifie le hold crédit dur (étend FG41) avant une action
    sensible (accepter un devis, générer une facture).

    Flag OFF (``CompanyProfile.credit_hold_actif``) → no-op, comportement FG41
    intact (avertissement seul, jamais consulté ici). Flag ON et le client est
    en dépassement (plafond et/ou retard, voir
    ``apps.crm.selectors.credit_hold_check``) : lève ``CreditHoldError`` SAUF
    si ``override=True`` (responsable/admin explicite) — l'override est
    journalisé (chatter du devis si fourni + audit) mais laisse passer
    l'action. Ne renvoie rien ; lève ou passe silencieusement.

    WIR93 — COEXISTENCE AVEC ``apps.credit`` (décision consignée en tête de
    ``apps/credit/services.py``). Ce moteur (FG41/XFAC28) reste le SEUL branché
    en production ; ``apps.credit.services.verifier_hold_credit`` (NTCRD6)
    n'a aucun appelant tant que NTCRD7/NTCRD8 ne sont pas livrés. Les deux
    consomment la MÊME assiette de factures, à un écart près, volontaire et
    unique : ce chemin ne compte que les factures ``emise``/``en_retard``,
    quand ``apps.credit`` inclut aussi les ``brouillon``. Cet écart est
    verrouillé par ``apps/credit/tests/test_wir93_encours_non_divergence.py``
    (via ``apps.credit.services.ecart_encours_moteurs``) : élargir ou
    rétrécir l'assiette d'un seul côté rend ce test rouge. Ne JAMAIS
    dupliquer ici un troisième calcul d'encours."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=client.company)
    if not getattr(profile, 'credit_hold_actif', False):
        return

    from apps.crm.selectors import credit_hold_check
    seuil = getattr(profile, 'credit_hold_retard_jours', 0) or 0
    result = credit_hold_check(client, retard_jours_seuil=seuil)
    if not result['bloque']:
        return

    if not override:
        raise CreditHoldError(result['motif'])

    # Override responsable/admin : journalise (chatter + audit société).
    from apps.parametres.models_audit import SettingsAuditLog
    qui = getattr(user, 'username', '?') if user else '?'
    SettingsAuditLog.log_change(
        company=client.company, user=user, section='credit_hold',
        field='override', field_label='Blocage crédit — override',
        old='bloque', new=f'débloqué par {qui} ({contexte})',
    )
    if chatter_target is not None:
        from .. import activity
        activity.log_devis_credit_hold_override(
            chatter_target, user, result['motif'])


class SaleWarningError(Exception):
    """ZSAL9 — levée quand un devis porte un avertissement de vente BLOQUANT
    (produit et/ou client) sans override responsable/admin.

    Porte le message concaténé (``motif``) pour un 403 explicite."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def verifier_sale_warnings(devis, *, override=False, user=None,
                           chatter_target=None):
    """ZSAL9 — vérifie les avertissements de vente (« sale warnings ») avant une
    action sensible (accepter un devis, générer une facture).

    Collecte les messages BLOQUANTS du client du devis et des produits de ses
    lignes (lus via ``stock.selectors`` — jamais d'import de ``stock.models``).
    Sans message bloquant → no-op. Avec au moins un message bloquant : lève
    ``SaleWarningError`` SAUF si ``override=True`` (responsable/admin explicite),
    auquel cas l'override est journalisé (chatter du devis si fourni). Les
    avertissements NON bloquants n'empêchent jamais l'action (ils ne sont
    qu'affichés côté écran). Ne renvoie rien ; lève ou passe silencieusement."""
    motifs = []

    client = getattr(devis, 'client', None)
    if client is not None and getattr(client, 'avertissement_bloquant', False) \
            and (getattr(client, 'avertissement_vente', '') or '').strip():
        motifs.append(f'Client — {client.avertissement_vente.strip()}')

    from apps.stock import selectors as stock_selectors
    produit_ids = list(
        devis.lignes.exclude(produit__isnull=True)
        .values_list('produit_id', flat=True)
    )
    for row in stock_selectors.produits_avertissements(devis.company, produit_ids):
        if row.get('avertissement_bloquant') \
                and (row.get('avertissement_vente') or '').strip():
            motifs.append(
                f"Produit « {row.get('nom', '')} » — "
                f"{row['avertissement_vente'].strip()}")

    if not motifs:
        return

    motif = ' ; '.join(motifs)
    if not override:
        raise SaleWarningError(motif)

    # Override responsable/admin : journalise au chatter du devis.
    if chatter_target is not None:
        from .. import activity
        activity.log_devis_sale_warning_override(chatter_target, user, motif)


def _s2(x):
    from decimal import Decimal
    return str(Decimal(x or 0).quantize(Decimal('0.01')))


def dossier_contentieux_data(factures):
    """XFAC21 — assemble les données du pack contentieux pour un jeu de
    factures en souffrance (toutes du MÊME client — vérifié par l'appelant).

    Renvoie un dict prêt pour le template ``dossier_contentieux.html`` :
    factures concernées, total réclamé, historique des relances (RelanceLog) +
    emails (EmailLog), promesses de paiement ROMPUES (PromessePaiement).
    Lecture seule."""
    from django.utils import timezone
    from ..models import PromessePaiement

    factures = list(factures)
    client = factures[0].client if factures else None

    lignes_factures = []
    total_du = 0
    relances = []
    emails = []
    promesses_rompues = []

    for f in factures:
        total_du += f.montant_du
        lignes_factures.append({
            'reference': f.reference,
            'date_echeance': (
                f.date_echeance.isoformat() if f.date_echeance else ''),
            'jours_retard': f.jours_retard,
            'total_ttc': _s2(f.total_ttc),
            'du': _s2(f.montant_du),
        })
        for r in f.relances.all().order_by('-date', '-id'):
            relances.append({
                'date': r.date.isoformat() if r.date else '',
                'facture_reference': f.reference,
                'niveau_nom': r.niveau_nom or '',
                'note': r.note or '',
            })
        for e in f.email_logs.all().order_by('-created_at'):
            emails.append({
                'date': e.created_at.isoformat() if e.created_at else '',
                'direction': e.get_direction_display(),
                'sujet': e.sujet or '',
            })
        for p in f.promesses_paiement.filter(
                statut=PromessePaiement.Statut.ROMPUE):
            promesses_rompues.append({
                'facture_reference': f.reference,
                'date_promise': p.date_promise.isoformat(),
                'montant_promis': _s2(p.montant_promis),
            })

    return {
        'client': {
            'nom': f'{client.nom} {client.prenom or ""}'.strip() if client else '',
            'email': getattr(client, 'email', '') or '',
            'telephone': getattr(client, 'telephone', '') or '',
            'adresse': getattr(client, 'adresse', '') or '',
        },
        'factures': lignes_factures,
        'total_du': _s2(total_du),
        'relances': relances,
        'emails': emails,
        'promesses_rompues': promesses_rompues,
        'date_creation': timezone.now().date().isoformat(),
    }


def ouvrir_dossier_contentieux(*, factures, user=None):
    """XFAC21 — passage en recouvrement externe pour un jeu de factures.

    (a) assemble les données du pack (voir ``dossier_contentieux_data``) ;
    (b) ouvre une ``litiges.Reclamation`` de type recouvrement via
        ``apps.litiges.services.creer_dossier_recouvrement`` (jamais un import
        de son modèle) ;
    (c) marque les factures ``exclu_relances`` (comms ordinaires gelées) avec
        trace chatter « passé au contentieux le … ».

    Toutes les factures DOIVENT appartenir au même client + à la même société
    (vérifié par l'appelant — la vue scope déjà par client). Renvoie
    ``(dossier_data, reclamation)``."""
    from django.utils import timezone
    from ..models import Facture

    factures = list(factures)
    if not factures:
        raise ValueError('Aucune facture sélectionnée.')
    client = factures[0].client
    company = factures[0].company

    dossier = dossier_contentieux_data(factures)

    from apps.litiges.services import creer_dossier_recouvrement
    references = ', '.join(f.reference for f in factures)
    reclamation = creer_dossier_recouvrement(
        company=company, source_type='client', source_id=client.id,
        objet=f'Recouvrement externe — {client.nom} ({references})',
        montant_conteste=sum((f.montant_du for f in factures), 0),
        description=f'Factures concernées : {references}.',
        user=user,
    )

    from .. import activity
    qui = getattr(user, 'username', '?') if user else 'automatique'
    today = timezone.now().date().isoformat()
    for f in factures:
        if f.statut == Facture.Statut.ANNULEE:
            continue
        f.exclu_relances = True
        f.save(update_fields=['exclu_relances'])
        activity.log_facture_activity_contentieux(f, user, qui, today)

    return dossier, reclamation


def enregistrer_contestation_portail(facture, *, motif_label, commentaire=''):
    """XFAC27 — Trace côté ventes la contestation d'une facture ouverte par
    le client depuis le portail self-service (``apps.compta`` appelle CETTE
    fonction, jamais un import direct de ``apps.ventes.models``/``activity``).
    Ne change AUCUN statut de la facture — seule la réclamation créée côté
    ``apps.litiges`` suspend les relances (LITIGE3)."""
    from .. import activity
    return activity.log_facture_contestation_portail(
        facture, motif_label, commentaire=commentaire)


# ── QJ4 — Relance automatique cadencée des devis envoyés ─────────────────────
# Logique : pour chaque devis « envoyé » (statut ENVOYE) dont date_envoi est
# renseignée, on contrôle si l'un des paliers de la cadence est échu
# (aujourd'hui >= date_envoi + jours[niveau]) et s'il n'a pas encore été
# déclenché (pas de DevisNudgeLog pour ce niveau). On surface alors un draft
# wa.me au vendeur — ou on envoie un email si le canal email est configuré.
# La relance s'arrête dès que le statut passe à ACCEPTE ou REFUSE.

# Modèles de message de relance — FR et AR.
# Clés : ref (référence devis), jours (palier), client_nom, wa_url (lien
# public). Les accolades dobles {{ }} échappées en cas d'imbrication Django
# template — ici on utilise .format() directement, pas de template Django.
_NUDGE_MSG_FR = (
    "Bonjour,\n\n"
    "Le devis {ref} envoyé à {client_nom} il y a {jours} jours est toujours "
    "en attente de validation.\n\n"
    "Pensez à relancer votre client :\n{wa_url}\n\n"
    "Cordialement,\nL'équipe TAQINOR"
)

_NUDGE_MSG_AR = (
    "مرحبا،\n\n"
    "لا يزال عرض "
    "{ref} المرسل إلى "
    "{client_nom} منذ {jours} أيام "
    "في انتظار الموافقة.\n\n"
    "يُرجى متابعة "
    "العميل:\n{wa_url}\n\n"
    "مع التحيات،\n"
    "فريق TAQINOR"
)


def _build_wa_draft_url(phone, text):
    """Construit un lien wa.me pré-rempli. phone peut inclure '+' ou non."""
    import urllib.parse
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if not digits:
        return None
    encoded = urllib.parse.quote(text)
    return f'https://wa.me/{digits}?text={encoded}'


def _get_nudge_days():
    """Renvoie la cadence de relance depuis les settings (ou la valeur par défaut)."""
    from django.conf import settings
    from apps.ventes.models import DEVIS_NUDGE_DEFAULT_DAYS
    return getattr(settings, 'DEVIS_NUDGE_DAYS', DEVIS_NUDGE_DEFAULT_DAYS)


def _nudge_suppressed(devis, today, engagement_days=3):
    """QX13 — une relance de devis doit-elle être différée/sautée ?

    Trois signaux de réalité (la cadence était aveugle à l'activité) :
      * ``lead.relance_date`` est dans le FUTUR (le vendeur a déjà planifié un
        contact) → on ne double pas ;
      * une activité de contact MANUELLE existe récemment sur le lead (via un
        sélecteur crm optionnel, jamais un import de modèle crm) ;
      * un engagement proposition récent (< engagement_days) sur le ShareLink
        (le client vient de regarder → laisser respirer).

    Retourne True pour SUPPRIMER/différer, False pour laisser passer. Best-
    effort : toute erreur → False (on ne bloque jamais une relance par bug)."""
    from datetime import timedelta
    try:
        lead_id = getattr(devis, 'lead_id', None)
        if lead_id:
            from apps.crm import selectors as crm_selectors
            lead = crm_selectors.get_company_lead(devis.company, lead_id)
            if lead is not None:
                relance = getattr(lead, 'relance_date', None)
                if relance and relance > today:
                    return True
                # Activité de contact manuelle récente — via sélecteur crm si
                # disponible (jamais un import de modèle crm). Coordination :
                # une fonction dédiée ``lead_recent_manual_contact`` pourra être
                # ajoutée côté crm ; en son absence, ce signal est ignoré.
                fn = getattr(crm_selectors, 'lead_recent_manual_contact', None)
                if callable(fn):
                    try:
                        if fn(devis.company, lead_id):
                            return True
                    except Exception:  # noqa: BLE001
                        pass
    except Exception:  # noqa: BLE001
        pass
    # Engagement proposition récent (ShareLink — in-lane).
    try:
        from apps.ventes.models import ShareLink
        link = (ShareLink.objects
                .filter(devis=devis)
                .order_by('-created_at')
                .first())
        seen = getattr(link, 'last_viewed_at', None) if link else None
        if seen is not None:
            seen_date = seen.date() if hasattr(seen, 'date') else seen
            if seen_date >= today - timedelta(days=engagement_days):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _journaliser_relance_marketing(devis, *, jours, canal, niveau):
    """WIR96 — miroir marketing d'une relance de devis abandonné.

    ``marketing.RelanceDevisAbandonne`` + son service
    ``enregistrer_relance_devis_abandonne`` existaient sans AUCUN appelant :
    aucune relance n'était jamais journalisée côté marketing (le calendrier
    marketing lisait une table toujours vide). On les alimente ici, au moment
    exact où la relance part réellement (après création du ``DevisNudgeLog``,
    qui reste la source de vérité anti-doublon côté ventes).

    Écriture via la frontière ``apps.marketing.services`` uniquement (jamais un
    import des modèles marketing) ; ``devis_id`` reste une référence OPAQUE
    côté marketing. Best-effort : une erreur ne doit jamais faire échouer la
    relance elle-même."""
    if not getattr(devis, 'company_id', None):
        return
    try:
        from apps.marketing.services import (
            enregistrer_relance_devis_abandonne)
        enregistrer_relance_devis_abandonne(
            devis.company,
            devis_id=devis.pk,
            devis_reference=devis.reference or '',
            jours_sans_reponse=jours or 0,
            canal=str(canal or ''),
            note=f'Relance automatique niveau {niveau + 1} (QJ4).',
        )
    except Exception as exc:  # noqa: BLE001 — miroir best-effort
        logger.warning(
            'WIR96: journalisation marketing de la relance échouée '
            'pour devis %s : %s', getattr(devis, 'reference', '?'), exc)


def send_devis_followup_nudges():
    """QJ4 — Déclenche les relances cadencées pour les devis « envoyés ».

    Pour chaque devis ENVOYE avec date_envoi renseignée :
    - parcourt les paliers de la cadence (j+2, j+5, j+10 par défaut) ;
    - si today >= date_envoi + jours[niveau] ET que ce niveau n'a jamais été
      déclenché (pas de DevisNudgeLog) → envoie la relance ;
    - préfère un email si le canal email est configuré, sinon surface un draft
      wa.me au vendeur (logged) ;
    - enregistre un DevisNudgeLog pour éviter tout doublon.

    Idempotent : safe à ré-exécuter sans effet si tous les niveaux dus ont déjà
    leur DevisNudgeLog. Renvoie le nombre total de nudges déclenchés.

    RULE #4 : ne touche JAMAIS au statut du Devis.
    Multi-tenant : chaque devis est scopé company (never trusts body company).
    """
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo('Africa/Casablanca')

        def _today():
            return timezone.now().astimezone(_tz).date()
    except Exception:
        def _today():
            return timezone.localdate()

    from apps.ventes.models import Devis, DevisNudgeLog, ShareLink
    from apps.ventes.email_service import is_email_configured

    nudge_days = _get_nudge_days()
    today = _today()

    # Only look at envoye devis with a known send date.
    candidates = Devis.objects.filter(
        statut=Devis.Statut.ENVOYE,
        date_envoi__isnull=False,
    ).select_related('client', 'company', 'created_by').prefetch_related(
        'nudge_logs',
    )

    use_email = is_email_configured()
    total_sent = 0

    for devis in candidates:
        # Double-check: cadence stops on accept/refuse (belt-and-suspenders
        # since we filter on ENVOYE above, but guards concurrent transitions).
        if devis.statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE):
            continue

        # date_envoi is a DateTimeField — extract date in Casablanca tz.
        try:
            envoi_date = devis.date_envoi.astimezone(
                ZoneInfo('Africa/Casablanca')).date()
        except Exception:
            envoi_date = devis.date_envoi.date()

        # Which levels already fired?
        fired = set(
            devis.nudge_logs.values_list('niveau', flat=True)
        )

        client = getattr(devis, 'client', None)
        client_nom = (getattr(client, 'nom', '') or '') if client else ''
        vendeur = getattr(devis, 'created_by', None)

        # QX13 — respecte la réalité : relance planifiée, contact manuel
        # récent, ou engagement proposition récent → on diffère ce tour.
        if _nudge_suppressed(devis, today):
            continue

        for idx, jours in enumerate(nudge_days):
            if idx in fired:
                continue  # already sent for this level — idempotent
            trigger_date = envoi_date + __import__('datetime').timedelta(days=jours)
            if today < trigger_date:
                continue  # not due yet

            # Build the public share link for the seller to use.
            # QX13 — via le builder UNIQUE client_links (chemin /proposition/,
            # jamais /proposal/ qui 404 sur le site). PV84 — nom du client
            # inclus dans l'URL (cosmétique, token toujours seul secret).
            try:
                share_link = ShareLink.for_devis(devis)
                from apps.ventes.utils.client_links import url_proposition
                proposal_url = url_proposition(devis, share_link.token)
            except Exception:
                proposal_url = ''

            msg_fr = _NUDGE_MSG_FR.format(
                ref=devis.reference,
                client_nom=client_nom or 'votre client',
                jours=jours,
                wa_url=proposal_url,
            )
            msg_ar = _NUDGE_MSG_AR.format(
                ref=devis.reference,
                client_nom=client_nom or 'عميلك',
                jours=jours,
                wa_url=proposal_url,
            )

            canal = DevisNudgeLog.Canal.WA_DRAFT

            # Bilingual body used for email (FR + AR separator).
            msg_bilingual = msg_fr + '\n\n---\n\n' + msg_ar

            if use_email and vendeur and getattr(vendeur, 'email', ''):
                # Send email to seller (bilingual FR + AR).
                _send_nudge_email(
                    to_email=vendeur.email,
                    devis_ref=devis.reference,
                    subject_fr=f'Relance devis {devis.reference} — niveau {idx + 1}',
                    body_fr=msg_bilingual,
                )
                canal = DevisNudgeLog.Canal.EMAIL
            else:
                # QX13 — brouillon wa.me vers le CLIENT (le lien proposition à
                # partager), et non le téléphone du vendeur.
                client_phone = (getattr(client, 'telephone', '') or ''
                                if client else '')
                wa_url = (_build_wa_draft_url(client_phone, msg_fr)
                          or proposal_url)
                logger.info(
                    'QJ4 nudge wa_draft devis=%s niveau=%d j+%d vendeur=%s url=%s',
                    devis.reference, idx, jours,
                    getattr(vendeur, 'username', '?'), wa_url)
                # QX13 — le brouillon wa.me ne partait qu'en LOG (invisible) :
                # crée une vraie Notification in-app au vendeur, avec le lien
                # proposition + le brouillon wa.me prêts et un deep-link devis.
                if vendeur is not None:
                    try:
                        from apps.notifications.services import notify
                        from apps.notifications.models import EventType
                        notify(
                            vendeur, EventType.DEVIS_NUDGE_DUE,
                            title=(f'Relance à faire — devis {devis.reference} '
                                   f'(niveau {idx + 1})'),
                            body=(f'Aucune réponse depuis {jours} j. '
                                  f'Proposition : {proposal_url or "—"}'
                                  + (f'\nBrouillon WhatsApp : {wa_url}'
                                     if wa_url else '')),
                            link=f'/ventes/devis?devis={devis.id}',
                            company=devis.company)
                    except Exception as exc:  # noqa: BLE001 — best-effort
                        logger.warning(
                            'QX13: notification relance échec devis %s : %s',
                            devis.reference, exc)

            # Record the fired level — unique_together prevents duplicates.
            try:
                DevisNudgeLog.objects.create(
                    company=devis.company,
                    devis=devis,
                    niveau=idx,
                    jours=jours,
                    canal=canal,
                )
                total_sent += 1
                logger.info(
                    'QJ4: nudge N%d déclenché pour devis %s (j+%d, canal=%s)',
                    idx, devis.reference, jours, canal)
                _journaliser_relance_marketing(
                    devis, jours=jours, canal=canal, niveau=idx)
            except Exception as exc:
                # IntegrityError → already fired concurrently — safe to ignore.
                logger.warning(
                    'QJ4: DevisNudgeLog creation skipped for devis %s niveau=%d: %s',
                    devis.reference, idx, exc)

    logger.info('QJ4 send_devis_followup_nudges: %d nudge(s) déclenchés', total_sent)
    return total_sent


def _send_nudge_email(*, to_email, devis_ref, subject_fr, body_fr):
    """Envoie un email de relance au vendeur (NO-OP sans backend email configuré).

    Best-effort : ne lève jamais, consigne juste le résultat en log.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        send_mail(subject_fr, body_fr, from_email, [to_email], fail_silently=False)
        logger.info('QJ4: email relance envoyé à %s (devis %s)', to_email, devis_ref)
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ4: email relance échec pour %s: %s', devis_ref, exc)


# ── QJ5 — Expiration automatique des devis + hygiène funnel ──────────────────


def expire_stale_devis():
    """QJ5 — Bascule les devis envoyés dépassés en « expiré » et avance le funnel.

    Deux effets ATOMIQUEMENT SÉPARÉS (chaque devis est traité indépendamment) :

    1. ``envoye → expire`` pour tout devis dont la date de validité effective
       est dépassée. Délègue à ``ventes.utils.expiry.is_expired`` (même logique
       que l'indicateur à la volée, garantie de cohérence). Ne touche JAMAIS un
       devis ``accepte`` ou ``refuse`` (rule #4). Idempotent : un devis déjà
       ``expire`` est ignoré.

    2. Pour le lead lié au devis expiré (s'il en a un) : si le lead est à
       ``QUOTE_SENT`` il avance vers ``FOLLOW_UP``; s'il est déjà à ``FOLLOW_UP``
       depuis plus de COLD_DAYS jours (configurable, défaut 30) et n'a reçu
       aucune activité récente, il est parqué à ``COLD``. Ne recule JAMAIS un
       lead déjà plus avancé (SIGNED) et ignore les leads perdus (drapeau perdu).
       STAGES.py keys utilisées, jamais hardcodées.

    Renvoie un dict ``{expired, funnel_followup, funnel_cold}`` pour les tests.
    """
    from ..models import Devis

    # QX11 — date Casablanca-aware (comme ses tâches sœurs), plus
    # ``date.today()`` (fuseau serveur) qui pouvait décaler l'expiration d'un
    # jour selon l'UTC.
    from ..scheduled import casablanca_today
    today = casablanca_today()
    expired = 0
    funnel_followup = 0
    funnel_cold = 0

    # Candidats : devis envoyés uniquement (jamais accepte/refuse/expire).
    candidates = Devis.objects.filter(
        statut=Devis.Statut.ENVOYE,
    ).select_related('lead', 'lead__company')

    for devis in candidates:
        from ..utils.expiry import is_expired
        if not is_expired(devis, today=today):
            continue

        # Flip to expired through the single status-change path: direct field
        # write + chatter log. Using the same field pattern as other beat jobs
        # (check_overdue_factures) — safe, reversible via git revert.
        devis.statut = Devis.Statut.EXPIRE
        devis.save(update_fields=['statut'])

        # Chatter entry via ventes.activity (exists for devis accepted/sent —
        # reuse the generic note pattern).
        try:
            from apps.ventes import activity as _act
            _act.log_devis_note(
                devis, None,
                'Devis expiré automatiquement (date de validité dépassée).')
        except Exception as exc:  # noqa: BLE001
            logger.warning('QJ5: log chatter échec devis %s : %s',
                           devis.reference, exc)

        # YEVNT10 — une mutation AUTOMATIQUE (cron, hors requête HTTP) échappe
        # à l'audit par signaux request-scopé. Cette expiration est journalisée
        # « système » CÔTÉ audit, via un abonnement à l'événement
        # `devis_expired` émis ci-dessous (apps/audit/receivers.py) — jamais par
        # un import direct ventes→audit (M4 : les réactions passent par
        # core.events).

        # YEVNT2 — événement métier (notifications/audit s'abonnent), jamais
        # réémis pour un devis déjà expiré (garde amont via le queryset ENVOYE
        # + is_expired). Best-effort : ne casse jamais le sweep.
        try:
            from core.events import devis_expired
            devis_expired.send(
                sender=Devis, devis=devis, ancien_statut='envoye')
        except Exception as exc:  # noqa: BLE001
            logger.warning('YEVNT2: devis_expired échoué pour devis %s : %s',
                           devis.reference, exc)

        expired += 1

        # Funnel hygiene: advance QUOTE_SENT → FOLLOW_UP via crm.services.
        lead = devis.lead
        if lead is None:
            continue

        try:
            fup, cold = _advance_lead_on_expiry(lead, today=today)
            funnel_followup += int(fup)
            funnel_cold += int(cold)
        except Exception as exc:  # noqa: BLE001
            logger.warning('QJ5: avance funnel échec lead %s : %s',
                           getattr(lead, 'pk', '?'), exc)

    logger.info(
        'QJ5 expire_stale_devis: %d expiré(s), %d → FOLLOW_UP, %d → COLD',
        expired, funnel_followup, funnel_cold)
    return {'expired': expired, 'funnel_followup': funnel_followup,
            'funnel_cold': funnel_cold}


# Days a QUOTE_SENT lead stays at FOLLOW_UP before being parked COLD (no
# recent activity). Kept as a module-level constant so tests can patch it.
_COLD_AFTER_FOLLOWUP_DAYS = 30


def _advance_lead_on_expiry(lead, today):
    """Avance l'étape du lead lié à un devis expiré (QUOTE_SENT → FOLLOW_UP,
    puis FOLLOW_UP → COLD si inactif depuis COLD_AFTER_FOLLOWUP_DAYS jours).

    Ne recule JAMAIS. Ignore les leads perdus. Utilise les clés STAGES.py.
    Renvoie (moved_to_followup: bool, moved_to_cold: bool).

    CRX20 — les deux écritures passent par ``apps.crm.services.
    appliquer_stage_lead`` (chemin canonique qui émet ``lead_stage_changed``)
    et les clés d'étape viennent d'``apps.crm.stages`` (donc de la STAGES.py
    racine, règle #2) — plus aucun littéral d'étape ici.
    """
    from datetime import timedelta
    from apps.crm import stages
    from apps.crm.models import LeadActivity
    from apps.crm.services import appliquer_stage_lead

    if lead.perdu:
        return False, False

    moved_fup = False
    moved_cold = False

    if lead.stage == stages.QUOTE_SENT:
        # Only advance if lead is not already further.
        from apps.crm.services import _rang_funnel
        if _rang_funnel(lead.stage) < _rang_funnel(stages.FOLLOW_UP):
            ancien = lead.stage
            moved_fup = appliquer_stage_lead(lead, stages.FOLLOW_UP, user=None)
            if moved_fup:
                from apps.crm import activity as crm_activity
                # Pass raw stage keys; _display resolves choices labels.
                crm_activity.log_bulk_change(
                    lead, user=None,
                    field='stage',
                    old_val=ancien,
                    new_val=stages.FOLLOW_UP,
                )
        return moved_fup, False

    if lead.stage == stages.FOLLOW_UP:
        # Park COLD only if no activity in last _COLD_AFTER_FOLLOWUP_DAYS days.
        cutoff = today - timedelta(days=_COLD_AFTER_FOLLOWUP_DAYS)
        recent_activity = LeadActivity.objects.filter(
            lead=lead,
            created_at__date__gte=cutoff,
        ).exists()
        if recent_activity:
            return False, False
        ancien = lead.stage
        moved_cold = appliquer_stage_lead(lead, stages.COLD, user=None)
        if moved_cold:
            from apps.crm import activity as crm_activity
            crm_activity.log_bulk_change(
                lead, user=None,
                field='stage',
                old_val=ancien,
                new_val=stages.COLD,
            )
        return False, moved_cold

    return False, False
