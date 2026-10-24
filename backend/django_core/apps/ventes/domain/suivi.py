"""ADOC131 (D-ADOC-4) — durée de vie du lien public de suivi post-signature.

Le lien public (``ShareLink`` du devis : même jeton pour ``/proposition`` et
``/suivi``) expirait à 30 jours de sa création — en plein chantier. Règle :

* à l'ACCEPTATION (``accept_devis``, porte unique), ``ouvrir_suivi`` pose
  ``suivi_prolonge_le`` sur les liens non révoqués du devis : ils restent
  valides tant que le chantier n'est pas réceptionné (``ShareLink.is_valid``) ;
* à la RÉCEPTION du chantier (``core.events.chantier_receptionne``),
  ``fermer_suivi_a_reception`` pose l'échéance ``date_reception + 90 jours``
  (le lien vit tout le 90e jour) et remet ``suivi_prolonge_le`` à null ;
* ``revoquer_liens_publics`` coupe le lien immédiatement (``revoque_le``).

ADEV17 (C-ADEV-009) — la chaîne de révision : une V1 acceptée puis révisée
gardait un lien prolongé « jusqu'à la réception » que plus rien ne fermait
(le chantier est rattaché à la V2). Désormais ``ouvrir_suivi`` sur la V2 lève
la prolongation des versions qu'elle remplace
(``selectors.devis_predecesseurs_revision_ids``), et la réception ferme
immédiatement (``expires_at`` = maintenant) les liens encore ouverts de toutes
ces versions : seul le lien de la version réceptionnée vit réception + 90 j.

Aucun statut n'est écrit ici (devis, BC, facture, chantier) : seules les dates
du lien changent.
"""
import datetime
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Durée de vie du suivi après la réception du chantier (D-ADOC-4).
SUIVI_APRES_RECEPTION_JOURS = 90


def _predecesseurs_ids(devis):
    from apps.ventes.selectors import devis_predecesseurs_revision_ids
    return devis_predecesseurs_revision_ids(devis)


def ouvrir_suivi(devis):
    """Prolonge les liens publics non révoqués de ``devis`` jusqu'à la
    réception de son chantier, et lève la prolongation des versions que
    ``devis`` remplace (ADEV17). Renvoie le nombre de liens prolongés."""
    from apps.ventes.models import ShareLink
    predecesseurs = _predecesseurs_ids(devis)
    if predecesseurs:
        (ShareLink.objects
         .filter(devis_id__in=predecesseurs,
                 suivi_prolonge_le__isnull=False)
         .update(suivi_prolonge_le=None))
    return (ShareLink.objects
            .filter(devis_id=devis.pk, revoque_le__isnull=True,
                    suivi_prolonge_le__isnull=True)
            .update(suivi_prolonge_le=timezone.now()))


def echeance_apres_reception(date_reception):
    """Instant d'expiration : minuit qui SUIT le 90e jour après la réception
    (le lien répond encore pendant toute la journée réception + 90 j)."""
    jour = date_reception + datetime.timedelta(
        days=SUIVI_APRES_RECEPTION_JOURS + 1)
    return timezone.make_aware(
        datetime.datetime.combine(jour, datetime.time.min))


def fermer_suivi_a_reception(devis_id, date_reception=None):
    """Pose l'échéance réception + 90 j sur les liens du devis ``devis_id``
    et lève la prolongation. Renvoie le nombre de liens mis à jour."""
    from apps.ventes.models import ShareLink
    if not devis_id:
        return 0
    from apps.ventes.models import Devis
    from django.db.models import Q
    date_reception = date_reception or timezone.localdate()
    n = (ShareLink.objects
         .filter(devis_id=devis_id, revoque_le__isnull=True)
         .update(expires_at=echeance_apres_reception(date_reception),
                 suivi_prolonge_le=None))
    # ADEV17 — les versions remplacées par révision : leurs liens encore
    # ouverts (prolongés ou non expirés) sont fermés MAINTENANT.
    devis = Devis.objects.filter(pk=devis_id).only('pk', 'company_id').first()
    predecesseurs = _predecesseurs_ids(devis) if devis is not None else []
    if predecesseurs:
        maintenant = timezone.now()
        n += (ShareLink.objects
              .filter(devis_id__in=predecesseurs, revoque_le__isnull=True)
              .filter(Q(suivi_prolonge_le__isnull=False)
                      | Q(expires_at__gt=maintenant))
              .update(expires_at=maintenant, suivi_prolonge_le=None))
    return n


