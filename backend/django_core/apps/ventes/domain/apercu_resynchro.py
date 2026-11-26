"""ACAL1320 (D-ACAL-73 = corriger_dire, fondateur 26/11/2026) — l'APERÇU d'une resynchronisation.

Avant « Resynchroniser le devis », l'écran dit ce qui CHANGERA au devis lié — et, pour un devis
envoyé, que le devis que le client a reçu sera corrigé sur place (règle QJR5) — puis demande de
confirmer. Rien n'est écrit avant la confirmation.

UN SEUL CALCUL. La resynchronisation RÉELLE (:func:`resynchronisation.sync_devis_from_layout`, le
mode « réconcilier » du pipeline, ses refus de statut, ses désignations, sa trace « corrigé après
envoi ») est jouée DANS un point de sauvegarde (``transaction.atomic``) que ce module annule en
levant :class:`_Annule` : tout ce qu'elle a écrit en base repart, et les rappels ``on_commit``
posés sous ce point de sauvegarde sont abandonnés avec lui (Django). Aucune seconde
implémentation : ce qui est montré est ce que le geste réel ferait.

Ce module ne joue PAS l'enveloppe :func:`resynchronisation.resynchroniser_conception` : ses suites
(échéancier re-basé, affiche copiée dans le magasin d'objets, annonce ``layout_finalise``, études
rafraîchies) ne changent ni les lignes ni les totaux, et l'affiche écrirait HORS de la base.

Les montants sont LUS sur le devis (lignes : ``LigneDevis.total_ht`` ; totaux : ``Devis.total_ht``
/ ``total_ttc``, vue NET de ``domain.argent``) et servis en chaînes décimales au centime.
"""
from decimal import ROUND_HALF_UP, Decimal

__all__ = ['apercu_de_resynchronisation', 'ecarts_de_lignes', 'jeton_de_resynchronisation']

_CENTIME = Decimal('0.01')


class _Annule(Exception):
    """Levée pour ANNULER le point de sauvegarde de l'aperçu (jamais visible hors de ce module)."""


def _texte(valeur):
    """Une quantité ou un montant en chaîne décimale au centime ; ``None`` reste ``None``."""
    if valeur is None:
        return None
    return str(Decimal(str(valeur)).quantize(_CENTIME, rounding=ROUND_HALF_UP))


def _photo_ligne(ligne):
    return {'designation': ligne.designation or '', 'variante': getattr(ligne, 'variante', '') or '',
            'produit': ligne.produit_id, 'quantite': _texte(ligne.quantite),
            'prix_unitaire': _texte(ligne.prix_unitaire), 'remise': _texte(getattr(ligne, 'remise', None)),
            'total_ht': _texte(ligne.total_ht)}


def _photo(devis):
    """``{lignes: {pk: photo}, totaux: {ht, ttc}}`` du devis tel qu'il est EN BASE (relu)."""
    lignes = {ligne.pk: _photo_ligne(ligne) for ligne in devis.lignes.order_by('ordre', 'pk')}
    return {'lignes': lignes, 'totaux': {'ht': _texte(devis.total_ht), 'ttc': _texte(devis.total_ttc)}}


def _traces_de_correction(devis_pk):
    """Le nombre de traces « corrigé après envoi » du devis (``activity.log_devis_correction_apres_envoi``)."""
    from apps.ventes.models import DevisActivity

    return DevisActivity.objects.filter(devis_id=devis_pk, field='correction_apres_envoi').count()


def _court(photo):
    return {cle: photo[cle] for cle in ('designation', 'variante', 'quantite', 'prix_unitaire', 'total_ht')}


def ecarts_de_lignes(avant, apres):
    """``(ajouts, retraits, changements)`` entre deux photos de lignes (``{pk: photo}``). Pure.

    Une ligne de même ``pk`` dont le produit, la désignation, la quantité, le prix ou la remise a
    bougé est un CHANGEMENT (avant → après) ; ``pk`` nouveau = ajout ; ``pk`` disparu = retrait."""
    ajouts = [_court(apres[pk]) for pk in apres if pk not in avant]
    retraits = [_court(avant[pk]) for pk in avant if pk not in apres]
    changements = []
    for pk in avant:
        if pk not in apres or avant[pk] == apres[pk]:
            continue
        a, b = avant[pk], apres[pk]
        changements.append({
            'designation_avant': a['designation'], 'designation_apres': b['designation'],
            'variante': b['variante'], 'quantite_avant': a['quantite'], 'quantite_apres': b['quantite'],
            'prix_unitaire_avant': a['prix_unitaire'], 'prix_unitaire_apres': b['prix_unitaire'],
            'total_ht_avant': a['total_ht'], 'total_ht_apres': b['total_ht']})
    return ajouts, retraits, changements


