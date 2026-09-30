"""QA-COHERENCE — chiffres de l'ÉTUDE : stockés vs recalculés vs imprimés.

Portage des règles utiles du prototype COUV-HOR
(``docs/decisions/COUV-HOR/auditeur_coherence_prototype.py``, exécuté sur la
prod : 310 devis en 15 s, faux positifs mesurés dans
``audit-qa-complet.md`` §4). Sont portées : I2, I4, I5, I6, I7, I8 (= I12,
parité PDF / proposition publique), I10, et l'hygiène numérique (I6c
généralisée). NE sont PAS portées : I1 (devenu tautologique après #738 — il
relit le chiffre du moteur), I3 et I9 (bruyantes tant que la dérive du
barème JS n'est pas corrigée), I11 (compare deux options différentes en
« Les deux » — fort taux de faux positifs mesuré).

Le document est construit par ``ctx.donnees_devis`` (une fois par devis, dans
une transaction annulée, sans accès réseau — voir ``contexte``).
"""
from __future__ import annotations

import math

from .contexte import num
from .registre import (GRAVITE_AVERTISSEMENT, GRAVITE_CRITIQUE, PORTEE_DEVIS,
                       TOLERANCES, regle)

TOL = TOLERANCES


def _ep(devis):
    return devis.etude_params if isinstance(devis.etude_params, dict) else {}


def _bloc_horaire(ep):
    eh = ep.get('etude_horaire')
    return eh if isinstance(eh, dict) else None


def _residentiel(devis):
    from apps.ventes.quote_engine.residential import renderer as R
    return R.is_residential(devis, {'pdf_mode': 'full'})


def couche_et_raison(data):
    """``(page 1 imprimée, raison)`` du PDF résidentiel : raison ``printed``,
    ``legacy_renderer`` (hors gabarit résidentiel), ``economic_layer_omitted``
    (omission VOULUE, Z2) ou ``no_synthese`` — comme le prototype."""
    from apps.ventes.quote_engine.residential import renderer as R
    try:
        d = R._augment(data)
    except R.Unsupported:
        return None, 'legacy_renderer'
    if d.get('masquer_synthese') or d.get('masquer_economies'):
        return None, 'economic_layer_omitted'
    if d.get('coverage_pct') is None:
        return None, 'no_synthese'
    return d, 'printed'


def couche_imprimee(data):
    """Ce que la page 1 du PDF résidentiel imprime, ou ``None``."""
    return couche_et_raison(data)[0]


def option_imprimee(data):
    """L'option que la page 1 décrit (prototype : ``avec`` dès que le
    document porte deux options ou l'option avec)."""
    avec = bool(data.get('deux_options', True)) or bool(
        data.get('avec_ok', True))
    return 'avec' if avec else 'sans'


def factures_reelles(devis, ep):
    """(12 factures MAD/mois réellement données, source) ou (None, None).
    Priorité aux 12 factures stockées dans l'étude, sinon le couple
    hiver/été du lead (lu par ``apps.crm.selectors`` — jamais ses modèles)."""
    fm = ep.get('factures_mensuelles_reelles')
    if isinstance(fm, (list, tuple)) and len(fm) == 12:
        vals = [num(v) for v in fm]
        if all(v is not None and v > 0 for v in vals):
            return vals, 'factures_mensuelles_reelles'
    try:
        from apps.crm.selectors import lead_bills_for_devis
        from apps.ventes.etude_horaire import serie_mad_mensuelle
        b = lead_bills_for_devis(devis) or {}
        serie = serie_mad_mensuelle(b.get('facture_hiver'),
                                    b.get('facture_ete'),
                                    b.get('ete_differente'))
        if serie:
            return [float(v) for v in serie], 'lead_hiver_ete'
    except Exception:  # noqa: BLE001 — pas de factures lisibles = pas de règle
        pass
    return None, None


def nombres_invalides(obj, chemin='', out=None, profondeur=0):
    """Chemins des NaN/inf dans les données du document (champs qui
    atteignent un document client). Bornée (profondeur 6, 60 éléments par
    liste, 6 chemins au plus) ; les gros blobs techniques sont ignorés."""
    if out is None:
        out = []
    if profondeur > 6 or len(out) > 5:
        return out
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            out.append(chemin)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('etude', 'roof_layout', 'electrical_design'):
                continue
            nombres_invalides(v, f'{chemin}.{k}', out, profondeur + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj[:60]):
            nombres_invalides(v, f'{chemin}[{i}]', out, profondeur + 1)
    return out


