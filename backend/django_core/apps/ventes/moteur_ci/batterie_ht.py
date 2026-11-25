"""Option « AVEC BATTERIE » C&I en HAUTE TENSION — règles pures (HT24,
décision fondateur du 24/11/2026 : « With battery now also picks from HV
inverters »).

Deux familles, jamais mêlées :

* BASSE tension — hybride dont la fenêtre batterie publiée plafonne à
  ``batterie.TENSION_PORT_BT_MAX_V`` (60 V), batteries en PARALLÈLE appariées
  par leur tension nominale (``etude_ci_batterie.batteries_compatibles``) ;
* HAUTE tension — hybride au-delà de 60 V (Deye SUN-80K-SG02HP3, 160–1000 V),
  pack empilé EN SÉRIE dont la fiche publie ses bornes de série et la tension
  d'UN module (Deye BOS-B Pro-A3 : 5 à 15 modules de 51,2 V avec un hybride).

L'appairage HAUTE tension se PROUVE par la tension, sur les fiches : une
grappe de n modules est valide sur un hybride si et seulement si
``série mini ≤ n ≤ série maxi`` et ``fenêtre mini ≤ n × tension du module ≤
fenêtre maxi``. Plusieurs grappes en parallèle sont IDENTIQUES (même tension) :
une banque de q modules est k grappes de q ÷ k modules, le moins de grappes
possible. Au plus une grappe par entrée batterie publiée de chaque hybride de
la combinaison (une par appareil quand la fiche ne publie pas ses entrées), et
au plus les grappes en parallèle publiées par la batterie.

Aucun Django, aucun modèle (garde AST de ``test_ciq107``) ; aucune valeur de
secours : un champ non publié est NOMMÉ, jamais remplacé par un défaut.
"""
from __future__ import annotations

import math

SOURCE_HT = 'décision fondateur du 24/11/2026 — « With battery now also picks from HV inverters »'
#: Champs de fiche d'une grappe en série (clés de ``specs_for_produit``) et
#: leur nom dit au fondateur.
CHAMPS_SERIE = (('serie_min', 'modules en série par grappe (mini)'),
                ('serie_max', 'modules en série par grappe (maxi)'),
                ('v_module', "tension d'un module"))
#: Garde de terminaison de l'énumération des tailles (modules), jamais une taille.
MAX_MODULES_HT = 500


def _f(valeur):
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def _entier(valeur):
    x = _f(valeur)
    return int(x) if x is not None and x == int(x) else None


def donnees_serie(batterie):
    """``(série mini, série maxi, tension d'un module)`` d'une batterie, des
    valeurs PUBLIÉES seulement ; ``None`` pour chaque champ absent."""
    b = batterie or {}
    return _entier(b.get('serie_min')), _entier(b.get('serie_max')), _f(b.get('v_module'))


def declare_serie(batterie):
    """La fiche déclare-t-elle (même en partie) une grappe en série ? Une
    batterie qui en publie un champ n'est plus une batterie basse tension."""
    return any(v is not None for v in donnees_serie(batterie))


def manque_serie(batterie):
    """Ce qui manque à la fiche d'un pack haute tension pour composer une
    grappe (liste vide = complète), noms dits au fondateur ; des bornes
    publiées à l'envers sont nommées aussi."""
    valeurs = donnees_serie(batterie)
    manque = [libelle for (_cle, libelle), v in zip(CHAMPS_SERIE, valeurs) if v is None]
    if not manque and valeurs[0] > valeurs[1]:
        manque.append('bornes de série incohérentes (mini %d > maxi %d)' % valeurs[:2])
    return manque


def series_valides(batterie, plage):
    """Les nombres de modules en série d'une grappe valide sur la fenêtre
    ``plage`` (V) d'un hybride ; ``[]`` si la fiche ne la permet pas."""
    smin, smax, v = donnees_serie(batterie)
    if manque_serie(batterie) or not plage or len(plage) != 2:
        return []
    bas, haut = float(plage[0]), float(plage[1])
    return [n for n in range(smin, smax + 1) if bas - 1e-9 <= n * v <= haut + 1e-9]


