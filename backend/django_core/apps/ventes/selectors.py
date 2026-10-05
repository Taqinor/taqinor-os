"""Sélecteurs LECTURE SEULE du domaine Ventes exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les devis à travers ces
fonctions plutôt qu'en important `apps.ventes.models` directement (voir
CLAUDE.md, règle de modularité). Comportement strictement identique aux requêtes
inline d'origine.
"""


def compter_devis(company):
    """SCA22 — nombre de devis d'une société (console fondateur). Point d'entrée
    cross-app en LECTURE : ``authentication`` lit ce compteur sans importer
    ``apps.ventes.models``."""
    from .models import Devis
    return Devis.objects.filter(company=company).count()


def devis_for_lead(lead, ids):
    """Devis d'un lead (dans la société du lead), pour les ids donnés, triés par
    id. Liste matérialisée — comportement identique au filtre inline d'origine."""
    from .models import Devis
    return list(
        Devis.objects.filter(id__in=ids, lead=lead, company=lead.company)
        .order_by('id'))


def devis_lecture_seule_pour_lead(lead):
    """VT3 — les devis d'un lead, en LECTURE SEULE, pour un panneau externe.

    Écrit pour le panneau « client + devis » de la visite technique terrain
    (``apps/crm``) : c'est la SEULE porte par laquelle crm lit un devis — la
    frontière M3 interdit d'importer ``ventes.models`` depuis une autre app
    domaine.

    CE QUI SORT, ET RIEN D'AUTRE : référence, statut, date, total TTC, et les
    lignes PRODUIT comptées dans les totaux (désignation, quantité, prix
    unitaire TTC, total TTC). ``prix_achat`` — et toute donnée de coût ou de
    marge — ne franchit JAMAIS cette fonction : le panneau est montré au
    commercial ET dérivé d'un document client.

    Les montants TTC sont dérivés du HT de chaque ligne par son taux de TVA
    EFFECTIF (celui de la ligne, sinon celui du devis) : aucune valeur
    inventée, aucun taux par défaut codé ici.
    """
    from decimal import ROUND_HALF_UP, Decimal

    from .models import Devis

    cent = Decimal('0.01')
    dossiers = []
    devis_qs = (Devis.objects
                .filter(lead=lead, company=lead.company)
                .prefetch_related('lignes')
                .order_by('-id'))
    for devis in devis_qs:
        lignes = []
        for ligne in devis.lignes.all():
            if not ligne.compte_dans_totaux:
                continue
            taux = Decimal(str(ligne.taux_tva_effectif or 0))
            coefficient = Decimal('1') + (taux / Decimal('100'))
            unitaire = Decimal(str(ligne.prix_unitaire or 0)) * coefficient
            total = Decimal(str(ligne.total_ht)) * coefficient
            lignes.append({
                'designation': ligne.designation,
                'quantite': str(Decimal(str(ligne.quantite or 0))),
                'prix_unitaire_ttc': str(
                    unitaire.quantize(cent, rounding=ROUND_HALF_UP)),
                'total_ttc': str(
                    total.quantize(cent, rounding=ROUND_HALF_UP)),
            })
        dossiers.append({
            'id': devis.id,
            'numero': devis.reference,
            'statut': devis.statut,
            'date': (devis.date_creation.date().isoformat()
                     if devis.date_creation else None),
            'total_ttc': str(
                Decimal(str(devis.total_ttc)).quantize(
                    cent, rounding=ROUND_HALF_UP)),
            'lignes': lignes,
        })
    return dossiers


def get_devis_by_pk(pk):
    """Devis par pk (ou None). Lecture seule, non scopé — l'appelant vérifie la
    société comme avant."""
    from .models import Devis
    return Devis.objects.filter(pk=pk).first()


def devis_value_for_lead(lead_id, company):
    """PUB31 — montant TTC + devise du devis le plus RÉCENT lié à un lead.

    Point d'entrée cross-app LECTURE SEULE, fonction FINE, pour
    ``apps.adsengine.capi_crm`` (enrichissement OPTIONNEL, flag-gaté, de
    l'événement CAPI CRM-stage QUOTE_SENT avec ``custom_data.value/currency`` —
    jamais un import de ``apps.ventes.models`` côté adsengine, jamais touché le
    chemin ``signed_contract``/``capi_odoo``, distinct et intact). Renvoie
    ``{'value': float, 'currency': str}`` ou ``None`` si aucun devis lié."""
    if not lead_id:
        return None
    from .models import Devis
    devis = (Devis.objects
             .filter(lead_id=lead_id, company=company)
             .order_by('-date_creation', '-id')
             .first())
    if devis is None:
        return None
    return {'value': float(devis.total_ttc), 'currency': devis.devise or 'MAD'}


def is_devis_accepte(devis):
    """Vrai si le devis est au statut « Accepté » (sans exposer l'enum)."""
    from .models import Devis
    return devis.statut == Devis.Statut.ACCEPTE


def production_attendue_pour_devis(devis_id):
    """YSERV8 — production annuelle attendue (kWh) calculée au devis.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.monitoring`` (jamais
    un import direct de ``ventes.models``) : lit la production annuelle stockée
    dans ``Devis.etude_params['production_annuelle']`` (semée par le moteur
    solaire à la création). Renvoie un ``Decimal`` positif, ou ``None`` si le
    devis n'existe pas, n'a pas d'étude, ou porte une valeur non exploitable.
    """
    from decimal import Decimal, InvalidOperation

    from .models import Devis
    devis = Devis.objects.filter(pk=devis_id).only('etude_params').first()
    if devis is None:
        return None
    params = devis.etude_params or {}
    raw = params.get('production_annuelle')
    if raw is None:
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return val if val > 0 else None


def pr_initial_pour_chantier(installation_id):
    """YSERV8 — énergie annuelle attendue (kWh) du test de performance FG278.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.monitoring`` : renvoie
    l'``energie_attendue_kwh`` du dernier ``TestPerformanceReception`` (PR
    initial de recette, FG278) lié au chantier donné, ou ``None`` s'il n'y en a
    pas de valeur exploitable. Le PR de recette prime sur l'étude du devis quand
    il existe (mesure terrain > prévision).
    """
    from decimal import Decimal, InvalidOperation

    from .models import TestPerformanceReception
    raw = (TestPerformanceReception.objects
           .filter(chantier_id=installation_id,
                   energie_attendue_kwh__isnull=False,
                   energie_attendue_kwh__gt=0)
           .order_by('-date_mesure', '-created_at')
           .values_list('energie_attendue_kwh', flat=True)
           .first())
    if raw is None:
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return val if val > 0 else None


# ── XPRJ21 — devis accepté → projet (gestion_projet) ─────────────────────────
_MOTS_CLES_MO = (
    'pose', 'installation', 'main d’œuvre', "main d'œuvre",
    'main d’oeuvre', "main d'oeuvre", 'mo ', 'montage',
)


def devis_pour_projet(devis_id, company):
    """Devis ACCEPTÉ prêt pour création de projet (XPRJ21) — scopé société.

    Thin selector cross-app pour ``apps.gestion_projet`` (jamais un import de
    ``ventes.models``) : renvoie ``None`` si le devis n'existe pas, n'est pas
    de la société demandée, ou n'est pas ACCEPTÉ. Sinon un dict LECTURE SEULE
    avec les données nécessaires à la création du projet + du budget v1
    ventilé matériel/main-d'œuvre (classification par mots-clés de la
    désignation, alignée sur ``frontend/src/features/ventes/solar.js``).
    """
    from .models import Devis

    devis = (
        Devis.objects.filter(pk=devis_id, company=company)
        .select_related('client')
        .prefetch_related('lignes')
        .first())
    if devis is None or devis.statut != Devis.Statut.ACCEPTE:
        return None

    lignes_mo = []
    lignes_materiel = []
    for ligne in devis.lignes.all():
        cible = lignes_mo if _est_main_oeuvre(ligne.designation) \
            else lignes_materiel

        cible.append({
            'designation': ligne.designation,
            'total_ht': ligne.total_ht,
        })

    montant_mo = sum((ligne['total_ht'] for ligne in lignes_mo), 0)
    montant_materiel = sum(
        (ligne['total_ht'] for ligne in lignes_materiel), 0)

    return {
        'id': devis.id,
        'reference': devis.reference,
        'client_id': devis.client_id,
        'lead_id': devis.lead_id,
        'montant_materiel': montant_materiel,
        'montant_main_oeuvre': montant_mo,
        'nb_lignes_materiel': len(lignes_materiel),
        'nb_lignes_main_oeuvre': len(lignes_mo),
    }


def _est_main_oeuvre(designation):
    d = (designation or '').lower()
    return any(mot in d for mot in _MOTS_CLES_MO)