# ── I4 — signature du repli « factures ÷ 1,20 » ────────────────────────────
@regle('ETU_I4_CONSO_REPLI',
       "Consommation annuelle stockée = Σ factures ÷ 1,20 (prix de repli, "
       "au lieu du barème réel)",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS)
def i4_conso_repli(r, devis, ctx):
    """Incident COUV-HOR : la conso était dérivée des 12 factures au prix
    PLAT de repli (1,20 MAD/kWh) au lieu du barème progressif — 129 devis
    (35 envoyés) mesurés. Données stockées seulement, aucun rendu."""
    ep = _ep(devis)
    conso = num(ep.get('conso_annuelle'))
    if not conso:
        return []
    fm = ep.get('factures_mensuelles_reelles')
    if not (isinstance(fm, (list, tuple)) and len(fm) == 12):
        return []
    vals = [num(v) for v in fm]
    if not all(v is not None and v > 0 for v in vals):
        return []
    somme = sum(vals)
    repli = somme / TOL['I4_prix_plat']
    if abs(conso - repli) > TOL['I4_kwh']:
        return []
    return [r.violation(
        devis, f"Conso annuelle {round(conso)} kWh = Σ factures "
               f"{round(somme)} MAD ÷ {TOL['I4_prix_plat']} : repli au prix "
               "plat au lieu du barème.",
        valeurs={'conso_annuelle': round(conso), 'somme_factures': round(somme),
                 'factures_div_prix_plat': round(repli),
                 'distributeur': ep.get('distributeur')},
        attendu='conso issue du barème progressif')]


# ── Hygiène numérique des paramètres d'étude stockés ───────────────────────
_PARAMS_POSITIFS = ('puissance_kwc', 'production_annuelle', 'conso_annuelle',
                    'tarif_kwh')


@regle('ETU_PARAMS_NUMERIQUES',
       "Paramètre d'étude stocké négatif (kWc, production, conso, tarif, "
       "factures)",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS)
def params_numeriques(r, devis, ctx):
    """kWc, production annuelle, conso annuelle, tarif et factures mensuelles
    sont des grandeurs physiques/monétaires ≥ 0 (lues par ``Devis.save`` —
    prix au kWc — et par le moteur de devis). Postgres jsonb refuse
    NaN/Infinity : seul le signe peut dériver."""
    ep = _ep(devis)
    negatifs = []
    for k in _PARAMS_POSITIFS:
        v = num(ep.get(k))
        if v is not None and v < 0:
            negatifs.append(k)
    fm = ep.get('factures_mensuelles_reelles')
    if isinstance(fm, (list, tuple)):
        for i, v in enumerate(fm):
            f = num(v)
            if f is not None and f < 0:
                negatifs.append(f'factures_mensuelles_reelles[{i}]')
    if not negatifs:
        return []
    return [r.violation(devis, "Paramètre(s) d'étude négatif(s) : "
                               + ', '.join(negatifs) + '.',
                        valeurs={'champs': negatifs,
                                 **{k: ep.get(k) for k in _PARAMS_POSITIFS
                                    if k in negatifs}},
                        attendu='>= 0')]


