"""LA lecture de la vente — plan_facturation, etat_vente, factures_de_la_vente,
chaine_vente ; lecture pure ; n'importe aucune couche d'écriture.

VNT9 (Groupe VNT, lot M0 « fondations ») — module créé vide ; VNT16 y pose
``chaine_vente`` (remonte ``superseded_by``, jamais ``version_parent``),
``factures_de_la_vente`` (définie UNE fois : les quatre portes — tranche,
complète, BC, consolidée — sur TOUTE la chaîne de versions) et
``plan_facturation`` (le moteur des tranches/cumuls) ; VNT23 y compose
``etat_vente``.

Propriétaire : facturation (J5, ``docs/ownership.yml``). Aucun second modèle
de lecture de la vente n'existe ailleurs (pas de ``selectors_vente.py`` ni de
``domain/plan_facturation.py``) : tout lecteur hors ventes passe par la façade
``apps.ventes.selectors`` (contrat ``vente-lue-par-la-facade``).

Règles d'argent (décisions D-VNT, arbitrages du 12/10/2026) :
  * un BROUILLON est PRÉVU, jamais FACTURÉ (``emis_net`` ne compte que les
    factures émises / en retard / payées) ;
  * seuls les avoirs de CORRECTION des factures émises sont nettés (ATOT36) :
    ils rendent du facturable ; un geste commercial ou un retour réduit le DÛ
    de sa facture, jamais le facturé ;
  * cibles CUMULATIVES bornées : une tranche en % vaut q(prix convenu × %),
    une tranche en MAD son montant ; la cible cumulée d'une tranche est la
    somme des valeurs déclarées jusqu'à elle, bornée au prix convenu ; une
    tranche à faire vaut sa cible cumulée moins ce qui est déjà prévu avant
    elle ; la DERNIÈRE tranche à faire vaut le RESTE exact (TTC, HT, TVA et
    chaque taux), de sorte que Σ = prix convenu au centime.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal('0')
CENT = Decimal('0.01')
#: Statuts d'une facture ÉMISE (numéro légal) : la seule comptée « facturée ».
STATUTS_EMIS = ('emise', 'payee', 'en_retard')
STATUT_BROUILLON = 'brouillon'
STATUT_ANNULEE = 'annulee'


def _q(valeur) -> Decimal:
    return Decimal(str(valeur)).quantize(CENT, rounding=ROUND_HALF_UP)


def _d(valeur) -> Decimal:
    return Decimal(str(valeur if valeur is not None else 0))


# ── La chaîne de versions ────────────────────────────────────────────────────

def chaine_vente(devis) -> list:
    """Les versions de la vente de ``devis``, de la plus ANCIENNE à la TÊTE.

    Suit ``superseded_by`` (révision) dans les deux sens, même société ;
    jamais ``version_parent`` (partagé avec les variantes et les gammes, qui
    ne remplacent rien). Un devis jamais révisé (ni parent, ni remplaçant)
    est sa propre chaîne SANS requête (chemin des listes)."""
    from apps.ventes.models import Devis
    if getattr(devis, 'pk', None) is None:
        return [devis]
    lot = getattr(devis, '_lot_vente', None)
    if lot is not None:  # VNT68 — chaîne déjà résolue pour toute la page
        return list(lot['chaine'])
    if devis.superseded_by_id is None and devis.version_parent_id is None:
        return [devis]
    company_id = devis.company_id
    tete, vus = devis, {devis.pk}
    while tete.superseded_by_id and tete.superseded_by_id not in vus:
        suivant = (Devis.objects.filter(company_id=company_id,
                                        pk=tete.superseded_by_id).first())
        if suivant is None:
            break
        vus.add(suivant.pk)
        tete = suivant
    from apps.ventes.selectors import devis_predecesseurs_revision_ids
    anciens_ids = devis_predecesseurs_revision_ids(tete)  # proche → ancien
    connus = {devis.pk: devis, tete.pk: tete}
    manquants = [i for i in anciens_ids if i not in connus]
    if manquants:
        connus.update({d.pk: d for d in Devis.objects.filter(
            company_id=company_id, pk__in=manquants)})
    return [connus[i] for i in reversed(anciens_ids) if i in connus] + [tete]


def _ids_chaine(devis) -> list:
    return [d.pk for d in chaine_vente(devis) if d.pk is not None]


# ── Les factures de la vente (LA définition) ─────────────────────────────────

_PREFETCH_FACTURE = ('paiements', 'avoirs', 'avoirs__lignes', 'lignes',
                     'affectations_paiement__paiement')


def _factures_et_parts(devis, *, inclure_annulees=False) -> list:
    """``[(facture, ratio)]`` de la vente : ``ratio`` = part de la facture
    imputée à la vente (1 pour une facture de la chaîne ; part TTC convenue
    des sources pour une CONSOLIDÉE, :func:`_parts_des_sources`). Trié par
    id."""
    from django.db.models import Q

    from apps.ventes.models import Facture
    if getattr(devis, 'pk', None) is None:
        return []
    ids = _ids_chaine(devis)
    company_id = devis.company_id
    lot = getattr(devis, '_lot_vente', None)
    if lot is not None:
        # VNT68 — chemin des listes : factures de la chaîne chargées en lot.
        directes = list(lot['directes'])
    elif ids == [devis.pk]:
        # Chemin des listes (YOPSB13) : la relation PRÉCHARGÉE du devis.
        directes = list(devis.factures.all())
    else:
        directes = list(Facture.objects.filter(
            company_id=company_id, devis_id__in=ids)
            .prefetch_related(*_PREFETCH_FACTURE))
    if not inclure_annulees:
        directes = [f for f in directes if f.statut != STATUT_ANNULEE]
    parts = {f.pk: (f, Decimal('1')) for f in directes}
    accepte = any(getattr(d, 'statut', None) == 'accepte'
                  for d in chaine_vente(devis))
    # BC (``bon_commande__devis``) et CONSOLIDÉE (``FactureSource``, devis
    # NULL) : une seule requête, et seulement pour une vente acceptée sans
    # facture directe ÉMISE — le seul cas où une consolidée émise peut
    # exister (la facture de BC porte aussi ``devis``, AUD112 ; un brouillon
    # ne ferme aucune porte, VNT20).
    if accepte and not any(f.statut in STATUTS_EMIS for f in directes):
        if lot is not None:
            autres = [f for f in lot['autres'] if f.pk not in parts
                      and (inclure_annulees or f.statut != STATUT_ANNULEE)]
            sources = [s for f in autres for s in lot['sources'].get(f.pk, ())]
        else:
            autres = (Facture.objects.filter(company_id=company_id)
                      .filter(Q(bon_commande__devis_id__in=ids)
                              | Q(sources__devis_id__in=ids))
                      .exclude(pk__in=list(parts))
                      .distinct().prefetch_related(*_PREFETCH_FACTURE))
            if not inclure_annulees:
                autres = autres.exclude(statut=STATUT_ANNULEE)
            autres = list(autres)
            sources = None
        if autres:
            if sources is None:
                from apps.ventes.models_facturation import FactureSource
                sources = list(FactureSource.objects.filter(
                    facture_id__in=[f.pk for f in autres])
                    .select_related('devis'))
            sous_parts = {}
            for (fid, did), part in _parts_des_sources(sources).items():
                if did in ids:
                    sous_parts[fid] = sous_parts.get(fid, ZERO) + part
            for f in autres:
                ratio = Decimal('1')
                if f.devis_id not in ids and f.pk in sous_parts:
                    ratio = sous_parts[f.pk]
                parts[f.pk] = (f, ratio)
    return sorted(parts.values(), key=lambda p: p[0].pk)


def _parts_des_sources(sources) -> dict:
    """``{(facture_id, devis_id): part}`` d'une CONSOLIDÉE : TTC convenu du
    devis source (``option_totaux``) / Σ TTC convenus des sources de la
    facture. ``consolider_factures`` compose la consolidée à Σ TTC des devis
    AU CENTIME (ATOT3) : part × TTC facture = TTC du devis, exactement.
    Jamais sous-total HT AVANT remise / HT APRÈS remise (gonflé de la
    remise : 100 800 imputés à une vente de 95 700) ni un prorata HT sur des
    taux de TVA mêlés (17 250 pour 17 000)."""
    from apps.ventes.utils.options import option_totaux
    ttc, totaux = {}, {}
    for s in sources:
        if s.devis_id not in ttc:
            ttc[s.devis_id] = _d(option_totaux(s.devis)['ttc'])
        totaux[s.facture_id] = totaux.get(s.facture_id, ZERO) + ttc[s.devis_id]
    return {(s.facture_id, s.devis_id): (
        ttc[s.devis_id] / totaux[s.facture_id]
        if totaux[s.facture_id] > 0 else ZERO) for s in sources}


def factures_de_la_vente(devis, *, inclure_annulees=False) -> list:
    """LES factures de la vente de ``devis`` (liste triée par id) : toute la
    chaîne de versions (``superseded_by``), les quatre portes (tranche,
    complète, BC, consolidée). Annulées exclues par défaut. Brouillons
    COMPRIS : à l'appelant de distinguer prévu (brouillon) et facturé."""
    return [f for f, _r in _factures_et_parts(
        devis, inclure_annulees=inclure_annulees)]


