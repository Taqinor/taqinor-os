"""CIQ204 — moteur ``economie_ci`` (1/6) : valorisation HEURE PAR HEURE.

Économie = facture d'énergie AVANT − APRÈS, le kWh solaire évité valorisé au
prix du POSTE réellement couvert (``tarif_ci.tarif_du_poste``), JAMAIS à une
moyenne pondérée incluant la pointe, JAMAIS un prix plat. La prime fixe (prime
× puissance souscrite) est IDENTIQUE avant et après : aucune économie de prime
ni de puissance souscrite n'est attribuée au PV seul (convention 2 ; la loi
82-21 art. 10 ne donne que le droit de modifier l'abonnement).

Entrée = sortie de l'aperçu C&I (contrat CIQ2 ``etude_ci_preview.json``) :
``bilan.horaire`` [{mois, type_jour, nb_jours, autoconso_kwh[24],
surplus_kwh[24]}] et ``profil_charge.jours_types`` [{mois, type_jour, nb_jours,
charge_kwh[24]}] — heures en GMT. Sortie = la partie « valorisation » du
contrat CIQ3 ``economie_ci.json`` (statut, tarif, economie_annee1,
facture_avant, facture_apres, revente, hypotheses) ; les flux, la base HT/TTC
et les indicateurs relèvent des étapes suivantes (CIQ205-CIQ209).

Module PUR : aucune base, aucun import de modèle, aucune clé interdite
(``calepinage/services/note_calcul.CLES_INTERDITES``).
"""
from __future__ import annotations

from apps.ventes import tarif_ci
from apps.ventes.quote_engine.constants_82_21 import MENTION_ART13, MENTION_BT

STATUT_CALCULE = 'calcule'
STATUT_OMIS = 'omis'
MOTIF_TARIF_OMIS = (
    "contrat d'électricité non déclaré et aucune facture lue : aucun tarif — "
    "économies non chiffrées (aucun prix plat supposé)")
MOTIF_BI_HORAIRE = (
    "option bi-horaire : plages heures pleines / normales non saisies — "
    "économies non chiffrées (aucune plage devinée)")
MOTIF_SANS_HORAIRE = (
    "matrice horaire de l'étude C&I absente : économies non chiffrées")
ETIQUETTE_CONSO_ESTIMEE = (
    "consommation estimée (barème national) — les kWh de votre facture "
    "affineront ce chiffre")
_POSTES_MT = ('pointe', 'pleines', 'creuses')


def _f(v):
    try:
        if v is None or isinstance(v, bool):
            return 0.0
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


def _vide(motif, tarif):
    return {
        'statut': STATUT_OMIS,
        'motifs_omission': [motif],
        'tarif': tarif,
        'economie_annee1': None,
        'facture_avant': None,
        'facture_apres': None,
        'revente': None,
        'hypotheses': [],
    }


def _charges_par_jour_type(apercu):
    out = {}
    jours = ((apercu.get('profil_charge') or {}).get('jours_types') or [])
    for j in jours:
        if isinstance(j, dict):
            out[(j.get('mois'), j.get('type_jour'))] = j.get('charge_kwh')
    return out


def _cellules(apercu):
    """[(mois, heure, autoconso_kwh, charge_kwh|None)] pondérées par nb_jours.

    L'autoconsommation d'une heure est bornée par la charge de cette heure
    quand elle est connue : on ne peut pas éviter plus que ce qu'on consomme
    (garantit économie ≤ facture d'énergie avant).
    """
    horaire = ((apercu.get('bilan') or {}).get('horaire')) or []
    charges = _charges_par_jour_type(apercu)
    cellules = []
    for bloc in horaire:
        if not isinstance(bloc, dict):
            continue
        mois = bloc.get('mois')
        n = _f(bloc.get('nb_jours'))
        auto = bloc.get('autoconso_kwh') or []
        charge = charges.get((mois, bloc.get('type_jour')))
        for h in range(24):
            a = _f(auto[h]) if h < len(auto) else 0.0
            c = None
            if charge is not None and h < len(charge):
                c = _f(charge[h])
                a = min(a, c)
            cellules.append((mois, h, a * n, None if c is None else c * n))
    return cellules


def _tension(apercu, tarif):
    if tarif.get('contrat') == 'mt_general':
        return 'mt'
    er = apercu.get('entrees_resolues') or {}
    t = er.get('tension')
    if isinstance(t, dict):
        t = t.get('valeur')
    return (t or 'bt').lower()


def _revente_bt(apercu):
    bilan = apercu.get('bilan') or {}
    non_valorise = bilan.get('non_valorise_kwh')
    if non_valorise is None:
        non_valorise = bilan.get('surplus_kwh')
    hyp = []
    if non_valorise is not None:
        hyp.append({'cle': 'surplus_non_valorise_kwh',
                    'valeur': non_valorise, 'statut': 'source',
                    'source': 'etude_ci.bilan'})
    return {
        'statut': 'absente_bt',
        'kwh_an': None,
        'plafond_kwh': None,
        'tarifs': [],
        'valeur_mad_an': None,
        'mentions': [MENTION_BT, MENTION_ART13],
        'hypotheses': hyp,
    }


def _ligne(poste, kwh, ht, ttc):
    return {'poste': poste, 'kwh_evites': int(round(kwh)),
            'tarif_kwh': ht, 'mad': round(kwh * ht, 2),
            'tarif_kwh_ttc': ttc, 'mad_ttc': round(kwh * ttc, 2)}


def _valoriser_mt(cellules, tarif):
    prix = {p['poste']: p for p in tarif['tarifs_par_poste']}
    evites = dict.fromkeys(_POSTES_MT, 0.0)
    avant = dict.fromkeys(_POSTES_MT, 0.0)
    charge_connue = all(c is not None for _m, _h, _a, c in cellules)
    for mois, h, a, c in cellules:
        entree = tarif_ci.tarif_du_poste(tarif, mois, h)
        if entree is None:
            continue
        evites[entree['poste']] += a
        if c is not None:
            avant[entree['poste']] += c
    par_poste = [_ligne(p, evites[p], prix[p]['tarif_kwh_ht'],
                        prix[p]['tarif_kwh_ttc'])
                 for p in _POSTES_MT if evites[p] > 0]
    if not charge_connue:
        return par_poste, None, None
    fav, fap = [], []
    for p in _POSTES_MT:
        ht, ttc = prix[p]['tarif_kwh_ht'], prix[p]['tarif_kwh_ttc']
        apres = max(0.0, avant[p] - evites[p])
        fav.append({'poste': p, 'kwh': int(round(avant[p])),
                    'mad_ht': round(avant[p] * ht, 2),
                    'mad_ttc': round(avant[p] * ttc, 2)})
        fap.append({'poste': p, 'kwh': int(round(apres)),
                    'mad_ht': round(apres * ht, 2),
                    'mad_ttc': round(apres * ttc, 2)})
    return par_poste, fav, fap


def _kwh_par_tranche(conso, seuils):
    out = []
    for lo, hi in seuils:
        lo = lo or 0.0
        haut = conso if hi is None else min(conso, hi)
        out.append(max(0.0, haut - lo))
    return out


def _valoriser_bt(cellules, tarif, apercu, tarif_declare):
    postes = tarif['tarifs_par_poste']
    seuils = tarif_ci._seuils_bt(tarif, tarif_declare)
    if seuils is None or len(seuils) != len(postes):
        return None
    conso_mois = {}
    auto_mois = {}
    charge_connue = all(c is not None for _m, _h, _a, c in cellules)
    for mois, _h, a, c in cellules:
        auto_mois[mois] = auto_mois.get(mois, 0.0) + a
        if c is not None:
            conso_mois[mois] = conso_mois.get(mois, 0.0) + c
    if not charge_connue:
        for pm in ((apercu.get('bilan') or {}).get('par_mois') or []):
            if isinstance(pm, dict) and pm.get('consommation_kwh') is not None:
                conso_mois[pm.get('mois')] = _f(pm.get('consommation_kwh'))
    if not conso_mois:
        return None
    evites = [0.0] * len(postes)
    kwh_avant = [0.0] * len(postes)
    kwh_apres = [0.0] * len(postes)
    for mois, conso in conso_mois.items():
        auto = min(auto_mois.get(mois, 0.0), conso)
        av = _kwh_par_tranche(conso, seuils)
        ap = _kwh_par_tranche(conso - auto, seuils)
        for i in range(len(postes)):
            kwh_avant[i] += av[i]
            kwh_apres[i] += ap[i]
            evites[i] += av[i] - ap[i]
    par_poste = [_ligne(p['poste'], evites[i], p['tarif_kwh_ht'],
                        p['tarif_kwh_ttc'])
                 for i, p in enumerate(postes) if evites[i] > 0]
    nom = '+'.join(p['poste'] for p in postes)

    def _facture(kwhs):
        return [{'poste': nom,
                 'mad_ht': round(sum(k * p['tarif_kwh_ht']
                                     for k, p in zip(kwhs, postes)), 2),
                 'mad_ttc': round(sum(k * p['tarif_kwh_ttc']
                                      for k, p in zip(kwhs, postes)), 2)}]
    return par_poste, _facture(kwh_avant), _facture(kwh_apres)