def compatible(hybride, batterie):
    """La batterie forme-t-elle au moins une grappe valide sur cet hybride ?"""
    return bool(series_valides(batterie, (hybride or {}).get('plage_batterie_v')))


def grappes_par_appareil(hybride):
    """Entrées batterie publiées par la fiche de l'hybride ; une seule quand
    elles ne le sont pas (la borne la plus prudente, dite en hypothèse)."""
    return _entier((hybride or {}).get('bat_nb_entrees')) or 1


def grappes_max_batterie(batterie):
    """Grappes en parallèle publiées par la batterie, ``None`` sinon."""
    return _entier((batterie or {}).get('grappes_max'))


def tailles_admissibles(batterie, hybrides, grappes_max):
    """``{q: k}`` — les banques que le matériel permet (q modules en k grappes
    identiques, k le plus petit), triées : n valide sur la fenêtre de CHAQUE
    hybride retenu (le modèle de la combinaison n'est connu qu'au champ),
    ``k ≤ grappes_max``."""
    communes = None
    for h in hybrides or []:
        valides = set(series_valides(batterie, h.get('plage_batterie_v')))
        communes = valides if communes is None else communes & valides
    tailles = {}
    for k in range(1, max(0, int(grappes_max or 0)) + 1):
        for n in sorted(communes or ()):
            if k * n <= MAX_MODULES_HT:
                tailles.setdefault(k * n, k)
    return dict(sorted(tailles.items()))


def plus_grande_taille(tailles, plafond):
    """La plus grande banque admissible ≤ ``plafond`` modules, 0 sinon."""
    return max((q for q in tailles or {} if q <= plafond), default=0)


def grappes_portees(banque, onduleurs, hybrides):
    """La combinaison porte-t-elle les grappes de la banque ? Vrai pour une
    banque basse tension (aucune grappe) ; sinon ``k ≤ Σ entrées batterie des
    appareils``."""
    par_taille = (banque or {}).get('grappes_par_taille')
    if not par_taille:
        return True
    k = par_taille.get(int((banque or {}).get('quantite') or 0))
    if k is None:
        return False
    fiches = {h.get('produit'): h for h in hybrides or []}
    entrees = sum(grappes_par_appareil(fiches.get(i.get('produit'))) * int(i.get('quantite') or 0)
                  for i in (onduleurs or {}).get('combinaison') or [])
    return k <= entrees


def grappes_de(banque):
    """Le nombre de grappes de la banque (``None`` hors grappe en série)."""
    par_taille = (banque or {}).get('grappes_par_taille') or {}
    return par_taille.get(int((banque or {}).get('quantite') or 0))


#: HT24 — les accessoires d'une GRAPPE, UN jeu par grappe : (rôle C&I,
#: désignation de ligne, clé d'hypothèse, code d'alerte quand l'article manque).
ACCESSOIRES_GRAPPE = (
    ('boitier_batterie_ht', 'Boîtier de contrôle haute tension', 'boitier_controle_haute_tension',
     'BOITIER_HAUTE_TENSION_A_VERIFIER'),
    ('rack_batterie_ht', 'Rack et câblage de puissance', 'rack_haute_tension',
     'RACK_HAUTE_TENSION_A_VERIFIER'),
)
ROLES_ACCESSOIRES = tuple(role for role, *_reste in ACCESSOIRES_GRAPPE)
#: Fiche Deye « C&I ESS SOLUTION BOS-B Pro-A3 », p. 2 (accessoire BOS-B-PDU-2-A).
SOURCE_BOITIER = ('fiche Deye « C&I ESS SOLUTION BOS-B Pro-A3 », p. 2 « Battery Pack Accessories » '
                  '(BOS-B-PDU-2-A) — un boîtier par grappe')