def _avoirs_correction_ttc(facture):
    """(ttc, ht, tva) des avoirs ÉMIS de CORRECTION de ``facture`` (ATOT36)."""
    ttc = ht = tva = ZERO
    for a in facture.avoirs.all():
        if a.statut == 'emise' and a.type == 'correction':
            ttc += _d(a.total_ttc)
            ht += _d(a.total_ht)
            tva += _d(a.total_tva)
    return ttc, ht, tva


def _montants_nets(facture, ratio):
    """(ttc, ht, tva) imputés à la vente, nets des avoirs de CORRECTION."""
    c_ttc, c_ht, c_tva = _avoirs_correction_ttc(facture)
    return ((_d(facture.total_ttc) - c_ttc) * ratio,
            (_d(facture.total_ht) - c_ht) * ratio,
            (_d(facture.total_tva) - c_tva) * ratio)


# ── Le plan de facturation ───────────────────────────────────────────────────

def _est_tranche(facture, ids):
    """Une facture de TRANCHE : sur la chaîne, sans BC, pas la complète."""
    return (facture.devis_id in ids and facture.bon_commande_id is None
            and facture.type_facture != 'complete')


def _ventilation(paniers, ttc, ht, tva):
    if len(paniers) < 2:
        return None
    from apps.facturation.totaux import ventilation_document_fige
    return ventilation_document_fige(paniers, ttc=ttc, ht=ht, tva=tva)


