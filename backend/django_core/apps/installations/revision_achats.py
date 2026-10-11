"""AMET14 (C-AMET-013, C17) — révision V2 d'un devis et achats déjà émis.

Quand une V2 de devis change la nomenclature figée d'un chantier,
``services._realigner_nomenclature_revision`` réécrit la liste de matériel et
les réservations. Les demandes d'achat DÉJÀ ÉMISES du chantier (soumise /
approuvée / commandée) ne sont jamais modifiées : elles sont MARQUÉES
« à revoir (V2) » (``a_revoir_v2``) avec le diff (``diff_v2``), et le
responsable du chantier est notifié. Module séparé : ``services.py`` est un
fichier-mur.

Diff par produit : ``{"<produit_id>": {"ancien": n, "nouveau": m, "da": q}}``
— ``ancien``/``nouveau`` = quantité de la nomenclature du chantier avant /
après la V2, ``da`` = quantité portée par la DA. Seuls les produits dont la
nomenclature a CHANGÉ et que la DA porte sont listés ; une V2 sans écart
(rejeu identique) ne touche donc rien — pas de doublon de drapeau.
"""
from .models_demande_achat import DemandeAchat


def _diff_pour_da(demande, anciennes, nouvelles):
    diff = {}
    for ligne in demande.lignes.all():
        pid = ligne.produit_id
        if not pid:
            continue
        ancien = anciennes.get(pid, 0)
        nouveau = nouvelles.get(pid, 0)
        if ancien == nouveau:
            continue
        entree = diff.setdefault(
            str(pid), {'ancien': ancien, 'nouveau': nouveau, 'da': 0})
        entree['da'] += float(ligne.quantite or 0)
    return diff


def marquer_achats_a_revoir(chantier, anciennes, nouvelles, user=None):
    """Marque « à revoir (V2) » les DA émises de ``chantier`` dont un produit
    voit sa quantité de nomenclature changer. Aucune quantité n'est modifiée.
    ``anciennes`` / ``nouvelles`` : ``{produit_id: quantite}``. Renvoie le
    nombre de DA marquées."""
    if anciennes == nouvelles:
        return 0
    demandes = (
        DemandeAchat.objects
        .filter(company=chantier.company, chantier=chantier)
        .exclude(statut__in=[DemandeAchat.Statut.BROUILLON,
                             DemandeAchat.Statut.REFUSEE])
        .prefetch_related('lignes'))
    marquees = []
    for demande in demandes:
        diff = _diff_pour_da(demande, anciennes, nouvelles)
        if not diff:
            continue
        # `update()` : ni statut ni quantité touchés, pas de hook de document.
        DemandeAchat.objects.filter(pk=demande.pk).update(
            a_revoir_v2=True, diff_v2=diff)
        marquees.append(demande.reference)
    if marquees:
        _avertir(chantier, marquees, user)
    return len(marquees)


def _avertir(chantier, references, user):
    """Chatter du chantier + notification (canal existant) du responsable."""
    from . import activity
    liste = ', '.join(references)
    activity.log_note(
        chantier, user,
        f'Révision du devis : demande(s) d\'achat à revoir (V2) — {liste}. '
        'Quantités inchangées.')
    responsable = getattr(chantier, 'technicien_responsable', None)
    if responsable is None or not getattr(responsable, 'pk', None):
        return
    try:
        from django.db import transaction
        from apps.notifications.services import notify
        from apps.notifications.types_evenements import EventType
        company = chantier.company
        titre = f'Achats à revoir (V2) — {chantier.reference}'
        corps = (f'La révision du devis change la nomenclature du chantier '
                 f'« {chantier.reference} » : {liste} à revoir.')
        lien = f'/chantiers?id={chantier.pk}'

        def _envoyer():
            try:
                notify(responsable, EventType.DA_DECIDEE, titre,
                       body=corps, link=lien, company=company)
            except Exception:  # pragma: no cover - défensif
                pass

        transaction.on_commit(_envoyer)
    except Exception:  # pragma: no cover - défensif
        pass

def figer_bom_revisee(chantier, devis, figer, quantites):
    """Fige la nomenclature de la V2 sur `chantier` puis marque les DA émises
    « à revoir (V2) » ; rend les quantités de la nouvelle nomenclature.
    `figer(devis)` / `quantites(chantier)` : `services._freeze_bom` /
    `services._bom_quantities` (injectés : pas d'import circulaire)."""
    anciens = quantites(chantier)
    chantier.bom = figer(devis)
    chantier.save(update_fields=['bom'])
    nouveaux = quantites(chantier)
    marquer_achats_a_revoir(chantier, anciens, nouveaux)
    return nouveaux