def jeton_de_resynchronisation(devis, layout, designations=None):
    """Revue du 26/11 — l'empreinte des ENTRÉES d'une resynchronisation (rien n'est stocké) : le document
    du calepinage (aux surfaces chiffrées), l'onduleur et la batterie désignés, et l'état du devis que
    ``reconcilier`` lit (statut, empreinte de pose, marqueur des désignations, scénario, lignes). Même
    calcul à l'aperçu et à la confirmation : différent ⇒ l'aperçu ne décrit plus ce qui serait écrit."""
    import hashlib
    import json

    from apps.ventes.models import Devis

    frais = Devis.objects.get(pk=devis.pk)
    entrees = {
        'layout': layout if isinstance(layout, dict) else {},
        'designations': {cle: (designations or {}).get(cle) for cle in ('onduleur', 'batterie')},
        'devis': {'statut': frais.statut, 'layout_hash': frais.layout_hash or '',
                  'marqueur': (frais.roof_layout or {}).get('_designations') if isinstance(frais.roof_layout, dict)
                  else None,
                  'scenario': (frais.etude_params or {}).get('scenario'),
                  'lignes': sorted(_photo(frais)['lignes'].items())},
    }
    brut = json.dumps(entrees, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode('utf-8')).hexdigest()


def apercu_de_resynchronisation(devis, layout, user=None, *, designations=None):
    """Ce que ``sync_devis_from_layout(devis, layout, user, designations=…)`` CHANGERAIT, sans rien
    écrire (forme : ``apps/calepinage/contract_samples/calepinage_apercu_resync.json``).

    Raises:
        SyncLayoutError: le refus de la resynchronisation réelle (statut, document), TEL QUEL — le
            point de sauvegarde est alors annulé par ``atomic`` lui-même.
    """
    from django.db import transaction

    from apps.ventes.models import Devis

    from .resynchronisation import sync_devis_from_layout

    jeton = jeton_de_resynchronisation(devis, layout, designations)  # AVANT de jouer : les entrées lues
    avant = _photo(Devis.objects.get(pk=devis.pk))
    statut = Devis.objects.filter(pk=devis.pk).values_list('statut', flat=True).first()
    traces_avant = _traces_de_correction(devis.pk)
    jeu = {}
    try:
        with transaction.atomic():
            frais = Devis.objects.get(pk=devis.pk)  # jamais l'instance de l'appelant : elle serait recalée
            jeu['resultat'] = dict(sync_devis_from_layout(frais, layout, user, designations=designations) or {})
            jeu['apres'] = _photo(Devis.objects.get(pk=devis.pk))
            # La trace « corrigé après envoi » que le geste réel POSERAIT (QJR518 : seulement quand un
            # contenu vu par le client change) — lue sous le point de sauvegarde, jamais devinée.
            jeu['trace'] = _traces_de_correction(devis.pk) > traces_avant
            raise _Annule
    except _Annule:
        pass
    resultat, apres = jeu['resultat'], jeu['apres']
    ajouts, retraits, changements = ecarts_de_lignes(avant['lignes'], apres['lignes'])
    return {
        'inchange': bool(resultat.get('inchange')),
        'statut': statut,
        'reference': getattr(devis, 'reference', None) or None,
        'corrige_apres_envoi': bool(jeu['trace']),
        'ajouts': ajouts, 'retraits': retraits, 'changements': changements,
        'totaux': {'avant': avant['totaux'], 'apres': apres['totaux']},
        'avertissements': list(resultat.get('avertissements') or ()),
        'panneaux': resultat.get('panneaux'), 'kwc': resultat.get('kwc'),
        'scenario': resultat.get('scenario'), 'batterie': resultat.get('batterie'),
        'jeton': jeton,
    }