def _ventilation_reste(paniers, autres, ttc, ht, tva):
    """La DERNIÈRE tranche prend le reste de CHAQUE taux quand toutes les
    autres sont ventilées et que les restes se referment ; sinon prorata."""
    if len(paniers) < 2:
        return None
    if autres and all(v for v in autres):
        taux = [_d(b['taux']) for b in paniers]
        bases = {t: _d(b['base_ht']) for t, b in zip(taux, paniers)}
        tvas = {t: _d(b['montant']) for t, b in zip(taux, paniers)}
        for vent in autres:
            for b in vent:
                t = _d(b['taux'])
                if t in bases:
                    bases[t] -= _d(b['base_ht'])
                    tvas[t] -= _d(b['montant'])
        if (sum(bases.values()) == ht and sum(tvas.values()) == tva):
            return [{'taux': str(t), 'base_ht': str(_q(bases[t])),
                     'montant': str(_q(tvas[t]))} for t in taux]
    return _ventilation(paniers, ttc, ht, tva)


def _somme(couples):
    """(ttc, ht, tva) nets (avoirs de correction déduits) de ``couples``
    ``[(facture, part)]``."""
    ttc = ht = tva = ZERO
    for f, ratio in couples:
        a, b, d = _montants_nets(f, ratio)
        ttc, ht, tva = ttc + a, ht + b, tva + d
    return ttc, ht, tva


def _couverture(parts, cles, ids):
    """``({clé: [(facture, part)]}, hors)`` — couverture par CLÉ (ATOT5) ;
    une facture de tranche SANS clé (historique) occupe, dans l'ordre, la
    première clé libre. ``hors`` = factures ÉMISES hors échéancier (complète,
    BC, consolidée, clé disparue). VNT20 — un BROUILLON hors échéancier (BC,
    complète, complément de révision) est une alternative concurrente, pas
    une part du plan : il ne réduit aucune tranche ; seule son ÉMISSION est
    bornée au prix convenu (:func:`motif_emission_hors_prix`)."""
    couvrantes = {c: [] for c in cles}
    hors, sans_cle = [], []
    for f, ratio in parts:
        if f.statut not in STATUTS_EMIS and f.statut != STATUT_BROUILLON:
            continue
        if _est_tranche(f, ids) and f.cle_tranche in couvrantes:
            couvrantes[f.cle_tranche].append((f, ratio))
        elif _est_tranche(f, ids) and not f.cle_tranche:
            sans_cle.append((f, ratio))
        else:
            hors.append((f, ratio))
    for f, ratio in sans_cle:
        libre = next((c for c in cles if not couvrantes[c]), None)
        (hors if libre is None else couvrantes[libre]).append((f, ratio))
    return couvrantes, [(f, r) for f, r in hors if f.statut in STATUTS_EMIS]


def _montants_a_faire(t, valeur, v, ctx, i, etat):
    """(ttc, ht, tva) d'une tranche À FAIRE. La FERMANTE (dernière à faire)
    vaut le RESTE exact (TTC, HT, TVA) ; une autre vaut sa cible cumulée
    moins ce qui est prévu avant elle, bornée au prix convenu (une tranche
    inchangée garde la fraction déclarée : HT d'hier au centime)."""
    from apps.ventes.utils.echeancier import UNITE_MONTANT
    t_ttc, t_ht, t_tva = ctx['T']
    cumul = etat['cumul']
    apres = [ctx['realise'][c] for c in ctx['cles'][i + 1:]
             if c in ctx['realise']]
    reste_ttc = t_ttc - cumul[0] - sum((r[0] for r in apres), ZERO)
    if i == ctx['fermante']:
        if reste_ttc <= 0:
            return ZERO, ZERO, ZERO
        return (reste_ttc,
                t_ht - cumul[1] - sum((r[1] for r in apres), ZERO),
                t_tva - cumul[2] - sum((r[2] for r in apres), ZERO))
    ttc = max(ZERO, min(etat['declare'] - cumul[0], reste_ttc))
    if t['unite'] != UNITE_MONTANT and ttc == v:
        frac = valeur / 100
    else:
        frac = (ttc / t_ttc) if t_ttc > 0 else ZERO
    ht = _q(t_ht * frac) if ttc > 0 else ZERO
    return ttc, ht, ttc - ht


