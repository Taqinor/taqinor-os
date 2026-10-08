"""QA-COHERENCE — invariants des DOCUMENTS (devis, bon de commande, facture).

Chaque règle est justifiée par le code qu'elle surveille (cité dans sa
docstring). Aucune ne lit ``prix_achat`` ni aucune marge, aucune n'écrit.

Invariants volontairement ABSENTS (déjà garantis par la base, une règle ne
pourrait jamais tirer) : unicité des références par société
(``unique_together (company, reference)`` sur Devis/BonCommande/Facture),
quantités/prix/remises négatifs sur les lignes (``CheckConstraint`` AUD188 sur
LigneDevis/LigneFacture).
"""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .registre import (GRAVITE_AVERTISSEMENT, GRAVITE_CRITIQUE, PORTEE_DEVIS,
                       PORTEE_FACTURE, TOLERANCES, regle)

STATUT_ACCEPTE = 'accepte'
STATUT_BROUILLON = 'brouillon'
FACTURE_ANNULEE = 'annulee'
BC_ANNULE = 'annule'


def _f(v):
    return float(v or 0)


def _base_panier(panier):
    for k in ('base', 'base_ht', 'ht_net'):
        if panier.get(k) is not None:
            return _f(panier.get(k))
    return 0.0


def ecarts_chaine(totaux, *, remise_pct=None, tol=None):
    """Recalcule, étage par étage, la chaîne ``ht_brut → remise → arrondi →
    ht_net → TVA (par taux) → TTC`` d'un dict de totaux et rend la liste des étages
    dont la valeur portée s'écarte du recalcul de plus de ``tol``.

    Accepte Decimal ou float, paniers ``{taux, base|base_ht|ht_net,
    montant}``. Chaque entrée : ``{'etage', 'porte', 'recalcule'}``."""
    tol = TOLERANCES['centime'] if tol is None else tol
    t = totaux
    ecarts = []

    def _ecart(etage, porte, recalcule):
        if abs(_f(porte) - _f(recalcule)) > tol:
            ecarts.append({'etage': etage, 'porte': round(_f(porte), 2),
                           'recalcule': round(_f(recalcule), 2)})

    ht_brut, remise = _f(t.get('ht_brut')), _f(t.get('remise'))
    ht_net, tva, ttc = _f(t.get('ht_net')), _f(t.get('tva')), _f(t.get('ttc'))
    # ARRONDI-100 — la baisse de HT au palier de 100 MAD (0 sans palier).
    arrondi = _f(t.get('arrondi'))
    if remise_pct is not None:
        _ecart('remise', remise, round(ht_brut * _f(remise_pct) / 100, 2)
               if _f(remise_pct) > 0 else 0.0)
    if arrondi < 0:
        _ecart('arrondi', arrondi, 0.0)
    _ecart('ht_net', ht_net, ht_brut - remise - arrondi)
    paniers = list(t.get('tva_par_taux') or [])
    if paniers:
        _ecart('somme_bases_tva', sum(_base_panier(p) for p in paniers),
               ht_net)
        _ecart('somme_tva', sum(_f(p.get('montant')) for p in paniers), tva)
        for p in paniers:
            _ecart(f"tva_{_f(p.get('taux')):g}", p.get('montant'),
                   round(_base_panier(p) * _f(p.get('taux')) / 100, 2))
    _ecart('ttc', ttc, ht_net + tva)
    return ecarts


# ── Totaux du devis (modèle) ────────────────────────────────────────────────
@regle('DOC_TOTAUX_DEVIS',
       "Chaîne des totaux du devis (lignes → HT → remise → TVA → TTC) "
       "incohérente au centime",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS)
