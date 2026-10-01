"""QJR545 (Groupe QJR5, contrat QJR503 ``devis_verrou_edition.json``) — verrou
OPTIMISTE d'édition d'un devis.

LE JETON. ``Devis.updated_at`` (``auto_now``) tel que servi par le GET. Il
était AVEUGLE aux écritures système : la resynchro catalogue sauve la LIGNE
(``update_fields``) et l'écrivain d'étude sauve ``update_fields=
['etude_params']`` — ``updated_at`` ne bougeait pas, donc deux vendeurs (ou un
vendeur et le catalogue) pouvaient s'écraser sans le savoir.

* :func:`toucher_devis` — avance ``updated_at`` par un ``UPDATE`` d'une seule
  colonne ; appelée par CHAQUE écrivain du devis ou de ses lignes. Elle rend
  l'horodatage posé pour que l'appelant réaligne son instance (une réponse 2xx
  porte TOUJOURS le jeton réellement en base).
* :func:`verifier_jeton` — si le corps porte ``expected_updated_at`` et qu'il
  diffère du jeton en base, rend la charge 409 ``{code: 'devis_modifie',
  detail, updated_at, updated_by_nom}`` ; sinon ``None``. Champ ABSENT ⇒
  comportement inchangé (Copilote, devis automatique).

Lit le statut, ne l'écrit jamais (règle #4).
"""
from django.utils import timezone
from django.utils.dateparse import parse_datetime

CODE_DEVIS_MODIFIE = 'devis_modifie'
MSG_DEVIS_MODIFIE = (
    "Ce devis a été modifié par un autre utilisateur depuis votre ouverture. "
    "Rechargez avant d'enregistrer.")


def toucher_devis(devis_id):
    """Avance ``updated_at`` du devis ``devis_id`` (une colonne, aucun signal,
    aucun gel ``prix_par_kwc``). Rend l'horodatage posé, ou ``None``."""
    if not devis_id:
        return None
    from apps.ventes.models import Devis
    maintenant = timezone.now()
    Devis.objects.filter(pk=devis_id).update(updated_at=maintenant)
    return maintenant


def toucher(devis):
    """:func:`toucher_devis` + réalignement de l'instance en mémoire."""
    pk = getattr(devis, 'pk', None)
    horodatage = toucher_devis(pk)
    if horodatage is not None:
        devis.updated_at = horodatage
    return horodatage


def _jeton_attendu(donnees):
    if not hasattr(donnees, 'get'):
        return None
    brut = donnees.get('expected_updated_at')
    if brut in (None, ''):
        return None
    return brut


def verifier_jeton(devis, donnees):
    """``None`` si l'écriture peut passer ; sinon la charge du 409."""
    brut = _jeton_attendu(donnees)
    if brut is None:
        return None
    from apps.ventes.models import Devis
    ligne = (Devis.objects.filter(pk=devis.pk)
             .values('updated_at', 'updated_by__first_name',
                     'updated_by__last_name', 'updated_by__username')
             .first())
    if ligne is None:
        return None
    courant = ligne['updated_at']
    attendu = parse_datetime(str(brut))
    if attendu is not None and timezone.is_naive(attendu):
        attendu = timezone.make_aware(attendu)
    if attendu is not None and courant is not None and attendu == courant:
        return None
    nom = ' '.join(p for p in (ligne['updated_by__first_name'],
                               ligne['updated_by__last_name']) if p).strip()
    return {
        'code': CODE_DEVIS_MODIFIE,
        'detail': MSG_DEVIS_MODIFIE,
        'updated_at': courant.isoformat() if courant else '',
        'updated_by_nom': nom or (ligne['updated_by__username'] or ''),
    }