def _tranche_du_plan(i, t, cle, ctx, etat):
    """Une ligne du plan ; avance ``etat`` (cible déclarée cumulée, cumul
    prévu TTC/HT/TVA, ventilations déjà posées)."""
    from apps.ventes.utils.echeancier import UNITE_MONTANT, _tranche_type
    t_ttc = ctx['T'][0]
    realise = ctx['realise']
    valeur = _d(t['valeur'])
    v = _q(valeur) if t['unite'] == UNITE_MONTANT else \
        _q(t_ttc * valeur / 100)
    if cle in realise and t['unite'] != UNITE_MONTANT:
        # Une tranche en % déjà facturée vaut ce qu'elle a facturé (le
        # montant tapé fait foi, D-VNT-3) ; une tranche en MAD garde son
        # montant contractuel (un écart — facture re-pointée d'une version
        # antérieure — est absorbé par la tranche suivante).
        v = _q(realise[cle][0])
    etat['declare'] = min(t_ttc, etat['declare'] + v)
    ligne = {'cle': cle, 'key': t['key'], 'libelle': t['libelle'],
             'unite': t['unite'], 'valeur': valeur,
             'cible_cumul_ttc': _q(etat['declare']),
             'type': _tranche_type(t['key'], i == len(ctx['cles']) - 1),
             'statut': 'a_faire', 'facture_id': None}
    for extra in ('jalon', 'delai_reglement_jours', 'payeur'):
        if t.get(extra) is not None:
            ligne[extra] = t[extra]
    vent = None
    if cle in realise:
        ttc, ht, tva = realise[cle]
        fs = [f for f, _r in ctx['couvrantes'][cle]]
        ligne['statut'] = ('emise' if any(f.statut in STATUTS_EMIS
                                          for f in fs) else 'brouillon')
        ligne['facture_id'] = fs[0].pk
        vent = fs[0].ventilation_tva if len(fs) == 1 else None
    else:
        ttc, ht, tva = _montants_a_faire(t, valeur, v, ctx, i, etat)
    ttc, ht, tva = _q(ttc), _q(ht), _q(tva)
    if ligne['statut'] == 'a_faire' and ttc > 0:
        vent = (_ventilation_reste(ctx['paniers'], etat['ventilations'],
                                   ttc, ht, tva)
                if i == ctx['fermante'] else
                _ventilation(ctx['paniers'], ttc, ht, tva))
    etat['ventilations'].append(vent)
    ligne.update({
        'montant_ttc': ttc, 'ht': ht, 'tva': tva, 'ventilation_tva': vent,
        'pourcentage': (_q(ttc / t_ttc * 100) if t_ttc > 0 else ZERO),
        'is_last': i == ctx['fermante'],
    })
    c = etat['cumul']
    etat['cumul'] = (c[0] + ttc, c[1] + ht, c[2] + tva)
    return ligne


def plan_facturation(devis, option=None, lignes=None) -> dict:
    """LE plan de facturation de la vente de ``devis`` (lecture pure).

    Rend ``{prix_convenu_ttc, prix_convenu_ht, prix_convenu_tva, tranches,
    emis_net, brouillons, prevu, reste_a_facturer, prochaine, hors_tranche,
    factures_parts}`` où ``tranches`` = ``[{cle, key, libelle, unite, valeur,
    cible_cumul_ttc, montant_ttc, ht, tva, ventilation_tva, pourcentage,
    type, statut, facture_id, is_last, ...}]`` (``statut`` ∈ emise |
    brouillon | a_faire) et ``prochaine`` = la première tranche ``a_faire``
    de montant > 0 (ou None).

    Le prix convenu est ``option_totaux(devis, option, lignes)`` ; les
    factures sont celles de TOUTE la vente (``factures_de_la_vente``)."""
    from apps.ventes.utils.echeancier import (
        cles_tranches, tranches_normalisees)
    from apps.ventes.utils.options import option_totaux
    tot = option_totaux(devis, option=option, lignes=lignes)
    prix = (_d(tot['ttc']), _d(tot['ht']), _d(tot['tva']))
    ids = set(_ids_chaine(devis)) if getattr(devis, 'pk', None) else set()
    parts = _factures_et_parts(devis)
    emis_net = sum((_montants_nets(f, r)[0] for f, r in parts
                    if f.statut in STATUTS_EMIS), ZERO)
    brouillons = sum((_d(f.total_ttc) * r for f, r in parts
                      if f.statut == STATUT_BROUILLON), ZERO)
    tranches = tranches_normalisees(devis)
    cles = cles_tranches(tranches)
    couvrantes, hors = _couverture(parts, cles, ids)
    a_faire = [i for i, c in enumerate(cles) if not couvrantes[c]]
    ctx = {'T': prix, 'cles': cles, 'couvrantes': couvrantes,
           'realise': {c: _somme(couvrantes[c]) for c in cles
                       if couvrantes[c]},
           'fermante': a_faire[-1] if a_faire else None,
           'paniers': [{'taux': b['taux'], 'base_ht': b['base_ht'],
                        'montant': b['montant']}
                       for b in (tot.get('tva_par_taux') or [])]}
    etat = {'declare': ZERO, 'cumul': _somme(hors), 'ventilations': []}
    sortie = [_tranche_du_plan(i, t, cle, ctx, etat)
              for i, (t, cle) in enumerate(zip(tranches, cles))]
    reste = prix[0] - emis_net - brouillons
    return {
        'prix_convenu_ttc': _q(prix[0]),
        'prix_convenu_ht': _q(prix[1]),
        'prix_convenu_tva': _q(prix[2]),
        'tranches': sortie,
        'emis_net': _q(emis_net),
        'brouillons': _q(brouillons),
        'prevu': _q(emis_net + brouillons),
        'reste_a_facturer': _q(reste if reste > 0 else ZERO),
        'prochaine': next((t for t in sortie if t['statut'] == 'a_faire'
                           and t['montant_ttc'] > 0), None),
        'hors_tranche': [f.pk for f, _r in hors],
        # (facture, part) vivantes de la vente — lecteurs internes (solde,
        # etat_vente) ; jamais sérialisé tel quel.
        'factures_parts': parts,
    }


# ── « Une vente ne se facture qu'une fois » — à l'ÉMISSION (VNT20) ──────────