def devis_card(devis_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un devis pour le partage dans la
    messagerie. Scopée société : None si le devis n'appartient pas à la société.
    Format {label, subtitle, url}. N'expose aucun prix d'achat/marge."""
    from .models import Devis
    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .select_related('client').first())
    if devis is None:
        return None
    parts = []
    try:
        parts.append(devis.get_statut_display())
    except Exception:  # pragma: no cover - défensif
        pass
    client = getattr(devis, 'client', None)
    if client is not None:
        parts.append(str(client))
    return {
        'label': f'Devis {devis.reference}',
        'subtitle': ' · '.join(p for p in parts if p),
        'url': f'/devis/{devis.pk}',
    }


# ── DC23 — UN référentiel TVA + UN selector `tva_par_taux` ──────────────────
# La ventilation de la TVA par taux était copiée à l'identique dans trois
# propriétés (Devis/Facture/Avoir) ; FEC (exports.py) et DGI (dgi/) la
# reconsommaient. `tva_buckets` est désormais l'UNIQUE implémentation : un
# panier par taux effectif, réconcilié au centime. Les trois modèles et les
# exports DGI/FEC y délèguent → une seule logique de bucket, comportement
# strictement identique (mono-taux : formule d'origine HT×taux sans arrondi par
# panier → figures historiques inchangées ; taux mixtes : panier arrondi au
# centime dont la somme = total TVA).

# Référentiel des taux de TVA marocains (réforme 2024–2026). Source unique de
# vérité côté backend pour les contrôles/labels ; les taux EFFECTIFS d'un
# document restent portés par chaque ligne (taux_tva_effectif) ou le profil
# société (CompanyProfile.tva_standard / tva_panneaux). Ne fixe AUCUNE valeur
# en dur dans les calculs — sert de table de référence partagée.
TAUX_TVA_REFERENTIEL = {
    'standard': 20,     # équipements et prestations
    'panneaux': 10,     # panneaux photovoltaïques (réforme)
    'exonere': 0,       # opérations exonérées
}


def ligne_compte_dans_totaux(li):
    """XSAL5/XSAL14 — une ligne entre-t-elle dans les totaux d'un devis ?

    Est comptée UNIQUEMENT une ligne PRODUIT non optionnelle. Sont exclues des
    totaux (HT/TVA/TTC) : les lignes optionnelles non activées (XSAL5) et les
    lignes de section/note sans prix (XSAL14). Robuste par ``getattr`` : une
    ligne d'un autre modèle (LigneFacture/LigneAvoir, dépourvue de ces
    attributs) est TOUJOURS comptée → factures/avoirs strictement inchangés.
    """
    if getattr(li, 'optionnelle', False):
        return False
    return getattr(li, 'type_ligne', 'produit') == 'produit'


def tva_buckets(lignes, *, fallback_taux, frozen=None):
    """Ventilation TVA canonique (DC23). UNE seule implémentation partagée.

    Args:
        lignes: itérable de lignes exposant ``total_ht`` (Decimal-coercible) et
            ``taux_tva_effectif`` (taux %).
        fallback_taux: taux à utiliser quand il n'y a aucune ligne (mono-taux du
            document).
        frozen: tuple optionnel ``(taux, base_ht, montant)`` pour un montant figé
            (facture de tranche / acompte) — renvoyé tel quel en un seul panier.

    Returns: liste de paniers ``{'taux', 'base_ht', 'montant'}``. Mono-taux :
        formule d'origine (HT × taux, aucun arrondi par panier). Taux mixtes :
        un panier par taux, chaque TVA arrondie au centime.
    """
    from decimal import Decimal, ROUND_HALF_UP
    if frozen is not None:
        taux, base_ht, montant = frozen
        return [{'taux': taux, 'base_ht': base_ht, 'montant': montant}]

    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    buckets = {}
    for ligne in lignes:
        rate = Decimal(str(ligne.taux_tva_effectif))
        buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)

    def q(x):
        return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if len(buckets) <= 1:
        rate = next(iter(buckets), Decimal(str(fallback_taux)))
        base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
        # AUD189 — LA MÊME POLITIQUE QUE LA CHAÎNE CANONIQUE. Cette branche
        # rendait `base × taux` NON quantifié, en déléguant l'arrondi à
        # l'affichage : DEUX chaînes d'arrondi coexistaient donc sur la MÊME
        # facture (celle-ci et `_canonical_totaux`, qui quantifie en
        # ROUND_HALF_UP). La branche multi-taux ci-dessous quantifiait déjà ;
        # seul le mono-taux ne le faisait pas. Une seule politique, partout.
        return [{'taux': rate, 'base_ht': q(base),
                 'montant': q(base * rate / Decimal('100'))}]
    return [
        {'taux': rate, 'base_ht': q(buckets[rate]),
         'montant': q(buckets[rate] * rate / Decimal('100'))}
        for rate in sorted(buckets)
    ]


# ── QJ29 — Multi-propriétés : totaux par villa + total général ───────────────
# Un seul document, jamais scindé. Deux modes, tous deux additifs :
#   (A) ×N villas identiques : multiplicateur ``etude_params['nombre_proprietes']``
#       (défaut 1) appliqué aux totaux HT/TVA/TTC et à la production/économies.
#   (B) villas différentes : les lignes portent ``groupe_index`` (0 = commun,
#       1..N = villa N) → sous-totaux par villa + total général.
# Quand rien n'est utilisé (pas de groupe, N=1), le chemin mono-système reste
# STRICTEMENT inchangé (aucune de ces fonctions n'est appelée sur ce chemin).


def _absorber_arrondi(tva_par_taux, ttc, pas):
    """ARRONDI-100 (fondateur, 02/10/2026) — « tous mes devis finissent par
    deux zéros, sans centimes : garde les prix des articles, baisse juste le
    total au palier de 100 DH inférieur ».

    Le TTC ``ttc`` est ramené au multiple de ``pas`` INFÉRIEUR (jamais
    au-dessus : l'arrondi ne fait que baisser le prix). La baisse est une
    réduction de HT sur les paniers de TVA, dont la TVA est recalculée par la
    règle de la chaîne (``q(base × taux / 100)``) : ``ht_net + tva == ttc``
    tient donc toujours, au centime, et aucune ligne ne change de prix.

    ORDRE D'ESSAI (déterministe — l'écran le rejoue à l'identique) : le panier
    au taux le PLUS ÉLEVÉ absorbe ; à un seul taux, certains TTC ne sont
    atteints par AUCUNE base au centime (p. ex. 500,00 à 10 %), donc un autre
    panier peut céder de 1 à ``_ARRONDI_CENTIMES_CEDES`` centimes de HT en
    plus ; puis le panier suivant absorbe ; en dernier recours, le palier
    d'en dessous (un devis mono-taux 10 % seulement, une fois sur onze). Aucun
    palier atteignable ⇒ ``None`` (le total reste exact). Un TTC inférieur à
    ``pas`` n'est jamais ramené à zéro.

    Rend ``(paniers, arrondi_ht)`` ou ``None`` quand il n'y a rien à faire.
    MIROIR EXACT : ``frontend/src/features/ventes/remise.js``
    (``absorberArrondi``) — même ordre d'essai, même règle d'arrondi.
    """
    from decimal import Decimal as D, ROUND_FLOOR, ROUND_HALF_UP as RH

    pas = D(str(pas or 0))
    if pas <= 0 or ttc < pas:
        return None
    cible = (ttc / pas).to_integral_value(rounding=ROUND_FLOOR) * pas
    if cible == ttc:
        return None
    centime = D('0.01')

    def tva_de(base, taux):
        return (base * taux / D('100')).quantize(centime, rounding=RH)

    taux = [D(str(p['taux'])) for p in tva_par_taux]
    bases = [p['ht_net'] for p in tva_par_taux]
    ordre = sorted(range(len(bases)), key=lambda k: taux[k], reverse=True)
    for essai in (cible, cible - pas):
        if essai <= 0:
            break
        for i in ordre:
            # (autre panier qui cède, centimes cédés) — (None, 0) d'abord.
            cessions = [(None, 0)] + [
                (j, d) for j in ordre if j != i
                for d in range(1, _ARRONDI_CENTIMES_CEDES + 1)]
            for j, d in cessions:
                nouvelles = list(bases)
                if j is not None:
                    nouvelles[j] = bases[j] - d * centime
                    if nouvelles[j] < 0:
                        continue
                autres = sum((nouvelles[k] + tva_de(nouvelles[k], taux[k])
                              for k in range(len(bases)) if k != i), D('0'))
                reste = essai - autres      # le TTC que le panier i porte
                if reste < 0:
                    continue
                x0 = (reste * 100 / (100 + taux[i])).quantize(
                    centime, rounding=ROUND_FLOOR)
                for k in (-2, -1, 0, 1, 2):
                    x = x0 + k * centime
                    if x < 0 or x > bases[i]:
                        continue
                    if x + tva_de(x, taux[i]) == reste:
                        nouvelles[i] = x
                        paniers = [dict(p) for p in tva_par_taux]
                        for k, p in enumerate(paniers):
                            p.update(ht_net=nouvelles[k], base_ht=nouvelles[k],
                                     montant=tva_de(nouvelles[k], taux[k]))
                        return paniers, (sum(bases, D('0'))
                                         - sum(nouvelles, D('0')))
    return None


#: ARRONDI-100 — centimes de HT qu'un second panier de TVA peut céder pour que
#: le palier soit atteint exactement (2 suffisent sur 20 000 devis 10 %/20 %
#: simulés ; 5 laisse de la marge). Miroir : ``remise.js``.
_ARRONDI_CENTIMES_CEDES = 5


def _canonical_totaux(lignes, *, remise_globale_pct, fallback_taux,
                      arrondi_pas=None):
    """QJ29 — chaîne HT → remise → TVA (par taux) → TTC pour un lot de lignes.

    ``lignes`` : itérable de LigneDevis (expose ``total_ht`` et
    ``taux_tva_effectif``). Renvoie un dict {ht_brut, remise, arrondi, ht_net,
    tva, tva_par_taux, ttc}. La remise globale s'applique proportionnellement à
    chaque panier de taux (comme le builder), réconcilié au centime.

    ARRONDI-100 — ``arrondi_pas`` (MAD, p. ex. 100) ramène le TTC au palier
    inférieur (:func:`_absorber_arrondi`) ; ``arrondi`` est la baisse de HT
    correspondante, entre la remise et le HT net. Absent / 0 (factures
    saisies, avoirs, lots, villas) ⇒ ``arrondi == 0`` et chiffres inchangés.
    """
    from decimal import Decimal as D, ROUND_HALF_UP as RH
    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    disc = D(str(remise_globale_pct or 0))

    def q(x):
        return x.quantize(D('0.01'), rounding=RH)

    ht_brut = sum((D(str(li.total_ht)) for li in lignes), D('0'))
    remise = q(ht_brut * disc / D('100')) if disc > 0 else D('0')
    # ERR-QAH-PROP-TOTAUX-REMISE-100-NEGATIF — un HT brut à demi-centime
    # (0,005) et une remise de 100 % arrondie AU-DESSUS (0,01) donnaient un HT
    # net de q(-0,005) = -0,01, donc un TTC négatif : le HT net est borné à 0
    # (une remise ne rend jamais un document négatif). Aucun effet ailleurs :
    # hors ce cas limite, ``ht_brut - remise`` est toujours ≥ 0.
    ht_net = max(q(ht_brut - remise), D('0.00'))

    buckets = {}
    for li in lignes:
        rate = D(str(li.taux_tva_effectif
                     if li.taux_tva_effectif is not None else fallback_taux))
        buckets[rate] = buckets.get(rate, D('0')) + D(str(li.total_ht))

    # Chaque panier expose ``ht_net`` ET ``base_ht`` (alias) : ``base_ht`` est la
    # clé qu'attendent les consommateurs de ``tva_buckets`` (UBL, PDF facture),
    # ``ht_net`` reste pour les appelants historiques — les deux valent la base
    # HT nette (après remise) du panier, pour un drop-in compatible (QX1/QX2).
    if len(buckets) <= 1:
        rate = next(iter(buckets), D(str(fallback_taux)))
        tva_amt = q(ht_net * rate / D('100'))
        tva_par_taux = [{'taux': rate, 'montant': tva_amt,
                         'ht_net': ht_net, 'base_ht': ht_net}]
    else:
        rates = sorted(buckets)
        nets = {r: q(buckets[r] * (D('1') - disc / D('100'))) for r in rates}
        residu = q(ht_net - sum(nets.values(), D('0')))
        nets[rates[-1]] = q(nets[rates[-1]] + residu)
        tva_par_taux = [
            {'taux': r, 'montant': q(nets[r] * r / D('100')),
             'ht_net': nets[r], 'base_ht': nets[r]}
            for r in rates
        ]
        tva_amt = q(sum((b['montant'] for b in tva_par_taux), D('0')))

    ttc = q(ht_net + tva_amt)
    arrondi = D('0.00')
    absorbe = _absorber_arrondi(tva_par_taux, ttc, arrondi_pas)
    if absorbe is not None:
        tva_par_taux, arrondi = absorbe
        ht_net = q(ht_net - arrondi)
        tva_amt = q(sum((b['montant'] for b in tva_par_taux), D('0')))
        ttc = q(ht_net + tva_amt)
    return {
        'ht_brut': q(ht_brut), 'remise': remise, 'arrondi': arrondi,
        'ht_net': ht_net, 'tva': tva_amt, 'tva_par_taux': tva_par_taux,
        'ttc': ttc,
    }


def multi_villa_totaux(devis):
    """QJ29 — totaux par villa + total général d'un devis multi-propriétés.

    Renvoie None quand le devis n'est PAS multi-villa (aucune ligne groupée) :
    le chemin mono-système reste inchangé. Sinon :
        {
          'groupes': [{'index', 'label', 'totaux': {...}}, ...],  # trié par index
          'grand_total': {...},   # chaîne canonique sur TOUTES les lignes
        }
    ``index`` 0 = équipement commun. Company scoping : on lit uniquement les
    lignes du devis fourni (déjà borné à sa société par l'appelant).
    """
    lignes = list(devis.lignes.all())
    grouped = [li for li in lignes if getattr(li, 'groupe_index', None) is not None]
    if not grouped:
        return None

    fallback = devis.taux_tva
    remise = devis.remise_globale
    by_index = {}
    labels = {}
    for li in lignes:
        idx = getattr(li, 'groupe_index', None)
        if idx is None:
            continue
        by_index.setdefault(idx, []).append(li)
        lbl = (getattr(li, 'groupe_label', '') or '').strip()
        if lbl and idx not in labels:
            labels[idx] = lbl

    groupes = []
    for idx in sorted(by_index):
        default_label = 'Équipement commun' if idx == 0 else f'Villa {idx}'
        groupes.append({
            'index': idx,
            'label': labels.get(idx, default_label),
            'totaux': _canonical_totaux(
                by_index[idx], remise_globale_pct=remise,
                fallback_taux=fallback),
        })

    # QJR8 — les lignes SANS groupe_index ne disparaissent plus : elles
    # rejoignent une rubrique nommée « Hors groupe » plutôt que d'être omises
    # du détail par villa (elles restaient déjà comptées nulle part avant ce
    # correctif, ni dans un sous-total, ni dans le total général).
    hors_groupe = [
        li for li in lignes if getattr(li, 'groupe_index', None) is None]
    if hors_groupe:
        groupes.append({
            'index': None,
            'label': 'Hors groupe',
            'totaux': _canonical_totaux(
                hors_groupe, remise_globale_pct=remise,
                fallback_taux=fallback),
        })

    # QJR8 — le total général porte désormais la MÊME population de lignes que
    # la chaîne canonique du document entier (`ligne_compte_dans_totaux`
    # honoré via `_canonical_totaux`), groupées ou non : avant ce correctif, ne
    # sommer que les lignes groupées rendait `grand_total` < total du document
    # dès qu'une ligne hors groupe existait — deux chiffres irréconciliables
    # sur la même page d'un PDF client.
    # ARRONDI-100 — le total général EST l'argent du devis (``Devis.total_ttc``
    # passe par le même palier) ; les sous-totaux par villa restent exacts.
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    grand_total = _canonical_totaux(
        lignes, remise_globale_pct=remise, fallback_taux=fallback,
        arrondi_pas=PAS_ARRONDI_DEVIS)
    return {'groupes': groupes, 'grand_total': grand_total}


from .multivilla import nombre_proprietes, puissance_kwc_projet  # noqa: E402,F401 — ré-export


def totaux_multi_proprietes(totaux, n):
    """ERR-QAC-MULTIVILLA-TOTAL-XN — met un dict de totaux canoniques (sortie
    de :func:`_canonical_totaux`) à l'échelle ×N villas identiques.

    DÉCISION FONDATEUR (30/09/2026, « ×N everywhere ») : la facturation suit le
    total ×N IMPRIMÉ. Le document multiplie le total d'UNE villa (lignes =
    une villa) par N, étage par étage (``builder._scale_tot``) ; on fait
    EXACTEMENT la même chose ici, en Decimal : chaque étage au centime × un
    entier reste au centime, donc ``ht_net + tva == ttc`` tient toujours et le
    ×N de l'ERP est au centime celui du PDF. N=1 → le dict est rendu tel quel
    (chemin mono-système inchangé au bit près).
    """
    if n <= 1 or not isinstance(totaux, dict):
        return totaux
    out = dict(totaux)
    for k in ('ht_brut', 'remise', 'arrondi', 'ht_net', 'tva', 'ttc'):
        if out.get(k) is not None:
            out[k] = out[k] * n
    if isinstance(out.get('tva_par_taux'), list):
        paniers = []
        for b in out['tva_par_taux']:
            b = dict(b)
            for k in ('montant', 'ht_net', 'base_ht'):
                if b.get(k) is not None:
                    b[k] = b[k] * n
            paniers.append(b)
        out['tva_par_taux'] = paniers
    return out


def montants_devis(devis_ids, company):
    """CHT12 — Montants HT/TTC d'une liste de devis, EN BATCH.

    Point d'entrée cross-app en LECTURE SEULE (ex. le P&L projet de
    ``gestion_projet``, via ``installations.selectors``) — jamais un import
    direct de ``ventes.models``, façon batch de ``ca_devis_factures_par_
    clients``. Renvoie ``{devis_id: {'ht': Decimal, 'ttc': Decimal}}`` ; un id
    inconnu ou d'une autre société n'apparaît PAS dans le résultat."""
    from decimal import Decimal

    from .models import Devis

    devis_ids = list(devis_ids or [])
    if not devis_ids:
        return {}
    out = {}
    for devis in Devis.objects.filter(company=company, id__in=devis_ids):
        try:
            ht = Decimal(str(devis.total_ht or 0))
            ttc = Decimal(str(devis.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser l'appelant
            ht = ttc = Decimal('0')
        out[devis.id] = {'ht': ht, 'ttc': ttc}
    return out


def lignes_louables_devis(devis, produit_ids_louables):
    """ZCTR6 — Lignes d'un devis dont le produit est LOUABLE.

    Point d'entrée cross-app en LECTURE SEULE (rattachement d'ordres de
    location à un devis accepté) — jamais un import direct de
    ``apps.ventes.models`` depuis l'extérieur. L'appelant
    fournit ``produit_ids_louables`` (résolu via
    ``stock.selectors.produits_louables_qs`` — jamais réimporté ici, aucune
    dépendance directe à ``stock``). Renvoie une liste de dicts
    ``{'produit_id', 'quantite', 'ligne_id'}`` — une ligne dont le produit
    n'est PAS louable est simplement absente (ignorée par l'appelant)."""
    from .models import LigneDevis

    if not produit_ids_louables:
        return []
    lignes = (
        LigneDevis.objects
        .filter(devis=devis, produit_id__in=produit_ids_louables)
        .order_by('id')
    )
    return [
        {
            'ligne_id': ligne.id,
            'produit_id': ligne.produit_id,
            'quantite': ligne.quantite,
        }
        for ligne in lignes
    ]


def resoudre_plan_commission(company, owner):
    """XSAL6 — Point d'entrée cross-app (reporting/insights) pour résoudre le
    plan de commission d'un commercial.

    Ordre : plan actif dédié à ``owner`` → plan actif par défaut de la société
    (``owner=None``) → ``None`` (l'appelant retombe alors sur
    ``CompanyProfile.commission_mode``, comportement historique inchangé).
    Lecture seule ; ne consulte jamais ``prix_achat`` ici (la base
    ``marge_interne`` reste calculée et gardée ADMIN-ONLY côté appelant)."""
    from .models import PlanCommission

    if company is None:
        return None
    qs = PlanCommission.objects.filter(company=company, actif=True)
    if owner is not None:
        plan = qs.filter(owner=owner).first()
        if plan is not None:
            return plan
    return qs.filter(owner__isnull=True).first()


def devis_milestones(token):
    """QX34 — jalons post-signature d'un devis, résolus depuis un jeton
    ShareLink (lecture seule, public, tokenisé). Rien n'est muté.

    Dérive la timeline à partir des LIGNES EXISTANTES (aucun nouveau statut) :
    accepté → acompte reçu (Paiement) → matériel commandé (BonCommande) →
    installation (chantier via le sélecteur installations) → facturé.

    Renvoie ``None`` si le jeton est invalide/expiré/sans devis, sinon un dict
    ``{reference, milestones: [{key, label, done, date}]}``. Multi-tenant :
    le jeton borne un unique devis d'une seule société (aucune fuite d'une
    autre société), et jamais de prix d'achat/marge.
    """
    from django.utils import timezone
    from .models import ShareLink

    link = (ShareLink.objects
            .select_related('devis', 'devis__company')
            .filter(token=token).first())
    if link is None or not link.is_valid or not link.devis_id:
        return None
    devis = link.devis

    def _iso(d):
        return d.isoformat() if d is not None else None

    # 1) Accepté.
    accepte = devis.statut in ('accepte',) or devis.date_acceptation is not None
    date_accepte = getattr(devis, 'date_acceptation', None)

    # 2) Acompte reçu — un Paiement existe sur une facture liée au devis.
    from .models import Paiement
    paiement = (Paiement.objects
                .filter(facture__devis=devis)
                .order_by('date_paiement')
                .first())
    if paiement is None:
        # Chaîne BC → facture.
        paiement = (Paiement.objects
                    .filter(facture__bon_commande__devis=devis)
                    .order_by('date_paiement')
                    .first())
    acompte_recu = paiement is not None

    # 3) Matériel commandé — un BonCommande existe.
    bc = getattr(devis, 'bon_commande', None)
    materiel_commande = bc is not None
    date_bc = getattr(bc, 'date_creation', None) if bc else None

    # 4) Installation — chantier lié (via sélecteur installations, jamais
    #    d'import de son modèle).
    chantier = None
    try:
        from apps.installations.selectors import installation_for_devis
        chantier = installation_for_devis(devis)
    except Exception:  # noqa: BLE001 — best-effort
        chantier = None
    installation_faite = chantier is not None

    # 5) Facturé — au moins une facture liée.
    # AUD114 — `bc.factures` N'EXISTE PAS : l'accesseur inverse de
    # `Facture.bon_commande` est `facture` au SINGULIER (OneToOneField), donc
    # cette ligne levait AttributeError et le client qui cliquait le lien de
    # suivi que l'ERP lui avait envoyé recevait une page 500. Le court-circuit
    # du `or` ne sauvait rien : la branche gauche est justement fausse pour une
    # facture de la chaîne BC (cf. AUD112). Requête explicite (pas `hasattr`,
    # qui avale l'erreur) et parenthésage du ternaire, qui se lisait en réalité
    # `A or (B if bc else False)`.
    from .models import Facture as _Facture
    facture_emise = devis.factures.exists() or (
        bc is not None
        and _Facture.objects.filter(bon_commande=bc).exists())

    milestones = [
        {'key': 'accepte', 'label': 'Proposition acceptée',
         'done': bool(accepte), 'date': _iso(date_accepte)},
        {'key': 'acompte', 'label': 'Acompte reçu',
         'done': bool(acompte_recu),
         'date': _iso(getattr(paiement, 'date_paiement', None))},
        {'key': 'materiel', 'label': 'Matériel commandé',
         'done': bool(materiel_commande),
         'date': (date_bc.date().isoformat()
                  if hasattr(date_bc, 'date') else _iso(date_bc))},
        {'key': 'installation', 'label': 'Installation',
         'done': bool(installation_faite),
         'date': (getattr(chantier, 'statut', None)
                  if chantier is not None else None)},
        {'key': 'facture', 'label': 'Facturé',
         'done': bool(facture_emise), 'date': None},
    ]
    return {
        'reference': devis.reference,
        'generated_at': timezone.now().isoformat(),
        'milestones': milestones,
    }


def devis_events_for_lead(lead_id, company):
    """QX32be — événements de cycle de vie des devis d'un LEAD (lecture seule).

    Point d'entrée cross-app UNIQUE pour que ``crm`` fusionne les jalons devis
    (envoyé/ouvert/signé/refusé) + un résumé d'engagement dans son historique
    lead, SANS importer ``apps.ventes.models``. Multi-tenant : borné à la
    société fournie (jamais de fuite d'une autre société). Jamais de
    ``prix_achat``/marge.

    Renvoie une liste d'événements triés (plus récents d'abord) :
    ``[{devis_id, reference, kind, label, at, engagement}]`` où ``kind`` ∈
    {sent, opened, signed, refused}. ``engagement`` (résumé par section) n'est
    posé que sur l'événement ``opened``.
    """
    from .models import Devis, ShareLink

    if not lead_id:
        return []
    devis_qs = (Devis.objects
                .filter(lead_id=lead_id, company=company)
                .order_by('-date_creation'))

    # Résumé d'engagement par devis (dernier ShareLink vu).
    links = (ShareLink.objects
             .filter(devis__lead_id=lead_id, devis__company=company)
             .order_by('devis_id', '-created_at'))
    eng_by_devis = {}
    first_view_by_devis = {}
    for lk in links:
        if lk.devis_id not in eng_by_devis:
            eng_by_devis[lk.devis_id] = lk.engagement_summary
            first_view_by_devis[lk.devis_id] = lk.first_viewed_at

    def _iso(d):
        return d.isoformat() if d is not None else None

    events = []
    for devis in devis_qs:
        ref = devis.reference
        if devis.date_envoi is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'sent',
                'label': 'Devis envoyé', 'at': _iso(devis.date_envoi),
                'engagement': None,
            })
        fv = first_view_by_devis.get(devis.id)
        if fv is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'opened',
                'label': 'Proposition ouverte', 'at': _iso(fv),
                'engagement': eng_by_devis.get(devis.id) or {},
            })
        if devis.statut == 'accepte' and devis.date_acceptation is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'signed',
                'label': 'Devis signé', 'at': _iso(devis.date_acceptation),
                'engagement': None,
            })
        if devis.statut == 'refuse' and devis.date_refus is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'refused',
                'label': 'Devis refusé', 'at': _iso(devis.date_refus),
                'engagement': None,
            })
    events.sort(key=lambda e: (e['at'] or ''), reverse=True)
    return events


# ── PUB58/59/60 — Contacts pour les audiences de croissance (ADSDEEP57) ──────
# Lecture directe des FK Devis→crm.Client/Lead déjà déclarées sur le modèle
# (même pattern que `analyse_facturation`/`revenu_attribue_campagne`) — jamais
# un import d'``apps.crm.models``.

def _client_contact(client):
    """Contact ``{'email', 'telephone'}`` d'un ``crm.Client`` (ou ``None`` si
    aucun identifiant exploitable). Même contrat que
    ``apps.crm.selectors.clients_contact_identifiers``."""
    if client is None:
        return None
    email = client.email or ''
    telephone = client.telephone or ''
    if not email and not telephone:
        return None
    return {'email': email, 'telephone': telephone}


def _devis_contact(devis):
    """Contact ``{'email', 'telephone'}`` résolu depuis le LEAD d'origine du
    devis si présent, sinon le client. ``None`` si aucun identifiant."""
    if devis.lead_id and devis.lead:
        email = devis.lead.email or ''
        telephone = devis.lead.telephone or devis.lead.whatsapp or ''
        if email or telephone:
            return {'email': email, 'telephone': telephone}
    return _client_contact(devis.client)


def devis_view_tracking_segments(company):
    """PUB58 — Segmente les devis ENVOYÉS non encore ACCEPTÉS/REFUSÉS/EXPIRÉS
    de la société en deux paniers de contacts, depuis le view-tracking
    ``ShareLink`` (QJ1) qui dort en base :

      * ``jamais_ouvert`` — devis envoyé, AUCUN ``ShareLink`` consulté
        (``view_count`` nul sur tous ses liens, ou aucun lien du tout) ;
      * ``ouvert_non_signe`` — devis envoyé et consulté (au moins un
        ``ShareLink`` avec ``view_count`` > 0), toujours pas accepté
        (objection prix probable).

    Chaque panier appelle un angle de relance différent (PUB58). Renvoie
    ``{'jamais_ouvert': [...], 'ouvert_non_signe': [...]}`` (dicts
    ``{'email', 'telephone'}``, même contrat que
    ``apps.crm.selectors.lead_contact_identifiers``)."""
    from .models import Devis

    qs = (Devis.objects
          .filter(company=company, statut=Devis.Statut.ENVOYE)
          .select_related('client', 'lead')
          .prefetch_related('share_links'))

    jamais_ouvert, ouvert_non_signe = [], []
    for devis in qs:
        contact = _devis_contact(devis)
        if not contact:
            continue
        views = [sl.view_count for sl in devis.share_links.all()]
        if views and max(views) > 0:
            ouvert_non_signe.append(contact)
        else:
            jamais_ouvert.append(contact)
    return {'jamais_ouvert': jamais_ouvert, 'ouvert_non_signe': ouvert_non_signe}


def devis_ouverts_ratio_client(company, client_id, *, limit=200):
    """CAD140 — pour chaque devis NON-BROUILLON du client ``client_id``, a-t-il
    été ouvert au moins une fois par le client (``ShareLink.view_count`` > 0,
    compteur de visites DISTINCTES fiabilisé par CAD137) ?

    Reprend le signal comportemental (ouverture de proposition) que
    ``apps.crm.engagement`` cite depuis sa création mais n'a jamais pu porter,
    faute d'un sélecteur PAR CLIENT côté ``ventes`` — ``devis_view_tracking_
    segments`` (PUB58) n'agrège qu'en PANIER de contacts (email/téléphone),
    jamais par ``client_id``.

    Renvoie ``{'total': int, 'ouverts': int}`` — jamais un ratio pré-calculé,
    pour ne rien arrondir deux fois côté appelant (même patron que
    ``_ratio_devis_acceptes_score``/``devis_du_client_portail``). Un client
    sans aucun devis non-brouillon renvoie ``{'total': 0, 'ouverts': 0}`` —
    zéro documents, jamais une pénalité fantôme.

    Lecture seule. Jamais un import de ``apps.crm.models`` : ``client_id``
    suffit, exactement le même contrat que ``devis_du_client_portail``.
    """
    from .models import Devis

    if company is None or not client_id:
        return {'total': 0, 'ouverts': 0}
    qs = (Devis.objects
          .filter(company=company, client_id=client_id)
          .exclude(statut=Devis.Statut.BROUILLON)
          .prefetch_related('share_links')
          .order_by('-date_creation')[:limit])
    total = 0
    ouverts = 0
    for devis in qs:
        total += 1
        views = [sl.view_count for sl in devis.share_links.all()]
        if views and max(views) > 0:
            ouverts += 1
    return {'total': total, 'ouverts': ouverts}


def expired_devis_contacts(company):
    """PUB59 — Contacts des devis EXPIRÉS (``Devis.statut='expire'``) de la
    société — angle de relance « votre prix était valable 30 j, nouvelle
    offre ». Un devis expiré est un statut DOCUMENT (rule #4), distinct du
    stade funnel COLD du lead (rule #2) : les deux ne se mélangent jamais
    ici (aucune lecture de ``stage``).

    EXCLUSION signée : un client qui a, PAR AILLEURS, au moins un devis
    ACCEPTÉ est retiré du segment — on ne relance jamais quelqu'un qui a
    déjà acheté. Renvoie une liste de dicts ``{'email', 'telephone'}``."""
    from .models import Devis

    expired = list(
        Devis.objects
        .filter(company=company, statut=Devis.Statut.EXPIRE)
        .select_related('client'))
    if not expired:
        return []

    client_ids = {d.client_id for d in expired if d.client_id}
    signed_client_ids = set(
        Devis.objects.filter(
            company=company, statut=Devis.Statut.ACCEPTE,
            client_id__in=client_ids)
        .values_list('client_id', flat=True)) if client_ids else set()

    seen, contacts = set(), []
    for devis in expired:
        if not devis.client_id:
            continue
        if devis.client_id in signed_client_ids or devis.client_id in seen:
            continue
        contact = _client_contact(devis.client)
        if not contact:
            continue
        seen.add(devis.client_id)
        contacts.append(contact)
    return contacts


def signed_clients_cross_sell_segments(company):
    """PUB60 — Segmente les clients SIGNÉS (≥1 devis ACCEPTÉ) en deux paniers
    d'upsell base installée :

      * ``sans_contrat`` — aucun ``sav.ContratMaintenance`` actif, lu via
        ``apps.sav.selectors.clients_sans_contrat_actif`` (version bulk de
        YSERV10 ``client_a_contrat_actif`` — RÉUTILISÉE, jamais
        réimplémentée) ;
      * ``sans_batterie`` — le devis d'ORIGINE (le premier ACCEPTÉ,
        chronologiquement) ne portait PAS l'option ``avec_batterie``.

    Renvoie ``{'sans_contrat': [...], 'sans_batterie': [...]}`` (dicts
    ``{'email', 'telephone'}``)."""
    from .models import Devis

    accepted = (Devis.objects
                .filter(company=company, statut=Devis.Statut.ACCEPTE)
                .select_related('client')
                .order_by('client_id', 'date_creation'))

    origin_by_client = {}
    for devis in accepted:
        if devis.client_id and devis.client_id not in origin_by_client:
            origin_by_client[devis.client_id] = devis  # 1er vu = le + ancien

    if not origin_by_client:
        return {'sans_contrat': [], 'sans_batterie': []}

    from apps.sav.selectors import clients_sans_contrat_actif
    sans_contrat_ids = clients_sans_contrat_actif(
        company, list(origin_by_client.keys()))

    sans_contrat, sans_batterie = [], []
    for client_id, devis in origin_by_client.items():
        contact = _client_contact(devis.client)
        if not contact:
            continue
        if client_id in sans_contrat_ids:
            sans_contrat.append(contact)
        if devis.option_acceptee != Devis.OptionAcceptee.AVEC_BATTERIE:
            sans_batterie.append(contact)
    return {'sans_contrat': sans_contrat, 'sans_batterie': sans_batterie}


def devis_accepted_totals_by_lead(company, lead_ids):
    """PUB62 — Total TTC des devis ACCEPTÉS par ``lead_id`` (somme si un lead
    a plusieurs devis signés) — le « ticket moyen » de la carte chaleur
    ville. Lecture directe de la FK ``Devis.lead``. Renvoie
    ``{lead_id: Decimal}`` — un ``lead_id`` sans devis accepté est ABSENT
    (jamais un 0 fabriqué)."""
    from decimal import Decimal

    from .models import Devis

    lead_ids = list(lead_ids or [])
    if not lead_ids:
        return {}
    totals = {}
    for devis in (Devis.objects
                  .filter(company=company, statut=Devis.Statut.ACCEPTE,
                          lead_id__in=lead_ids)):
        try:
            amount = Decimal(str(devis.total_ttc or 0))
        except Exception:
            amount = Decimal('0')
        totals[devis.lead_id] = totals.get(devis.lead_id, Decimal('0')) + amount
    return totals


def signature_velocity_by_month_and_mode(company):
    """PUB67 — Nombre de devis ACCEPTÉS (signatures), par MOIS CALENDAIRE
    (1-12, toutes années confondues — la SAISONNALITÉ récurrente, pas une
    série temporelle) et par ``mode_installation``. Référence temporelle =
    ``date_acceptation`` (posée à l'acceptation), repli sur ``date_creation``
    pour les rares devis acceptés sans cette date.

    Renvoie ``{'par_mode': {mode: {1..12: count}}, 'mois_couverts': int}`` —
    ``mois_couverts`` = nombre de MOIS-CALENDAIRES (année, mois) DISTINCTS
    couverts par au moins un devis accepté, tous modes confondus (le signal
    de fiabilité — l'appelant exige ≥12 pour parler d'un cycle annuel
    complet, règle checked-facts)."""
    from collections import defaultdict

    from .models import Devis

    counts = defaultdict(lambda: defaultdict(int))
    covered_year_months = set()
    qs = (Devis.objects
          .filter(company=company, statut=Devis.Statut.ACCEPTE)
          .values_list('mode_installation', 'date_acceptation',
                       'date_creation'))
    for mode, date_acceptation, date_creation in qs:
        ref = date_acceptation or (
            date_creation.date() if date_creation else None)
        if ref is None:
            continue
        key = mode or '(non renseigné)'
        counts[key][ref.month] += 1
        covered_year_months.add((ref.year, ref.month))
    return {
        'par_mode': {mode: dict(months) for mode, months in counts.items()},
        'mois_couverts': len(covered_year_months),
    }


def faits_temoignage_devis(company, devis_id):
    """PUB63 — Faits VÉRIFIÉS d'un devis pour un brief témoignage créatif.

    Point d'entrée cross-app LECTURE SEULE pour ``apps.adsengine`` (jamais un
    import de ``ventes.models`` côté adsengine). Renvoie ``None`` si le devis
    n'existe pas / n'appartient pas à la société. Sinon un dict :
    ``{signed, client_id, client_nom, puissance_kwc, production_kwh,
    economie_annuelle, ville}`` — chiffres tirés de l'ÉTUDE du devis (faits du
    projet réel, jamais inventés ; ``None`` par champ absent). ``signed`` reflète
    le statut « Accepté » (un deal signé)."""
    from .models import Devis

    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .select_related('client').first())
    if devis is None:
        return None
    etude = devis.etude_params or {}
    client = getattr(devis, 'client', None)

    def _num(*keys):
        for key in keys:
            val = etude.get(key)
            if val not in (None, ''):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None
        return None

    return {
        'signed': devis.statut == Devis.Statut.ACCEPTE,
        'client_id': getattr(client, 'id', None),
        'client_nom': str(client) if client is not None else '',
        'puissance_kwc': _num('puissance_kwc', 'kwc', 'champ_kwc'),
        'production_kwh': _num('annualKwh', 'production_annuelle_kwh'),
        'economie_annuelle': _num('economies_annuelles', 'savings'),
        'ville': (etude.get('ville') or '').strip() or None,
        'reference': devis.reference,
    }


# ── NTPRT10/NTPRT11 — Lectures self-service du PORTAIL CLIENT ───────────────
#
# Point d'entrée cross-app UNIQUE de ``apps.portail`` sur les documents
# ``ventes`` (jamais un import de ``apps.ventes.models`` depuis portail).
# Lecture SEULE et volontairement PAUVRE : uniquement ce qu'un client peut voir
# de SON dossier. Aucun champ de coût/marge n'y figure (``prix_achat``,
# ``marge``… ne sortent JAMAIS vers un écran client — registre
# ``core.permissions.SENSITIVE_FIELDS``), ni aucune donnée interne
# (propriétaire, notes, portée de visibilité).
#
# Les fonctions exigent ``company`` ET ``client_id`` : un ``client_id`` absent
# renvoie VIDE, jamais tous les documents de la société.

def devis_modifiabilite(devis):
    """QJR516 (contrat QJR500) — le verdict de modifiabilité d'un devis pour
    un AUTRE app (la ligne devis de la fiche lead, ``crm/serializers``) :
    ``{modifiable, raison_non_modifiable, revision_possible, is_active}``.
    Même prédicat que ``DevisSerializer`` (``domain/modifiabilite``), jamais
    une règle recopiée côté crm."""
    from .domain.modifiabilite import verdict
    resultat = dict(verdict(devis))
    resultat['is_active'] = bool(devis.is_active)
    return resultat


def devis_envoyes_du_client(company_id, client_id):
    """QJR590 — devis ACTIFS au statut « envoyé » d'un client (borné
    société) : ceux dont le client a déjà reçu un exemplaire et qui reçoivent
    une trace « corrigé après envoi » quand l'identité client est corrigée.
    Un accepté garde son exemplaire signé figé (exclu)."""
    from .models import Devis

    if not company_id or not client_id:
        return []
    return list(Devis.objects.filter(
        company_id=company_id, client_id=client_id, is_active=True,
        statut=Devis.Statut.ENVOYE))


def devis_du_client_portail(company, client_id, *, limit=200):
    """NTPRT10 — Devis visibles par le client ``client_id`` sur son portail.

    Les BROUILLONS internes sont EXCLUS : un devis non envoyé n'a jamais été
    montré au client, l'exposer serait une fuite de travail en cours.
    """
    from .models import Devis

    if company is None or not client_id:
        return []
    # QJR520 — une version remplacée n'est plus listée à côté de sa
    # remplaçante (is_active=True).
    qs = (Devis.objects
          .filter(company=company, client_id=client_id, is_active=True)
          .exclude(statut=Devis.Statut.BROUILLON)
          .order_by('-date_creation')[:limit])
    return [{
        'id': d.id,
        'reference': d.reference,
        'statut': d.statut,
        'statut_display': d.get_statut_display(),
        'date_creation': d.date_creation,
        'date_validite': d.date_validite,
        'total_ttc': str(d.total_ttc),
        'accepte': d.statut == Devis.Statut.ACCEPTE,
        # QJR565 (contrat portail ``mes_devis_liste.json``) — date de la
        # dernière correction après envoi (``etude_params.resync_apres_envoi``),
        # null sinon — JAMAIS updated_at.
        'mis_a_jour_le': _date_correction_apres_envoi(d),
    } for d in qs]


def _date_correction_apres_envoi(devis):
    """QJR565 — ISO de ``etude_params.resync_apres_envoi.date`` ou ``None``."""
    params = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    marqueur = params.get('resync_apres_envoi')
    if isinstance(marqueur, dict):
        return marqueur.get('date') or None
    return None


def devis_du_client_portail_obj(company, client_id, devis_id):
    """NTPRT10 — UN devis du client (objet ORM), ou ``None``.

    Le triplet (société, client, id) est exigé : un devis d'un autre client —
    ou d'une autre société — est INTROUVABLE, jamais « trouvé puis refusé ».
    """
    from .models import Devis

    if company is None or not client_id or not devis_id:
        return None
    return (Devis.objects
            .filter(company=company, client_id=client_id, pk=devis_id)
            .exclude(statut=Devis.Statut.BROUILLON)
            .first())


def factures_du_client_portail(company, client_id, *, limit=200):
    """NTPRT11 — Factures visibles par le client ``client_id`` sur son portail.

    Mêmes règles : brouillons internes exclus, aucun champ de coût.
    ``montant_du`` est le reste à payer déjà calculé par le modèle (source
    unique — jamais un recalcul local qui divergerait de l'écran interne),
    SAUF pour une facture ANNULÉE (AUD137) : ``Facture.montant_du`` ignore le
    statut par construction et rend donc le TTC entier pour une annulation
    sans paiement — l'agrégat portail compense ici en la figeant à '0.00'.
    ``payable`` (AUD137) est le SEUL champ que l'écran doit lire pour décider
    d'afficher « reste dû » et le bouton « Payer » : faux pour ANNULEE et
    PAYEE, jamais dérivé côté client depuis ``statut``.
    """
    from .models import Facture

    if company is None or not client_id:
        return []
    qs = (Facture.objects
          .filter(company=company, client_id=client_id)
          .exclude(statut=Facture.Statut.BROUILLON)
          # AUD159 — EXACTEMENT les relations lues par les deux propriétés
          # sérialisées ci-dessous : `total_ttc` itère `lignes` (via
          # `tva_par_taux`) et `montant_du` touche `paiements`,
          # `affectations_paiement`, `avoirs`, `notes_debit` et
          # `retenues_subies`. Le queryset n'avait AUCUN prefetch : jusqu'à
          # ~7 requêtes par facture, sur 200 factures par page — d'une surface
          # PUBLIQUE, donc exposée à la charge externe. La SOURCE des chiffres
          # ne change pas : les propriétés modèles restent propriétaires.
          .prefetch_related('lignes', 'paiements', 'avoirs', 'notes_debit',
                            'retenues_subies',
                            'affectations_paiement__paiement')
          .order_by('-date_emission', '-id')[:limit])
    return [{
        'id': f.id,
        'reference': f.reference,
        'statut': f.statut,
        'statut_display': f.get_statut_display(),
        'date_emission': f.date_emission,
        'date_echeance': f.date_echeance,
        'montant_ttc': str(f.total_ttc),
        'montant_du': ('0.00' if f.statut == Facture.Statut.ANNULEE
                       else str(f.montant_du)),
        'payee': f.statut == Facture.Statut.PAYEE,
        'payable': f.statut not in (
            Facture.Statut.ANNULEE, Facture.Statut.PAYEE),
    } for f in qs]


def facture_du_client_portail(company, client_id, facture_id):
    """NTPRT11 — UNE facture du client (objet ORM), ou ``None``. Voir ci-dessus."""
    from .models import Facture

    if company is None or not client_id or not facture_id:
        return None
    return (Facture.objects
            .filter(company=company, client_id=client_id, pk=facture_id)
            .exclude(statut=Facture.Statut.BROUILLON)
            .first())


def facture_est_payable_portail(facture):
    """AUD137 — une facture ANNULÉE ou déjà PAYÉE n'est plus payable au
    portail. Utilisé par ``portail.views_client.payer`` AVANT de créer/
    réutiliser une intention de paiement — jamais un import de
    ``apps.facturation.models`` côté portail (frontière cross-app)."""
    from .models import Facture

    return facture is not None and facture.statut not in (
        Facture.Statut.ANNULEE, Facture.Statut.PAYEE)


# ── NTPRT9 — Tableau de bord CLIENT (devis en attente / factures impayées) ──

def resume_portail_client(company, client_id):
    """NTPRT9 — Cartes « Devis en attente » / « Factures impayées » du
    tableau de bord portail CLIENT (``apps.portail.views_client``).

    Même périmètre EXACTEMENT que ``devis_du_client_portail``/
    ``factures_du_client_portail`` ci-dessus (brouillons exclus, aucun champ
    de coût) : les compteurs matchent donc, par construction, ce que l'écran
    interne montrerait pour ce même client — jamais un recalcul divergent.
    ``devis_en_attente`` = devis ``ENVOYE`` (ni accepté/refusé/expiré, en
    attente d'une décision du client). ``factures_impayees`` = factures
    ``EMISE``/``EN_RETARD`` (ni payées, ni annulées, ni brouillon) ;
    ``prochaine_echeance`` = la date d'échéance la plus proche parmi elles
    (``None`` si aucune échéance renseignée). Lecture seule."""
    from .models import Devis, Facture

    vide = {
        'devis_en_attente': 0,
        'factures_impayees': 0,
        'prochaine_echeance': None,
    }
    if company is None or not client_id:
        return vide

    devis_en_attente = Devis.objects.filter(
        company=company, client_id=client_id,
        statut=Devis.Statut.ENVOYE).count()

    factures_impayees_qs = Facture.objects.filter(
        company=company, client_id=client_id,
        statut__in=(Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
    prochaine_echeance = (
        factures_impayees_qs
        .exclude(date_echeance__isnull=True)
        .order_by('date_echeance')
        .values_list('date_echeance', flat=True)
        .first())

    return {
        'devis_en_attente': devis_en_attente,
        'factures_impayees': factures_impayees_qs.count(),
        # Chaîne ISO, jamais un objet date : la valeur part telle quelle dans
        # la réponse JSON du tableau de bord portail (contrat
        # apps/portail/contract_samples/client_tableau_de_bord.json).
        'prochaine_echeance': (
            prochaine_echeance.isoformat() if prochaine_echeance else None),
    }


def ca_par_entite(company, entite_ids):
    """NTADM25 — CA (devis retenus + factures) agrégé PAR ENTITÉ (NTADM2).

    Point d'entrée cross-app sanctionné pour ``apps.entites`` (vue consolidée
    « Groupe »), jamais un import direct de ``ventes.models``. MÊME règle de
    calcul que ``ca_devis_factures_par_clients`` — aucune logique dupliquée :
    devis REFUSÉS et factures ANNULÉES exclus, ``total_ttc`` sommé tel quel.

    Renvoie ``{entite_id: {'ca_devis': Decimal, 'ca_factures': Decimal,
    'nb_devis': int, 'nb_factures': int}}`` ; une entité sans document
    n'apparaît PAS (l'appelant fournit un défaut à zéro). Lecture seule,
    bornée à ``company`` — jamais de fuite cross-société.
    """
    from decimal import Decimal

    from .models import Devis, Facture

    ids = [i for i in (entite_ids or []) if i is not None]
    if not ids:
        return {}

    def _vide():
        return {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        }

    out = {}
    devis_qs = (Devis.objects
                .filter(company=company, entite_id__in=ids)
                .exclude(statut=Devis.Statut.REFUSE))
    for devis in devis_qs:
        entry = out.setdefault(devis.entite_id, _vide())
        try:
            entry['ca_devis'] += Decimal(str(devis.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_devis'] += 1

    facture_qs = (Facture.objects
                  .filter(company=company, entite_id__in=ids)
                  .exclude(statut=Facture.Statut.ANNULEE))
    for facture in facture_qs:
        entry = out.setdefault(facture.entite_id, _vide())
        try:
            entry['ca_factures'] += Decimal(str(facture.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_factures'] += 1
    return out


# ── QX29/QX30/PACT17 — « Relances du jour » : file d'action des devis ────────

def devis_action_requise(company, *, today=None, jours_sans_reponse=3,
                         jours_avant_expiration=7, jours_non_facture=7):
    """PACT17 — Regroupe les devis d'une société par ACTION ATTENDUE, miroir
    exact de ``apps.sav.selectors.file_action`` (ZSAV6, parité Odoo « Activity
    view »). C'est l'agrégat que ``DevisActionBoardPage`` consomme : il
    n'avait jamais été construit côté serveur, donc l'écran — pourtant publié
    au menu des rôles responsable/admin — était mort.

    Chaque devis tombe dans EXACTEMENT UN panier (le premier qui matche, dans
    l'ordre ci-dessous), pour qu'un même devis ne soit jamais compté deux
    fois :

      * ``acceptes_non_factures`` — accepté depuis plus de
        ``jours_non_facture`` jours sans aucune ``Facture`` liée (réutilise
        ``devis_a_facturer``, ZFAC12 — aucune logique dupliquée) ;
      * ``refuses_sans_motif``    — refusé sans ``motif_refus`` (QX26 : un
        refus sans motif est une information perdue pour toujours) ;
      * ``expirant_bientot``      — envoyé, ``date_validite`` dans les
        ``jours_avant_expiration`` jours (échéance non encore dépassée).
        CAD138 : ce panier passe DEVANT l'engagement — une date de validité
        qui tombe est une urgence datée ;
      * ``engagement_relance``    — envoyé et le moteur d'engagement (QX30be,
        ``ShareLink.engagement_triggers_fired``) a tiré au moins un
        déclencheur ENCORE actif (non ouvert 24 h / ouvert non signé 48 h /
        rouvert 3×). CAD138 : un déclencheur de plus de
        ``DECLENCHEUR_PEREMPTION_JOURS`` jours sort du panier ;
      * ``envoyes_sans_reponse``  — envoyé depuis plus de
        ``jours_sans_reponse`` jours sans aucun des signaux ci-dessus (palier
        de cadence).

    Les devis ``brouillon`` et ``expire`` ne sont JAMAIS dans un panier : le
    premier n'est pas encore parti, le second n'appelle plus de relance.

    Renvoie ``{'buckets': {clé: {'count': int, 'ids': [int, …]}, …},
    'wa_drafts': {devis_id: 'message'}, 'devis': {devis_id: {…}}}``.

      * ``wa_drafts`` ne porte QUE la file ``engagement_relance`` (le seul cas
        où le serveur sait quoi dire) ; l'écran retombe sur le lien wa.me nu
        partout ailleurs.
      * ``devis`` porte de quoi RENDRE chaque ligne (référence, client,
        téléphone, WhatsApp, total, CAD115 : ``prochaine_touche_crm``) pour
        les ids cités. Sans lui l'écran devait re-télécharger la liste des
        devis et n'y trouvait ni ``client_telephone`` ni ``client_whatsapp``
        (``DevisSerializer`` ne les publie pas) : les raccourcis « Appeler » /
        WhatsApp ne s'affichaient JAMAIS, et une référence au-delà de la
        première page de 50 tombait sur « #42 ». Le serveur sert donc ce dont
        l'écran a besoin, en un seul appel.

    Lecture seule, bornée à ``company`` — jamais de fuite cross-société.
    Aucun prix d'achat ni marge n'est exposé (règle #4) : seul le total TTC,
    déjà visible du client, accompagne la ligne.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import Devis

    today = today or timezone.localdate()
    now = timezone.now()

    envoyes_sans_reponse = []
    acceptes_non_factures = []
    refuses_sans_motif = []
    expirant_bientot = []
    engagement_relance = []
    wa_drafts = {}

    # ── Acceptés non facturés : ZFAC12 tel quel (jamais recodé ici) ──
    for devis in devis_a_facturer(company, jours=jours_non_facture,
                                  today=today):
        acceptes_non_factures.append(devis.id)

    # ── Refusés sans motif (QX26) ──
    refuses_sans_motif.extend(
        Devis.objects
        .filter(company=company, statut=Devis.Statut.REFUSE)
        .exclude(motif_refus__gt='')
        .order_by('id')
        .values_list('id', flat=True)
    )

    # ── Devis ENVOYÉS : un seul panier par devis, priorité au signal le plus
    # fort (engagement mesuré > échéance qui approche > simple cadence).
    envoyes = (Devis.objects
               .filter(company=company, statut=Devis.Statut.ENVOYE)
               .select_related('client')
               .prefetch_related('share_links')
               .order_by('id'))
    limite_expiration = today + timedelta(days=jours_avant_expiration)

    for devis in envoyes:
        # CAD138 — L'EXPIRATION PASSE DEVANT L'ENGAGEMENT. Une date de
        # validité qui tombe dans trois jours est une urgence DATÉE ; un
        # drapeau de comportement ne l'est plus après trois semaines. L'ordre
        # inverse cachait le premier derrière le second.
        if (devis.date_validite is not None
                and today <= devis.date_validite <= limite_expiration):
            expirant_bientot.append(devis.id)
            continue
        # CAD138 — et les déclencheurs se PÉRIMENT : inscrits une fois pour
        # toutes, sans aucun code de remise à zéro, ils ne sortaient jamais du
        # panier.
        declencheurs = set()
        for link in devis.share_links.all():
            declencheurs |= declencheurs_actifs(link, devis=devis, now=now)
        if declencheurs:
            engagement_relance.append(devis.id)
            wa_drafts[devis.id] = _brouillon_relance_engagement(
                devis, declencheurs)
            continue
        envoye_le = devis.date_envoi
        if (envoye_le is not None
                and (now - envoye_le) >= timedelta(days=jours_sans_reponse)):
            envoyes_sans_reponse.append(devis.id)

    paniers = {
        'envoyes_sans_reponse': envoyes_sans_reponse,
        'acceptes_non_factures': acceptes_non_factures,
        'refuses_sans_motif': refuses_sans_motif,
        'expirant_bientot': expirant_bientot,
        'engagement_relance': engagement_relance,
    }
    cites = {i for ids in paniers.values() for i in ids}
    # `prefetch_related('lignes')` : `Devis.total_ttc` itère les lignes — sans
    # ce préchargement, une requête PAR devis affiché (N+1).
    lignes = list(
        Devis.objects
        .filter(company=company, pk__in=cites)
        .select_related('client', 'lead')
        .prefetch_related('lignes'))

    # CAD115 — SIG9 : « Action requise » (vue Ventes) et la file calendaire du
    # CRM pouvaient réclamer le même devis le même jour avec deux messages
    # différents, sans aucun arbitrage entre elles. Chaque ligne affiche donc
    # ici la prochaine touche CRM déjà programmée (``crm.RelanceEtape`` À
    # FAIRE) — lue via le selector CRM sanctionné (jamais un import de
    # ``apps.crm.models``), une seule requête pour tous les leads cités
    # (même patron que ``prochaine_touche_par_lead`` côté MRY5).
    from apps.crm.selectors import prochaine_touche_par_lead
    lead_ids = {d.lead_id for d in lignes if d.lead_id}
    touches = prochaine_touche_par_lead(company, lead_ids)

    return {
        'buckets': {
            cle: {'count': len(ids), 'ids': list(ids)}
            for cle, ids in paniers.items()
        },
        'wa_drafts': wa_drafts,
        'devis': {d.id: _ligne_action_requise(d, touches) for d in lignes},
    }


def _ligne_action_requise(devis, touches=None):
    """PACT17 — de quoi RENDRE une ligne de « Relances du jour », rien de plus.

    Le WhatsApp vient du lead lié quand il existe (``crm.Lead.whatsapp``, lu
    par la relation string-FK déjà déclarée — jamais un import de
    ``apps.crm.models``, même motif que ``DevisSerializer.get_lead_nom``),
    sinon le téléphone du client fait office de numéro joignable. Le total est
    rendu en TEXTE décimal (jamais un flottant) — ``formatMAD`` le lit tel
    quel côté écran.

    CAD115 — ``touches`` est le dict ``{lead_id: (due_at, due_date, cadence,
    canal)}`` de ``apps.crm.selectors.prochaine_touche_par_lead`` : la ligne
    publie ``prochaine_touche_crm`` (``None`` quand le devis n'a pas de lead
    ou que le lead n'a aucune touche À FAIRE — jamais une valeur inventée).
    """
    client = getattr(devis, 'client', None)
    telephone = (getattr(client, 'telephone', '') or '') if client else ''
    whatsapp = ''
    if devis.lead_id:
        whatsapp = getattr(devis.lead, 'whatsapp', '') or ''
    total = devis.total_ttc
    touche = (touches or {}).get(devis.lead_id) if devis.lead_id else None
    prochaine_touche_crm = None
    if touche:
        due_at, due_date, cadence, canal = touche
        prochaine_touche_crm = {
            'due_at': due_at.isoformat() if due_at else None,
            'due_date': due_date.isoformat() if due_date else None,
            'cadence': cadence or '',
            'canal': canal or '',
        }
    return {
        'id': devis.id,
        'reference': devis.reference or '',
        'client_nom': (getattr(client, 'nom', '') or '') if client else '',
        'client_telephone': telephone,
        'client_whatsapp': whatsapp,
        'total_ttc': str(total) if total is not None else None,
        'prochaine_touche_crm': prochaine_touche_crm,
    }


def _brouillon_relance_engagement(devis, declencheurs):
    """PACT17/QX30 — message WhatsApp pré-rempli pour la file d'engagement.

    Le texte suit le déclencheur le plus parlant (jamais un message générique
    quand le serveur sait quoi dire) et ne cite AUCUN prix : un brouillon part
    tel quel dans WhatsApp, il doit rester une relance, pas une offre.
    """
    client = getattr(devis, 'client', None)
    # Prénom + nom, comme partout ailleurs dans ce fichier : « Bonjour Benali »
    # (le patronyme seul) ne se dit pas en français — on salue quelqu'un par
    # son prénom, ou par son nom complet. Un brouillon part TEL QUEL dans
    # WhatsApp : la salutation est la première chose que le client lit.
    prenom = (getattr(client, 'prenom', '') or '').strip() if client else ''
    patronyme = (getattr(client, 'nom', '') or '').strip() if client else ''
    nom = f'{prenom} {patronyme}'.strip()
    salutation = f'Bonjour {nom}' if nom else 'Bonjour'
    reference = getattr(devis, 'reference', '') or ''
    suffixe = f' (réf. {reference})' if reference else ''

    if 'reopened_3x' in declencheurs:
        corps = ('vous avez consulté votre proposition plusieurs fois'
                 f'{suffixe} — puis-je répondre à une question ?')
    elif 'opened_not_signed_48h' in declencheurs:
        corps = (f'avez-vous pu parcourir votre proposition{suffixe} ? '
                 'Je reste disponible pour en discuter.')
    else:
        corps = (f'votre proposition{suffixe} vous attend toujours — '
                 'souhaitez-vous que je vous la présente ?')
    return f'{salutation}, {corps}'


def devis_envoyes_periode(company, *, date_debut=None, date_fin=None,
                          commercial_id=None):
    """NTCPQ24 — Devis ENVOYÉS (ou au-delà) d'une société sur une période.

    Point d'entrée cross-app en LECTURE (sans importer
    ``apps.ventes.models``). La période porte
    sur ``date_envoi`` ; bornes optionnelles (ouvertes si absentes). Précharge
    les lignes/produits (le calcul de conformité les parcourt)."""
    from .models import Devis
    qs = Devis.objects.filter(
        company=company, date_envoi__isnull=False,
    ).select_related('client', 'created_by').prefetch_related(
        'lignes__produit__categorie')
    if date_debut:
        qs = qs.filter(date_envoi__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_envoi__date__lte=date_fin)
    if commercial_id:
        qs = qs.filter(created_by_id=commercial_id)
    return qs.order_by('date_envoi', 'id')


def devis_envoyes_en_attente(company, since=None):
    """MRY23 — Devis ENVOYÉS et TOUJOURS en attente de réponse depuis ``since``.

    Point d'entrée cross-app en LECTURE (``apps.crm`` démarre sa cadence
    « après devis » dessus sans importer ``apps.ventes.models``). Différence
    avec ``devis_envoyes_periode``, qui reste inchangé : le statut est
    contraint à ``ENVOYE``. Sans ce filtre, la reprise MRY23 relançait un
    client sur une proposition qu'il avait déjà ACCEPTÉE (ou refusée, ou qui
    avait expiré) — « alors, ce PDF ? » trois jours après la signature.

    ``since`` est un datetime (borne basse sur ``date_envoi``, ouverte si
    absente)."""
    from .models import Devis
    qs = Devis.objects.filter(
        company=company, statut=Devis.Statut.ENVOYE,
        date_envoi__isnull=False)
    if since is not None:
        qs = qs.filter(date_envoi__gte=since)
    return qs.order_by('date_envoi', 'id')


def lead_a_un_devis(lead):
    """MRY11 — Ce lead a-t-il déjà REÇU une proposition (devis sorti du
    brouillon : envoyé, accepté, refusé ou expiré) ?

    Lecture cross-app pour ``apps.crm`` (choix du gabarit de réveil : un lead
    jamais chiffré ne doit pas lire « vous aviez reçu un devis chez nous »).
    Un brouillon jamais envoyé ne compte pas."""
    from .models import Devis
    if lead is None or not getattr(lead, 'pk', None):
        return False
    return Devis.objects.filter(
        company_id=lead.company_id, lead=lead,
    ).exclude(statut=Devis.Statut.BROUILLON).exists()


def resultats_devis_periode(company, lead_ids, *, depuis, depuis_jour):
    """COCKPIT-CONTRÔLE (30/09/2026) — deux RÉSULTATS du bloc « Contrôle du
    suivi » du CRM, sur les leads ``lead_ids`` (itérable ou sous-requête
    d'identifiants) : les devis passés « envoyé » depuis ``depuis`` (instant
    aware, sur ``date_envoi`` — posée une fois au passage brouillon → envoyé)
    et les devis passés « accepté » depuis ``depuis_jour`` (sur
    ``date_acceptation``, une date). Lecture cross-app pour ``apps.crm``
    (frontière M3), bornée par ``company``. Deux COUNT.

    Rend ``{'envoyes': int, 'acceptes': int}``."""
    from .models import Devis

    base = Devis.objects.filter(company=company, lead_id__in=lead_ids)
    return {
        'envoyes': base.filter(date_envoi__gte=depuis).count(),
        'acceptes': base.filter(date_acceptation__gte=depuis_jour).count(),
    }


def leads_ayant_recu_un_devis(company, lead_ids):
    """Chaîne commerciale (décision fondateur du 25/09/2026) — sous-ensemble
    de ``lead_ids`` ayant déjà REÇU une proposition : la version EN LOT de
    ``lead_a_un_devis`` (devis sorti du brouillon : envoyé, accepté, refusé ou
    expiré). Renvoie un ``set`` d'identifiants de leads.

    Lecture cross-app pour ``apps.crm`` (les compteurs du cockpit « joints
    sans devis » / « visites à venir sans devis ») : une requête pour N leads,
    jamais une par lead."""
    from .models import Devis
    ids = list(lead_ids or [])
    if not ids:
        return set()
    return set(Devis.objects.filter(
        company=company, lead_id__in=ids,
    ).exclude(statut=Devis.Statut.BROUILLON).values_list('lead_id', flat=True))


def dernier_devis_relancable_du_lead(lead, brouillon_compris=False):
    """QJ-INVARIANT (fondateur 07/09/2026) — le devis le PLUS RÉCENT du lead
    encore relançable (ni refusé, ni expiré, ni accepté). ``None`` si aucun.

    RELANCE-SUITE (fondateur 08/09/2026, lead test1 aa) : par défaut seul un
    devis ENVOYÉ compte — « je fais le devis, je l'envoie, PUIS les étapes de
    suivi viennent ». Un BROUILLON n'est retenu que sur demande explicite
    (``brouillon_compris``), quand l'humain vient de cocher l'étape « préparer
    et envoyer le devis » : devis parti par WhatsApp hors ERP, statut resté
    brouillon (cas AR du 07/09).

    Lecture cross-app pour ``apps.crm`` (le filet « jamais un lead actif sans
    prochaine étape » choisit entre plan après-devis et étape générique)."""
    from .models import Devis
    if lead is None or not getattr(lead, 'pk', None):
        return None
    # M4 (revue Fable 07/09/2026) — ACCEPTE exclu aussi : relancer « alors,
    # cette proposition ? » un client qui a dit oui est exactement ce que
    # ``leads_avec_devis_accepte`` (placement) veut éviter.
    exclus = [Devis.Statut.REFUSE, Devis.Statut.EXPIRE, Devis.Statut.ACCEPTE]
    if not brouillon_compris:
        exclus.append(Devis.Statut.BROUILLON)
    return (Devis.objects
            .filter(company_id=lead.company_id, lead=lead)
            .exclude(statut__in=exclus)
            .order_by('-id').first())


def leads_avec_devis_accepte(company, lead_ids):
    """MRY30 — sous-ensemble de ``lead_ids`` portant AU MOINS un devis
    ACCEPTÉ. Renvoie un ``set`` d'identifiants de leads.

    Lecture cross-app pour ``apps.crm`` (le placement des anciens leads doit
    ÉCARTER un dossier déjà accepté : le relancer reviendrait à demander
    « alors, ce devis ? » à quelqu'un qui a dit oui — il n'attend qu'un
    passage en Signé, à la main). EN LOT : le placement traite plusieurs
    centaines de leads, une requête par lead serait un N+1 assumé."""
    from .models import Devis
    ids = list(lead_ids or [])
    if not ids:
        return set()
    return set(Devis.objects.filter(
        company=company, lead_id__in=ids, statut=Devis.Statut.ACCEPTE,
    ).values_list('lead_id', flat=True))


def dernier_devis_envoye_par_lead(company, lead_ids):
    """MRY30 — ``{lead_id: Devis}`` du devis ENVOYÉ le PLUS RÉCENT de chaque
    lead demandé (statut ``envoye`` uniquement, ``date_envoi`` renseignée).

    Lecture cross-app pour ``apps.crm`` : le placement des anciens leads date
    la cadence « après devis » depuis l'envoi RÉEL. Le statut compte autant
    que la date — un devis accepté, refusé ou expiré n'attend plus de
    réponse. EN LOT, pour la même raison que ci-dessus."""
    from .models import Devis
    ids = list(lead_ids or [])
    if not ids:
        return {}
    par_lead = {}
    # Tri CROISSANT : la dernière ligne écrite pour un lead est donc la plus
    # récente. `id` départage deux envois à la même seconde.
    for devis in Devis.objects.filter(
            company=company, lead_id__in=ids,
            statut=Devis.Statut.ENVOYE, date_envoi__isnull=False,
    ).order_by('lead_id', 'date_envoi', 'id'):
        par_lead[devis.lead_id] = devis
    return par_lead


def devis_en_cours(company):
    """NTCPQ23 — Devis NON encore acceptés d'une société (brouillon/envoyé).

    Point d'entrée cross-app en LECTURE (tableau de bord de marge interne,
    sans importer ``apps.ventes.models``).
    Précharge les lignes et leurs produits (le calcul de marge les parcourt)."""
    from .models import Devis
    return Devis.objects.filter(
        company=company,
        statut__in=(Devis.Statut.BROUILLON, Devis.Statut.ENVOYE),
    ).select_related('client', 'created_by').prefetch_related(
        'lignes__produit__categorie').order_by('-date_creation')


def frequence_co_achat(company, produit_id, *, limite=10):
    """NTCPQ19 — Fréquence de CO-ACHAT d'un produit dans les devis ACCEPTÉS.

    Point d'entrée cross-app en LECTURE (sans importer
    ``apps.ventes.models``) : renvoie ``[(produit_id, nb_devis), ...]`` trié par
    fréquence décroissante — les produits apparaissant dans les mêmes devis
    acceptés de la SOCIÉTÉ que ``produit_id``, hors lui-même. Lecture pure,
    jamais de prix d'achat ni de marge."""
    from collections import Counter
    from .models import Devis, LigneDevis

    devis_ids = LigneDevis.objects.filter(
        devis__company=company, devis__statut=Devis.Statut.ACCEPTE,
        produit_id=produit_id).values_list('devis_id', flat=True)
    devis_ids = set(devis_ids)
    if not devis_ids:
        return []
    paires = list(LigneDevis.objects.filter(
        devis_id__in=devis_ids).exclude(
            produit_id=produit_id).exclude(
                produit_id=None).values_list('devis_id', 'produit_id'))
    compteur = Counter({pid: 0 for _, pid in paires})
    vus = set()
    for devis_id, pid in paires:
        if (devis_id, pid) in vus:
            continue  # une même paire ne compte qu'une fois par devis
        vus.add((devis_id, pid))
        compteur[pid] += 1
    return compteur.most_common(limite)


def lots_totaux(devis):
    """NTCPQ18 — Sous-total PAR LOT + total consolidé d'un devis multi-sites.

    Renvoie ``None`` quand le devis ne porte AUCUN lot (chemin mono-site
    strictement inchangé). Sinon ::

        {
          'lots': [{'id', 'nom_lot', 'adresse_site', 'totaux': {...}}, ...],
          'hors_lot': {...} | None,      # lignes non rattachées à un lot
          'total_consolide': {...},      # TOUTES les lignes du devis
        }

    Chaque bloc de totaux passe par la MÊME chaîne canonique
    (``_canonical_totaux`` : HT brut → remise → TVA par taux → TTC) que les
    totaux du devis, donc la somme des lots + hors-lot recolle au total
    consolidé au centime — à l'``arrondi`` près (ARRONDI-100), que seul le
    total consolidé porte. Company scoping : seules les lignes du devis fourni
    (déjà borné à sa société par l'appelant) sont lues."""
    lots = list(devis.lots.all())
    if not lots:
        return None

    lignes = list(devis.lignes.all())
    fallback = devis.taux_tva
    remise = devis.remise_globale
    par_lot = {}
    for ligne in lignes:
        par_lot.setdefault(ligne.lot_id, []).append(ligne)

    blocs = [{
        'id': lot.id,
        'nom_lot': lot.nom_lot,
        'adresse_site': lot.adresse_site,
        'totaux': _canonical_totaux(
            par_lot.get(lot.id, []), remise_globale_pct=remise,
            fallback_taux=fallback),
    } for lot in lots]

    orphelines = par_lot.get(None, [])
    hors_lot = _canonical_totaux(
        orphelines, remise_globale_pct=remise,
        fallback_taux=fallback) if orphelines else None

    # ARRONDI-100 — le total consolidé EST l'argent du devis : même palier que
    # ``Devis.total_ttc`` (les blocs par lot restent exacts).
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    return {
        'lots': blocs,
        'hors_lot': hors_lot,
        'total_consolide': _canonical_totaux(
            lignes, remise_globale_pct=remise, fallback_taux=fallback,
            arrondi_pas=PAS_ARRONDI_DEVIS),
    }


# ── NTCPQ17 — Remises automatiques par palier de VOLUME, en cascade ──────────

def _paliers_volume_actifs(company):
    from .models import PalierRemiseVolume
    return list(PalierRemiseVolume.objects.filter(
        company=company, actif=True))


def _meilleur_palier(paliers, produit, quantite):
    """Palier le plus fort satisfait par ``quantite`` pour ce produit.

    Ordre de préférence : ``priorite`` décroissante, puis ``quantite_min``
    la plus élevée atteinte, puis la remise la plus forte."""
    from decimal import Decimal
    quantite = Decimal(str(quantite or 0))
    candidats = [
        p for p in paliers
        if p.matches_produit(produit) and quantite >= p.quantite_min]
    if not candidats:
        return None
    candidats.sort(
        key=lambda p: (p.priorite, p.quantite_min, p.remise_pct),
        reverse=True)
    return candidats[0]


def _categories_ayant_atteint_leur_seuil(paliers, lignes):
    """Noms de catégories dont le VOLUME cumulé atteint un palier dédié.

    ``lignes`` : itérable de ``{produit, quantite}``. Seuls les paliers portant
    une catégorie comptent ici (un palier « tout le catalogue » n'identifie
    aucune catégorie)."""
    from collections import defaultdict
    from decimal import Decimal
    volumes = defaultdict(Decimal)
    for ligne in lignes:
        produit = ligne.get('produit')
        cat = getattr(getattr(produit, 'categorie', None), 'nom', None)
        if cat:
            volumes[cat] += Decimal(str(ligne.get('quantite') or 0))
    atteintes = set()
    for palier in paliers:
        nom = palier.categorie_nom
        if not nom:
            continue
        if volumes.get(nom, Decimal('0')) >= palier.quantite_min:
            atteintes.add(nom)
    return atteintes


def decomposition_remise_volume(*, company, produit, quantite, lignes=None):
    """NTCPQ17 — DÉCOMPOSITION de la remise volume (remise ligne + cascade).

    * **Remise de ligne** : le meilleur palier satisfait par la quantité de
      CETTE ligne (comportement palier simple, comme XSAL2).
    * **Cascade globale** : quand au moins DEUX catégories du panier atteignent
      chacune leur seuil, les paliers marqués ``cumulable`` dont la
      ``quantite_min`` est couverte par le volume TOTAL du panier s'ajoutent,
      dans l'ordre de ``priorite`` décroissante.

    ``lignes`` : le panier complet (``[{produit, quantite}, ...]``) ; absent, la
    cascade ne se déclenche pas (une seule ligne ne peut pas couvrir deux
    catégories). Renvoie ``{remise_ligne_pct, cascade, remise_totale_pct}`` —
    les remises se COMPOSENT (jamais une addition naïve qui dépasserait 100 %).
    Aucune donnée de marge / ``prix_achat`` n'entre dans ce calcul."""
    from decimal import Decimal, ROUND_HALF_UP

    cent = Decimal('0.01')
    paliers = _paliers_volume_actifs(company)
    vide = {'remise_ligne_pct': '0.00', 'cascade': [],
            'remise_totale_pct': '0.00'}
    if not paliers:
        return vide

    ligne_palier = _meilleur_palier(paliers, produit, quantite)
    remise_ligne = (
        Decimal(str(ligne_palier.remise_pct)) if ligne_palier
        else Decimal('0'))

    cascade = []
    lignes = list(lignes or [])
    if len(lignes) > 1:
        atteintes = _categories_ayant_atteint_leur_seuil(paliers, lignes)
        if len(atteintes) >= 2:
            volume_total = sum(
                (Decimal(str(li.get('quantite') or 0)) for li in lignes),
                Decimal('0'))
            cumulables = [
                p for p in paliers
                if p.cumulable and volume_total >= p.quantite_min
                and (ligne_palier is None or p.id != ligne_palier.id)]
            cumulables.sort(
                key=lambda p: (p.priorite, p.quantite_min), reverse=True)
            cascade = [{
                'palier_id': p.id,
                'categorie_nom': p.categorie_nom,
                'quantite_min': str(p.quantite_min),
                'remise_pct': str(p.remise_pct),
                'portee': 'global',
            } for p in cumulables]

    reste = Decimal('1') - remise_ligne / Decimal('100')
    for entree in cascade:
        reste *= Decimal('1') - Decimal(entree['remise_pct']) / Decimal('100')
    totale = ((Decimal('1') - reste) * Decimal('100')).quantize(
        cent, ROUND_HALF_UP)

    return {
        'remise_ligne_pct': str(remise_ligne.quantize(cent, ROUND_HALF_UP)),
        'remise_ligne_palier_id': ligne_palier.id if ligne_palier else None,
        'cascade': cascade,
        'remise_totale_pct': str(totale),
    }


# ── NTEXT6 — source de liste whitelistée pour les boucles d'automatisation ──

def lignes_devis_pour_automatisation(devis_id, company, *, limite=200):
    """Lignes d'un devis, en LECTURE SEULE, pour une boucle d'automatisation.

    Thin selector cross-app (``apps.automation`` n'importe JAMAIS
    ``ventes.models``) : renvoie une liste de dicts bornée à ``limite``, scopée
    société, n'exposant AUCUN prix d'achat ni marge — uniquement ce qu'une
    sous-action a besoin de connaître d'une ligne. Les décimales sont rendues
    en CHAÎNES : le contexte d'une boucle peut être gelé en JSON (NTEXT7).
    Liste vide si le devis n'existe pas ou appartient à une autre société.
    """
    from .models import Devis

    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .prefetch_related('lignes').first())
    if devis is None:
        return []
    lignes = []
    for ligne in list(devis.lignes.all())[:max(0, int(limite))]:
        lignes.append({
            'id': ligne.pk,
            'designation': ligne.designation,
            'quantite': ('' if ligne.quantite is None
                         else str(ligne.quantite)),
            'produit_id': ligne.produit_id,
            'total_ht': str(ligne.total_ht),
        })
    return lignes