def on_chantier_receptionne(sender, installation=None, **kwargs):
    """Récepteur de ``core.events.chantier_receptionne`` (branché dans
    ``VentesConfig.ready``). Lit uniquement le payload de l'événement
    (``devis_id``, ``date_reception``) — aucun import du modèle chantier."""
    if installation is None:
        return
    fermer_suivi_a_reception(
        getattr(installation, 'devis_id', None),
        getattr(installation, 'date_reception', None))


def revoquer_liens_publics(devis):
    """Révoque tous les liens publics encore non révoqués de ``devis``.
    Renvoie ``(nombre, horodatage)``."""
    from apps.ventes.models import ShareLink
    maintenant = timezone.now()
    n = (ShareLink.objects
         .filter(devis_id=devis.pk, revoque_le__isnull=True)
         .update(revoque_le=maintenant))
    return n, maintenant


# ── ADEV97 (L3 lien public, 24/10/2026) — FIN DE VIE AUTOMATIQUE DU LIEN ────
#
# Un devis REFUSÉ, REMPLACÉ par une nouvelle version, ou dont le LEAD est
# perdu ne se lit plus au jeton client (prix, identité) : ses liens publics
# sont révoqués d'eux-mêmes, une note de chatter dit pourquoi. Un devis
# ACCEPTÉ n'est JAMAIS révoqué ici (ADOC131 : son lien sert la page en
# lecture seule et ``/suivi/`` jusqu'à la réception + 90 jours). Aucun statut
# n'est écrit (règle #4) : seule ``ShareLink.revoque_le`` change.

#: Motifs de la note de chatter (un par déclencheur).
MOTIF_REFUS = 'devis refusé'
MOTIF_REMPLACE = 'remplacé par une nouvelle version'
MOTIF_LEAD_PERDU = 'lead perdu'


def revoquer_en_fin_de_vie(devis, motif):
    """ADEV97 — révoque les liens vivants de ``devis`` (jamais un accepté) et
    note au chatter la raison ; rend le nombre de liens révoqués. Best-effort
    côté appelant (récepteurs) : ne lève que sur une erreur de base."""
    if devis is None or getattr(devis, 'statut', None) == 'accepte':
        return 0
    from django.db import transaction
    try:
        # Point de sauvegarde (ADEV54) : abonné best-effort d'un événement émis
        # dans la transaction de l'appelant — son échec n'annule jamais le refus.
        with transaction.atomic():
            n, _quand = revoquer_liens_publics(devis)
            if n:
                from apps.ventes import activity
                activity.log_devis_note(
                    devis, None, 'Lien public de la proposition révoqué '
                    f'automatiquement ({motif}).')
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger.warning('ADEV97 : liens non révoqués (devis %s, %s)',
                       getattr(devis, 'reference', '?'), motif, exc_info=True)
        return 0
    return n


def on_devis_refused(sender, devis=None, **kwargs):
    """Récepteur de ``core.events.devis_refused`` (FG44)."""
    revoquer_en_fin_de_vie(devis, MOTIF_REFUS)


def on_devis_revise(sender, ancien=None, nouveau=None, **kwargs):
    """Récepteur de ``core.events.devis_revise`` (ACAL91, après commit) : la
    version REMPLACÉE perd son lien (la nouvelle version a le sien à l'envoi)."""
    revoquer_en_fin_de_vie(ancien, MOTIF_REMPLACE)


def on_lead_enregistre(sender, instance=None, **kwargs):
    """``post_save`` de ``crm.Lead`` (référence paresseuse, aucun import du
    modèle) : un lead ``perdu`` révoque les liens de ses devis non acceptés.
    Idempotent (seuls les liens encore vivants sont touchés)."""
    if instance is None or not getattr(instance, 'perdu', False):
        return
    from django.db import transaction
    from apps.ventes.models import Devis, ShareLink
    try:
        with transaction.atomic():
            devis_ids = list(
                ShareLink.objects
                .filter(devis__lead_id=instance.pk,
                        devis__company_id=getattr(instance, 'company_id', None),
                        revoque_le__isnull=True)
                .exclude(devis__statut=Devis.Statut.ACCEPTE)
                .values_list('devis_id', flat=True).distinct())
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger.warning('ADEV97 : liens du lead perdu #%s illisibles',
                       instance.pk, exc_info=True)
        return
    for devis in Devis.objects.filter(pk__in=devis_ids):
        revoquer_en_fin_de_vie(devis, MOTIF_LEAD_PERDU)