def valoriser(apercu_ci, tarif, *, millesime=2026, tarif_declare=None,
              facture_energie_declaree_ttc=None):
    """La valorisation horaire d'une étude C&I (forme ``economie_ci``).

    ``tarif`` = sortie de ``tarif_ci.tarif_applicable`` (``omis`` ⇒ statut
    omis + motif nommé). ``tarif_declare`` sert aux seuils des tranches BT
    déclarées. ``facture_energie_declaree_ttc`` : quand la consommation a été
    INVERSÉE d'une facture en MAD au barème national (QJR665), l'économie est
    plafonnée à cette énergie déclarée et étiquetée « consommation estimée ».
    ``millesime`` est porté par ``tarif`` (tva_millesime) ; il est accepté ici
    pour l'appelant et n'altère aucun prix.
    """
    del millesime  # le millésime vit dans ``tarif`` (tva_millesime)
    apercu = apercu_ci if isinstance(apercu_ci, dict) else {}
    if not isinstance(tarif, dict) or tarif.get('origine') == \
            tarif_ci.ORIGINE_OMIS or not tarif.get('tarifs_par_poste'):
        return _vide(MOTIF_TARIF_OMIS, tarif)
    if any(p['poste'] in ('normales',) for p in tarif['tarifs_par_poste']):
        return _vide(MOTIF_BI_HORAIRE, tarif)
    cellules = _cellules(apercu)
    if not cellules:
        return _vide(MOTIF_SANS_HORAIRE, tarif)

    tension = _tension(apercu, tarif)
    if tarif.get('contrat') == 'mt_general':
        res = _valoriser_mt(cellules, tarif)
    else:
        res = _valoriser_bt(cellules, tarif, apercu, tarif_declare)
        if res is None:
            return _vide(MOTIF_SANS_HORAIRE, tarif)
    par_poste, fav, fap = res

    total_ht = round(sum(p['mad'] for p in par_poste), 2)
    total_ttc = round(sum(p['mad_ttc'] for p in par_poste), 2)
    hypotheses = []
    cap = facture_energie_declaree_ttc
    try:
        cap = None if cap is None else float(cap)
    except (TypeError, ValueError):
        cap = None
    if cap is not None and cap >= 0:
        hypotheses.append({'cle': 'consommation', 'valeur': None,
                           'statut': 'estimation',
                           'source': ETIQUETTE_CONSO_ESTIMEE})
        if total_ttc > cap and total_ttc > 0:
            facteur = cap / total_ttc
            for p in par_poste:
                p['kwh_evites'] = int(round(p['kwh_evites'] * facteur))
                p['mad'] = round(p['mad'] * facteur, 2)
                p['mad_ttc'] = round(p['mad_ttc'] * facteur, 2)
            total_ht = round(sum(p['mad'] for p in par_poste), 2)
            total_ttc = round(sum(p['mad_ttc'] for p in par_poste), 2)

    avant_ht = sum(e['mad_ht'] for e in fav) if fav else None
    part = (round(total_ht / avant_ht * 100, 1)
            if avant_ht else None)
    prime = tarif.get('prime_fixe_annuelle_mad')
    return {
        'statut': STATUT_CALCULE,
        'motifs_omission': [],
        'tarif': tarif,
        'economie_annee1': {
            'par_poste': par_poste,
            'total_mad': total_ht,
            'total_mad_ttc': total_ttc,
            'part_facture_energie_pct': part,
        },
        'facture_avant': (None if fav is None else
                          {'energie_par_poste': fav, 'prime_fixe_mad': prime}),
        'facture_apres': (None if fap is None else
                          {'energie_par_poste': fap, 'prime_fixe_mad': prime}),
        # BT : aucune ligne de revente ; MT : valorisée par l'étape dédiée,
        # seulement si la revente est demandée (jamais ici).
        'revente': _revente_bt(apercu) if tension != 'mt' else None,
        'hypotheses': hypotheses,
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIQ205 — moteur ``economie_ci`` (2/6) : base HT si la TVA est récupérable,
# TTC sinon, les deux bases côte à côte quand c'est inconnu (D-CIQ-3).
# ═════════════════════════════════════════════════════════════════════════════
# Un assujetti récupère la TVA (10 % panneaux, 20 % le reste, 20 % sur
# l'électricité en 2026) : son retour se compte HT/HT. Une clinique exonérée
# sans droit à déduction (CGI art. 91) ou un commerce hors champ supporte
# vraiment le TTC. Inconnu ⇒ les DEUX bases (un TTC seul raccourcirait de 3 à
# 5 % le retour d'un assujetti ; les deux bases ne surestiment jamais). AUCUN
# défaut tiré de la catégorie. La chaîne du document (HT → TVA → TTC) et la
# saisie 100 % TTC du générateur ne changent pas.

TVA_OUI = 'oui'
TVA_NON = 'non'
TVA_INCONNU = 'inconnu'
TVA_VALEURS = (TVA_OUI, TVA_NON, TVA_INCONNU)
#: Provenances admises de la saisie (contrat ``economie_ci.json``).
TVA_PROVENANCES = ('lead', 'declare_client')

BASE_HT = 'ht'
BASE_TTC = 'ttc'
BASE_DEUX = 'deux'

MOTIF_BASE_HT = "TVA récupérable déclarée « oui » : économies en HT (D-CIQ-3)"
MOTIF_BASE_TTC = (
    "TVA non récupérable déclarée « non » : économies en TTC (D-CIQ-3)")
MOTIF_BASE_DEUX = (
    "statut TVA non déclaré : les deux bases sont montrées (HT et TTC, "
    "D-CIQ-3)")


class SaisieEconomieCiInvalide(ValueError):
    """Une saisie de ``saisies_economie_ci`` REFUSÉE — ``champ`` la nomme."""

    def __init__(self, message, *, champ):
        super().__init__(message)
        self.champ = champ


def _valeur_tva(brute):
    """'oui' | 'non' | None (« ne sait pas », vide ou inconnu)."""
    if isinstance(brute, dict):
        brute = brute.get('valeur')
    if not isinstance(brute, str):
        return None
    v = brute.strip().lower()
    return v if v in (TVA_OUI, TVA_NON) else None


def lire_saisie_tva(saisie):
    """Normalise ``saisies_economie_ci.tva_recuperable`` (idempotent).

    ``None`` / vide ⇒ ``None``. Sinon ``{valeur, provenance, saisi_le}`` ;
    une valeur hors {oui, non, inconnu} est refusée en nommant le champ.
    Normaliser une saisie déjà normalisée la rend INCHANGÉE (enregistrer →
    rouvrir → enregistrer sans toucher = saisie identique).
    """
    champ = 'saisies_economie_ci.tva_recuperable'
    if saisie in (None, '', {}):
        return None
    if isinstance(saisie, str):
        saisie = {'valeur': saisie}
    if not isinstance(saisie, dict):
        raise SaisieEconomieCiInvalide(
            f"{champ} : un objet {{valeur, provenance, saisi_le}} est "
            "attendu.", champ=champ)
    valeur = str(saisie.get('valeur') or '').strip().lower()
    if valeur not in TVA_VALEURS:
        raise SaisieEconomieCiInvalide(
            f"{champ}.valeur : choisir parmi {', '.join(TVA_VALEURS)}.",
            champ=f'{champ}.valeur')
    provenance = saisie.get('provenance') or 'declare_client'
    if provenance not in TVA_PROVENANCES:
        raise SaisieEconomieCiInvalide(
            f"{champ}.provenance : choisir parmi "
            f"{', '.join(TVA_PROVENANCES)}.", champ=f'{champ}.provenance')
    return {'valeur': valeur, 'provenance': provenance,
            'saisi_le': saisie.get('saisi_le') or None}


def resoudre_tva_recuperable(valeur_lead=None, saisie=None):
    """La TVA récupérable RETENUE : le lead d'abord, puis la saisie.

    ``valeur_lead`` = ``Lead.tva_recuperable`` (oui | non | ne_sait_pas | vide,
    lu par l'orchestrateur via ``crm.selectors``) ; ``saisie`` =
    ``saisies_economie_ci.tva_recuperable``. Rien de déclaré ⇒ ``inconnu`` —
    jamais un défaut tiré de la catégorie.
    """
    lead = _valeur_tva(valeur_lead)
    if lead is not None:
        return {'valeur': lead, 'provenance': 'lead', 'saisi_le': None}
    lu = lire_saisie_tva(saisie)
    if lu is not None and lu['valeur'] in (TVA_OUI, TVA_NON):
        return lu
    return {'valeur': TVA_INCONNU,
            'provenance': (lu or {}).get('provenance'),
            'saisi_le': (lu or {}).get('saisi_le')}


def _montant(v):
    try:
        if v is None or isinstance(v, bool):
            return None
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, 2) if x >= 0 else None