def totaux_devis(r, devis, ctx):
    """``Devis.total_*`` lisent ``domain.argent.totaux(vue=NET)`` (QJR51) :
    remise globale honorée, option effective. On re-vérifie l'arithmétique
    de chaque étage, et — pour un devis MONO-option, où aucun filtre d'option
    ne s'applique (``utils.options.option_totaux`` ne filtre que si
    ``has_two_options``) — que le HT brut est bien la somme des lignes
    comptées (``LigneDevis.compte_dans_totaux``)."""
    from apps.ventes.domain.argent import Vue, totaux
    from apps.ventes.utils.options import deux_options_declarees
    # ERR-QAC-MULTIVILLA-TOTAL-XN — l'arithmétique se vérifie sur UNE villa
    # (les lignes en décrivent une) ; le ×N n'est qu'une multiplication
    # entière exacte de chaque étage (``selectors.totaux_multi_proprietes``).
    t = totaux(devis, vue=Vue.NET, unitaire=True)
    d = {'ht_brut': t.ht_brut, 'remise': t.remise, 'arrondi': t.arrondi,
         'ht_net': t.ht_net, 'tva': t.tva, 'ttc': t.ttc,
         'tva_par_taux': list(t.tva_par_taux)}
    ecarts = ecarts_chaine(d, remise_pct=devis.remise_globale)
    # ARRONDI-100 (fondateur, 02/10/2026) — tout devis finit par deux zéros :
    # un TTC d'au moins un palier qui n'y tombe pas est une violation.
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    if t.ttc >= PAS_ARRONDI_DEVIS and t.ttc % PAS_ARRONDI_DEVIS:
        ecarts.append({'etage': 'palier_100',
                       'porte': round(_f(t.ttc), 2),
                       'recalcule': round(_f(t.ttc - t.ttc % PAS_ARRONDI_DEVIS),
                                          2)})
    if not deux_options_declarees(devis):
        somme = sum((li.total_ht for li in devis.lignes.all()
                     if li.compte_dans_totaux), Decimal('0'))
        if abs(_f(somme) - _f(t.ht_brut)) > TOLERANCES['centime']:
            ecarts.append({'etage': 'somme_lignes',
                           'porte': round(_f(t.ht_brut), 2),
                           'recalcule': round(_f(somme), 2)})
    return [r.violation(
        devis, f"Totaux du devis incohérents : étage « {e['etage']} » porte "
               f"{e['porte']} au lieu de {e['recalcule']}.",
        valeurs=e, attendu=e['recalcule'], cle={'etage': e['etage']})
        for e in ecarts]


