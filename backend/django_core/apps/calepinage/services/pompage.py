"""CAL155-158 — dimensionnement du pompage solaire, côté module.

CE QUE CE FICHIER NE RECODE PAS
--------------------------------
Le calcul du volume pompé heure par heure existe déjà et reste la SEULE
source : ``apps.ventes.solar_design.pumping_cycle_yield`` (débit × profil
horaire pondéré par l'irradiation, ou mode PLAT débit × heures). Ce module
ne fait qu'ALIMENTER ses paramètres avec des données RÉELLES — besoin en eau
saisi, HMT calculée depuis un puits, facteurs mensuels PVGIS, pompe/variateur
assortis — jamais un second calcul de volume.

ZÉRO CHIFFRE INVENTÉ (CLAUDE.md)
----------------------------------
Chaque fonction de ce fichier documente sa source : ``saisie`` (l'utilisateur
a tapé la valeur), ``fiche`` (la fiche technique/catalogue du produit),
``pvgis`` (l'irradiation réelle du site) — jamais une valeur par défaut
inventée. Une donnée manquante fait tomber le résultat vers ``None`` (la
carte correspondante disparaît côté écran), jamais vers 0 ni vers une
hypothèse tacite.

Fonctions PURES (pas de requête, pas d'écriture) : les appelants (vues,
sélecteurs) construisent les entrées depuis ``apps.stock.selectors`` et
``apps.parametres.pvgis_profils``, jamais l'inverse.
"""
from __future__ import annotations

#: Tensions standard du catalogue pompage (CLAUDE.md « Pompage sizing »).
TENSION_MONO_V = 220
TENSION_TRI_V = 380


def _flottant(valeur, defaut=None):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


# ═══════════════════════════════════════════════════════════════════════════
# CAL155 — besoin en eau journalier/mensuel + réservoir + autonomie
# ═══════════════════════════════════════════════════════════════════════════

#: Jours par mois (année non bissextile) — même convention que
#: ``apps.ventes.solar_design._DAYS_IN_MONTH``, dupliquée ici en tant que
#: CONSTANTE PURE (pas d'import croisé pour une liste de 12 entiers connus).
JOURS_PAR_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def couverture_besoin_eau(*, besoin_m3_jour=None, besoin_m3_mois=None,
                          volume_reservoir_m3=None, production_m3_mois=None,
                          jours_par_mois=None):
    """CAL155 — couverture du besoin en eau MOIS PAR MOIS + autonomie réservoir.

    ``besoin_m3_jour`` : besoin JOURNALIER constant (m³/j), SAISI par
    l'utilisateur — sert de repli pour tout mois sans valeur mensuelle
    explicite.
    ``besoin_m3_mois`` : liste de 12 besoins MENSUELS SAISIS (m³/mois),
    ``None`` à un index = pas de saisie mensuelle pour ce mois-là (repli sur
    ``besoin_m3_jour``). Les deux peuvent se combiner (saisonnalité connue
    certains mois seulement).
    ``production_m3_mois`` : les 12 volumes PRODUITS (typiquement
    ``pumping_cycle_yield(...)['monthly_m3']`` ou le résultat pondéré PVGIS
    de :func:`pompage_mensuel_pvgis`).

    AUCUN besoin saisi (ni journalier ni mensuel) ⇒ ``besoin_m3_mois`` et
    ``couverture_pct_mois`` valent ``None`` — « besoin non saisi ⇒ aucun taux
    de couverture publié » (CLAUDE.md, zéro chiffre inventé : publier un taux
    contre un besoin supposé mentirait).

    Rend ``{besoin_m3_mois: [12]|None, couverture_pct_mois: [12]|None,
    autonomie_jours: float|None, besoin_source: 'saisie'|None}``.
    """
    jours = list(jours_par_mois) if jours_par_mois and len(jours_par_mois) == 12 \
        else list(JOURS_PAR_MOIS)
    besoin_jour = _flottant(besoin_m3_jour)
    mensuel_saisi = list(besoin_m3_mois) if besoin_m3_mois and len(besoin_m3_mois) == 12 \
        else [None] * 12

    besoin_effectif = []
    for mois in range(12):
        valeur_mois = _flottant(mensuel_saisi[mois])
        if valeur_mois is not None:
            besoin_effectif.append(valeur_mois)
        elif besoin_jour is not None:
            besoin_effectif.append(besoin_jour * jours[mois])
        else:
            besoin_effectif.append(None)

    if all(v is None for v in besoin_effectif):
        return {
            'besoin_m3_mois': None,
            'couverture_pct_mois': None,
            'autonomie_jours': None,
            'besoin_source': None,
        }

    production = list(production_m3_mois) if production_m3_mois and len(
        production_m3_mois) == 12 else [None] * 12
    couverture = []
    for mois in range(12):
        besoin = besoin_effectif[mois]
        prod = _flottant(production[mois])
        if besoin is None or besoin <= 0 or prod is None:
            couverture.append(None)
        else:
            couverture.append(round(prod / besoin * 100, 1))

    autonomie = None
    reservoir = _flottant(volume_reservoir_m3)
    if reservoir is not None and reservoir > 0:
        # Référence d'autonomie : le besoin journalier SAISI s'il existe,
        # sinon la moyenne des besoins mensuels effectivement saisis/déduits
        # (jamais une hypothèse — dérivée directement de ce que l'utilisateur
        # a tapé).
        reference = besoin_jour
        if reference is None:
            valeurs = [v for v in besoin_effectif if v is not None]
            moyenne_mois = sum(valeurs) / len(valeurs) if valeurs else None
            reference = (moyenne_mois / (sum(jours) / 12)
                         if moyenne_mois is not None else None)
        if reference is not None and reference > 0:
            autonomie = round(reservoir / reference, 1)

    return {
        'besoin_m3_mois': [round(v, 2) if v is not None else None
                           for v in besoin_effectif],
        'couverture_pct_mois': couverture,
        'autonomie_jours': autonomie,
        'besoin_source': 'saisie',
    }