def base_economique(tva_recuperable, *, investissement=None,
                    economie_annee1=None):
    """La base économique d'un devis C&I (D-CIQ-3).

    ``tva_recuperable`` : sortie de :func:`resoudre_tva_recuperable` (ou la
    valeur nue oui | non | inconnu). ``investissement`` : totaux de l'option
    retenue ``{ht, ttc}`` (``utils.options.option_totaux``, recalculés côté
    serveur). ``economie_annee1`` : le bloc de :func:`valoriser`
    (``total_mad`` = HT, ``total_mad_ttc`` = TTC : prix déclarés HT, ou TTC ÷
    (1 + TVA énergie du millésime) via ``tarif_ci``).

    Retour : ``{base, motif_base, tva_recuperable, investissement_ht_mad,
    investissement_ttc_mad, economie_annee1_ht_mad, economie_annee1_ttc_mad,
    base_amortissable_mad, flux}`` — ``flux`` liste les flux à construire
    (``flux_ht`` / ``flux_ttc`` / les deux).
    """
    if isinstance(tva_recuperable, dict):
        valeur = tva_recuperable.get('valeur')
    else:
        valeur = tva_recuperable
    valeur = valeur if valeur in TVA_VALEURS else TVA_INCONNU
    if valeur == TVA_OUI:
        base, motif, flux = BASE_HT, MOTIF_BASE_HT, ['flux_ht']
    elif valeur == TVA_NON:
        base, motif, flux = BASE_TTC, MOTIF_BASE_TTC, ['flux_ttc']
    else:
        base, motif, flux = BASE_DEUX, MOTIF_BASE_DEUX, ['flux_ht', 'flux_ttc']

    inv = investissement if isinstance(investissement, dict) else {}
    inv_ht, inv_ttc = _montant(inv.get('ht')), _montant(inv.get('ttc'))
    eco = economie_annee1 if isinstance(economie_annee1, dict) else {}
    eco_ht = _montant(eco.get('total_mad'))
    eco_ttc = _montant(eco.get('total_mad_ttc'))
    # Base amortissable (CIQ233) : HT quand la TVA se récupère, TTC quand
    # elle est supportée ; inconnue tant que le statut n'est pas déclaré.
    amortissable = {BASE_HT: inv_ht, BASE_TTC: inv_ttc}.get(base)
    return {
        'base': base,
        'motif_base': motif,
        'tva_recuperable': valeur,
        'investissement_ht_mad': inv_ht,
        'investissement_ttc_mad': inv_ttc,
        'economie_annee1_ht_mad': eco_ht,
        'economie_annee1_ttc_mad': eco_ttc,
        'base_amortissable_mad': amortissable,
        'flux': flux,
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIQ206 — moteur ``economie_ci`` (3/6) : UN flux 25 ans par
# ``economie.flux_de_tresorerie``, jalons 5/10/15/20/25, TRI avec son
# horizon, VAN sur le seul taux DÉCLARÉ du client, coût du kWh solaire à côté
# du tarif évité.
# ═════════════════════════════════════════════════════════════════════════════
# AUCUNE seconde arithmétique : le flux est celui de ``flux_de_tresorerie``
# (economie.py n'est pas modifié) ; ce module ne fait que lui passer des
# hypothèses EXPLICITES et sourcées. La revente (CIQ207) n'entre JAMAIS dans
# le flux de tête.

#: Horizon d'analyse C&I (D-CIQ-10).
HORIZON_CI_ANS = 25
HORIZON_CI_SOURCE = 'D-CIQ-10 : 25 ans'
#: Jalons publiés du cumul (D-CIQ-10).
JALONS_CI_ANS = (5, 10, 15, 20, 25)
#: Indexation : tarif de vente CONSTANT (QX39 / QRES54), saisie à 0.
MENTION_INDEXATION_CONSTANTE = 'tarif de vente constant (hypothèse)'
#: Dégradation annuelle des modules : médiane publiée, source unique
#: ``quote_engine.pricing.PANEL_DEGRADATION``.
DEGRADATION_CI_SOURCE = 'médiane Jordan & Kurtz, NREL/JA-5200-51664, 2012'
#: Remplacement de l'onduleur à mi-vie (``pricing.INVERTER_REPLACE_YEAR`` ;
#: principe IEA PVPS), au montant RÉEL de sa ligne (décision Q1 du 20/08).
ONDULEUR_MOTIF = "remplacement à mi-vie (principe IEA PVPS, décision Q1 du " \
                 "20/08/2026), au montant réel de la ligne onduleur du devis"
MOTIF_SANS_ONDULEUR = (
    "aucune ligne onduleur dans le devis — aucun remplacement porté au flux")
MOTIF_VAN_OMISE = (
    "VAN omise : taux d'actualisation non déclaré par le client")
MOTIF_LCOE_NON_ACTUALISE = (
    "coût moyen NON actualisé : coût total ÷ production totale sur 25 ans "
    "(aucun taux d'actualisation déclaré par le client)")
MOTIF_OM_PROPOSE = "O&M proposé, non souscrit — non déduit"
MOTIF_OM_SANS_PRIX = "tarif O&M à renseigner — non déduit"
MOTIF_OM_ABSENT = "aucune option O&M sur le devis — aucune charge annuelle"


def _pricing():
    from apps.ventes.quote_engine import pricing
    return pricing


def lire_taux_client(saisie):
    """``saisies_economie_ci.taux_actualisation_client`` validé, ou None.

    ``{valeur_pct, source, saisi_le}`` ; un taux sans source est refusé en
    nommant ``taux_actualisation_client.source`` (D-CIQ-10 : seul le taux
    DÉCLARÉ par le client ouvre la VAN).
    """
    if saisie in (None, '', {}):
        return None
    champ = 'taux_actualisation_client'
    if not isinstance(saisie, dict):
        raise SaisieEconomieCiInvalide(
            f"{champ} : un objet {{valeur_pct, source, saisi_le}} est "
            "attendu.", champ=champ)
    brut = saisie.get('valeur_pct')
    if brut is None or brut == '':
        return None
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        valeur = None
    if valeur is None or valeur != valeur or valeur <= -100:
        raise SaisieEconomieCiInvalide(
            f"{champ}.valeur_pct : un taux en % (> −100) est attendu.",
            champ=f'{champ}.valeur_pct')
    source = str(saisie.get('source') or '').strip()
    if not source:
        raise SaisieEconomieCiInvalide(
            f"{champ}.source : le taux d'actualisation doit porter sa source "
            "(déclaré par le client).", champ=f'{champ}.source')
    return {'valeur_pct': valeur, 'source': source,
            'saisi_le': saisie.get('saisi_le') or None}


def _om(om, cle_base):
    """``(charge annuelle | None, bloc om du contrat)`` (D-CIQ-12).

    ``om`` : ``{activee, ht, ttc, source}`` lu de la ligne O&M du devis (rôle
    du contrat CIQ7) ou None. Activée avec prix ⇒ charge déduite ; activée
    sans prix ⇒ « tarif O&M à renseigner » ; optionnelle ⇒ « proposé, non
    souscrit — non déduit ».
    """
    if not isinstance(om, dict):
        return None, {'statut': 'absent', 'montant_mad_an': None,
                      'source': MOTIF_OM_ABSENT}
    montant = _montant(om.get(cle_base))
    if not om.get('activee'):
        return None, {'statut': 'propose', 'montant_mad_an': montant,
                      'source': MOTIF_OM_PROPOSE}
    if montant is None:
        return None, {'statut': 'tarif_a_renseigner', 'montant_mad_an': None,
                      'source': MOTIF_OM_SANS_PRIX}
    source = str(om.get('source') or '').strip() or \
        'ligne O&M souscrite du devis'
    return montant, {'statut': 'souscrit', 'montant_mad_an': montant,
                     'source': source}


def _un_flux(investissement, economie, *, production, taux, onduleur, charge,
             om_bloc, cle_base, collecteur=None):
    from apps.ventes import economie as eco_mod
    pricing = _pricing()
    deg_pct = pricing.PANEL_DEGRADATION * 100.0
    remplacements = []
    montant_onduleur = None if onduleur is None else _montant(
        onduleur.get(cle_base))
    if montant_onduleur is not None:
        remplacements.append({
            'equipement': 'onduleur',
            'annee': pricing.INVERTER_REPLACE_YEAR,
            'mode': 'remplacer',
            'montant_mad': montant_onduleur,
            'source': str(onduleur.get('source') or '').strip()
            or 'ligne onduleur du devis'})
    taux_brut = None if taux is None else {
        'valeur': taux['valeur_pct'],
        'source': f"déclaré par le client — {taux['source']}",
        'saisie_le': taux['saisi_le']}
    libelle = 'HT' if cle_base == 'ht' else 'TTC'
    investissement = {'valeur': investissement,
                      'source': f"devis — total {libelle} de l'option retenue"}
    economie = {'valeur': economie,
                'source': 'economie_ci.economie_annee1 (valorisation horaire '
                          'au tarif du poste)'}
    production = {'valeur': production,
                  'source': 'etude_ci.bilan (moteur C&I)'}
    charge_brute = None if charge is None else {
        'valeur': charge, 'source': om_bloc['source']}
    entrees = dict(
        investissement_mad=investissement,
        economie_annee1_mad=economie,
        production_annee1_kwh=production,
        horizon_ans={'valeur': HORIZON_CI_ANS, 'source': HORIZON_CI_SOURCE},
        taux_actualisation_pct=taux_brut,
        indexation_pct={'valeur': 0.0,
                        'source': MENTION_INDEXATION_CONSTANTE},
        degradation_pct={'valeur': deg_pct, 'source': DEGRADATION_CI_SOURCE},
        charges_annuelles_mad=charge_brute,
        remplacements=remplacements)
    if collecteur is not None:
        # CIQ231 — les entrées EXACTES du flux de base, relancées par
        # :func:`sensibilites_ci` en ne changeant qu'UNE grandeur.
        collecteur[cle_base] = entrees
    bloc = eco_mod.flux_de_tresorerie(**entrees)
    omissions = [o for o in bloc['omissions']
                 if o['cle'] not in ('remplacements', 'charges_annuelles_mad')]
    if montant_onduleur is None:
        omissions.append({'cle': 'remplacements',
                          'motif': MOTIF_SANS_ONDULEUR})
    if charge is None:
        omissions.append({'cle': 'charges_annuelles_mad',
                          'motif': om_bloc['source']})
    lcoe_actualise = taux is not None
    if taux is None and bloc['flux'] and production['valeur']:
        # Coût moyen NON actualisé, étiqueté : le même calcul LCOE du module
        # economie à un taux de 0 (= coût total ÷ production totale).
        lcoe = eco_mod.lcoe(
            investissement_mad=investissement,
            charges_annuelles_mad=charge_brute,
            production_annuelle_kwh=production,
            horizon_ans=HORIZON_CI_ANS,
            taux_actualisation_pct={'valeur': 0.0,
                                    'source': MOTIF_LCOE_NON_ACTUALISE},
            degradation_pct={'valeur': deg_pct,
                             'source': DEGRADATION_CI_SOURCE},
            remplacements=remplacements)['lcoe_mad_kwh']
        bloc['lcoe_mad_kwh'] = lcoe
        omissions = [o for o in omissions if o['cle'] != 'lcoe_mad_kwh']
        omissions.append({'cle': 'lcoe_actualise',
                          'motif': MOTIF_LCOE_NON_ACTUALISE})
    if taux is None:
        omissions = [o for o in omissions
                     if o['cle'] not in ('van_mad', 'retour_actualise_ans')]
        omissions.append({'cle': 'van_mad', 'motif': MOTIF_VAN_OMISE})
    bloc['omissions'] = omissions
    remplacement = None
    if montant_onduleur is not None:
        remplacement = {
            'composant': 'onduleur',
            'annee': pricing.INVERTER_REPLACE_YEAR,
            'montant_ttc_mad': _montant(onduleur.get('ttc')),
            'montant_ht_mad': _montant(onduleur.get('ht')),
            'source': remplacements[0]['source'],
            'motif': ONDULEUR_MOTIF,
        }
    return bloc, remplacement, lcoe_actualise


def _jalons(bloc):
    if not bloc or not bloc.get('flux'):
        return []
    par_annee = {f['annee']: f['cumul_mad'] for f in bloc['flux']}
    return [{'annee': a, 'cumul_mad': par_annee.get(a)}
            for a in JALONS_CI_ANS if a in par_annee]


def flux_ci(base_eco, *, production_annee1_kwh=None, kwh_evites_an=None,
            onduleur=None, om=None, taux_actualisation_client=None,
            collecteur=None):
    """Le flux 25 ans d'un devis C&I et ses indicateurs (forme
    ``economie_ci.json`` : ``flux_ht`` / ``flux_ttc``, ``jalons``,
    ``indicateurs``, ``remplacements``, ``om``).

    ``base_eco`` : sortie de :func:`base_economique`. ``onduleur`` :
    ``{ht, ttc, source}`` = montant RÉEL des lignes onduleur du devis (None =
    aucune ligne : omission nommée). ``om`` : voir :func:`_om`.
    ``taux_actualisation_client`` : saisie brute (validée par
    :func:`lire_taux_client`). La revente n'entre jamais ici.
    ``collecteur`` (CIQ231) : dict facultatif qui reçoit, par base
    (``ht``/``ttc``), les entrées exactes passées à ``flux_de_tresorerie``.
    """
    taux = lire_taux_client(taux_actualisation_client)
    sortie = {'base': base_eco['base'], 'motif_base': base_eco['motif_base'],
              'flux_ht': None, 'flux_ttc': None, 'jalons': [],
              'indicateurs': None, 'remplacements': [], 'om': None}
    principal = 'flux_ttc' if base_eco['base'] == BASE_TTC else 'flux_ht'
    actualise = False
    for cle in base_eco['flux']:
        cle_base = 'ht' if cle == 'flux_ht' else 'ttc'
        charge, om_bloc = _om(om, cle_base)
        bloc, remplacement, actualise_ = _un_flux(
            base_eco[f'investissement_{cle_base}_mad'],
            base_eco[f'economie_annee1_{cle_base}_mad'],
            production=production_annee1_kwh, taux=taux, onduleur=onduleur,
            charge=charge, om_bloc=om_bloc, cle_base=cle_base,
            collecteur=collecteur)
        sortie[cle] = bloc
        if cle == principal:
            sortie['om'] = om_bloc
            actualise = actualise_
            if remplacement is not None:
                sortie['remplacements'] = [remplacement]
    bloc = sortie[principal]
    sortie['jalons'] = _jalons(bloc)
    if base_eco['base'] == BASE_DEUX:
        sortie['jalons_ttc'] = _jalons(sortie['flux_ttc'])
    economie = base_eco[
        'economie_annee1_' + ('ttc' if principal == 'flux_ttc' else 'ht')
        + '_mad']
    kwh = _montant(kwh_evites_an)
    sortie['indicateurs'] = {
        'tri_pct': bloc['tri_pct'],
        'tri_horizon_ans': HORIZON_CI_ANS,
        'retour_ans': bloc['retour_ans'],
        'van_mad': bloc['van_mad'],
        'van_motif': None if taux is not None else MOTIF_VAN_OMISE,
        'lcoe_mad_kwh': bloc['lcoe_mad_kwh'],
        'lcoe_actualise': actualise,
        'tarif_kwh_evite_moyen': (round(economie / kwh, 4)
                                  if economie is not None and kwh else None),
    }
    return sortie


# ═════════════════════════════════════════════════════════════════════════════
# CIQ207 — moteur ``economie_ci`` (4/6) : revente 82-21 du surplus HORAIRE,
# MT/HT seulement, au tarif ANRE brut HT, plafonnée à 20 % de la production
# annuelle, potentiel non garanti tenu HORS du retour.
# ═════════════════════════════════════════════════════════════════════════════
# Le tarif d'excédent ANRE (décision 04/26 art. 6-7) ne vise que MT/HT/THT ;
# en BT il sera « fixé ultérieurement » ⇒ aucune ligne chiffrée. Le surplus
# est la SOMME des cellules horaires de surplus de l'aperçu (CIQ2), jamais un
# solde annuel production − autoconsommé. Aucune déduction TURD/TURT
# (D-CIQ-4). La revente est une LIGNE À CÔTÉ : jamais additionnée au retour
# ni au TRI de tête (:func:`flux_ci` ne la reçoit pas).

TENSIONS_REVENTE = ('mt', 'ht', 'tht')
MENTION_NON_GARANTI = (
    "Potentiel annuel plafonné, non garanti : écrêtement et arrêts sans "
    "compensation (loi 82-21 art. 32).")
MENTION_SECOND_COMPTEUR = (
    "Second compteur de l'énergie autoproduite exigé (ANRE 04/26 art. 9).")
MENTION_TSS = (
    "TSS éventuelle sur l'énergie injectée non déduite (ANRE 02/25 §4).")
MENTION_TARIF_ARRETE = (
    "Tarif arrêté à la signature de la convention puis indexé sur le tarif "
    "général moyen (ANRE 04/26 art. 10) — tenu constant ici, aucune "
    "indexation supposée.")
MENTION_REVENTE_IGNOREE_BT = (
    "Revente demandée : ignorée en basse tension (aucun tarif d'excédent BT).")
MOTIF_TENSION_INCONNUE = (
    "tension de raccordement non déclarée : revente non évaluée")
MOTIF_PRODUCTION_INCONNUE = (
    "production annuelle inconnue : plafond légal de 20 % non calculable — "
    "revente non chiffrée")


def _revente_omise(motif, hypotheses):
    return {'statut': 'omise', 'kwh_an': None, 'plafond_kwh': None,
            'tarifs': [], 'valeur_mad_an': None,
            'mentions': [motif, MENTION_ART13], 'hypotheses': hypotheses}


def _surplus_par_poste(apercu):
    """{'pointe': kWh, 'hors_pointe': kWh} des cellules horaires (GMT)."""
    officiels = tarif_ci.officiels
    out = {'pointe': 0.0, 'hors_pointe': 0.0}
    horaire = ((apercu.get('bilan') or {}).get('horaire')) or []
    for bloc in horaire:
        if not isinstance(bloc, dict):
            continue
        n = _f(bloc.get('nb_jours'))
        surplus = bloc.get('surplus_kwh') or []
        for h in range(min(24, len(surplus))):
            kwh = _f(surplus[h]) * n
            if not kwh:
                continue
            poste = officiels.poste_horaire(bloc.get('mois'), h)
            out['pointe' if poste == 'pointe' else 'hors_pointe'] += kwh
    return out


def revente_ci(apercu_ci, *, tension, revente_demandee,
               date_signature_prevue=None, production_annuelle_kwh=None):
    """La revente 82-21 du surplus d'un site C&I (forme ``revente`` du
    contrat ``economie_ci.json``), ou ``None`` (MT sans revente demandée).

    ``production_annuelle_kwh`` : production du site (défaut :
    ``bilan.production_kwh`` de l'aperçu) — base du plafond légal de 20 %.
    """
    from apps.ventes.quote_engine import constants_82_21 as c8221
    apercu = apercu_ci if isinstance(apercu_ci, dict) else {}
    t = (tension or '').strip().lower() if isinstance(tension, str) else None
    if t and t not in TENSIONS_REVENTE:
        bloc = _revente_bt(apercu)
        if revente_demandee:
            bloc['mentions'].append(MENTION_REVENTE_IGNOREE_BT)
        return bloc
    if not revente_demandee:
        return None
    hypotheses = [{'cle': 'revente_demandee', 'valeur': True,
                   'statut': 'declare',
                   'source': 'saisies_economie_ci.revente_demandee'}]
    if not t:
        return _revente_omise(MOTIF_TENSION_INCONNUE, hypotheses)
    tarif, motif = c8221.tarif_excedent_en_vigueur(date_signature_prevue)
    if tarif is None:
        return _revente_omise(motif, hypotheses)
    production = production_annuelle_kwh
    if production is None:
        production = (apercu.get('bilan') or {}).get('production_kwh')
    production = _f(production)
    if not production:
        return _revente_omise(MOTIF_PRODUCTION_INCONNUE, hypotheses)

    par_poste = _surplus_par_poste(apercu)
    surplus = sum(par_poste.values())
    plafond = production * c8221.PLAFOND_INJECTION_PCT / 100.0
    kwh_an = min(surplus, plafond)
    facteur = kwh_an / surplus if surplus else 0.0
    prix = {'pointe': tarif['pointe'], 'hors_pointe': tarif['hors_pointe']}
    tarifs, valeur = [], 0.0
    for poste in ('pointe', 'hors_pointe'):
        kwh = par_poste[poste] * facteur
        if kwh <= 0:
            continue
        tarifs.append({'poste': poste, 'kwh': int(round(kwh)),
                       'tarif_kwh_ht': prix[poste]})
        valeur += kwh * prix[poste]
    hypotheses.append({'cle': 'surplus_horaire_kwh',
                       'valeur': int(round(surplus)), 'statut': 'source',
                       'source': 'etude_ci.bilan.horaire (somme des heures '
                                 'de surplus)'})
    return {
        'statut': 'calculee',
        'kwh_an': int(round(kwh_an)),
        'plafond_kwh': int(round(plafond)),
        'tarifs': tarifs,
        'valeur_mad_an': round(valeur, 2),
        'mentions': [c8221.MENTION_82_21, MENTION_NON_GARANTI,
                     MENTION_SECOND_COMPTEUR, MENTION_TSS,
                     MENTION_TARIF_ARRETE, MENTION_ART13],
        'hypotheses': hypotheses,
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIQ208 — moteur ``economie_ci`` (5/6) : financement construit UNIQUEMENT
# depuis l'offre ÉCRITE d'un prêteur ou d'un bailleur (D-CIQ-15).
# ═════════════════════════════════════════════════════════════════════════════
# Aucun taux inventé : un taux ÉCRIT sur l'offre ⇒ échéancier par
# ``economie.tableau_pret`` (la seule formule d'annuité du dépôt) ; sinon
# l'échéance TAPÉE telle quelle, sans taux calculé. Le mot « crédit-bail »
# n'apparaît dans aucune sortie tant que ``TariffSettings.
# mention_credit_bail_autorisee`` (CIQ211) est faux (avis juridique d'abord,
# loi 82-21 art. 2). PV80 tient : aucun financement hors commercial /
# industriel.

NATURES_FINANCEMENT = ('credit', 'credit_bail')
MODES_FINANCEMENT_CI = ('commercial', 'industriel')
SOURCE_FINANCEMENT = 'offre écrite saisie par le vendeur'


def _date_courte(iso):
    import datetime as _dt
    try:
        return _dt.date.fromisoformat(str(iso)[:10]).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return None


def _libelle_financement(offre, nature, credit_bail_autorise):
    if nature == 'credit':
        tete = 'Offre de crédit'
    elif credit_bail_autorise:
        tete = 'Offre de crédit-bail'
    else:
        tete = 'Offre de financement'
    reference = str(offre.get('reference_offre') or '').strip()
    preteur = str(offre.get('preteur') or '').strip()
    if not reference:
        return tete  # le prêteur n'est nommé qu'avec la référence de l'offre
    morceaux = [tete]
    if preteur:
        morceaux.append(f'de {preteur}')
    date = _date_courte(offre.get('date_offre'))
    if date:
        morceaux.append(f'du {date}')
    return ' '.join(morceaux) + f' (réf. {reference})'


def _nombre_offre(offre, cle, *, entier=False, requis=False):
    champ = f'offre_financement.{cle}'
    brut = offre.get(cle)
    if brut is None or brut == '':
        if requis:
            raise SaisieEconomieCiInvalide(
                f"{champ} : à saisir depuis l'offre écrite.", champ=champ)
        return None
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        valeur = None
    if valeur is None or valeur != valeur or valeur < 0 or (
            entier and (valeur != int(valeur) or valeur < 1)):
        raise SaisieEconomieCiInvalide(
            f"{champ} : valeur « {brut} » refusée.", champ=champ)
    return int(valeur) if entier else valeur


def financement_ci(offre, base_eco, *, mode_installation,
                   mention_credit_bail_autorisee=False):
    """Le bloc ``financement`` du contrat ``economie_ci.json``, ou ``None``.

    ``offre`` = ``saisies_economie_ci.offre_financement`` (None ⇒ aucun
    financement). ``base_eco`` : sortie de :func:`base_economique` (économie
    de l'année 1 en HT et TTC). ``mention_credit_bail_autorisee`` : réglage
    ``TariffSettings`` (CIQ211), lu par l'orchestrateur. Refus nommés
    ``offre_financement.<champ>`` (:class:`SaisieEconomieCiInvalide`).
    """
    mode = str(mode_installation or '').strip().lower()
    if mode not in MODES_FINANCEMENT_CI or offre in (None, {}):
        return None  # PV80 : jamais de financement résidentiel
    if not isinstance(offre, dict):
        raise SaisieEconomieCiInvalide(
            "offre_financement : un objet est attendu.",
            champ='offre_financement')
    if not str(offre.get('source') or '').strip():
        raise SaisieEconomieCiInvalide(
            "offre_financement.source : le financement se construit "
            "seulement depuis une offre ÉCRITE (« offre écrite de <prêteur> "
            "du <date> »).", champ='offre_financement.source')
    nature = offre.get('nature')
    if nature not in NATURES_FINANCEMENT:
        raise SaisieEconomieCiInvalide(
            f"offre_financement.nature : choisir parmi "
            f"{', '.join(NATURES_FINANCEMENT)}.",
            champ='offre_financement.nature')
    base_echeance = offre.get('base_echeance')
    if base_echeance not in ('ht', 'ttc'):
        raise SaisieEconomieCiInvalide(
            "offre_financement.base_echeance : ht ou ttc.",
            champ='offre_financement.base_echeance')
    base = base_eco.get('base')
    if (base == BASE_HT and base_echeance != 'ht') or (
            base == BASE_TTC and base_echeance != 'ttc'):
        raise SaisieEconomieCiInvalide(
            f"offre_financement.base_echeance : échéance en "
            f"{base_echeance.upper()} face à des économies en "
            f"{base.upper()} — même base exigée.",
            champ='offre_financement.base_echeance')
    duree = _nombre_offre(offre, 'duree_mois', entier=True, requis=True)
    taux = _nombre_offre(offre, 'taux_annuel_pct')
    if taux is not None:
        from apps.ventes import economie as eco_mod
        principal = _nombre_offre(offre, 'montant_finance_mad', requis=True)
        try:
            tableau = eco_mod.tableau_pret(
                principal_mad=principal, taux_annuel_pct=taux,
                duree_mois=duree, type_pret='annuite')
        except eco_mod.EconomieInvalide as refus:
            raise SaisieEconomieCiInvalide(
                f"offre_financement.{refus}",
                champ=f'offre_financement.{refus.champ}') from refus
        echeance = tableau['mensualite_mad']
    else:
        echeance = _nombre_offre(offre, 'echeance_mad', requis=True)
    economie_an = base_eco.get(f'economie_annee1_{base_echeance}_mad')
    mensuelle = None if economie_an is None else round(economie_an / 12, 2)
    return {
        'libelle_client': _libelle_financement(
            offre, nature, mention_credit_bail_autorisee),
        'echeance_mad': round(echeance, 2),
        'economie_mensuelle_moyenne_mad': mensuelle,
        'ecart_mensuel_mad': (None if mensuelle is None
                              else round(mensuelle - echeance, 2)),
        'duree_mois': duree,
        'source': SOURCE_FINANCEMENT,
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIQ209 — moteur ``economie_ci`` (6/6) : vue INTERNE face à une offre CSE/PPA
# concurrente, depuis le tarif ÉCRIT du prospect (D-CIQ-16), et
# :func:`economie_ci_publique`, la SEULE forme servie à un chemin client.
# ═════════════════════════════════════════════════════════════════════════════
# Aucune offre de tiers-investisseur de TAQINOR (D-CIQ-16 : le client reste
# l'autoproducteur, loi 13-09 parquée) ; aucun nom de concurrent stocké ni
# servi. Le paiement de l'offre = tarif HT ÉCRIT × kWh solaires livrés — la
# MÊME production et la MÊME dégradation que le flux d'achat ; l'indexation
# n'existe QUE si elle est écrite sur l'offre (sinon tarif constant, hypothèse
# nommée). Au-delà de la durée de l'offre rien n'est supposé.

#: Clés INTERNES jamais servies à un chemin client (PDF, /proposition, lien
#: public, messages) — retirées RÉCURSIVEMENT par :func:`economie_ci_publique`.
CLES_INTERNES = ('vue_interne', 'alertes_internes', 'comparaison_cse',
                 'apres_impot', 'sr500')
MENTION_CSE_INDEXATION_ABSENTE = (
    "tarif de l'offre constant : aucune indexation écrite sur l'offre "
    "(hypothèse)")
MOTIF_CSE_SANS_FLUX_HT = (
    "flux d'achat HT non construit : l'offre (tarif HT) n'est comparée qu'à "
    "des économies HT — comparaison non évaluée")
MOTIF_CSE_SANS_PRODUCTION = (
    "production annuelle inconnue : kWh livrés par l'offre non calculables — "
    "comparaison non évaluée")


def _nombre_cse(offre, cle, *, requis=False, entier=False, strict=False):
    champ = f'offre_cse_concurrente.{cle}'
    brut = offre.get(cle)
    if brut is None or brut == '':
        if requis:
            raise SaisieEconomieCiInvalide(
                f"{champ} : à saisir depuis l'offre écrite du prospect.",
                champ=champ)
        return None
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        valeur = None
    invalide = (valeur is None or valeur != valeur
                or (strict and valeur <= -100)
                or (not strict and valeur < 0)
                or (entier and (valeur != int(valeur) or valeur < 1)))
    if invalide:
        raise SaisieEconomieCiInvalide(
            f"{champ} : valeur « {brut} » refusée.", champ=champ)
    return int(valeur) if entier else valeur


def lire_offre_cse(offre):
    """``saisies_economie_ci.offre_cse_concurrente`` validée, ou None.

    ``{tarif_kwh_ht, duree_ans, indexation_pct_an (SEULEMENT si écrite),
    source}`` — tout autre champ (nom du concurrent…) est IGNORÉ, jamais
    recopié. Refus nommés ``offre_cse_concurrente.<champ>``.
    """
    if offre in (None, '', {}):
        return None
    if not isinstance(offre, dict):
        raise SaisieEconomieCiInvalide(
            "offre_cse_concurrente : un objet est attendu.",
            champ='offre_cse_concurrente')
    source = str(offre.get('source') or '').strip()
    if not source:
        raise SaisieEconomieCiInvalide(
            "offre_cse_concurrente.source : la comparaison se construit "
            "seulement depuis le tarif ÉCRIT de l'offre du prospect.",
            champ='offre_cse_concurrente.source')
    return {
        'tarif_kwh_ht': _nombre_cse(offre, 'tarif_kwh_ht', requis=True),
        'duree_ans': _nombre_cse(offre, 'duree_ans', requis=True,
                                 entier=True),
        'indexation_pct_an': _nombre_cse(offre, 'indexation_pct_an',
                                         strict=True),
        'source': source,
    }


def _hypothese_flux(flux, cle):
    for h in (flux or {}).get('hypotheses') or []:
        if isinstance(h, dict) and h.get('cle') == cle:
            return h.get('valeur')
    return None


def comparaison_cse(flux, offre_cse, production):
    """La comparaison INTERNE achat ↔ offre CSE/PPA (``vue_interne.
    comparaison_cse`` du contrat ``economie_ci.json``), ou None sans offre.

    ``flux`` : le flux d'achat HT (bloc ``flux_ht`` de :func:`flux_ci`) ;
    ``offre_cse`` : saisie brute (validée par :func:`lire_offre_cse`) ;
    ``production`` : production de l'année 1 (kWh) — la même que le flux.

    Par année t ≤ min(durée de l'offre, horizon du flux) : kWh livrés =
    production × (1 − dégradation du flux)^(t−1) ; paiement de l'offre =
    tarif × (1 + indexation écrite)^(t−1) × kWh ; gain net de l'offre =
    économie du flux − paiement ; croisement = première année où le cumul
    de l'achat atteint le cumul net de l'offre.
    """
    offre = lire_offre_cse(offre_cse)
    if offre is None:
        return None
    hypotheses = [{'cle': 'tarif_kwh_ht', 'valeur': offre['tarif_kwh_ht'],
                   'statut': 'declare', 'source': offre['source']},
                  {'cle': 'duree_ans', 'valeur': offre['duree_ans'],
                   'statut': 'declare', 'source': offre['source']}]
    if offre['indexation_pct_an'] is None:
        idx = 0.0
        hypotheses.append({'cle': 'indexation_pct_an', 'valeur': 0.0,
                           'statut': 'hypothese',
                           'source': MENTION_CSE_INDEXATION_ABSENTE})
    else:
        idx = offre['indexation_pct_an']
        hypotheses.append({'cle': 'indexation_pct_an', 'valeur': idx,
                           'statut': 'declare', 'source': offre['source']})
    sortie = {'statut': 'omise', 'motif': None, 'annees': [],
              'cumul_offre_mad': None, 'cumul_achat_mad': None,
              'annee_croisement': None, 'hypotheses': hypotheses}
    lignes = (flux or {}).get('flux') or []
    if not lignes:
        sortie['motif'] = MOTIF_CSE_SANS_FLUX_HT
        return sortie
    prod = _montant(production)
    if not prod:
        sortie['motif'] = MOTIF_CSE_SANS_PRODUCTION
        return sortie
    deg = _f(_hypothese_flux(flux, 'degradation_pct')) / 100.0
    hypotheses.append({'cle': 'production_annee1_kwh', 'valeur': prod,
                       'statut': 'source',
                       'source': "même production que le flux d'achat"})
    par_annee = {f['annee']: f for f in lignes}
    horizon = min(offre['duree_ans'], max(par_annee))
    annees, cumul_offre, cumul_net = [], 0.0, 0.0
    croisement = None
    for t in range(1, horizon + 1):
        ligne = par_annee.get(t)
        if ligne is None:
            break
        kwh = prod * (1.0 - deg) ** (t - 1)
        paiement = offre['tarif_kwh_ht'] * (1.0 + idx / 100.0) ** (t - 1) * kwh
        cumul_offre += paiement
        cumul_net += (ligne.get('economie_mad') or 0.0) - paiement
        cumul_achat = ligne.get('cumul_mad')
        if croisement is None and cumul_achat is not None \
                and cumul_achat >= cumul_net:
            croisement = t
        annees.append({'annee': t, 'kwh_livres': int(round(kwh)),
                       'paiement_offre_mad': round(paiement, 2),
                       'cumul_offre_mad': round(cumul_offre, 2),
                       'cumul_offre_net_mad': round(cumul_net, 2),
                       'cumul_achat_mad': cumul_achat})
    sortie.update({
        'statut': 'calculee',
        'annees': annees,
        'cumul_offre_mad': round(cumul_offre, 2),
        'cumul_achat_mad': annees[-1]['cumul_achat_mad'] if annees else None,
        'annee_croisement': croisement,
    })
    return sortie


def _sans_internes(objet):
    if isinstance(objet, dict):
        return {k: _sans_internes(v) for k, v in objet.items()
                if k not in CLES_INTERNES}
    if isinstance(objet, list):
        return [_sans_internes(v) for v in objet]
    return objet


def economie_ci_publique(bloc):
    """Le bloc ``economie_ci`` SANS rien d'interne — la SEULE fonction qu'un
    chemin client appelle (PDF /proposal, /proposition, lien public).

    Retire récursivement ``vue_interne``, ``alertes_internes`` et les clés
    internes qu'elles portent (:data:`CLES_INTERNES`) ; ne modifie jamais
    ``bloc`` (copie).
    """
    if not isinstance(bloc, dict):
        return bloc
    return _sans_internes(bloc)


# ═════════════════════════════════════════════════════════════════════════════
# CIQ210 — ASSEMBLAGE du bloc ``economie_ci`` (contrat ``economie_ci.json``) et
# lecture d'un devis : UNE fonction sert l'aperçu, la lecture interne, le PDF
# et /proposition (celles-ci par :func:`economie_ci_publique`).
# ═════════════════════════════════════════════════════════════════════════════
# Entrées : l'aperçu C&I (contrat CIQ2 ``etude_ci_preview.json`` — la forme
# stockée ``etude_params.etude_ci`` en est le sous-ensemble ``entrees_resolues``
# / ``profil_charge`` / ``bilan`` / ``alertes``), ``tarif_declare``,
# ``saisies_economie_ci``, l'investissement de l'option retenue (totaux CLIENT
# HT/TTC, jamais ``prix_achat``) et les lignes (onduleur, O&M). Aucun prix plat,
# aucun taux d'autoconsommation forfaitaire, aucune économie de calepinage.

MOTIF_ETUDE_CI_ABSENTE = (
    "étude C&I du devis absente (aucun panneau au devis ou étude non "
    "calculée) — économies non chiffrées")
MOTIF_FINANCEMENT_ABSENT = "aucune offre écrite de prêteur saisie (D-CIQ-15)"
ALERTE_TARIF_REPLI = (
    "Tarif valorisé sur la grille officielle (repli) : lire une facture du "
    "client pour un chiffre déclaré.")
#: Alertes de l'étude C&I RELAYÉES (jamais recalculées) dans
#: ``alertes_internes`` — l'alerte cos φ de CIQ134.
CODES_ALERTES_RELAYEES = ('cos_phi_apres_pv',)
PARCOURS_AIDE = ('aucun', 'sr500', 'autre')
MOTIF_SR500_AUCUN = "aucun parcours d'aide déclaré"
MOTIF_SR500 = ("candidature SR500 manuelle d'abord (D-CIQ-17) — indicateur "
               "interne seulement, jamais un montant")
MOTIF_AIDE_AUTRE = ("parcours d'aide « autre » déclaré — non évalué, jamais "
                    "un montant")
HYPOTHESE_VALORISATION = {
    'cle': 'valorisation',
    'valeur': 'tarif du poste horaire couvert, heure par heure',
    'statut': 'source', 'source': 'conventions Groupe CIQ'}
#: Ordre des clés du contrat (``exemple``).
CLES_BLOC = ('statut', 'motifs_omission', 'base', 'motif_base', 'tarif',
             'economie_annee1', 'facture_avant', 'facture_apres', 'revente',
             'flux_ht', 'flux_ttc', 'jalons', 'jalons_ttc', 'indicateurs',
             'remplacements', 'om', 'sensibilites', 'financement',
             'hypotheses', 'omissions', 'alertes_internes', 'vue_interne')


def _resolue(apercu, feuille):
    entree = (apercu.get('entrees_resolues') or {}).get(feuille)
    return entree.get('valeur') if isinstance(entree, dict) else entree


def _sr500(saisies):
    parcours = str(saisies.get('parcours_aide') or 'aucun').strip().lower()
    if parcours not in PARCOURS_AIDE:
        raise SaisieEconomieCiInvalide(
            f"saisies_economie_ci.parcours_aide : choisir parmi "
            f"{', '.join(PARCOURS_AIDE)}.",
            champ='saisies_economie_ci.parcours_aide')
    motif = {'aucun': MOTIF_SR500_AUCUN, 'sr500': MOTIF_SR500,
             'autre': MOTIF_AIDE_AUTRE}[parcours]
    return {'statut': 'non_evalue', 'motif': motif}


def _hypothese_tarif(tarif):
    origine = tarif.get('origine')
    premier = (tarif.get('tarifs_par_poste') or [{}])[0]
    if origine == tarif_ci.ORIGINE_GRILLE:
        libelle = tarif_ci._LIBELLES_CONTRAT.get(tarif.get('contrat'),
                                                 tarif.get('contrat'))
        return {'cle': 'tarif', 'valeur': f'grille ONEE {libelle}, repli',
                'statut': 'estimation', 'source': tarif_ci.MENTION_GRILLE}
    return {'cle': 'tarif', 'valeur': premier.get('source'),
            'statut': 'declare', 'source': tarif.get('mention')}


def _alertes_internes(apercu, tarif):
    alertes = []
    if tarif.get('origine') == tarif_ci.ORIGINE_GRILLE:
        alertes.append({'code': 'tarif_repli', 'message': ALERTE_TARIF_REPLI,
                        'interne': True})
    for alerte in apercu.get('alertes') or []:
        if isinstance(alerte, dict) and \
                alerte.get('code') in CODES_ALERTES_RELAYEES:
            relayee = dict(alerte)
            relayee['interne'] = True
            alertes.append(relayee)
    return alertes


def _somme_lignes(lignes, cle_filtre):
    ht = ttc = 0.0
    trouve = False
    sources = []
    for ligne in lignes:
        if not cle_filtre(ligne):
            continue
        h, t = _montant(ligne.get('ht')), _montant(ligne.get('ttc'))
        if h is None or t is None:
            continue
        trouve = True
        ht += h
        ttc += t
        if ligne.get('designation'):
            sources.append(str(ligne['designation']))
    if not trouve:
        return None
    return {'ht': round(ht, 2), 'ttc': round(ttc, 2), 'sources': sources}


def onduleur_et_om(lignes):
    """``(onduleur, om)`` lus sur les lignes de l'option retenue.

    ``lignes`` : ``[{designation, ht, ttc, optionnelle, onduleur (bool),
    role_ci}]`` — totaux CLIENT. Onduleur = lignes onduleur COMPTÉES (montant
    réel, décision Q1) ; O&M = lignes du rôle ``om_ci`` : activée si au moins
    une n'est pas optionnelle (D-CIQ-12). None quand aucune ligne.
    """
    lignes = [li for li in (lignes or []) if isinstance(li, dict)]
    ond = _somme_lignes(
        lignes, lambda li: li.get('onduleur') and not li.get('optionnelle'))
    onduleur = None
    if ond is not None:
        onduleur = {'ht': ond['ht'], 'ttc': ond['ttc'],
                    'source': 'ligne onduleur du devis'
                    + (f" ({', '.join(ond['sources'])})"
                       if ond['sources'] else '')}
    om_lignes = [li for li in lignes if li.get('role_ci') == 'om_ci']
    om = None
    if om_lignes:
        activee = any(not li.get('optionnelle') for li in om_lignes)
        retenues = [li for li in om_lignes
                    if not li.get('optionnelle')] if activee else om_lignes
        somme = _somme_lignes(retenues, lambda li: True)
        om = {'activee': activee,
              'ht': None if somme is None else somme['ht'],
              'ttc': None if somme is None else somme['ttc'],
              'source': 'ligne O&M souscrite du devis'}
    return onduleur, om


def _bloc_omis(motif, tarif, *, alertes, vue_interne):
    bloc = dict.fromkeys(CLES_BLOC)
    bloc.update({
        'statut': STATUT_OMIS, 'motifs_omission': [motif], 'tarif': tarif,
        'jalons': [], 'remplacements': [], 'sensibilites': [],
        'hypotheses': [], 'omissions': [], 'alertes_internes': alertes,
        'vue_interne': vue_interne,
    })
    del bloc['jalons_ttc']
    del bloc['financement']
    return bloc


def assembler_economie_ci(apercu_ci, *, saisies=None, tarif_declare=None,
                          investissement=None, lignes=None,
                          mode_installation=None, reglages=None):
    """Le bloc ``economie_ci`` INTERNE (avec ``vue_interne`` et
    ``alertes_internes``) — forme ``exemple`` du contrat ``economie_ci.json``.

    ``apercu_ci`` : sortie de l'aperçu C&I (ou ``etude_params.etude_ci``) ;
    ``tarif_declare`` : ``etude_params.tarif_declare`` (sinon celui résolu par
    l'aperçu) ; ``saisies`` : ``saisies_economie_ci`` ; ``investissement`` :
    ``{ht, ttc}`` CLIENT de l'option retenue ; ``lignes`` : voir
    :func:`onduleur_et_om` ; ``reglages`` : ``{mention_credit_bail_autorisee}``
    (``TariffSettings``, CIQ211). Refus nommés par
    :class:`SaisieEconomieCiInvalide`. Aucune écriture.
    """
    apercu = apercu_ci if isinstance(apercu_ci, dict) else {}
    saisies = saisies if isinstance(saisies, dict) else {}
    reglages = reglages if isinstance(reglages, dict) else {}
    if not isinstance(tarif_declare, dict):
        tarif_declare = _resolue(apercu, 'tarif_declare')
        if not isinstance(tarif_declare, dict):
            tarif_declare = None
    tension = _resolue(apercu, 'tension')
    tension = tension.strip().lower() if isinstance(tension, str) else None
    tarif = tarif_ci.tarif_applicable(tarif_declare, tension=tension)
    vue_interne = {'comparaison_cse': None, 'sr500': _sr500(saisies),
                   'apres_impot': None}
    alertes = _alertes_internes(apercu, tarif)
    if not apercu.get('bilan'):
        motif = (MOTIF_TARIF_OMIS if tarif.get('origine') ==
                 tarif_ci.ORIGINE_OMIS else MOTIF_ETUDE_CI_ABSENTE)
        return _bloc_omis(motif, tarif, alertes=alertes,
                          vue_interne=vue_interne)
    valo = valoriser(apercu, tarif, tarif_declare=tarif_declare)
    if valo['statut'] == STATUT_OMIS:
        return _bloc_omis(valo['motifs_omission'][0], tarif, alertes=alertes,
                          vue_interne=vue_interne)

    tva = resoudre_tva_recuperable(_resolue(apercu, 'tva_recuperable'),
                                   saisies.get('tva_recuperable'))
    base = base_economique(tva, investissement=investissement,
                           economie_annee1=valo['economie_annee1'])
    production = _montant((apercu.get('bilan') or {}).get('production_kwh'))
    kwh_evites = sum(_f(p.get('kwh_evites'))
                     for p in valo['economie_annee1']['par_poste'])
    onduleur, om = onduleur_et_om(lignes)
    collecteur = {}
    flux = flux_ci(base, production_annee1_kwh=production,
                   kwh_evites_an=kwh_evites, onduleur=onduleur, om=om,
                   taux_actualisation_client=saisies.get(
                       'taux_actualisation_client'),
                   collecteur=collecteur)
    revente = valo['revente']
    tension_revente = tension or (
        'mt' if tarif.get('contrat') == 'mt_general' else None)
    if tension_revente:
        revente = revente_ci(
            apercu, tension=tension_revente,
            revente_demandee=bool(saisies.get('revente_demandee')),
            production_annuelle_kwh=production)
    financement = financement_ci(
        saisies.get('offre_financement'), base,
        mode_installation=mode_installation,
        mention_credit_bail_autorisee=bool(
            reglages.get('mention_credit_bail_autorisee')))
    vue_interne['comparaison_cse'] = comparaison_cse(
        flux['flux_ht'], saisies.get('offre_cse_concurrente'), production)
    omissions = []
    if flux['indicateurs'] and flux['indicateurs'].get('van_motif'):
        omissions.append({'cle': 'van_mad',
                          'motif': flux['indicateurs']['van_motif']})
    if financement is None:
        omissions.append({'cle': 'financement',
                          'motif': MOTIF_FINANCEMENT_ABSENT})
    sensibilites = []
    if str(mode_installation or '').strip().lower() == 'industriel':
        # CIQ231 — industriel SEULEMENT, sur le flux de la base principale.
        cle_base = 'ttc' if flux['base'] == BASE_TTC else 'ht'
        sensibilites, omis = sensibilites_ci(
            collecteur.get(cle_base), apercu, tarif, reglages,
            tarif_declare=tarif_declare, cle_base=cle_base)
        if omis is not None:
            omissions.append(omis)
        # CIQ233 — vue INTERNE après impôt (industriel, saisie du client).
        apres, motif_apres = apres_impot_ci(
            saisies.get('fiscalite_client'), base, collecteur)
        vue_interne['apres_impot'] = apres
        if motif_apres is not None:
            vue_interne['apres_impot_motif'] = motif_apres
    hypotheses = [dict(HYPOTHESE_VALORISATION), _hypothese_tarif(tarif)]
    hypotheses.extend(valo.get('hypotheses') or [])
    bloc = {
        'statut': STATUT_CALCULE,
        'motifs_omission': [],
        'base': flux['base'],
        'motif_base': flux['motif_base'],
        'tarif': tarif,
        'economie_annee1': valo['economie_annee1'],
        'facture_avant': valo['facture_avant'],
        'facture_apres': valo['facture_apres'],
        'revente': revente,
        'flux_ht': flux['flux_ht'],
        'flux_ttc': flux['flux_ttc'],
        'jalons': flux['jalons'],
        'jalons_ttc': flux.get('jalons_ttc'),
        'indicateurs': flux['indicateurs'],
        'remplacements': flux['remplacements'],
        'om': flux['om'],
        'sensibilites': sensibilites,
        'financement': financement,
        'hypotheses': hypotheses,
        'omissions': omissions,
        'alertes_internes': alertes,
        'vue_interne': vue_interne,
    }
    if 'jalons_ttc' not in flux:
        del bloc['jalons_ttc']
    if financement is None:
        del bloc['financement']
    return bloc


# ═════════════════════════════════════════════════════════════════════════════
# CIQ231 — sensibilités INDUSTRIELLES sur les SEULES valeurs saisies par Reda
# (``TariffSettings.sensibilites_ci``, CIQ211 ; D-CIQ-10, convention 16).
# ═════════════════════════════════════════════════════════════════════════════
# Chaque scénario relance DIRECTEMENT ``economie.flux_de_tresorerie`` (sans le
# modifier ni passer par ``comparer_scenarios``, qui exige une indexation
# identique d'un scénario à l'autre) avec les entrées EXACTES du flux de base,
# en ne changeant qu'UNE grandeur :
#   indexation_tarif ⇒ ``indexation_pct`` = variation (%/an ; base 0, QX39) ;
#   degradation      ⇒ ``degradation_pct`` = variation (%/an) ;
#   tarif_kwh        ⇒ prix de chaque poste × (1 + v), puis :func:`valoriser` ;
#   production       ⇒ production de chaque cellule horaire × (1 + v),
#                      autoconsommé = min(production, charge déclarée) cellule
#                      par cellule, puis :func:`valoriser` (jamais une économie
#                      mise à l'échelle linéairement).
# Aucun scénario par défaut, aucun P90 inventé.

SENSIBILITE_CLES = ('indexation_tarif', 'degradation', 'tarif_kwh',
                    'production')
SENSIBILITES_MAX = 4
MOTIF_SANS_SENSIBILITE = (
    "aucun scénario saisi (Paramètres — sensibilités C&I) : aucune "
    "sensibilité supposée")
MOTIF_SENSIBILITE_SANS_CHARGE = (
    "charge horaire déclarée absente : production non recalculable heure "
    "par heure — scénario non chiffré")


def _tarif_mis_a_l_echelle(tarif, facteur):
    sortie = dict(tarif)
    sortie['tarifs_par_poste'] = [
        dict(p, tarif_kwh_ht=round(_f(p.get('tarif_kwh_ht')) * facteur, 4),
             tarif_kwh_ttc=round(_f(p.get('tarif_kwh_ttc')) * facteur, 4))
        for p in tarif.get('tarifs_par_poste') or []]
    return sortie


def _apercu_production(apercu, facteur):
    """L'aperçu dont CHAQUE cellule horaire produit × ``facteur`` ;
    autoconsommé = min(production, charge), surplus = le reste. None quand la
    charge d'un jour type manque (rien n'est deviné)."""
    charges = _charges_par_jour_type(apercu)
    bilan = dict(apercu.get('bilan') or {})
    horaire = []
    for bloc in bilan.get('horaire') or []:
        if not isinstance(bloc, dict):
            continue
        charge = charges.get((bloc.get('mois'), bloc.get('type_jour')))
        if charge is None:
            return None
        auto = bloc.get('autoconso_kwh') or []
        surplus = bloc.get('surplus_kwh') or []
        a2, s2 = [], []
        for h in range(24):
            prod = ((_f(auto[h]) if h < len(auto) else 0.0)
                    + (_f(surplus[h]) if h < len(surplus) else 0.0)) * facteur
            c = _f(charge[h]) if h < len(charge) else 0.0
            a2.append(min(prod, c))
            s2.append(prod - min(prod, c))
        horaire.append(dict(bloc, autoconso_kwh=a2, surplus_kwh=s2))
    bilan['horaire'] = horaire
    if bilan.get('production_kwh') is not None:
        bilan['production_kwh'] = _f(bilan['production_kwh']) * facteur
    return dict(apercu, bilan=bilan)


def _economie_valorisee(apercu, tarif, tarif_declare, cle_base):
    valo = valoriser(apercu, tarif, tarif_declare=tarif_declare)
    eco1 = valo.get('economie_annee1') or {}
    return eco1.get('total_mad_ttc' if cle_base == 'ttc' else 'total_mad')


def _indicateur(bloc, cle):
    return None if not bloc else bloc.get(cle)


def _ecart(valeur, reference):
    if valeur is None or reference is None:
        return None
    return round(valeur - reference, 4)


def sensibilites_ci(flux_entrees, apercu_ci, tarif, reglages, *,
                    tarif_declare=None, cle_base='ht'):
    """``(sensibilites, omission|None)`` — la liste du contrat
    ``economie_ci.json`` [{cle, variation_pct, source, economie_annee1_mad,
    retour_ans, tri_pct, ecart_retour_ans, ecart_tri_pct}] et, sans scénario, l'omission nommée.

    ``flux_entrees`` : les entrées EXACTES du flux de base (collectées par
    :func:`flux_ci`) ; ``reglages`` : ``{sensibilites_ci: [...]}`` (CIQ211).
    """
    from apps.ventes import economie as eco_mod
    scenarios = (reglages or {}).get('sensibilites_ci') or []
    scenarios = [s for s in scenarios if isinstance(s, dict)
                 and s.get('cle') in SENSIBILITE_CLES
                 and str(s.get('source') or '').strip()][:SENSIBILITES_MAX]
    if not scenarios or not isinstance(flux_entrees, dict):
        return [], {'cle': 'sensibilites', 'motif': MOTIF_SANS_SENSIBILITE}
    apercu = apercu_ci if isinstance(apercu_ci, dict) else {}
    base = eco_mod.flux_de_tresorerie(**flux_entrees)
    sorties = []
    for sc in scenarios:
        cle = sc['cle']
        v = float(str(sc.get('variation_pct')).replace(',', '.'))
        source = str(sc['source']).strip()
        libelle = f'sensibilité saisie par la société — {source}'
        entrees = dict(flux_entrees)
        motif = None
        if cle == 'indexation_tarif':
            entrees['indexation_pct'] = {'valeur': v, 'source': libelle}
        elif cle == 'degradation':
            entrees['degradation_pct'] = {'valeur': v, 'source': libelle}
        elif cle == 'tarif_kwh':
            eco = _economie_valorisee(
                apercu, _tarif_mis_a_l_echelle(tarif, 1.0 + v / 100.0),
                tarif_declare, cle_base)
            entrees['economie_annee1_mad'] = {'valeur': eco, 'source': libelle}
        else:
            modifie = _apercu_production(apercu, 1.0 + v / 100.0)
            if modifie is None:
                motif = MOTIF_SENSIBILITE_SANS_CHARGE
            else:
                eco = _economie_valorisee(modifie, tarif, tarif_declare,
                                          cle_base)
                entrees['economie_annee1_mad'] = {'valeur': eco,
                                                  'source': libelle}
                prod = (entrees.get('production_annee1_kwh') or {})
                if isinstance(prod, dict) and prod.get('valeur') is not None:
                    entrees['production_annee1_kwh'] = dict(
                        prod, valeur=_f(prod['valeur']) * (1.0 + v / 100.0))
        bloc = None
        if motif is None:
            try:
                bloc = eco_mod.flux_de_tresorerie(**entrees)
            except eco_mod.EconomieInvalide as refus:
                motif = f'scénario refusé : {refus}'
        eco1 = (entrees.get('economie_annee1_mad') or {})
        ligne = {'cle': cle, 'variation_pct': v, 'source': source,
                 'economie_annee1_mad': (
                     _montant(eco1.get('valeur'))
                     if isinstance(eco1, dict) else _montant(eco1)),
                 'retour_ans': _indicateur(bloc, 'retour_ans'),
                 'tri_pct': _indicateur(bloc, 'tri_pct'),
                 'ecart_retour_ans': _ecart(_indicateur(bloc, 'retour_ans'),
                                            base.get('retour_ans')),
                 'ecart_tri_pct': _ecart(_indicateur(bloc, 'tri_pct'),
                                         base.get('tri_pct'))}
        if motif is not None:
            ligne['motif'] = motif
        sorties.append(ligne)
    return sorties, None


# ═════════════════════════════════════════════════════════════════════════════
# CIQ233 — vue INTERNE après impôt d'un industriel, seulement sur le taux d'IS
# et l'amortissement DÉCLARÉS par le client (jamais les réglages fiscaux de la
# société vendeuse) ; base amortissable HT quand la TVA est récupérable.
# ═════════════════════════════════════════════════════════════════════════════

MODES_AMORTISSEMENT_CI = ('lineaire', 'degressif')
MOTIF_APRES_IMPOT_OMIS = (
    "fiscalité du client non déclarée (taux d'IS et amortissement) : vue "
    "après impôt omise — jamais les réglages fiscaux de la société")


def _nombre_fiscal(fiscalite, cle, *, requis=True):
    champ = f'fiscalite_client.{cle}'
    brut = fiscalite.get(cle)
    if brut is None or brut == '':
        if requis:
            raise SaisieEconomieCiInvalide(
                f"{champ} : à saisir (déclaré par le client ou son "
                "comptable).", champ=champ)
        return None
    try:
        return float(str(brut).replace(',', '.'))
    except (TypeError, ValueError):
        raise SaisieEconomieCiInvalide(
            f"{champ} : valeur « {brut} » refusée.", champ=champ) from None


def lire_fiscalite_client(fiscalite):
    """``saisies_economie_ci.fiscalite_client`` validée, ou None.

    ``{taux_is_pct, amortissement_mode lineaire|degressif, duree_ans,
    amortissement_coefficient (dégressif), source}`` — refus nommés
    ``fiscalite_client.<champ>``.
    """
    if fiscalite in (None, '', {}):
        return None
    if not isinstance(fiscalite, dict):
        raise SaisieEconomieCiInvalide(
            "fiscalite_client : un objet est attendu.",
            champ='fiscalite_client')
    source = str(fiscalite.get('source') or '').strip()
    if not source:
        raise SaisieEconomieCiInvalide(
            "fiscalite_client.source : déclaré par le client ou son "
            "comptable — source obligatoire.", champ='fiscalite_client.source')
    mode = str(fiscalite.get('amortissement_mode') or '').strip().lower()
    if mode not in MODES_AMORTISSEMENT_CI:
        raise SaisieEconomieCiInvalide(
            "fiscalite_client.amortissement_mode : lineaire ou degressif.",
            champ='fiscalite_client.amortissement_mode')
    return {
        'taux_is_pct': _nombre_fiscal(fiscalite, 'taux_is_pct'),
        'amortissement_mode': mode,
        'duree_ans': _nombre_fiscal(fiscalite, 'duree_ans'),
        'amortissement_coefficient': _nombre_fiscal(
            fiscalite, 'amortissement_coefficient',
            requis=mode == 'degressif'),
        'source': source,
    }


def apres_impot_ci(fiscalite, base_eco, collecteur):
    """``(bloc apres_impot | None, motif | None)`` — ``vue_interne.
    apres_impot`` du contrat ``economie_ci.json``.

    ``flux_apres_impot`` (economie.py, inchangé) reçoit les entrées EXACTES
    du flux de base et ``base_amortissable_mad`` = total HT quand la TVA est
    récupérable (``oui``), TTC sinon (D-CIQ-3) — le flux suit la même base.
    """
    from apps.ventes import economie as eco_mod
    lu = lire_fiscalite_client(fiscalite)
    if lu is None:
        return None, MOTIF_APRES_IMPOT_OMIS
    cle_base = 'ht' if base_eco.get('tva_recuperable') == TVA_OUI else 'ttc'
    entrees = (collecteur or {}).get(cle_base)
    if entrees is None:
        return None, MOTIF_APRES_IMPOT_OMIS
    source = f"déclaré par le client — {lu['source']}"
    base = base_eco.get(f'investissement_{cle_base}_mad')
    libelle = ('HT (TVA récupérable)' if cle_base == 'ht'
               else 'TTC (TVA non récupérable ou non déclarée)')

    def saisie(valeur):
        return None if valeur is None else {'valeur': valeur,
                                            'source': source}
    try:
        res = eco_mod.flux_apres_impot(
            taux_imposition_pct=saisie(lu['taux_is_pct']),
            amortissement_mode=saisie(lu['amortissement_mode']),
            amortissement_duree_ans=saisie(
                None if lu['duree_ans'] is None else int(lu['duree_ans'])),
            amortissement_coefficient=saisie(
                lu['amortissement_coefficient']
                if lu['amortissement_mode'] == 'degressif' else None),
            base_amortissable_mad=None if base is None else {
                'valeur': base,
                'source': f"devis — total {libelle} de l'option retenue"},
            **entrees)
    except eco_mod.EconomieInvalide as refus:
        raise SaisieEconomieCiInvalide(
            f"fiscalite_client : {refus}",
            champ=f'fiscalite_client.{refus.champ}') from refus
    bloc = res['apres_impot']
    bloc['base'] = cle_base
    return bloc, None


# ── Lecture d'un devis (aucune écriture) ─────────────────────────────────────

def _est_onduleur(produit):
    if produit is None:
        return False
    roles = ' '.join(str(getattr(produit, r, '') or '')
                     for r in ('role_devis', 'role_ci'))
    if 'onduleur' in roles:
        return True
    categorie = getattr(produit, 'categorie', None)
    return getattr(categorie, 'type_equipement', None) == 'onduleur'


def lignes_pour_economie_ci(devis):
    """Les lignes de l'option RETENUE à la forme de :func:`onduleur_et_om` —
    totaux CLIENT (remise de ligne ET remise globale), jamais ``prix_achat``.
    Les O&M optionnelles restent lues (« proposé, non souscrit »)."""
    from apps.ventes.utils.options import (
        filter_lines_for_option, has_two_options, lignes_avec_produit,
        option_effective)
    lignes = lignes_avec_produit(devis)
    if has_two_options(devis):
        option = option_effective(devis)
        if option:
            lignes = filter_lines_for_option(lignes, option)
    remise_globale = _f(getattr(devis, 'remise_globale', 0))
    facteur = 1.0 - remise_globale / 100.0
    sorties = []
    for ligne in lignes:
        if getattr(ligne, 'type_ligne', 'produit') not in (None, '', 'produit'):
            continue
        produit = getattr(ligne, 'produit', None)
        tva = ligne.taux_tva if ligne.taux_tva is not None else devis.taux_tva
        ht = (_f(ligne.quantite) * _f(ligne.prix_unitaire)
              * (1.0 - _f(ligne.remise) / 100.0)) * facteur
        sorties.append({
            'designation': ligne.designation,
            'ht': round(ht, 2),
            'ttc': round(ht * (1.0 + _f(tva) / 100.0), 2),
            'optionnelle': bool(getattr(ligne, 'optionnelle', False)),
            'onduleur': _est_onduleur(produit),
            'role_ci': (getattr(produit, 'role_ci', '') or None)
            if produit is not None else None,
        })
    return sorties


def reglages_economie_ci(company):
    """``{mention_credit_bail_autorisee}`` du ``TariffSettings`` (CIQ211),
    lu sans jamais le créer ; vide sans réglage."""
    if company is None:
        return {}
    from apps.parametres.models_tariff import TariffSettings
    reglage = TariffSettings.objects.filter(company=company).first()
    if reglage is None:
        return {}
    return {
        'mention_credit_bail_autorisee': bool(
            getattr(reglage, 'mention_credit_bail_autorisee', False)),
        'sensibilites_ci': list(getattr(reglage, 'sensibilites_ci', None)
                                or []),
    }


def economie_ci_pour_devis(devis, company):
    """Le bloc ``economie_ci`` INTERNE d'un devis commercial / industriel
    (calculé à la lecture, jamais stocké ; aucune écriture, règle #4).

    Lit ``etude_params.etude_ci`` (aperçu C&I stocké par le rafraîchisseur
    CIQ119), ``tarif_declare``, ``saisies_economie_ci``, les totaux de
    l'option retenue (``utils.options.option_totaux``) et ses lignes.
    """
    from apps.ventes.utils.options import option_totaux
    params = getattr(devis, 'etude_params', None)
    params = params if isinstance(params, dict) else {}
    apercu = params.get('etude_ci')
    tarif_declare = params.get('tarif_declare')
    if not isinstance(tarif_declare, dict):
        tarif_declare = params.get('tarif') if isinstance(
            params.get('tarif'), dict) else None
    totaux = option_totaux(devis)
    return assembler_economie_ci(
        apercu if isinstance(apercu, dict) else {},
        saisies=params.get('saisies_economie_ci'),
        tarif_declare=tarif_declare,
        investissement={'ht': totaux.get('ht'), 'ttc': totaux.get('ttc')},
        lignes=lignes_pour_economie_ci(devis),
        mode_installation=getattr(devis, 'mode_installation', None),
        reglages=reglages_economie_ci(company))