@regle('DOC_TOTAUX_IMPRIMES',
       "Totaux imprimés (PDF/proposition) incohérents ou différents du "
       "total du devis",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def totaux_imprimes(r, devis, ctx):
    """Le moteur de devis imprime ``totaux_sans`` / ``totaux_avec`` /
    ``totaux_all`` (``builder._canonical_totaux`` → ``domain.argent``, QJR53)
    et la chaîne « Sous-total HT → Remise → Total HT → TVA → TTC ». Chaque
    chaîne imprimée doit tenir au centime, et le TTC que l'ERP retient pour
    le devis (``Devis.total_ttc``, option effective) doit être l'UN des TTC
    imprimés — sinon le client lit un prix et l'ERP en facture un autre."""
    data = ctx.donnees_devis(devis)
    out = []
    ttcs = {}
    remise_pct = data.get('discount_pct')
    for cle_tot in ('totaux_sans', 'totaux_avec', 'totaux_all'):
        tot = data.get(cle_tot)
        if not isinstance(tot, dict):
            continue
        ttcs[cle_tot] = _f(tot.get('ttc'))
        for e in ecarts_chaine(tot, remise_pct=remise_pct):
            out.append(r.violation(
                devis, f"Chaîne imprimée « {cle_tot} » incohérente : étage "
                       f"« {e['etage']} » imprime {e['porte']} au lieu de "
                       f"{e['recalcule']}.",
                valeurs=dict(e, totaux=cle_tot), attendu=e['recalcule'],
                cle={'totaux': cle_tot, 'etage': e['etage']}))
    # ERR-QAC-MULTIVILLA-TOTAL-XN — un devis ×N villas imprime AUSSI ses
    # totaux ×N (``totaux_multi``) : c'est l'un d'eux que l'ERP facture.
    multi = data.get('totaux_multi')
    if isinstance(multi, dict):
        for cle_opt, tot in multi.items():
            if isinstance(tot, dict) and tot.get('ttc') is not None:
                ttcs[f'totaux_multi_{cle_opt}'] = _f(tot.get('ttc'))
    if ttcs:
        modele = _f(devis.total_ttc)
        if not any(abs(modele - v) <= TOLERANCES['centime']
                   for v in ttcs.values()):
            out.append(r.violation(
                devis, f"Le total TTC du devis ({modele:.2f}) n'apparaît sur "
                       "aucune option imprimée.",
                valeurs={'total_ttc_devis': round(modele, 2),
                         'ttc_imprimes': {k: round(v, 2)
                                          for k, v in ttcs.items()}},
                attendu=sorted({round(v, 2) for v in ttcs.values()}),
                cle={'etage': 'ttc_modele_vs_imprime'}))
    return out


@regle('DOC_TOTAL_IMPRIME_NE_NOYAU',
       "Lignes imprimées, total imprimé et total du noyau (option effective) "
       "ne disent pas le même montant",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def total_imprime_ne_noyau(r, devis, ctx):
    """AMOT48 — complète ``DOC_TOTAUX_IMPRIMES`` (qui vérifie l'arithmétique
    de chaque chaîne et que le TTC du devis figure PARMI les options) : ici,
    LE total imprimé (``display_total``) doit ÊTRE le TTC unitaire de l'option
    effective du noyau (``domain.argent.totaux``), la somme des lignes
    imprimées (``all_items``) doit retomber sur le HT brut de ``totaux_all``,
    et un document à une option imprime ``display_total == totaux_all.ttc``.
    Même fonction que la garde du moteur
    (``quote_engine.builder.ecarts_totaux_imprimes``) — une seule écriture."""
    from apps.ventes.domain.argent import Vue, totaux
    from apps.ventes.quote_engine.builder import ecarts_totaux_imprimes
    data = ctx.donnees_devis(devis)
    ttc_noyau = _f(totaux(devis, vue=Vue.NET, unitaire=True).ttc)
    return [r.violation(
        devis, f"Total imprimé incohérent : « {e['etage']} » porte "
               f"{e['porte']:.2f} au lieu de {e['attendu']:.2f}.",
        valeurs=e, attendu=e['attendu'], cle={'etage': e['etage']})
        for e in ecarts_totaux_imprimes(
            data, ttc_noyau, tol=TOLERANCES['centime'])]


# ── Totaux de la facture ────────────────────────────────────────────────────
@regle('DOC_TOTAUX_FACTURE',
       "Chaîne des totaux de la facture incohérente",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_FACTURE)
def totaux_facture(r, facture, ctx):
    """``TotauxDocumentMixin`` (apps/facturation/totaux.py) : une facture
    NON figée passe par le noyau canonique sur ses lignes (``_canonique``) —
    chaîne vérifiée étage par étage + HT brut = Σ ``LigneFacture.total_ht`` ;
    une facture FIGÉE (tranche d'échéancier, ``montant_ht`` posé) porte ses
    trois montants tels quels — ils doivent vérifier HT + TVA = TTC (à
    quelques centimes : ``utils.echeancier.next_tranche`` arrondit chacun
    indépendamment)."""
    out = []
    if facture.montant_ht is not None:
        if facture.montant_tva is None or facture.montant_ttc is None:
            return out
        ecart = abs(_f(facture.montant_ht) + _f(facture.montant_tva)
                    - _f(facture.montant_ttc))
        if ecart > TOLERANCES['facture_figee_mad']:
            out.append(r.violation(
                facture, f"Facture figée : HT {_f(facture.montant_ht):.2f} + "
                         f"TVA {_f(facture.montant_tva):.2f} ≠ TTC "
                         f"{_f(facture.montant_ttc):.2f}.",
                valeurs={'montant_ht': _f(facture.montant_ht),
                         'montant_tva': _f(facture.montant_tva),
                         'montant_ttc': _f(facture.montant_ttc)},
                attendu=round(_f(facture.montant_ht)
                              + _f(facture.montant_tva), 2),
                cle={'etage': 'figee_ht_tva_ttc'}))
        return out
    t = facture.totaux_affichage
    d = dict(t, tva=facture.total_tva)
    ecarts = ecarts_chaine(d, remise_pct=facture.remise_globale)
    somme = sum((li.total_ht for li in facture.lignes.all()), Decimal('0'))
    if abs(_f(somme) - _f(t['ht_brut'])) > TOLERANCES['centime']:
        ecarts.append({'etage': 'somme_lignes',
                       'porte': round(_f(t['ht_brut']), 2),
                       'recalcule': round(_f(somme), 2)})
    for e in ecarts:
        out.append(r.violation(
            facture, f"Totaux de la facture incohérents : étage "
                     f"« {e['etage']} » porte {e['porte']} au lieu de "
                     f"{e['recalcule']}.",
            valeurs=e, attendu=e['recalcule'], cle={'etage': e['etage']}))
    return out


# ── Facturation ≤ devis ─────────────────────────────────────────────────────
@regle('DOC_FACTURATION_DEPASSE_DEVIS',
       "Le facturé (net des avoirs) dépasse le total de l'option retenue "
       "du devis",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS)
def facturation_depasse_devis(r, devis, ctx):
    """Les deux voies de facturation d'un devis (échéancier ``Facture.devis``
    et chaîne ``BonCommande → Facture``, ``selectors.factures_du_devis``,
    AUD112) facturent au plus l'option retenue : les tranches retombent au
    centime sur ``option_totaux(devis)['ttc']`` (le solde = reste exact,
    ``utils.echeancier.next_tranche``) et la facture de BC recopie les seules
    lignes de l'option (``option_lines``, ERR16) avec la remise globale.
    Un avoir actif réduit le facturé (``Facture.avoirs_total``) — une
    facture rectificative après avoir reste donc légitime."""
    factures = ctx.factures_actives_du_devis(devis.pk)
    if not factures:
        return []
    from apps.ventes.utils.options import option_totaux
    total_devis = _f(option_totaux(devis)['ttc'])
    facture_ttc = sum(_f(f.total_ttc) for f in factures)
    avoirs = sum(_f(f.avoirs_total) for f in factures)
    net = facture_ttc - avoirs
    if net <= total_devis + TOLERANCES['facturation_devis_mad']:
        return []
    return [r.violation(
        devis, f"Facturé net {net:.2f} (factures {facture_ttc:.2f} − avoirs "
               f"{avoirs:.2f}) > total du devis {total_devis:.2f}.",
        valeurs={'facture_ttc': round(facture_ttc, 2),
                 'avoirs_ttc': round(avoirs, 2),
                 'net_facture': round(net, 2),
                 'factures': sorted(f.reference for f in factures)},
        attendu=round(total_devis, 2))]


# ── Statuts ↔ liens ─────────────────────────────────────────────────────────
@regle('DOC_LIEN_DEVIS_NON_ACCEPTE',
       "Bon de commande ou facture rattaché à un devis non accepté",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS)
def lien_devis_non_accepte(r, devis, ctx):
    """``convertir_en_bc`` (views/devis.py) et ``creer_facture_tranche``
    (utils/echeancier.py) refusent tout devis qui n'est pas « accepte », et
    un devis accepté ne peut plus être refusé (``/refuser/`` n'accepte que
    brouillon/envoyé) ni repassé à accepté/refusé/expiré par PATCH
    (AUD505). Un BC non annulé ou une facture non annulée sur un devis qui
    n'est pas « accepte » est donc une chaîne documentaire cassée."""
    if devis.statut == STATUT_ACCEPTE:
        return []
    bc = getattr(devis, 'bon_commande', None)
    liens = {}
    if bc is not None and bc.statut != BC_ANNULE:
        liens['bon_commande'] = bc.reference
    factures = ctx.factures_actives_du_devis(devis.pk)
    if factures:
        liens['factures'] = sorted(f.reference for f in factures)
    if not liens:
        return []
    return [r.violation(
        devis, f"Devis au statut « {devis.statut} » mais déjà engagé en aval "
               f"({', '.join(sorted(liens))}).",
        valeurs=dict(liens, statut=devis.statut), attendu=STATUT_ACCEPTE)]


@regle('DOC_ACCEPTE_SANS_DATE',
       "Devis accepté sans date d'acceptation",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def accepte_sans_date(r, devis, ctx):
    """``domain.cycle_vie`` pose ``statut=accepte`` ET ``date_acceptation``
    dans le MÊME save (N25) — la seule porte depuis AUD505. Sans date, le
    rappel « devis à facturer » (``scheduled.devis_a_facturer_reminder``,
    qui calcule ``today − date_acceptation``) ignore le devis."""
    if devis.statut != STATUT_ACCEPTE or devis.date_acceptation is not None:
        return []
    return [r.violation(devis, "Devis accepté sans date d'acceptation.",
                        valeurs={'date_acceptation': None})]


# ── Dates ordonnées ─────────────────────────────────────────────────────────
@regle('DOC_VALIDITE_AVANT_CREATION',
       "Date de validité du devis antérieure à sa date de création",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def validite_avant_creation(r, devis, ctx):
    """``date_validite`` n'est posée que par la saisie du vendeur ou par
    ``cycle_vie.poser_validite_devis`` (à l'envoi, date calculée ≥ jour
    d'envoi) : une validité ANTÉRIEURE à la création est imprimée telle
    quelle (« valable jusqu'au … ») sur le document client."""
    if devis.date_validite is None or devis.date_creation is None:
        return []
    creation = timezone.localdate(devis.date_creation)
    if devis.date_validite >= creation:
        return []
    return [r.violation(
        devis, f"Validité {devis.date_validite.isoformat()} antérieure à la "
               f"création {creation.isoformat()}.",
        valeurs={'date_validite': devis.date_validite.isoformat(),
                 'date_creation': creation.isoformat()},
        attendu=f'>= {creation.isoformat()}')]


@regle('DOC_ECHEANCE_AVANT_EMISSION',
       "Date d'échéance de la facture antérieure à son émission",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_FACTURE)
def echeance_avant_emission(r, facture, ctx):
    """``facturation_ops.calculer_date_echeance`` dérive l'échéance de la
    date d'émission + délai client (≥ émission) ; une échéance antérieure
    fait passer la facture « en retard » dès sa naissance
    (``scheduled.check_overdue_factures``)."""
    if facture.statut == FACTURE_ANNULEE:
        return []
    if facture.date_echeance is None or facture.date_emission is None:
        return []
    if facture.date_echeance >= facture.date_emission:
        return []
    return [r.violation(
        facture, f"Échéance {facture.date_echeance.isoformat()} antérieure à "
                 f"l'émission {facture.date_emission.isoformat()}.",
        valeurs={'date_echeance': facture.date_echeance.isoformat(),
                 'date_emission': facture.date_emission.isoformat()},
        attendu=f'>= {facture.date_emission.isoformat()}')]


# ── Lignes ──────────────────────────────────────────────────────────────────
def _vide(texte):
    return not (texte or '').strip()


@regle('DOC_DESIGNATION_DEVIS',
       "Ligne produit de devis sans désignation",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def designation_devis(r, devis, ctx):
    """Une ligne PRODUIT est imprimée par sa désignation sur le PDF client ;
    le moteur y lit aussi les mots-clés de classement (panneau, onduleur…).
    Vide = une ligne muette sur le document et mal classée."""
    ids = [li.pk for li in devis.lignes.all()
           if li.est_ligne_produit and _vide(li.designation)]
    if not ids:
        return []
    return [r.violation(devis, f"{len(ids)} ligne(s) produit sans "
                               "désignation.",
                        valeurs={'lignes': ids})]


@regle('DOC_DESIGNATION_FACTURE',
       "Ligne de facture sans désignation",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_FACTURE)
def designation_facture(r, facture, ctx):
    """Mention obligatoire d'une facture : la désignation de chaque ligne."""
    ids = [li.pk for li in facture.lignes.all() if _vide(li.designation)]
    if not ids:
        return []
    return [r.violation(facture, f"{len(ids)} ligne(s) sans désignation.",
                        valeurs={'lignes': ids})]


@regle('DOC_LIGNE_SANS_PRIX',
       "Ligne produit comptée dans les totaux sans quantité ou sans prix "
       "(devis hors brouillon)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def ligne_sans_prix(r, devis, ctx):
    """XSAL14 a rendu ``quantite``/``prix_unitaire`` nullables pour les
    lignes de section/note ; une ligne PRODUIT comptée
    (``compte_dans_totaux``) sans l'un des deux vaut 0 en silence
    (``LigneDevis.total_ht``) — le prix disparaît du total. Un brouillon peut
    légitimement attendre son prix (« prix à renseigner ») : seuls les devis
    sortis du brouillon sont examinés."""
    if devis.statut == STATUT_BROUILLON:
        return []
    ids = [li.pk for li in devis.lignes.all()
           if li.compte_dans_totaux
           and (li.quantite is None or li.prix_unitaire is None)]
    if not ids:
        return []
    return [r.violation(devis, f"{len(ids)} ligne(s) produit sans quantité ou "
                               "sans prix, comptées pour 0.",
                        valeurs={'lignes': ids, 'statut': devis.statut})]