def factures_bloquantes(devis, porte) -> list:
    """Les factures ÉMISES de la vente qui ferment ``porte`` (``tranche`` :
    toute facture émise hors échéancier — complète, BC, consolidée ; autre
    porte : toute facture émise). Un BROUILLON ne ferme aucune porte : deux
    brouillons concurrents coexistent, le second ÉMIS est refusé
    (:func:`motif_emission_hors_prix`)."""
    if devis is None or getattr(devis, 'pk', None) is None:
        return []
    ids = set(_ids_chaine(devis))
    emises = [f for f, _r in _factures_et_parts(devis)
              if f.statut in STATUTS_EMIS]
    if porte == 'tranche':
        return [f for f in emises if not _est_tranche(f, ids)]
    return emises


def _ventes_de_la_facture(facture):
    """``[(devis, part)]`` que ``facture`` facture : son devis (ou celui de
    son BC) pour la part entière, sinon les sources d'une CONSOLIDÉE au
    prorata de leur TTC convenu (:func:`_parts_des_sources`)."""
    devis = facture.devis if facture.devis_id else None
    if devis is None and facture.bon_commande_id:
        devis = getattr(facture.bon_commande, 'devis', None)
    if devis is not None:
        return [(devis, Decimal('1'))]
    if facture.pk is None:
        return []
    sources = list(facture.sources.select_related('devis'))
    parts = _parts_des_sources(sources)
    return [(s.devis, parts[(s.facture_id, s.devis_id)]) for s in sources]


def motif_emission_hors_prix(facture):
    """None si l'émission de ``facture`` tient dans le prix convenu de sa
    (ses) vente(s) ; sinon le motif FR du refus (lecture pure — l'appelant,
    ``emettre_facture``, lève ``EmissionRefusee``).

    Refuse, pour une vente (devis ACCEPTÉ) : une facture d'une version
    REMPLACÉE ou archivée (``is_active`` faux) ; Σ émis net de la vente (avoirs de correction
    déduits, cette facture exclue) + la part de cette facture > prix
    convenu (+ un centime d'arrondi par facture)."""
    from apps.ventes.utils.options import option_totaux
    for devis, ratio in _ventes_de_la_facture(facture):
        # Seule une VENTE (devis accepté, même société) est bornée.
        if (devis is None or devis.company_id != facture.company_id
                or devis.statut != 'accepte'):
            continue
        if not devis.is_active:
            tete = chaine_vente(devis)[-1]
            if tete.pk != devis.pk:
                return (f'Le devis {devis.reference} a été remplacé par '
                        f'{tete.reference} : facturez la version en cours.')
            return (f'Le devis {devis.reference} est archivé : il ne se '
                    'facture plus.')
        emises = [(f, r) for f, r in _factures_et_parts(devis)
                  if f.statut in STATUTS_EMIS and f.pk != facture.pk]
        deja = sum((_montants_nets(f, r)[0] for f, r in emises), ZERO)
        part = _d(facture.total_ttc) * ratio
        prix = _d(option_totaux(devis)['ttc'])
        if deja + part > prix + CENT * (len(emises) + 1):
            refs = ', '.join(f.reference for f, _r in emises) or '—'
            return (f'Émission refusée : la vente {devis.reference} '
                    f'({_q(prix)} MAD TTC) est déjà facturée à '
                    f'{_q(deja)} MAD par {refs} ; cette facture '
                    f'({_q(part)} MAD) la dépasserait. Annulez ce brouillon '
                    'ou corrigez par un avoir.')
    return None


# ── L'état de la vente (VNT23, contrat ``vente_etat.json``) ──────────────────

#: Statuts d'un devis dont la révision est EN COURS (ni acceptée, ni close).
STATUTS_REVISION_OUVERTE = ('brouillon', 'envoye')
_TEXTE = '{:.2f}'


def _txt(valeur) -> str:
    return _TEXTE.format(_q(valeur))