# ═══════════════════════════════════════════════════════════════════════════
# CAL156 — HMT calculée par puits (niveau statique + rabattement + pertes),
# ITÉRATIVE puisque la hauteur dépend du débit délivré par la pompe.
# ═══════════════════════════════════════════════════════════════════════════

def _debit_a_hmt(courbe, hmt):
    """Port Python de ``frontend/src/features/ventes/solar.js debitAtHmt`` —
    MÊME interpolation linéaire, MÊME comportement aux bornes (au-delà de la
    capacité de la pompe ⇒ 0 ; en-deçà du dernier point mesuré ⇒ borné au
    dernier point). Deux implémentations d'une seule formule ne doivent
    JAMAIS diverger : toute modification ici doit être reportée côté JS (et
    inversement) — un test de parité (CAL158) les confronte sur un jeu de cas
    committé.
    """
    if not courbe:
        return None
    debits = courbe.get('debits_m3h')
    hmts = courbe.get('hmt_m')
    if not debits or not hmts or len(debits) < 2 or len(debits) != len(hmts):
        return None
    h = _flottant(hmt)
    if h is None or h <= 0:
        return None
    d = [float(x) for x in debits]
    hh = [float(x) for x in hmts]
    if h > hh[0]:
        return 0.0
    if h <= hh[-1]:
        return round(d[-1], 1)
    for i in range(len(hh) - 1):
        if h <= hh[i] and h > hh[i + 1]:
            t = (hh[i] - h) / (hh[i] - hh[i + 1])
            return round(d[i] + t * (d[i + 1] - d[i]), 1)
    return None


#: Les cinq données de puits EXIGÉES pour calculer une HMT (au lieu de la
#: saisir) — toute absence fait retomber sur la HMT saisie, ANNONCÉE comme
#: telle (jamais une HMT calculée à moitié, sur des données incomplètes).
_CHAMPS_PUITS_REQUIS = (
    'niveau_statique_m', 'coefficient_rabattement_m_par_m3h',
    'longueur_tuyauterie_m', 'coefficient_frottement',
    'hauteur_refoulement_m',
)


