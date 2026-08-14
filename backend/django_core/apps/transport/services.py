"""Services (écriture/orchestration) de l'app `apps.transport`.

Comme `selectors.py` (lecture), destiné à être importé PAR D'AUTRES APPS en
LOCAL/FONCTION (jamais au niveau module) — toute référence à un document
d'une autre app passe par une FK par chaîne ou par le sélecteur/service dédié
de cette app cible, jamais par un import direct de ses `models`.

Framework-agnostic : ces fonctions ne lèvent JAMAIS d'exception DRF — elles
renvoient `None`/une valeur ou un message d'erreur texte ; c'est à la vue
(`views.py`) de traduire en `rest_framework.exceptions.ValidationError` (400).
Une `django.core.exceptions.ValidationError` levée depuis `Model.save()` ne
serait PAS rattrapée par DRF et retomberait en 500 — piège déjà payé
ailleurs dans ce dépôt.
"""


def attribuer_numero(ordre):
    """NTLOG1 — pose `ordre.numero` (anti-collision, plus-haut-utilisé+1 par
    société) via `core.numbering.next_reference` — JAMAIS un `count()+1`
    (ARC6). No-op si déjà posé (idempotent)."""
    if ordre.numero:
        return ordre
    from core.numbering import next_reference

    from .models import OrdreTransport

    ordre.numero = next_reference(
        OrdreTransport, 'OT', ordre.company, field='numero')
    ordre.save(update_fields=['numero'])
    return ordre


def valider_mode_transport_champs(mode_transport, *, flotte_actif_id=None,
                                  conducteur_id=None,
                                  installations_transporteur_id=None):
    """NTLOG4 — un ordre en affrètement ne peut pas être affecté à un
    véhicule/conducteur interne, et un ordre en flotte propre ne référence
    pas de transporteur tiers. Prend des VALEURS SCALAIRES (pas une instance
    `OrdreTransport`) pour pouvoir être appelée à la fois avant la création
    (`serializer.validated_data`) et à la mise à jour (fusion instance +
    champs modifiés) — voir `views.OrdreTransportViewSet`. Renvoie un
    message d'erreur (str) ou `None`."""
    from .models import OrdreTransport

    if mode_transport == OrdreTransport.ModeTransport.AFFRETEMENT:
        if flotte_actif_id or conducteur_id:
            return (
                "Un ordre en mode affrètement ne peut pas être affecté à "
                "un véhicule/conducteur interne — désaffectez la flotte "
                "propre ou repassez l'ordre en « flotte propre ».")
    elif mode_transport == OrdreTransport.ModeTransport.FLOTTE_PROPRE:
        if installations_transporteur_id:
            return (
                "Un ordre en flotte propre ne référence pas de "
                "transporteur tiers — retirez le transporteur ou repassez "
                "l'ordre en « affrètement ».")
    return None


def log_activite_ordre(ordre, *, user=None, field='', field_label='',
                       old_value='', new_value='', body=''):
    """ARC8 — journalise un changement (statut d'ordre OU d'étape) dans le
    chatter générique `records.Activity` (NTLOG8 « HistoriqueTransport ») :
    AUCUN nouveau modèle `*Activity` maison — voir `apps/transport/platform.py`
    (`record_targets`)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    kind = Activity.Kind.NOTE if body else Activity.Kind.MODIFICATION
    return log_activity(
        ordre, kind, user=user, field=field, field_label=field_label,
        old_value=str(old_value), new_value=str(new_value), body=body,
        company=ordre.company)


def recalculer_statut_ordre(ordre, *, user=None):
    """NTLOG3 — fait avancer `ordre.statut` selon la progression de ses
    étapes (ordonnées par `sequence`) : dès que TOUTES les étapes sont
    « fait », l'ordre passe « livré » ; sinon, dès qu'au moins une étape est
    faite/en cours, l'ordre passe « en cours » (jamais de retour en arrière
    depuis « livré »/« annulé »). NTLOG8 — chaque avancement écrit une ligne
    de chatter horodatée sur l'ordre."""
    from .models import OrdreTransport

    if ordre.statut in (OrdreTransport.Statut.LIVRE, OrdreTransport.Statut.ANNULE):
        return ordre
    etapes = list(ordre.etapes.order_by('sequence', 'id'))
    if not etapes:
        return ordre

    tous_faits = all(
        e.statut_etape == e.StatutEtape.FAIT for e in etapes)
    au_moins_un_avance = any(
        e.statut_etape in (e.StatutEtape.FAIT, e.StatutEtape.EN_COURS)
        for e in etapes)

    nouveau_statut = ordre.statut
    if tous_faits:
        nouveau_statut = OrdreTransport.Statut.LIVRE
    elif au_moins_un_avance and ordre.statut in (
            OrdreTransport.Statut.BROUILLON, OrdreTransport.Statut.PLANIFIE):
        nouveau_statut = OrdreTransport.Statut.EN_COURS

    if nouveau_statut != ordre.statut:
        ancien = ordre.statut
        ordre.statut = nouveau_statut
        ordre.save(update_fields=['statut'])
        log_activite_ordre(
            ordre, user=user, field='statut', field_label='Statut',
            old_value=ancien, new_value=nouveau_statut)
    return ordre


def apres_changement_statut_etape(etape, ancien_statut, *, user=None):
    """NTLOG3/NTLOG8 — effets de bord après un changement DÉJÀ PERSISTÉ de
    `etape.statut_etape` (PATCH normal ou action dédiée `livrer/`) :
    journalise le changement dans le chatter de l'ordre parent et fait
    avancer automatiquement le statut de l'ordre
    (`recalculer_statut_ordre`). No-op si le statut n'a pas changé."""
    if ancien_statut == etape.statut_etape:
        return etape
    log_activite_ordre(
        etape.ordre, user=user, field='etape_statut',
        field_label=f'Étape {etape.sequence} ({etape.lieu or etape.type_etape})',
        old_value=ancien_statut, new_value=etape.statut_etape)
    recalculer_statut_ordre(etape.ordre, user=user)
    return etape
