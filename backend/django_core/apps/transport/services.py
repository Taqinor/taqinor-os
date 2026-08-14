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


def recalculer_statut_ordre(ordre):
    """NTLOG3 — fait avancer `ordre.statut` selon la progression de ses
    étapes (ordonnées par `sequence`) : dès que TOUTES les étapes sont
    « fait », l'ordre passe « livré » ; sinon, dès qu'au moins une étape est
    faite/en cours, l'ordre passe « en cours » (jamais de retour en arrière
    depuis « livré »/« annulé »)."""
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
        ordre.statut = nouveau_statut
        ordre.save(update_fields=['statut'])
    return ordre


def apres_changement_statut_etape(etape, ancien_statut):
    """NTLOG3 — effets de bord après un changement DÉJÀ PERSISTÉ de
    `etape.statut_etape` (PATCH normal ou action dédiée `livrer/`) : fait
    avancer automatiquement le statut de l'ordre parent
    (`recalculer_statut_ordre`). No-op si le statut n'a pas changé."""
    if ancien_statut == etape.statut_etape:
        return etape
    recalculer_statut_ordre(etape.ordre)
    return etape