def hmt_puits_iteree(*, courbe_pompe=None, hmt_saisie=None,
                     niveau_statique_m=None,
                     coefficient_rabattement_m_par_m3h=None,
                     longueur_tuyauterie_m=None, coefficient_frottement=None,
                     hauteur_refoulement_m=None, debit_initial_m3h=None,
                     max_iterations=20, tolerance_m3h=0.05):
    """CAL156 — HMT = niveau statique + rabattement(débit) + pertes de
    charge(longueur, débit, coefficient SAISI) + hauteur de refoulement,
    ITÉRÉE jusqu'à convergence avec la courbe pompe (la hauteur dépend du
    débit, le débit dépend de la hauteur).

    ``coefficient_rabattement_m_par_m3h`` : rabattement SPÉCIFIQUE du puits
    (m de rabattement par m³/h pompé) — une donnée de PUITS RÉEL (essai de
    pompage), jamais un coefficient de la littérature. ``coefficient_frottement``
    : coefficient de pertes de charge de la tuyauterie posée — SAISI, jamais
    une valeur Hazen-Williams par défaut (CLAUDE.md : « aucun coefficient
    inventé »). Modèle de pertes : ``coefficient_frottement × longueur_m ×
    débit²`` — la forme quadratique standard d'une perte de charge régulière,
    le coefficient absorbant matériau/diamètre/rugosité (tous SAISIS via ce
    seul coefficient plutôt que reconstruits depuis une table interne).

    DONNÉE DE PUITS MANQUANTE (l'une des cinq) ⇒ repli sur ``hmt_saisie``,
    ``source: 'saisie'`` — jamais une HMT calculée sur des données
    incomplètes. Rend toujours
    ``{hmt_m, source, composantes, debit_convergence_m3h, iterations}``.
    """
    donnees = {
        'niveau_statique_m': niveau_statique_m,
        'coefficient_rabattement_m_par_m3h': coefficient_rabattement_m_par_m3h,
        'longueur_tuyauterie_m': longueur_tuyauterie_m,
        'coefficient_frottement': coefficient_frottement,
        'hauteur_refoulement_m': hauteur_refoulement_m,
    }
    if any(donnees[champ] is None for champ in _CHAMPS_PUITS_REQUIS):
        return {
            'hmt_m': _flottant(hmt_saisie),
            'source': 'saisie',
            'composantes': None,
            'debit_convergence_m3h': None,
            'iterations': 0,
        }

    niveau = float(niveau_statique_m)
    coef_rabattement = float(coefficient_rabattement_m_par_m3h)
    longueur = float(longueur_tuyauterie_m)
    coef_frottement = float(coefficient_frottement)
    refoulement = float(hauteur_refoulement_m)

    premier_point = (courbe_pompe or {}).get('debits_m3h') or []
    debit = _flottant(debit_initial_m3h)
    if debit is None:
        debit = (float(premier_point[len(premier_point) // 2])
                 if premier_point else 1.0)
    if debit <= 0:
        debit = 1.0

    composantes = None
    hmt = niveau + refoulement
    for iteration in range(1, max_iterations + 1):
        rabattement = coef_rabattement * debit
        pertes = coef_frottement * longueur * (debit ** 2)
        hmt = niveau + rabattement + pertes + refoulement
        composantes = {
            'niveau_statique_m': round(niveau, 3),
            'rabattement_m': round(rabattement, 3),
            'pertes_charge_m': round(pertes, 3),
            'hauteur_refoulement_m': round(refoulement, 3),
        }
        nouveau_debit = _debit_a_hmt(courbe_pompe, hmt)
        if nouveau_debit is None:
            # HMT hors de la capacité de la pompe (ou courbe inexploitable) :
            # on rend la dernière HMT calculée, sans point de convergence
            # inventé.
            return {
                'hmt_m': round(hmt, 2), 'source': 'calculee',
                'composantes': composantes, 'debit_convergence_m3h': None,
                'iterations': iteration,
            }
        if abs(nouveau_debit - debit) <= tolerance_m3h:
            return {
                'hmt_m': round(hmt, 2), 'source': 'calculee',
                'composantes': composantes,
                'debit_convergence_m3h': round(nouveau_debit, 2),
                'iterations': iteration,
            }
        debit = nouveau_debit

    return {
        'hmt_m': round(hmt, 2), 'source': 'calculee',
        'composantes': composantes, 'debit_convergence_m3h': round(debit, 2),
        'iterations': max_iterations,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CAL157 — m³/jour PAR MOIS depuis l'irradiance PVGIS RÉELLE du site.
# ═══════════════════════════════════════════════════════════════════════════

def pompage_mensuel_pvgis(*, debit_hmt_m3h, pumping_hours=None, ville=None,
                          lat=None, lon=None, jours_par_mois=None):
    """CAL157 — 12 volumes mensuels pondérés par l'irradiation PVGIS RÉELLE
    du site (au lieu du m³/jour PLAT × jours du mois), en ALIMENTANT
    ``apps.ventes.solar_design.pumping_cycle_yield`` (jamais un second
    calcul de volume) via son paramètre ``monthly_irradiation_factor``.

    Source d'irradiation : ``apps.parametres.pvgis_profils.productible_mensuel``
    — le client PVGIS EXISTANT (live au point GPS, sinon table de la ville
    reconnue, sinon ancre la plus proche ; JAMAIS une saisonnalité inventée).
    Les facteurs mensuels sont l'``E_m`` de chaque mois RAPPORTÉ À LA MOYENNE
    annuelle (un mois deux fois plus ensoleillé que la moyenne pompe deux fois
    plus, à débit nominal égal).

    LE CALCUL PLAT HISTORIQUE RESTE PUBLIÉ, JAMAIS REMPLACÉ EN SILENCE
    (CLAUDE.md) — ``m3_mois_plat`` ET ``m3_mois_pvgis`` sortent tous les
    deux, avec l'écart mois par mois.

    PVGIS indisponible pour ce site (pas de coordonnées ET ville non
    reconnue) ⇒ ``m3_mois_pvgis``/``source_irradiation`` valent ``None``,
    warning explicite ; le m³/jour plat reste calculé et publié (jamais un
    résultat vide faute d'irradiation).
    """
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.solar_design import pumping_cycle_yield

    plat = pumping_cycle_yield(debit_hmt_m3h=debit_hmt_m3h,
                               pumping_hours=pumping_hours,
                               days_in_month=jours_par_mois)

    resultat_pvgis = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if resultat_pvgis is None:
        return {
            'm3_jour_plat': plat['daily_m3'],
            'm3_mois_plat': plat['monthly_m3'],
            'm3_mois_pvgis': None,
            'source_irradiation': None,
            'ecart_m3_mois': None,
            'warnings': plat['warnings'] + [
                "irradiation PVGIS indisponible pour ce site (ni coordonnées "
                "ni ville reconnue) — m³/jour reste le calcul plat (débit × "
                "heures), aucune pondération mensuelle publiée"],
        }
    valeurs_e_m, source = resultat_pvgis
    moyenne = sum(valeurs_e_m) / len(valeurs_e_m) if valeurs_e_m else 0.0
    facteurs = ([v / moyenne for v in valeurs_e_m] if moyenne
                else [1.0] * 12)

    pondere = pumping_cycle_yield(debit_hmt_m3h=debit_hmt_m3h,
                                  pumping_hours=pumping_hours,
                                  days_in_month=jours_par_mois,
                                  monthly_irradiation_factor=facteurs)

    ecarts = None
    if plat['monthly_m3'] is not None and pondere['monthly_m3'] is not None:
        ecarts = [round(pondere['monthly_m3'][i] - plat['monthly_m3'][i], 1)
                  for i in range(12)]

    return {
        'm3_jour_plat': plat['daily_m3'],
        'm3_mois_plat': plat['monthly_m3'],
        'm3_mois_pvgis': pondere['monthly_m3'],
        'source_irradiation': source,
        'ecart_m3_mois': ecarts,
        'warnings': plat['warnings'] + pondere['warnings'],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CAL158 — pompe + variateur assortis, PARITÉ avec l'écran devis
# (frontend/src/features/ventes/solar.js selectPompeByCurve /
# selectVariateurVeichi), et la garde absolue « jamais de m³/jour sans
# courbe ».
# ═══════════════════════════════════════════════════════════════════════════

def tension_produit(produit):
    """La tension (V) d'un produit pompe/variateur — champ ``tension_v``
    d'abord, sinon lue dans le nom (« 220V »/« 380V »), sinon ``None``
    (inconnue — reste candidate, aucune régression sur les fiches sans
    tension). MÊME priorité que ``solar.js tensionOf``."""
    tension = produit.get('tension_v')
    if tension:
        val = _flottant(tension)
        if val:
            return int(val)
    nom = (produit.get('nom') or '').lower()
    if '220' in nom and 'v' in nom:
        return TENSION_MONO_V
    if '380' in nom and 'v' in nom:
        return TENSION_TRI_V
    return None


def _tension_alim(alim):
    return TENSION_MONO_V if alim == 'mono' else TENSION_TRI_V


def _a_prix(produit):
    return (_flottant(produit.get('prix_vente'), 0.0) or 0.0) > 0


def selection_pompe(pompes, *, hmt, debit_souhaite_m3h, type_pompe='immerge',
                    alim='tri'):
    """CAL158 — port Python de ``solar.js selectPompeByCurve`` : la plus
    petite pompe (kW) DONT LA COURBE délivre ≥ ``debit_souhaite_m3h`` à
    ``hmt``, tension assortie à ``alim``, jamais un produit sans prix.

    GARDE ABSOLUE « jamais de m³/jour sans courbe » : une pompe SANS
    ``courbe_pompe`` est structurellement exclue de ``pompes`` avant même
    d'être candidate — cette fonction ne peut donc jamais renvoyer un
    ``debit_hmt_m3h`` fabriqué, et ``apps.ventes.solar_design.
    pumping_cycle_yield`` refuse déjà un débit ``None`` de son côté (double
    verrou, jamais un chiffre inventé nulle part sur ce chemin).

    ``pompes`` : liste de dicts ``{id, nom, pompe_kw, courbe_pompe,
    tension_v, prix_vente}`` — typiquement
    ``apps.stock.selectors.produits_par_type_equipement(company, 'pompe',
    avec_prix=False)`` mis en forme par l'appelant (le prix nul est filtré
    ICI, jamais avant, pour que ``sans_prix`` reste informatif).

    Rend ``{pompe, debit_hmt_m3h, kw, sans_prix, ecart_phase}`` — ``pompe``
    vaut ``None`` si aucune candidate compatible et pricée n'existe.
    """
    h = _flottant(hmt)
    q = _flottant(debit_souhaite_m3h)
    if not h or not q or h <= 0 or q <= 0:
        return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
                'sans_prix': [], 'ecart_phase': False}

    veut_surface = type_pompe == 'surface'
    tension_voulue = _tension_alim(alim) if alim else None

    candidats = []
    for p in pompes:
        if not p.get('courbe_pompe'):
            continue  # GARDE ABSOLUE — jamais candidate sans courbe.
        kw = _flottant(p.get('pompe_kw'), 0.0)
        if not kw or kw <= 0:
            continue
        debit_hmt = _debit_a_hmt(p['courbe_pompe'], h)
        if debit_hmt is None or debit_hmt < q:
            continue
        nom = (p.get('nom') or '').lower()
        if veut_surface and 'surface' not in nom:
            continue
        if not veut_surface and 'immerg' not in nom:
            continue
        candidats.append({'p': p, 'kw': kw, 'debit_hmt': debit_hmt,
                          'tension': tension_produit(p)})

    compatibles = [
        c for c in candidats
        if tension_voulue is None or c['tension'] is None
        or c['tension'] == tension_voulue]
    compatibles.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))

    pricees = [c for c in compatibles if _a_prix(c['p'])]
    if pricees:
        best = pricees[0]
        return {'pompe': best['p'], 'debit_hmt_m3h': best['debit_hmt'],
                'kw': best['kw'], 'sans_prix': [], 'ecart_phase': False}

    ecart_phase = bool(
        tension_voulue is not None
        and any(_a_prix(c['p']) and c['tension'] is not None
                and c['tension'] != tension_voulue for c in candidats))
    return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
            'sans_prix': [c['p'].get('nom') for c in compatibles],
            'ecart_phase': ecart_phase}


def selection_variateur(variateurs, kw, alim):
    """CAL158 — port Python de ``solar.js selectVariateurVeichi`` : le plus
    petit variateur VEICHI (mot « variateur », jamais un « afficheur ») dont
    ``kW ≥ kw`` demandé, tension assortie à ``alim``, jamais un produit sans
    prix. Repli JAMAIS silencieux : des variateurs compatibles existent mais
    aucun n'atteint le kW requis ⇒ ``insuffisant: True`` (pas le plus gros
    disponible sous-dimensionné).
    """
    tension_voulue = _tension_alim(alim)
    candidats = []
    for p in variateurs:
        nom = (p.get('nom') or '').lower()
        if 'variateur' not in nom or 'afficheur' in nom:
            continue
        pk = _flottant(p.get('pompe_kw'), 0.0)
        if not pk or pk <= 0 or not _a_prix(p):
            continue
        if tension_produit(p) != tension_voulue:
            continue
        candidats.append({'p': p, 'kw': pk})
    candidats.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))
    fit = next((c for c in candidats if c['kw'] >= kw), None)
    return {'variateur': fit['p'] if fit else None,
            'insuffisant': fit is None and bool(candidats)}
