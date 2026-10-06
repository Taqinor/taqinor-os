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

Aucun statut n'est écrit ici (devis, BC, facture, chantier) : seules les dates
du lien changent.
"""
import datetime

from django.utils import timezone

#: Durée de vie du suivi après la réception du chantier (D-ADOC-4).
SUIVI_APRES_RECEPTION_JOURS = 90


def ouvrir_suivi(devis):
    """Prolonge les liens publics non révoqués de ``devis`` jusqu'à la
    réception de son chantier. Renvoie le nombre de liens prolongés."""
    from apps.ventes.models import ShareLink
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
    date_reception = date_reception or timezone.localdate()
    return (ShareLink.objects
            .filter(devis_id=devis_id, revoque_le__isnull=True)
            .update(expires_at=echeance_apres_reception(date_reception),
                    suivi_prolonge_le=None))


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
