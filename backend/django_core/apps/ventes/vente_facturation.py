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
    imputée à la vente (1 pour une facture de la chaîne ; sous-total HT des
    sources / HT de la facture pour une CONSOLIDÉE). Trié par id."""
    from django.db.models import Q

    from apps.ventes.models import Facture
    if getattr(devis, 'pk', None) is None:
        return []
    ids = _ids_chaine(devis)
    company_id = devis.company_id
    if ids == [devis.pk]:
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
        autres = (Facture.objects.filter(company_id=company_id)
                  .filter(Q(bon_commande__devis_id__in=ids)
                          | Q(sources__devis_id__in=ids))
                  .exclude(pk__in=list(parts))
                  .distinct().prefetch_related(*_PREFETCH_FACTURE))
        if not inclure_annulees:
            autres = autres.exclude(statut=STATUT_ANNULEE)
        autres = list(autres)
        if autres:
            from apps.ventes.models_facturation import FactureSource
            sous_totaux = {}
            for fid, st in FactureSource.objects.filter(
                    facture_id__in=[f.pk for f in autres],
                    devis_id__in=ids).values_list(
                        'facture_id', 'sous_total_ht'):
                sous_totaux[fid] = sous_totaux.get(fid, ZERO) + _d(st)
            for f in autres:
                ratio = Decimal('1')
                if f.devis_id not in ids and f.pk in sous_totaux:
                    ht = _d(f.total_ht)
                    ratio = (sous_totaux[f.pk] / ht) if ht > 0 else ZERO
                parts[f.pk] = (f, ratio)
    return sorted(parts.values(), key=lambda p: p[0].pk)


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


def plan_facturation(devis, option=None, lignes=None) -> dict:
    """LE plan de facturation de la vente de ``devis`` (lecture pure).

    Rend ``{prix_convenu_ttc, prix_convenu_ht, prix_convenu_tva, tranches,
    emis_net, brouillons, prevu, reste_a_facturer, prochaine, hors_tranche}``
    où ``tranches`` = ``[{cle, key, libelle, unite, valeur, cible_cumul_ttc,
    montant_ttc, ht, tva, ventilation_tva, pourcentage, type, statut,
    facture_id, ...}]`` (``statut`` ∈ emise | brouillon | a_faire) et
    ``prochaine`` = la première tranche ``a_faire`` de montant > 0 (ou None).

    Le prix convenu est ``option_totaux(devis, option, lignes)`` ; les
    factures sont celles de TOUTE la vente (``factures_de_la_vente``)."""
    from apps.ventes.utils.echeancier import (
        UNITE_MONTANT, _tranche_type, cles_tranches, tranches_normalisees,
    )
    from apps.ventes.utils.options import option_totaux
    tot = option_totaux(devis, option=option, lignes=lignes)
    T_ttc, T_ht, T_tva = _d(tot['ttc']), _d(tot['ht']), _d(tot['tva'])
    paniers = [{'taux': b['taux'], 'base_ht': b['base_ht'],
                'montant': b['montant']}
               for b in (tot.get('tva_par_taux') or [])]

    ids = set(_ids_chaine(devis)) if getattr(devis, 'pk', None) else set()
    parts = _factures_et_parts(devis)
    emis_net = brouillons = ZERO
    for f, ratio in parts:
        ttc, _ht, _tva = _montants_nets(f, ratio)
        if f.statut in STATUTS_EMIS:
            emis_net += ttc
        elif f.statut == STATUT_BROUILLON:
            brouillons += _d(f.total_ttc) * ratio

    tranches = tranches_normalisees(devis)
    cles = cles_tranches(tranches)
    # Couverture par CLÉ (ATOT5) ; une facture de tranche SANS clé
    # (historique) occupe, dans l'ordre, la première clé libre.
    couvrantes = {c: [] for c in cles}
    hors = []
    sans_cle = []
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
        if libre is None:
            hors.append((f, ratio))
        else:
            couvrantes[libre].append((f, ratio))
    # VNT20 — un BROUILLON hors échéancier (facture de BC, complète,
    # complément de révision) est une alternative concurrente, pas une part
    # du plan : il ne réduit aucune tranche ; seule son ÉMISSION est bornée
    # au prix convenu (``motif_emission_hors_prix``).
    hors = [(f, r) for f, r in hors if f.statut in STATUTS_EMIS]

    # Ce qui est réalisé (net des corrections) par tranche couverte et hors
    # échéancier (complète, BC, consolidée, clé disparue).
    realise = {}
    for c in cles:
        if couvrantes[c]:
            ttc = ht = tva = ZERO
            for f, ratio in couvrantes[c]:
                a, b, d = _montants_nets(f, ratio)
                ttc, ht, tva = ttc + a, ht + b, tva + d
            realise[c] = (ttc, ht, tva)
    hors_ttc = hors_ht = hors_tva = ZERO
    for f, ratio in hors:
        a, b, d = _montants_nets(f, ratio)
        hors_ttc, hors_ht, hors_tva = hors_ttc + a, hors_ht + b, hors_tva + d

    a_faire = [i for i, c in enumerate(cles) if not couvrantes[c]]
    fermante = a_faire[-1] if a_faire else None
    sortie = []
    declare = ZERO
    cumul = (hors_ttc, hors_ht, hors_tva)
    ventilations = []
    for i, (t, cle) in enumerate(zip(tranches, cles)):
        valeur = _d(t['valeur'])
        v = _q(valeur) if t['unite'] == UNITE_MONTANT else \
            _q(T_ttc * valeur / 100)
        if cle in realise and t['unite'] != UNITE_MONTANT:
            # Une tranche en % déjà facturée vaut ce qu'elle a facturé (le
            # montant tapé fait foi, D-VNT-3) ; une tranche en MAD garde son
            # montant contractuel (un écart — facture re-pointée d'une
            # version antérieure — est absorbé par la tranche suivante).
            v = _q(realise[cle][0])
        declare = min(T_ttc, declare + v)
        ligne = {'cle': cle, 'key': t['key'], 'libelle': t['libelle'],
                 'unite': t['unite'], 'valeur': valeur,
                 'cible_cumul_ttc': _q(declare),
                 'type': _tranche_type(t['key'], i == len(tranches) - 1),
                 'statut': 'a_faire', 'facture_id': None}
        for extra in ('jalon', 'delai_reglement_jours', 'payeur'):
            if t.get(extra) is not None:
                ligne[extra] = t[extra]
        if cle in realise:
            ttc, ht, tva = realise[cle]
            fs = [f for f, _r in couvrantes[cle]]
            ligne['statut'] = ('emise' if any(f.statut in STATUTS_EMIS
                                              for f in fs) else 'brouillon')
            ligne['facture_id'] = fs[0].pk
            vent = fs[0].ventilation_tva if len(fs) == 1 else None
        elif i == fermante:
            apres = [realise[c] for c in cles[i + 1:] if c in realise]
            ttc = T_ttc - cumul[0] - sum((r[0] for r in apres), ZERO)
            ht = T_ht - cumul[1] - sum((r[1] for r in apres), ZERO)
            tva = T_tva - cumul[2] - sum((r[2] for r in apres), ZERO)
            if ttc <= 0:
                ttc = ht = tva = ZERO
            vent = None
        else:
            apres = sum((realise[c][0] for c in cles[i + 1:]
                         if c in realise), ZERO)
            ttc = max(ZERO, min(declare - cumul[0],
                                T_ttc - cumul[0] - apres))
            if t['unite'] != UNITE_MONTANT and ttc == v:
                frac = valeur / 100
            else:
                frac = (ttc / T_ttc) if T_ttc > 0 else ZERO
            ht = _q(T_ht * frac) if ttc > 0 else ZERO
            tva = ttc - ht
            vent = None
        ttc, ht, tva = _q(ttc), _q(ht), _q(tva)
        if ligne['statut'] == 'a_faire' and ttc > 0:
            vent = (_ventilation_reste(paniers, ventilations, ttc, ht, tva)
                    if i == fermante else
                    _ventilation(paniers, ttc, ht, tva))
        ventilations.append(vent)
        ligne.update({
            'montant_ttc': ttc, 'ht': ht, 'tva': tva,
            'ventilation_tva': vent,
            'pourcentage': (_q(ttc / T_ttc * 100) if T_ttc > 0 else ZERO),
            'is_last': i == fermante,
        })
        cumul = (cumul[0] + ttc, cumul[1] + ht, cumul[2] + tva)
        sortie.append(ligne)

    prochaine = next((t for t in sortie
                      if t['statut'] == 'a_faire' and t['montant_ttc'] > 0),
                     None)
    prevu = emis_net + brouillons
    reste = T_ttc - prevu
    return {
        'prix_convenu_ttc': _q(T_ttc),
        'prix_convenu_ht': _q(T_ht),
        'prix_convenu_tva': _q(T_tva),
        'tranches': sortie,
        'emis_net': _q(emis_net),
        'brouillons': _q(brouillons),
        'prevu': _q(prevu),
        'reste_a_facturer': _q(reste if reste > 0 else ZERO),
        'prochaine': prochaine,
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
    prorata de leur sous-total HT."""
    devis = facture.devis if facture.devis_id else None
    if devis is None and facture.bon_commande_id:
        devis = getattr(facture.bon_commande, 'devis', None)
    if devis is not None:
        return [(devis, Decimal('1'))]
    if facture.pk is None:
        return []
    ht = _d(facture.total_ht)
    return [(s.devis, (_d(s.sous_total_ht) / ht) if ht > 0 else ZERO)
            for s in facture.sources.select_related('devis')]


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