#: Le prix du rack : relevé pour UNE grappe de 6 modules — une HYPOTHÈSE pour
#: toute autre taille (fondateur 24/11/2026), dite, jamais tue.
SOURCE_RACK = ('prix fournisseur relevé pour une grappe de 6 modules ; à confirmer pour une grappe '
               'plus grande (devis Solarex Maroc n° S26/001708 du 27/07/2026)')


def lignes_accessoires(banque):
    """HT24 — les lignes des accessoires de grappe de la banque : un par
    grappe, l'article du catalogue de chaque rôle (``banque['accessoires']``) ;
    ``[]`` hors grappe (basse tension : composition inchangée) ou sans article
    (non composé, nommé par l'orchestrateur)."""
    from apps.ventes.moteur_ci.composition import ligne_accessoire_grappe
    k, articles = grappes_de(banque), (banque or {}).get('accessoires') or {}
    return [ligne_accessoire_grappe(role, articles[role], designation, k)
            for role, designation, _cle, _code in ACCESSOIRES_GRAPPE if k and articles.get(role)]


def accessoires_absents(banque):
    """``[(rôle, désignation, code d'alerte)]`` des accessoires de grappe
    qu'aucun article du catalogue ne porte."""
    articles = (banque or {}).get('accessoires') or {}
    return [(role, designation, code) for role, designation, _cle, code in ACCESSOIRES_GRAPPE
            if not articles.get(role)]


def _port_derive(banque, onduleurs, hybrides):
    """``(kW, grappes portées, courant A, tension de la grappe V)`` ou ``None``."""
    k, v = grappes_de(banque), donnees_serie(banque)[2]
    items = (onduleurs or {}).get('combinaison') or []
    if not k or not v or not items:
        return None
    fiches = {h.get('produit'): h for h in hybrides or []}
    courants, entrees = [], 0
    for item in items:
        h = fiches.get(item.get('produit')) or {}
        courant = _f(h.get('bat_i_max_entree_a'))
        if courant is None:
            return None
        courants.append(courant)
        entrees += grappes_par_appareil(h) * int(item.get('quantite') or 0)
    tension = int(banque['quantite']) // k * v
    portees = min(k, entrees)
    return portees * min(courants) * tension / 1000.0, portees, min(courants), tension


def borne_port_derivee_kw(banque, onduleurs, hybrides):
    """HT24 — la borne du port batterie DÉRIVÉE (kW) d'une grappe en série :
    ``min(grappes, Σ entrées batterie) × courant publié par entrée × tension
    nominale de la grappe ÷ 1000`` ; ``None`` hors grappe ou si un appareil de
    la combinaison ne publie pas son courant (port non appliqué, comme avant)."""
    derive = _port_derive(banque, onduleurs, hybrides)
    return derive[0] if derive else None


def message_nb_impose(nombre, batterie, tailles):
    """D-HYB-4 en haute tension — le refus NOMMÉ d'un nombre de batteries
    choisi que le matériel ne permet pas (bornes de série de la fiche)."""
    smin, smax, v = donnees_serie(batterie)
    liste = sorted(tailles or {})
    exemples = ', '.join(str(q) for q in liste[:14]) + (' …' if len(liste) > 14 else '')
    return ('Nombre de batteries choisi (%d) impossible en haute tension : une grappe compte '
            'de %d à %d modules de %s V en série (fiche de « %s »), plusieurs grappes sont '
            'identiques ; nombres possibles : %s.' % (
                nombre, smin, smax, ('%g' % v).replace('.', ','), (batterie or {}).get('nom') or '',
                exemples or 'aucun'))