# ── I7 — bloc horaire périmé (repli silencieux) ────────────────────────────
@regle('ETU_I7_BLOC_HORAIRE_PERIME',
       "Bloc horaire calculé pour un autre kWc que celui du devis (le moteur "
       "retombe en silence sur un modèle moins précis)",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def i7_bloc_perime(r, devis, ctx):
    """Le moteur rejette un bloc ``etude_horaire`` dont le kWc s'écarte de
    plus de 2 % de celui du devis (garde de fraîcheur) et chiffre alors les
    colonnes au modèle « factures »/« estimation » sans le dire. 60 devis
    mesurés (bloc = kWc_sans + kWc_avec)."""
    ep = _ep(devis)
    eh = _bloc_horaire(ep)
    if not eh:
        return []
    kwc_bloc = num(eh.get('kwc'))
    if not kwc_bloc:
        return []
    data = ctx.donnees_devis(devis)
    kwcs = {'doc': num(data.get('puissance_kwc'))}
    if data.get('panneaux_divergents'):
        kwcs['sans'] = num(data.get('puissance_kwc_sans'))
        kwcs['avec'] = num(data.get('puissance_kwc_avec'))
    pire = None
    for k, v in kwcs.items():
        if v:
            d = abs(kwc_bloc - v) / v
            if pire is None or d > pire[1]:
                pire = (k, d, v)
    if not pire or pire[1] <= TOL['I7_kwc_ratio']:
        return []
    return [r.violation(
        devis, f"Bloc horaire calculé pour {kwc_bloc} kWc, devis à "
               f"{pire[2]} kWc ({pire[0]}) : écart {pire[1]:.1%}.",
        valeurs={'kwc_bloc': kwc_bloc, 'kwc_devis': pire[2],
                 'colonne': pire[0], 'ecart': round(pire[1], 3),
                 'modele_sans': data.get('savings_model_sans'),
                 'modele_avec': data.get('savings_model_avec')},
        attendu=pire[2], cle={'colonne': pire[0]})]


# ── I2 — −N % vs couverture, régime linéaire (tranche haute) ───────────────
@regle('ETU_I2_REDUCTION_VS_COUVERTURE',
       "Réduction de facture imprimée (−N %) physiquement incompatible avec "
       "la couverture imprimée",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS, besoin_rendu=True)
def i2_reduction_vs_couverture(r, devis, ctx):
    """Quand CHAQUE mois reste dans la tranche haute même après solaire, la
    facture est linéaire en kWh : −N % ≈ couverture × (1 − part fixe). Donc
    ``couverture × (1 − part fixe) − 2 ≤ −N % ≤ couverture + 1``, élargi de
    1 pt de chaque côté parce que les deux chiffres sont imprimés arrondis à
    l'entier. Borne purement physique (aucun bloc « engine » requis).
    Gravité « avertissement » : la part fixe ignore le plafond TPPAN (bruit
    possible sur les grosses factures, audit §B.9)."""
    ep = _ep(devis)
    eh = _bloc_horaire(ep)
    if not eh or not _residentiel(devis):
        return []
    an = eh.get('annuel') if isinstance(eh.get('annuel'), dict) else {}
    if not num(an.get('consommation_kwh')) or not isinstance(
            eh.get('mois'), list):
        return []
    data = ctx.donnees_devis(devis)
    imprime = couche_imprimee(data)
    if not imprime:
        return []
    opt = option_imprimee(data)
    cle_auto = f'autoconsomme_{opt}_kwh'
    if opt == 'avec' and data.get('avec_batterie_differee'):
        cle_auto = 'autoconsomme_sans_kwh'
    restes = []
    for m in eh['mois']:
        cm = num((m or {}).get('consommation_kwh'))
        am = num((m or {}).get(cle_auto))
        if cm is None or am is None:
            return []
        restes.append(cm - am)
    if len(restes) != 12:
        return []
    tarif = ctx.tarif()
    if min(restes) <= tarif['top_start']:
        return []
    cov, cut = imprime.get('coverage_pct'), imprime.get('pct_cut')
    if cov is None or cut is None:
        return []
    ab = num(imprime.get('annual_before')) or 0
    part_fixe = min(0.5, 12 * tarif['fixed_mois'] / ab) if ab > 0 else 0
    arrondi = TOL['I2_arrondi_imprime_pts']
    bas = cov * (1 - part_fixe) - TOL['I2_plancher_marge_pts'] - arrondi
    haut = cov + TOL['I2_plafond_pts'] + arrondi
    if bas <= cut <= haut:
        return []
    return [r.violation(
        devis, f"−{cut} % imprimé pour une couverture de {cov} % : hors de "
               f"[{round(bas, 1)} ; {haut}] en régime linéaire.",
        valeurs={'couverture_pct': cov, 'reduction_pct': cut,
                 'mois_min_apres_kwh': round(min(restes)),
                 'part_fixe': round(part_fixe, 3), 'option': opt},
        attendu=[round(bas, 1), haut], cle={'option': opt})]


# ── I5 — facture actuelle imprimée vs factures réelles ─────────────────────
@regle('ETU_I5_FACTURE_ACTUELLE',
       "Facture actuelle imprimée ≠ somme des factures réelles du client "
       "(± 10 %)",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def i5_facture_actuelle(r, devis, ctx):
    """Le « avant » du document (page 1, bloc méthode, facture sans solaire)
    doit retomber sur ce que le client paie réellement : ses 12 factures
    stockées, sinon son couple hiver/été du lead."""
    ep = _ep(devis)
    if not ep:
        return []
    factures, source = factures_reelles(devis, ep)
    if not factures:
        return []
    somme = sum(factures)
    data = ctx.donnees_devis(devis)
    imprime = couche_imprimee(data) if _residentiel(devis) else None
    methode = data.get('savings_method') or {}
    candidats = {
        'page1_facture_avant': (imprime or {}).get('annual_before'),
        'methode_facture_actuelle': methode.get('facture_actuelle'),
        'facture_sans_solaire': data.get('facture_sans_solaire'),
    }
    out = []
    for figure, v in candidats.items():
        v = num(v)
        if not v:
            continue
        ratio = v / somme
        if abs(ratio - 1) > TOL['I5_ratio']:
            out.append(r.violation(
                devis, f"« {figure} » imprime {round(v)} MAD pour des "
                       f"factures réelles de {round(somme)} MAD "
                       f"(×{ratio:.2f}).",
                valeurs={'figure': figure, 'imprime': round(v),
                         'factures_reelles': round(somme), 'source': source,
                         'ratio': round(ratio, 3),
                         'modele': data.get('savings_model')},
                attendu=round(somme), cle={'figure': figure}))
    return out


# ── I6 — économies, retour sur investissement ──────────────────────────────
@regle('ETU_I6_ECONOMIES',
       "Économie annuelle nulle/négative ou supérieure à la facture, ou "
       "retour sur investissement incohérent avec prix ÷ économie",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS, besoin_rendu=True)
def i6_economies(r, devis, ctx):
    """On ne peut pas économiser plus que ce qu'on paie, ni afficher un
    retour qui ne ressemble pas à prix ÷ économie (tolérance 30 % : la courbe
    25 ans intègre dégradation, escalade et remplacements). Le plafond de 25
    ans du retour masque un système qui ne se rembourse jamais (audit :
    DEV-202609-0082, 25 ans imprimés pour 865 ans réels)."""
    if not _ep(devis):
        return []
    data = ctx.donnees_devis(devis)
    if data.get('masquer_economies'):
        return []
    if _residentiel(devis) and \
            couche_et_raison(data)[1] == 'economic_layer_omitted':
        return []
    fa = num((data.get('savings_method') or {}).get('facture_actuelle')) \
        or num(data.get('facture_sans_solaire'))
    out = []
    for opt, k_eco, k_roi, k_tot, k_ok in (
            ('sans', 'eco_s_ann', 'roi_s', 'total_sans', 'sans_ok'),
            ('avec', 'eco_a_ann', 'roi_a', 'total_avec', 'avec_ok')):
        if not data.get(k_ok):
            continue
        brut = data.get(k_eco)
        eco = num(brut)
        if eco is None or eco <= 0:
            if brut is not None:
                out.append(r.violation(
                    devis, f"Option {opt} : économie annuelle {brut} ≤ 0.",
                    valeurs={'option': opt, 'economie': brut},
                    attendu='> 0', cle={'option': opt, 'cas': 'eco_nulle'}))
            continue
        if fa and eco > fa * TOL['I6_eco_vs_facture']:
            out.append(r.violation(
                devis, f"Option {opt} : économie {round(eco)} MAD/an > "
                       f"facture actuelle {round(fa)} MAD/an.",
                valeurs={'option': opt, 'economie': round(eco),
                         'facture_actuelle': round(fa)},
                attendu=f'<= {round(fa)}',
                cle={'option': opt, 'cas': 'eco_sup_facture'}))
        roi, tot = num(data.get(k_roi)), num(data.get(k_tot))
        if roi and tot:
            simple = tot / eco
            ratio = roi / simple
            if abs(ratio - 1) > TOL['I6_payback_ratio']:
                out.append(r.violation(
                    devis, f"Option {opt} : retour imprimé {roi} ans vs prix "
                           f"÷ économie = {simple:.2f} ans (×{ratio:.2f}).",
                    valeurs={'option': opt, 'retour_imprime': roi,
                             'prix_sur_economie': round(simple, 2),
                             'ratio': round(ratio, 2),
                             'modele': data.get(f'savings_model_{opt}')},
                    attendu=round(simple, 2),
                    cle={'option': opt, 'cas': 'retour'}))
    return out


# ── Hygiène numérique des données du document ──────────────────────────────
_DOC_POSITIFS = ('prod_kwh', 'eco_s_ann', 'eco_a_ann', 'roi_s', 'roi_a',
                 'total_sans', 'total_avec')


@regle('ETU_DOCUMENT_NUMERIQUE',
       "NaN/infini ou valeur négative impossible dans les chiffres du "
       "document client",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def document_numerique(r, devis, ctx):
    """Tout nombre du dict de rendu atteint un document client (PDF ou
    proposition publique, qui sert le même dict) : NaN/inf y sont toujours
    une erreur ; production, économies, retours et totaux ne sont jamais
    négatifs ; page 1 : « après » ≥ 0 et −N % dans [0 ; 100]."""
    data = ctx.donnees_devis(devis)
    invalides = nombres_invalides(data)
    negatifs = [k for k in _DOC_POSITIFS if (num(data.get(k)) or 0) < 0]
    if _residentiel(devis):
        imprime = couche_imprimee(data)
        if imprime:
            if (num(imprime.get('annual_after')) or 0) < 0 or not (
                    0 <= (num(imprime.get('pct_cut')) or 0) <= 100):
                negatifs.append('page1_apres_ou_reduction')
    if not invalides and not negatifs:
        return []
    return [r.violation(
        devis, "Chiffres invalides dans le document : "
               + ', '.join(invalides[:3] + negatifs) + '.',
        valeurs={'nan_inf': invalides[:6], 'negatifs': negatifs},
        attendu='nombres finis et positifs')]


# ── I10 — graphe mensuel vs carte option (même page) ───────────────────────
@regle('ETU_I10_GRAPHE_VS_CARTE',
       "Total du graphe mensuel des économies ≠ économie annuelle de la "
       "carte option (± 3 %)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS, besoin_rendu=True)
def i10_graphe_vs_carte(r, devis, ctx):
    """Deux chiffres de la MÊME économie annuelle sur le même document : la
    somme des barres du graphe mensuel (page 1) et la carte de l'option."""
    if not _ep(devis) or not _residentiel(devis):
        return []
    data = ctx.donnees_devis(devis)
    imprime = couche_imprimee(data)
    if not imprime:
        return []
    opt = option_imprimee(data)
    carte = num(data.get('eco_a_ann' if opt == 'avec' else 'eco_s_ann'))
    graphe = num(imprime.get('eco_mensuelles_total'))
    if not carte or not graphe:
        return []
    ratio = graphe / carte
    if abs(ratio - 1) <= TOL['I10_ratio']:
        return []
    return [r.violation(
        devis, f"Graphe mensuel {round(graphe)} MAD vs carte option {opt} "
               f"{round(carte)} MAD (×{ratio:.3f}).",
        valeurs={'total_graphe': round(graphe), 'carte_option': round(carte),
                 'option': opt, 'ratio': round(ratio, 3),
                 'source_factures': data.get('factures_source')},
        attendu=round(carte), cle={'option': opt})]


# ── I8 / I12 — parité PDF (options du dernier rendu) vs proposition ────────
_CLES_SYNTHESE = ('pct_cut', 'coverage_pct', 'annual_before', 'annual_after',
                  'eco_option')
_CLES_DONNEES = ('eco_s_ann', 'eco_a_ann', 'roi_s', 'roi_a', 'total_sans',
                 'total_avec')


@regle('ETU_I8_PARITE_PDF_PROPOSITION',
       "Le PDF (options du dernier rendu) et la proposition publique "
       "impriment des chiffres différents",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def i8_parite(r, devis, ctx):
    """PDF et proposition partagent ``build_quote_data`` +
    ``synthese_economies`` : ils ne peuvent diverger que par les options de
    rendu (scénario, variante). On rejoue les options du DERNIER rendu PDF
    (``pdf_render_meta['options']``) contre la vue publique (``full``)."""
    if not _residentiel(devis):
        return []
    meta = devis.pdf_render_meta if isinstance(
        devis.pdf_render_meta, dict) else {}
    opts = meta.get('options') if isinstance(meta.get('options'), dict) \
        else None
    if opts is None:
        return []
    from apps.ventes.quote_engine.residential import renderer as R
    if not R.is_residential(devis, opts):
        return []
    d_pdf = ctx.donnees_devis(devis, opts)
    d_pub = ctx.donnees_devis(devis, {'pdf_mode': 'full'})
    s_pdf = R.synthese_economies(d_pdf)
    s_pub = R.synthese_economies(d_pub)
    ecarts = {}
    if (s_pdf is None) != (s_pub is None):
        ecarts['presence_synthese'] = [s_pdf is not None, s_pub is not None]
    elif s_pdf and s_pub:
        for k in _CLES_SYNTHESE:
            if s_pdf.get(k) != s_pub.get(k):
                ecarts[k] = [s_pdf.get(k), s_pub.get(k)]
    for k in _CLES_DONNEES:
        if d_pdf.get(k) != d_pub.get(k):
            ecarts[k] = [d_pdf.get(k), d_pub.get(k)]
    if not ecarts:
        return []
    return [r.violation(
        devis, 'PDF ≠ proposition publique sur : '
               + ', '.join(sorted(ecarts)) + '.',
        valeurs={'ecarts': ecarts,
                 'options_pdf': {k: opts.get(k) for k in
                                 ('scenario', 'pdf_mode', 'variante_option')
                                 if opts.get(k) is not None}},
        attendu='mêmes chiffres', cle={'champs': sorted(ecarts)})]