# ═══════════════════════════════════════════════════════════════════════════
# PVCOMPAT (fondateur 20/08/2026) — COMPATIBILITÉ DEUX À DEUX, point d'entrée
# cross-app.
#
# Le CALCUL vit dans ``apps.ventes.compatibilites`` (il tient au moteur
# électrique et au catalogue solaire, donc au domaine Ventes) ; l'ÉCRAN, lui,
# est la fiche produit du STOCK. Les trois fonctions ci-dessous sont la façade
# LICITE de ce calcul : `apps.stock` (et tout autre appelant) les appelle sans
# jamais importer `apps.ventes.compatibilites` ni, à plus forte raison, les
# modèles de ventes — exactement la règle cross-app de CLAUDE.md.
#
# Import FONCTION-LOCAL : ce module est chargé très tôt (les modèles y font des
# appels différés), et `compatibilites` tire `solar_design` + le noyau
# `core.electrique`. Le différer garde ce fichier sans dépendance au chargement.
# ═══════════════════════════════════════════════════════════════════════════
def compatibilites_du_produit(produit, company):
    """PVCOMPAT — la fiche « Compatibilités » d'un produit du stock.

    Forme CONTRACTUELLE committée dans
    ``apps/stock/contract_samples/produit_compatibilites.json`` :
    ``{produit, fiche_incomplete, installable, bilan, familles}``. Lecture
    seule, aucun prix (ni de vente, ni d'achat) ne traverse cette fonction.
    """
    from .compatibilites import compatibilites_du_produit as _impl
    return _impl(produit, company)