def hypotheses_banque(banque, onduleurs, hybrides):
    """Les hypothèses SOURCÉES de la banque haute tension retenue : grappes
    (n × tension du module, dans la fenêtre de l'hybride), entrées batterie et
    limite de parallèle (publiées ou non), puissance du port batterie."""
    par_taille = (banque or {}).get('grappes_par_taille') or {}
    q = int((banque or {}).get('quantite') or 0)
    k = par_taille.get(q)
    if not k:
        return []
    smin, smax, v = donnees_serie(banque)
    n = q // k
    items = (onduleurs or {}).get('combinaison') or []
    fiches = {h.get('produit'): h for h in hybrides or []}
    hyp = [{'cle': 'grappes_haute_tension', 'valeur': k, 'statut': 'source', 'source': (
        '%d grappe%s de %d modules en série (%d × %s V = %s V, bornes %d–%d de la fiche de « %s ») — %s'
        % (k, 's' if k > 1 else '', n, n, '%g' % v, '%g' % (n * v), smin, smax,
           banque.get('nom') or '', SOURCE_HT))}]
    for item in items:
        h = fiches.get(item.get('produit')) or {}
        plage = h.get('plage_batterie_v') or (None, None)
        entrees = _entier(h.get('bat_nb_entrees'))
        hyp.append({'cle': 'port_batterie_haute_tension', 'valeur': entrees,
                    'statut': 'source' if entrees else 'estimation', 'source': (
                        '« %s » : fenêtre batterie %g–%g V ; %s ; parallèle : %s ; %s' % (
                            h.get('nom') or '', plage[0] or 0, plage[1] or 0,
                            ('%d entrées batterie publiées' % entrees) if entrees
                            else 'entrées batterie non publiées : une grappe par appareil au plus',
                            ('%d appareils au plus (fiche)' % int(h['max_parallele_publie']))
                            if h.get('max_parallele_publie')
                            else 'limite non publiée : un seul appareil', _texte_port(h)))})
    derive = _port_derive(banque, onduleurs, hybrides)
    if derive:
        kw, portees, courant, tension = derive
        hyp.append({'cle': 'port_batterie_derive_kw', 'valeur': round(kw, 2), 'statut': 'estimation',
                    'source': ('dérivée : courant publié × tension nominale de la grappe — %d grappe(s) '
                               'portée(s) × %g A × %g V = %s kW (borne du port batterie, jamais une '
                               'puissance publiée)' % (portees, courant, tension,
                                                       ('%.2f' % kw).replace('.', ',')))})
    return hyp + _hypotheses_accessoires(banque, k)


def _texte_port(hybride):
    courant = _f((hybride or {}).get('bat_i_max_entree_a'))
    if courant is None:
        return ('puissance du port batterie non publiée (ni kW ni courant par entrée sur la fiche) : '
                'non appliquée (charge et décharge bornées par les modules et la puissance AC)')
    return ('courant publié %g A par entrée batterie : borne du port DÉRIVÉE (dérivée : courant '
            'publié × tension nominale de la grappe)' % courant)


def _hypotheses_accessoires(banque, k):
    """Chaque accessoire de grappe : composé en ligne (article au catalogue
    ; le rack dit que son prix est relevé pour une grappe de 6 modules), ou
    non composé, à créer en Stock (aucun article : l'option est sous-chiffrée)."""
    articles, sortie = (banque or {}).get('accessoires') or {}, []
    for role, designation, cle, _code in ACCESSOIRES_GRAPPE:
        article = articles.get(role)
        if article is None:
            sortie.append({'cle': cle, 'valeur': k, 'statut': 'estimation', 'source': (
                '%s, un par grappe (%d) : non composé en ligne — aucun article de rôle « %s » au '
                'catalogue, à créer en Stock' % (designation, k, role))})
            continue
        statut, source = ('source', SOURCE_BOITIER) if role == 'boitier_batterie_ht' \
            else ('estimation', SOURCE_RACK)
        sortie.append({'cle': cle, 'valeur': k, 'statut': statut, 'source': (
            '%d × « %s » composé(s) en ligne, un par grappe — %s' % (k, article.get('nom') or '', source))})
    return sortie