def peut_gerer_la_vente(user) -> bool:
    """Le palier des gestes d'argent de la vente (annuler, supprimer un
    brouillon, modifier un montant, échéancier d'un accepté, prix négocié) :
    ``IsAdminOrResponsableTier`` ET ``IsResponsableOrAdmin`` sur le module
    ventes (écriture) — arbitrage 5 du Groupe VNT : jamais un Commercial,
    ni un Technicien responsable, ni un Admin RH. Même prédicat que les
    vues : l'écran n'en redérive aucun."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    from types import SimpleNamespace

    from authentication.permissions import (
        IsAdminOrResponsableTier, IsResponsableOrAdmin)
    requete = SimpleNamespace(user=user, method='POST')
    vue = SimpleNamespace(permission_module='ventes')
    return (IsAdminOrResponsableTier().has_permission(requete, vue)
            and IsResponsableOrAdmin().has_permission(requete, vue))


def _nature(facture, ids) -> str:
    if facture.bon_commande_id:
        return 'bc'
    if facture.devis_id not in ids:
        return 'consolidee'
    return facture.type_facture


def _facture_etat(facture, ids, palier, actionnable) -> dict:
    from core.numbering import est_reference_provisoire
    statut = facture.statut
    emise = statut in STATUTS_EMIS
    brouillon = statut == STATUT_BROUILLON
    paiements = [{
        'id': p.pk, 'montant': _txt(p.montant),
        'date_paiement': (p.date_paiement.isoformat()
                          if p.date_paiement else None),
        'mode_paiement': p.mode, 'statut': p.statut,
        'peut': {'recu': p.statut not in ('rejete', 'annule_saisie')},
    } for p in sorted(facture.paiements.all(), key=lambda p: p.pk)]
    return {
        'id': facture.pk,
        'reference': facture.reference,
        'nature': str(_nature(facture, ids)),
        'statut': statut,
        'total_ttc': _txt(facture.total_ttc),
        'montant_paye': _txt(facture.montant_paye),
        'date_emission': (facture.date_emission.isoformat()
                          if emise and facture.date_emission else None),
        'paiements': paiements,
        'peut': {
            'emettre': brouillon and actionnable,
            'pdf': True,
            'envoyer': emise,
            'encaisser': statut in ('emise', 'en_retard')
            and _d(facture.montant_du) > 0,
            'annuler': emise and palier,
            'supprimer': (brouillon and palier
                          and est_reference_provisoire(facture.reference)),
            'modifier_montant': brouillon and palier,
        },
    }


def _tete_de_vente(chaine):
    """(tête, révision en cours) : la tête = le dernier ACCEPTÉ de la chaîne
    (sinon la version la plus récente) ; la révision en cours = une version
    POSTÉRIEURE à la tête encore brouillon ou envoyée."""
    acceptes = [d for d in chaine if d.statut == 'accepte']
    tete = acceptes[-1] if acceptes else chaine[-1]
    apres = chaine[chaine.index(tete) + 1:]
    ouvertes = [d for d in apres if d.statut in STATUTS_REVISION_OUVERTE]
    return tete, (ouvertes[-1] if ouvertes else None)


def _montants_vente(plan) -> dict:
    """Les montants (TEXTE) du bloc ``vente`` : émis net des corrections,
    brouillons à part, payé (rejetés / annulés exclus), reste à facturer et
    reste à payer (= dû des émises + reste à facturer = ``solde.restant``)."""
    parts = plan['factures_parts']
    emises = [(f, r) for f, r in parts if f.statut in STATUTS_EMIS]
    paye = sum((_d(f.montant_paye) * r for f, r in parts), ZERO)
    du = sum((_d(f.montant_du) * r for f, r in emises), ZERO)
    a_facturer = plan['prix_convenu_ttc'] - plan['emis_net']
    premiere = plan['tranches'][0] if plan['tranches'] else None
    return {
        'prix_convenu_ttc': _txt(plan['prix_convenu_ttc']),
        'emis_ttc': _txt(plan['emis_net']),
        'brouillons_ttc': _txt(plan['brouillons']),
        'paye_ttc': _txt(paye),
        'reste_a_facturer_ttc': _txt(plan['reste_a_facturer']),
        'reste_a_payer_ttc': _txt(
            du + (a_facturer if a_facturer > 0 else ZERO)),
        'acompte_propose': _txt(premiere['montant_ttc']
                                if premiere and plan['reste_a_facturer'] > 0
                                else ZERO),
    }


def _raison_bloquee(devis, tete, revision, brouillon_tranche) -> str:
    if revision is not None and revision.pk == devis.pk:
        return f'Révision de {tete.reference} : acceptez-la pour facturer.'
    if tete.pk != devis.pk:
        return ('Cette version a été remplacée : travaillez sur la version '
                'en cours.')
    if revision is not None:
        return (f'Révision {revision.reference} en cours — acceptez-la ou '
                'abandonnez-la.')
    if brouillon_tranche is None:
        return ''
    if brouillon_tranche['type'] == 'acompte':
        return "L'acompte est en brouillon : émettez-le."
    return (f"La tranche « {brouillon_tranche['libelle']} » est en "
            'brouillon : émettez-la.')


def _gestes_vente(plan, actionnable, palier) -> tuple:
    """(prochaine_action, prochaines tranches à faire, ``peut``)."""
    tranches = plan['tranches']
    a_venir = [t for t in tranches
               if t['statut'] == 'a_faire' and t['montant_ttc'] > 0]
    brouillon = next((t for t in tranches if t['statut'] == 'brouillon'),
                     None)
    if not actionnable:
        prochaine = 'aucune'
    elif brouillon is not None:
        prochaine = str(brouillon['type'])
    else:
        prochaine = str(a_venir[0]['type']) if a_venir else 'aucune'
    libre = actionnable and brouillon is None
    premiere = tranches[0] if tranches else None
    emises = any(f.statut in STATUTS_EMIS for f, _r in plan['factures_parts'])
    peut = {
        'facturer_acompte': bool(libre and premiere
                                 and premiere['statut'] == 'a_faire'
                                 and premiere['montant_ttc'] > 0),
        'facturer_solde': bool(libre and emises and a_venir),
        'facturer_complete': bool(libre and not plan['factures_parts']),
        'prix_negocie': actionnable and palier,
        'modifier_echeancier': (actionnable and palier
                                and plan['reste_a_facturer'] > 0),
    }
    return prochaine, a_venir, peut


def etat_vente(devis, user=None) -> dict:
    """L'état de la vente de ``devis`` (bloc ``vente`` du contrat
    ``vente_etat.json``), composé au-dessus de :func:`plan_facturation` et
    :func:`factures_de_la_vente` (importés, jamais redéfinis).

    Montants en TEXTE (:func:`_montants_vente`) ; ``factures`` = TOUTE la
    chaîne (+ BC + part de consolidée) ; ``peut`` = gestes autorisés pour
    ``user`` (palier :func:`peut_gerer_la_vente`) ; une version remplacée ou
    une révision en cours ferme tous les gestes de facturation."""
    return _etat_vente(devis, peut_gerer_la_vente(user))


def _etat_vente(devis, palier) -> dict:
    """:func:`etat_vente` pour un palier déjà résolu (une fois par liste)."""
    chaine = chaine_vente(devis)
    tete, revision = _tete_de_vente(chaine)
    plan = plan_facturation(tete)
    ids = {d.pk for d in chaine}
    est_tete = tete.pk == devis.pk
    actionnable = est_tete and revision is None and tete.statut == 'accepte'
    prochaine, a_venir, peut = _gestes_vente(plan, actionnable, palier)
    brouillon = next((t for t in plan['tranches']
                      if t['statut'] == 'brouillon'), None)
    return {
        **_montants_vente(plan),
        'factures': [_facture_etat(f, ids, palier, actionnable)
                     for f, _r in plan['factures_parts']],
        'versions': [{'id': d.pk, 'reference': d.reference,
                      'version': d.version, 'statut': d.statut,
                      'is_active': d.is_active}
                     for d in chaine[:chaine.index(tete) + 1]],
        'est_tete': est_tete,
        'tete_id': tete.pk,
        'revision_en_cours': ({'id': revision.pk,
                               'reference': revision.reference}
                              if revision is not None else None),
        'prochaine_action': prochaine,
        'raison_bloquee': _raison_bloquee(devis, tete, revision, brouillon),
        'prochaines_echeances': ([{'cle': t['cle'], 'libelle': t['libelle'],
                                   'montant_ttc': _txt(t['montant_ttc'])}
                                  for t in a_venir] if est_tete else []),
        'peut': peut,
    }


def etat_vente_map(rows, user=None, soldes=None) -> dict:
    """``{devis.pk: etat_vente(devis, user)}`` pour une liste de devis (la
    ligne devis du lead, la fiche, une page de la liste des devis) : le
    palier est résolu UNE fois et les chaînes/factures de toute la liste sont
    chargées en lot (:func:`ventes_prechargees`) — le nombre de requêtes ne
    grandit pas avec le nombre de devis (VNT68).

    ``soldes`` (dict fourni par l'appelant, VNT68/VNT70) reçoit, sous le MÊME
    lot, le bloc ``solde`` de chaque devis (``solde_devis``, valeurs en
    texte — contrat ``devis_solde.json``) : un seul appel pour les deux."""
    from apps.ventes.utils.echeancier import solde_devis
    rows = list(rows)
    palier = peut_gerer_la_vente(user)
    with ventes_prechargees(rows):
        if soldes is not None:
            soldes.update({d.pk: {k: str(v) for k, v in solde_devis(d).items()}
                           for d in rows})
        return {d.pk: _etat_vente(d, palier) for d in rows}


# ── Le lot d'une liste de devis (VNT68) ──────────────────────────────────────

#: Factures chargées en lot : ce que ``_facture_etat`` et ``montant_du`` lisent.
_PREFETCH_LOT = _PREFETCH_FACTURE + (
    'notes_debit', 'notes_debit__lignes', 'retenues_subies',
    'retenues_subies__paiement')


def _tete_lot(devis, connus):
    """La tête de la chaîne de ``devis`` (mêmes règles que :func:`chaine_vente`)."""
    tete, vus = devis, {devis.pk}
    while tete.superseded_by_id and tete.superseded_by_id not in vus:
        suivant = connus.get(tete.superseded_by_id)
        if suivant is None or suivant.company_id != devis.company_id:
            break
        vus.add(suivant.pk)
        tete = suivant
    return tete


def _versions_du_lot(complexes, connus):
    """Charge les versions des chaînes de ``complexes`` — têtes (en suivant
    ``superseded_by``) puis prédécesseurs — UNE requête par NIVEAU de chaîne
    pour toute la liste ; rend les niveaux de prédécesseurs dans l'ordre du
    sélecteur ``devis_predecesseurs_revision_ids``."""
    from apps.ventes.models import Devis
    qs = (Devis.objects
          .filter(company_id__in={d.company_id for d in complexes})
          .select_related('company')
          .prefetch_related('lignes', 'lignes__produit'))
    manquants = {d.superseded_by_id for d in complexes
                 if d.superseded_by_id} - set(connus)
    while manquants:
        nouveaux = list(qs.filter(pk__in=manquants))
        connus.update({d.pk: d for d in nouveaux})
        manquants = {d.superseded_by_id for d in nouveaux
                     if d.superseded_by_id} - set(connus)
    niveaux = []
    frontiere = {_tete_lot(d, connus).pk for d in complexes}
    vus = set(frontiere)
    while frontiere:
        niveau = list(qs.filter(superseded_by_id__in=frontiere))
        niveaux.append(niveau)
        for d in niveau:
            connus.setdefault(d.pk, d)
        frontiere = {d.pk for d in niveau} - vus
        vus.update(frontiere)
    return niveaux


def _chaine_lot(devis, connus, niveaux):
    """:func:`chaine_vente` de ``devis`` lue sur les versions du lot."""
    tete = _tete_lot(devis, connus)
    anciens, vus, front = [], {tete.pk}, {tete.pk}
    for niveau in niveaux:
        suivants = [d.pk for d in niveau if d.superseded_by_id in front
                    and d.pk not in vus and d.company_id == tete.company_id]
        if not suivants:
            break
        vus.update(suivants)
        anciens.extend(suivants)
        front = set(suivants)
    return [connus[i] for i in reversed(anciens)] + [tete]


def _factures_du_lot(chaines):
    """``{clé de chaîne: factures directes}`` : la relation PRÉCHARGÉE d'un
    devis seul, sinon UNE requête pour toutes les autres chaînes."""
    from apps.ventes.models import Facture
    sortie, a_charger = {}, {}
    for cle, chaine in chaines.items():
        seul = chaine[0] if len(chaine) == 1 else None
        if 'factures' in (getattr(seul, '_prefetched_objects_cache', None) or {}):
            sortie[cle] = list(seul.factures.all())
        else:
            a_charger[cle] = chaine
    if a_charger:
        membres = {d.pk for chaine in a_charger.values() for d in chaine}
        factures = list(Facture.objects.filter(
            company_id__in={c[-1].company_id for c in a_charger.values()},
            devis_id__in=membres).prefetch_related(*_PREFETCH_LOT))
        for cle, chaine in a_charger.items():
            sortie[cle] = [f for f in factures if f.devis_id in cle
                           and f.company_id == chaine[-1].company_id]
    return sortie


def _autres_du_lot(chaines, directes):
    """Factures de BC et CONSOLIDÉES des ventes acceptées sans facture directe
    émise (la condition de :func:`_factures_et_parts`) : UNE requête pour les
    factures, UNE pour leurs sources ; ``({clé: factures}, {facture_id:
    [sources]})``."""
    from django.db.models import Q

    from apps.ventes.models import Facture
    from apps.ventes.models_facturation import FactureSource
    besoins = {cle: chaine for cle, chaine in chaines.items()
               if any(d.statut == 'accepte' for d in chaine)
               and not any(f.statut in STATUTS_EMIS for f in directes[cle])}
    if not besoins:
        return {}, {}
    ids = {i for cle in besoins for i in cle}
    factures = list(Facture.objects
                    .filter(company_id__in={c[-1].company_id
                                            for c in besoins.values()})
                    .filter(Q(bon_commande__devis_id__in=ids)
                            | Q(sources__devis_id__in=ids))
                    .distinct().select_related('bon_commande')
                    .prefetch_related(*_PREFETCH_LOT))
    sources = {}
    if factures:
        for s in (FactureSource.objects
                  .filter(facture_id__in=[f.pk for f in factures])
                  .select_related('devis')
                  .prefetch_related('devis__lignes', 'devis__lignes__produit')):
            sources.setdefault(s.facture_id, []).append(s)
    autres = {}
    for cle, chaine in besoins.items():
        autres[cle] = [f for f in factures
                       if f.company_id == chaine[-1].company_id
                       and ((f.bon_commande_id
                             and f.bon_commande.devis_id in cle)
                            or any(s.devis_id in cle
                                   for s in sources.get(f.pk, ())))]
    return autres, sources


def _precharger(rows) -> list:
    """Pose ``_lot_vente`` (chaîne, factures directes, BC et consolidées) sur
    chaque devis de ``rows`` et sur les versions de leurs chaînes ; rend les
    devis posés (un devis déjà porteur d'un lot est laissé tel quel)."""
    rows = [d for d in rows if getattr(d, 'pk', None) is not None
            and getattr(d, '_lot_vente', None) is None]
    if not rows:
        return []
    # Ce que le prix convenu et l'échéancier lisent par devis (société,
    # lignes et produits) : déjà préchargé par la liste des devis (aucune
    # requête alors) ; chargé ici en lot pour une autre liste (lead, VNT70).
    from django.db.models import prefetch_related_objects
    prefetch_related_objects(rows, 'company', 'lignes', 'lignes__produit')
    connus = {d.pk: d for d in rows}
    complexes = [d for d in rows if d.superseded_by_id is not None
                 or d.version_parent_id is not None]
    niveaux = _versions_du_lot(complexes, connus) if complexes else []
    chaines, cle_de = {}, {}
    for d in rows:
        chaine = _chaine_lot(d, connus, niveaux) if d in complexes else [d]
        cle_de[id(d)] = tuple(v.pk for v in chaine)
        chaines.setdefault(cle_de[id(d)], chaine)
    directes = _factures_du_lot(chaines)
    autres, sources = _autres_du_lot(chaines, directes)
    lots = {cle: {'chaine': chaine, 'directes': directes[cle],
                  'autres': autres.get(cle, []), 'sources': sources}
            for cle, chaine in chaines.items()}
    poses = []
    porteurs = [(v, cle) for cle, chaine in chaines.items() for v in chaine]
    porteurs += [(d, cle_de[id(d)]) for d in rows]
    for d, cle in porteurs:
        if getattr(d, '_lot_vente', None) is None:
            d._lot_vente = lots[cle]
            poses.append(d)
    return poses


@contextmanager
def ventes_prechargees(rows):
    """Le temps du bloc, :func:`plan_facturation`, :func:`etat_vente` et
    ``solde_devis`` lisent les devis de ``rows`` (une liste) sans requête par
    devis ; le lot est retiré à la sortie (aucune écriture ne le voit)."""
    poses = _precharger(rows)
    try:
        yield
    finally:
        for d in poses:
            d.__dict__.pop('_lot_vente', None)