def verdict_panneau_onduleur(panneau, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple panneau/onduleur.

    ``statut`` ∈ ``compatible`` / ``reserve`` / ``incompatible`` / ``inconnu``,
    avec la TAXONOMIE du noyau ``core.electrique`` (bloquant → incompatible,
    alerte → réserve) et jamais un faux OK sur une fiche incomplète.
    """
    from .compatibilites import verdict_panneau_onduleur as _impl
    return _impl(panneau, onduleur)


def verdict_batterie_onduleur(batterie, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple batterie/onduleur.

    Délègue à la règle batterie UNIQUE du dépôt
    (``services._batterie_compatible``) : l'écran et la composition ne peuvent
    pas diverger.
    """
    from .compatibilites import verdict_batterie_onduleur as _impl
    return _impl(batterie, onduleur)


def share_link_niveau_map(devis_ids):
    """L-NIV-UI (24/08/2026) — ``niveau``/``otp_lecture`` des ``ShareLink``
    DÉJÀ EXISTANTS (jamais un mint) pour un lot de devis.

    Sert à ``apps.crm.serializers`` (fiche lead, onglet Devis) pour que le
    badge de niveau s'affiche dès le chargement de la fiche sans attendre un
    premier clic — le bug corrigé ici : avant, seul un POST ``share-link``
    (mint/re-mint explicite) alimentait l'état affiché côté écran, donc rien
    n'apparaissait après un simple rechargement tant que l'utilisateur n'avait
    pas ré-interagi. Lecture seule pure : ne crée jamais de lien, n'expose
    aucun token (aucun besoin pour le badge) — un devis sans lien encore minté
    est simplement absent du dict retourné."""
    from django.utils import timezone

    from .models import ShareLink
    ids = [i for i in (devis_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        ShareLink.objects
        .filter(devis_id__in=ids, expires_at__gt=timezone.now())
        .order_by('devis_id', '-expires_at')
        .values('devis_id', 'niveau', 'otp_lecture', 'sections')
    )
    out = {}
    for row in rows:
        devis_id = row['devis_id']
        if devis_id in out:  # garde la plus récente (première rencontrée)
            continue
        out[devis_id] = {
            'niveau': row['niveau'],
            'otp_lecture': row['otp_lecture'],
            # L-SECT (24/08/2026) — sections déjà posées sur CE lien, pour que
            # le dialogue « Envoyer au client » rouvre sur les cases réellement
            # en vigueur plutôt que sur les défauts. Dict vide = aucune case
            # décochée (comportement par défaut).
            'sections': row['sections'] or {},
        }
    return out


def share_link_lecture_map(devis_ids):
    """QJ-VUES (fondateur 09/09/2026 — « un endroit où je vois combien de fois
    le devis a été consulté, sur chaque fiche lead ») — statistiques de LECTURE
    CLIENT par devis, agrégées sur TOUS ses ``ShareLink`` (expirés compris :
    un lien re-minté après expiration ne remet jamais le compteur du devis à
    zéro), en UNE requête.

    Distinct de ``share_link_niveau_map`` (juste au-dessus) et PAS fusionné
    dedans : le badge de niveau ne doit exister que si un lien VALIDE existe
    (sa requête filtre les expirés), alors que le compteur de lectures est un
    HISTORIQUE — les deux sémantiques divergent. Lecture seule pure ; sert à
    ``apps.crm.serializers`` (fiche lead, onglet Devis). Un devis jamais
    partagé est absent du dict (le front affiche alors « jamais ouvert »).

    Les vues comptées ici sont celles de ``ShareLink.view_count`` — depuis
    QJ-ROBOTS (public_views), les robots d'aperçu (WhatsApp qui pré-charge la
    vignette du lien, crawlers) n'y entrent plus : le chiffre montré au
    commercial est une lecture HUMAINE."""
    from django.db.models import Max, Min, Sum

    from .models import ShareLink
    ids = [i for i in (devis_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        ShareLink.objects
        .filter(devis_id__in=ids)
        .values('devis_id')
        .annotate(
            nombre_vues=Sum('view_count'),
            premiere_consultation=Min('first_viewed_at'),
            derniere_consultation=Max('last_viewed_at'),
        )
    )
    out = {}
    for row in rows:
        premiere = row['premiere_consultation']
        derniere = row['derniere_consultation']
        out[row['devis_id']] = {
            'nombre_vues': row['nombre_vues'] or 0,
            'premiere_consultation': (
                premiere.isoformat() if premiere else None),
            'derniere_consultation': (
                derniere.isoformat() if derniere else None),
        }
    return out


def classer_produit_nom(nom):
    """STKCAT21 — le RÔLE de composition déduit des MOTS-CLÉS d'un nom, ou
    ``None``.

    Point d'entrée cross-app SANCTIONNÉ du classifieur par mots-clés : c'est
    par ici que ``apps.stock`` (le sérialiseur produit) lit la classification
    ventes, sans jamais importer ``apps.ventes.domain.catalogue`` — frontière
    inter-app, CLAUDE.md.

    Enveloppe MINCE de ``domain.catalogue.classer_produit`` : même entrée, même
    sortie, aucune règle en plus. C'est le REPLI PERMANENT de
    ``core.product_roles.role_effectif`` (rang 3, derrière le rôle déclaré sur
    la fiche et la famille de la catégorie) — il n'est jamais retiré. Pure
    lecture : ne requête rien, n'écrit rien.
    """
    from .domain.catalogue import classer_produit
    return classer_produit(nom)


def devis_utilisant_produit(user, produit_id, limit=20):
    """STKCAT25 — les devis RÉCENTS qui chiffrent ce produit, vus PAR ``user``.

    Frontière cross-app : ``apps.stock`` (onglet « Utilisé dans » de la fiche
    produit) lit les devis PAR ICI — jamais un import de ``apps.ventes.models``
    depuis une autre app.

    LA VISIBILITÉ EST CELLE DE LA LISTE ``/ventes/devis``, REJOUÉE À
    L'IDENTIQUE — jamais une copie allégée. Le chemin suit pas à pas
    ``DevisViewSet.get_queryset`` (``apps/ventes/views/devis.py``) et RÉUTILISE
    ses helpers, sans en réécrire un seul :

      1. ``company_qs`` (core.mixins)   — société (superuser sans société :
         tout ; compte sans société : rien) ;
      2. portail NTPRT10                — un compte externe ne voit QUE les
         devis de SON client, BROUILLON exclu (AUD143) ; une portée autre que
         « client », ou sans rattachement, ne voit RIEN (jamais tout) ;
      3. ``scope_queryset(created_by)`` — portée interne (Feature F).

    Sans ce rejeu, un commercial dont la portée masque un devis dans /ventes le
    verrait réapparaître par la fiche produit du Stock : la même donnée par une
    autre porte.

    Renvoie une liste de dicts ``{id, reference, client_nom, statut, date,
    total_ttc}``, du plus récent au plus ancien, bornée à ``limit``.
    ``total_ttc`` est un prix de VENTE en TEXTE décimal (jamais un flottant) ;
    ``date`` est la date de création en ISO. AUCUN prix d'achat, AUCUNE marge
    n'entre dans cette charge utile. Forme contractuelle :
    ``apps/stock/contract_samples/produit_utilise_dans.json``.
    """
    from apps.roles.permissions import is_portal_user, portal_scope_id
    from core.scoping import scope_queryset

    from .models import Devis
    # QJR655 — LA règle de portée société (core.mixins), celle de
    # TenantMixin : il n'existe pas DEUX règles société.
    from core.mixins import company_qs

    if user is None or not getattr(user, 'is_authenticated', False):
        return []
    if not produit_id:
        return []
    try:
        limite = int(limit)
    except (TypeError, ValueError):
        limite = 0
    if limite <= 0:
        return []

    qs = company_qs(Devis.objects.all(), user)
    if is_portal_user(user):
        scope = portal_scope_id(user)
        if getattr(user, 'portee', None) != 'portail_client' or scope is None:
            return []
        qs = qs.filter(client_id=scope).exclude(statut=Devis.Statut.BROUILLON)
    else:
        qs = scope_queryset(qs, user, ['created_by'])
        # NTADM3 — même périmètre d'entités que DevisViewSet (EntiteScopeMixin) ;
        # renvoie qs inchangé pour un rôle sans périmètre.
        from core.entite_scoping import scope_entite_queryset
        qs = scope_entite_queryset(qs, user)

    qs = (qs.filter(lignes__produit_id=produit_id)
            .select_related('client')
            .prefetch_related('lignes')
            .distinct()
            .order_by('-date_creation', '-id'))

    lignes = []
    for devis in qs[:limite]:
        client = devis.client
        lignes.append({
            'id': devis.id,
            'reference': devis.reference or '',
            'client_nom': (getattr(client, 'nom', '') or '') if client else '',
            'statut': devis.statut or '',
            'date': (devis.date_creation.date().isoformat()
                     if devis.date_creation else ''),
            'total_ttc': str(devis.total_ttc),
        })
    return lignes


# ── CAD59 (21/09/2026) — LA date de validité, celle que le PDF affiche ─────

def date_validite_effective(devis):
    """La date de validité RÉELLE d'un devis — celle qu'imprime le PDF.

    ``date_validite`` si elle est posée, sinon date de création + le réglage
    société ``quote_validity_days`` : exactement la règle que
    ``utils/expiry.date_expiration`` applique déjà pour le moteur de devis et
    le portail client. ``None`` si elle est indéterminable — l'appelant OMET
    alors sa phrase plutôt que d'inventer une date.

    Surface de LECTURE cross-app (le CRM la consomme depuis
    ``message_pour_etape``) : sans elle, le message WhatsApp ne lisait que
    ``devis.date_validite`` et supprimait sa phrase de validité pendant que le
    PDF, lui, affichait « valable jusqu'au X » — deux voix contradictoires sur
    le même dossier.
    """
    from apps.ventes.utils.expiry import date_expiration
    if devis is None:
        return None
    try:
        return date_expiration(devis)
    except Exception:  # noqa: BLE001 — jamais une date inventée en repli
        return None


# ── CAD-K ── CAD138 — le panier « relance d'engagement » se vide enfin ──────
#
# Audit L3 du 21/09/2026. Un déclencheur allumé était inscrit UNE FOIS POUR
# TOUTES : deux sites d'écriture, tous deux additifs, aucun code de remise à
# zéro — et le panier engagement passait AVANT le test d'expiration. Un devis
# dont la validité tombait dans trois jours restait donc caché derrière un
# drapeau « non ouvert » vieux de trois semaines. (Les déclencheurs
# s'éteignaient de toute façon à l'expiration du LIEN, ce qui n'est pas la
# même chose qu'un traitement.)
#
# DEUX CORRECTIONS, ET RIEN D'AUTRE : les déclencheurs se PÉRIMENT, et
# l'expiration passe DEVANT l'engagement dans l'ordre des paniers — une date
# de validité qui tombe est une urgence datée, un drapeau de comportement ne
# l'est plus après trois semaines.

#: Durée au-delà de laquelle un déclencheur d'engagement sort du panier.
#: Elle vient du texte de la tâche CAD138 — « un drapeau de comportement ne
#: l'est plus après TROIS SEMAINES » — et non d'un réglage : la péremption
#: est automatique, préférée à un geste manuel de plus pour une équipe de
#: deux personnes.
DECLENCHEUR_PEREMPTION_JOURS = 21


def dates_declencheurs(link):
    """``{clé: date ISO ou None}`` des déclencheurs allumés sur un lien.

    Accepte les DEUX formes : la LISTE historique (aucune date connue → la
    valeur est ``None``) et le DICT daté écrit depuis CAD138. Aucune migration
    n'est nécessaire — le champ est un ``JSONField``.
    """
    brut = getattr(link, 'engagement_triggers_fired', None) or []
    if isinstance(brut, dict):
        return {str(cle): valeur for cle, valeur in brut.items()}
    return {str(cle): None for cle in brut}


def marquer_declencheur(link, cle, *, quand=None):
    """Allume un déclencheur DATÉ sans perdre les dates déjà connues.

    Écrit la forme DICT sur le lien (sans le sauvegarder — l'appelant décide
    quand) et la renvoie. Un déclencheur déjà allumé est RAFRAÎCHI : il vient
    de se reproduire, la péremption repart de là."""
    from django.utils import timezone

    dates = dates_declencheurs(link)
    dates[str(cle)] = (quand or timezone.now()).isoformat()
    link.engagement_triggers_fired = dict(sorted(dates.items()))
    return link.engagement_triggers_fired


def _date_declencheur_heritee(link, devis=None):
    """Date de repli d'un déclencheur SANS date (forme liste d'avant CAD138).

    La meilleure preuve disponible de QUAND le comportement a eu lieu : la
    dernière consultation du lien, sinon l'envoi du devis, sinon la création
    du lien. Rien n'est inventé — on lit ce qui existe déjà."""
    for valeur in (getattr(link, 'last_viewed_at', None),
                   getattr(devis, 'date_envoi', None),
                   getattr(link, 'created_at', None)):
        if valeur is not None:
            return valeur
    return None


def declencheurs_actifs(link, *, devis=None, now=None):
    """Les déclencheurs d'engagement ENCORE actionnables sur ce lien.

    Un déclencheur de plus de ``DECLENCHEUR_PEREMPTION_JOURS`` jours sort du
    panier : il ne dit plus rien d'utile au commercial, et il masquait des
    devis dont la validité tombe. Un déclencheur sans date connue est daté par
    ``_date_declencheur_heritee`` ; sans aucune date exploitable, il est
    GARDÉ — on ne jette pas un signal faute de savoir le dater.
    """
    import datetime as _dt

    from django.utils import timezone

    now = now or timezone.now()
    limite = _dt.timedelta(days=DECLENCHEUR_PEREMPTION_JOURS)
    actifs = set()
    for cle, iso in dates_declencheurs(link).items():
        quand = None
        if iso:
            try:
                quand = _dt.datetime.fromisoformat(str(iso))
            except (TypeError, ValueError):
                quand = None
        if quand is None:
            quand = _date_declencheur_heritee(link, devis)
        if quand is None or (now - quand) < limite:
            actifs.add(cle)
    return actifs


# ── CAD-K ── CAD133 — engagement du client sur SA proposition ───────────────
def engagement_proposition_du_lead(lead_id, company):
    """CAD133 — ce que le client a FAIT de sa proposition (lecture seule).

    Point d'entrée cross-app UNIQUE pour que le score du CRM compte un
    COMPORTEMENT sans importer ``apps.ventes.models``. Multi-tenant : borné à
    la société fournie. Aucun montant, aucun prix d'achat, aucune marge — ce
    sont des faits de lecture, jamais du chiffrage.

    Renvoie ``{ouverte, vues, lue_en_detail, derniere_vue}`` :
      * ``ouverte``       — la proposition a été ouverte au moins une fois ;
      * ``vues``          — total des consultations (``ShareLink.view_count``) ;
      * ``lue_en_detail`` — un ``deep_engagement_logged_at`` existe ;
      * ``derniere_vue``  — le plus récent instant connu, ou ``None``.
    """
    from django.db.models import Max, Sum

    from .models import ShareLink

    vide = {'ouverte': False, 'vues': 0, 'lue_en_detail': False,
            'derniere_vue': None}
    if not lead_id or company is None:
        return vide
    agregat = (ShareLink.objects
               .filter(devis__lead_id=lead_id, devis__company=company)
               .aggregate(vues=Sum('view_count'),
                          premiere=Max('first_viewed_at'),
                          profond=Max('deep_engagement_logged_at')))
    vues = int(agregat.get('vues') or 0)
    premiere = agregat.get('premiere')
    profond = agregat.get('profond')
    instants = [i for i in (premiere, profond) if i is not None]
    return {
        'ouverte': premiere is not None or vues > 0,
        'vues': vues,
        'lue_en_detail': profond is not None,
        'derniere_vue': max(instants) if instants else None,
    }


def annotations_engagement_proposition():
    """CAD133 — les MÊMES faits, posés en ANNOTATIONS sur un queryset de leads.

    ``engagement_proposition_du_lead`` coûte une agrégation ``ShareLink`` PAR
    LEAD : sur la liste du CRM (qui calcule le score de chaque ligne) cela
    faisait repartir la base une fois par ligne — un N+1 franc. Les mêmes
    trois faits sont ici des sous-requêtes corrélées : la liste les obtient
    dans la requête qui charge déjà les leads, sans une requête de plus.

    À greffer par ``qs.annotate(**annotations_engagement_proposition())`` sur
    un queryset de ``crm.Lead``. Les trois attributs posés
    (``sig_vues_proposition``, ``sig_premiere_vue_proposition``,
    ``sig_lecture_profonde_at``) sont relus par ``apps.crm.signaux`` — la
    frontière M3 tient : ``apps.crm`` n'importe toujours pas
    ``apps.ventes.models``, il appelle ce sélecteur.
    """
    from django.db.models import (
        DateTimeField, IntegerField, Max, OuterRef, Subquery, Sum,
    )

    from .models import ShareLink

    base = (ShareLink.objects
            .filter(devis__lead=OuterRef('pk'),
                    devis__company=OuterRef('company'))
            .order_by()
            .values('devis__lead'))
    return {
        'sig_vues_proposition': Subquery(
            base.annotate(valeur=Sum('view_count')).values('valeur')[:1],
            output_field=IntegerField()),
        'sig_premiere_vue_proposition': Subquery(
            base.annotate(valeur=Max('first_viewed_at')).values('valeur')[:1],
            output_field=DateTimeField()),
        'sig_lecture_profonde_at': Subquery(
            base.annotate(
                valeur=Max('deep_engagement_logged_at')).values('valeur')[:1],
            output_field=DateTimeField()),
    }


def devis_predecesseurs_revision_ids(devis):
    """QJR559 — les ids des versions que ``devis`` REMPLACE, par révision
    (relation inverse ``remplace`` = ``superseded_by``), toute la chaîne
    (v3 → v2 → v1, du plus proche au plus ancien), même société. Jamais
    ``version_parent`` : il est partagé avec les variantes et les gammes, qui
    ne remplacent rien.

    Lu par ``installations`` (chantier unique), ``sav`` (contrat unique),
    ``crm`` (cadence de suivi) et le cycle de vie ventes (aval financier) —
    aucun import de ``ventes.models`` hors de cette app. Liste vide pour un
    objet non persisté."""
    from .models import Devis

    pk = getattr(devis, 'pk', None)
    company_id = getattr(devis, 'company_id', None)
    if pk is None or company_id is None:
        return []
    vus = {pk}
    ordre = []
    frontiere = [pk]
    while frontiere:
        suivants = [
            i for i in Devis.objects.filter(
                company_id=company_id, superseded_by_id__in=frontiere)
            .values_list('pk', flat=True)
            if i not in vus]
        vus.update(suivants)
        ordre.extend(suivants)
        frontiere = suivants
    return ordre


from .selectors_facturation import (  # noqa: E402,F401 — ré-export (SPL143)
    compter_factures,
    factures_echues,
    get_facture_scoped,
    releve_client_portail,
    releve_client_pdf_bytes,
    paiements_des_factures,
    paiements_totaux_par_mode,
    comportement_paiement,
    date_encaissement_prevue,
    references_factures,
    references_avoirs,
    encours_clients_par_tiers,
    encours_ouvert_par_tiers,
    reste_du_factures_brouillon,
    ca_devis_factures_par_clients,
    acompte_paye_pour_devis,
    etat_recouvrement_client,
    analyse_facturation,
    devis_a_facturer,
    tranche_facturee,
    jours_impaye_facture,
    montants_factures_par_devis,
    carnet_commande_par_mois,
    factures_via_bon_commande,
    factures_du_devis,
    devis_deja_facture,
    kpis_factures,
)


from .selectors_calepinage import (  # noqa: E402,F401 — ré-export (SPL144)
    conception_pour_lead,
    calepinage_du_devis,
    schema_unifilaire_svg,
    lignes_produits_calepinage,
    peremption_layout_devis,
    devis_brouillon_pour_layout,
    comparaison_calepinage_devis,
    devis_concevables,
    contexte_conception_devis,
)
