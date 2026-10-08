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

from django.utils import timezone

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
