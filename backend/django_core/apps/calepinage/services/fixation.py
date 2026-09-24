"""CALX359 — la NOMENCLATURE DE FIXATION d'un calepinage (contrat CALX335).

LE CONSTAT
----------
``services/lestage.py::masse_du_layout`` savait compter les modules d'un
document, mais la masse de structure par module était UN nombre saisi en
réglage : aucune quantité de rail, de pince ou de crochet n'était jamais
dérivée, et ``services/export_tableur.py`` servait modules / chaînes /
nomenclature sans aucune ligne de fixation.

CE QUE CE MODULE FAIT, ET RIEN D'AUTRE
--------------------------------------
Il LIT le document de conception et en tire six GRANDEURS (``BASES`` de
``services/catalogue_fixation.py``) — modules posés, rangées, pans,
jonctions entre modules voisins, extrémités de rangées, longueur des rangées
— puis applique à chaque composant du système choisi la règle de quantité
SAISIE par la société (``{base, facteur?, diviseur?}``, CALX358).

* **Les rangées** : même groupement au centimètre que la planche et le
  tableur (``export_tableur.rangees_du_pan``, ``PAS_DE_RANGEE_M``), ORIENTÉ
  par l'azimut du pan — pour un pan plein sud c'est exactement le groupement
  par ordonnée ; pour un pan tourné, les modules d'une même rangée physique
  ne partagent plus la même ordonnée et le groupement par ordonnée seule en
  ferait autant de rangées. Sans azimut connu, c'est ``rangees_du_pan`` tel
  quel.
* **Les segments** : une rangée se coupe là où un module manque (écart entre
  voisins supérieur au pas relevé, à la tolérance de rangée près) — un rail
  ne court pas au-dessus d'un trou, et chaque segment a DEUX extrémités.
* **Le pas** (centre à centre entre voisins) est RELEVÉ sur le pan, jamais
  supposé : un pan où aucun module n'a de voisin ne publie pas de longueur
  de rangée, et le dit.

ZÉRO CHIFFRE INVENTÉ (D-CALX 7) : une règle non saisie, un paramètre déclaré
mais non saisi (clé présente à ``null``), une grandeur illisible sur le
document ou un composant de référence non calculé donnent ``quantite: None``
et un ``manquant`` qui NOMME ce qui manque — jamais une quantité de repli.
Un test de surface relit CE fichier et refuse toute constante numérique hors
0 / 1 / 2 : aucune valeur normative n'y vit.

AUCUN MONTANT : ni prix, ni coût, ni marge (D5). Lecture PURE : aucune
écriture, aucun statut ne bouge.
"""
from __future__ import annotations

import math

__all__ = ['resoudre_systeme', 'bom_de_fixation', 'table_fixation']

#: Les rôles dont la quantité « u » se commande à l'unité.
UNITE_A_L_UNITE = 'u'


def _nombre(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _fr(valeur):
    """Un nombre saisi, écrit à la française (« 0,8 », « 2 »)."""
    return f'{valeur:g}'.replace('.', ',')


def _majuscule(texte):
    texte = str(texte or '')
    return texte[:1].upper() + texte[1:]


# ── Les grandeurs lues sur le document ──────────────────────────────────────

def _rangees_orientees(modules, azimut_deg):
    """``[[t, …] par rangée]`` : positions le long de la rangée, par rangée.

    Même tolérance que ``export_tableur.rangees_du_pan`` (le centimètre) ;
    l'axe de groupement est la ligne de plus grande pente du pan (azimut),
    l'axe de position lui est perpendiculaire.
    """
    from .export_tableur import PAS_DE_RANGEE_M, rangees_du_pan

    if azimut_deg is None:
        rangs = rangees_du_pan(modules)
        par_rang = {}
        for centre in modules:
            par_rang.setdefault(rangs[centre], []).append(centre[0])
        return [sorted(positions) for _rang, positions
                in sorted(par_rang.items())]

    angle = math.radians(azimut_deg)
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    par_rang = {}
    for est, nord in modules:
        pente = est * sin_a + nord * cos_a
        position = est * cos_a - nord * sin_a
        cle = round(pente / PAS_DE_RANGEE_M)
        par_rang.setdefault(cle, []).append(position)
    return [sorted(positions) for _cle, positions in sorted(par_rang.items())]


def _pas_du_pan(rangees):
    """Le pas centre à centre RELEVÉ : le plus petit écart entre voisins."""
    from .export_tableur import PAS_DE_RANGEE_M

    ecarts = [droite - gauche
              for positions in rangees
              for gauche, droite in zip(positions, positions[1:])
              if droite - gauche >= PAS_DE_RANGEE_M]
    return min(ecarts) if ecarts else None


def _segments(positions, pas):
    """Les segments CONTINUS d'une rangée (un trou coupe le rail)."""
    from .export_tableur import PAS_DE_RANGEE_M

    if not positions:
        return []
    segments, courant = [], [positions[0]]
    for gauche, droite in zip(positions, positions[1:]):
        if pas is not None and droite - gauche <= pas + PAS_DE_RANGEE_M:
            courant.append(droite)
        else:
            segments.append(courant)
            courant = [droite]
    segments.append(courant)
    return segments


def _grandeurs_du_document(roof_layout):
    """``{'valeurs': {base: nombre|None}, 'manquants': {base: motif}}``.

    Lecture PURE du document. Une grandeur illisible vaut ``None`` et son
    motif est NOMMÉ ; aucune n'est complétée.
    """
    from .catalogue_fixation import BASES
    from .planche import PlancheRefusee, geometrie_de_planche

    try:
        geometrie = geometrie_de_planche(roof_layout)
    except PlancheRefusee:
        motif = ("Aucune conception enregistrée : les grandeurs de la "
                 "nomenclature (modules, rangées, longueurs) ne se lisent "
                 "que sur le document.")
        return {'valeurs': {base: None for base in BASES},
                'manquants': {base: motif for base in BASES}}

    modules = rangees = pans = jonctions = extremites = 0
    longueur, pans_sans_pas = 0.0, []
    for pan in geometrie.get('pans') or ():
        centres = pan.get('modules') or []
        if not centres:
            continue
        pans += 1
        modules += len(centres)
        lignes = _rangees_orientees(centres, pan.get('azimut_deg'))
        rangees += len(lignes)
        pas = _pas_du_pan(lignes)
        for positions in lignes:
            for segment in _segments(positions, pas):
                jonctions += len(segment) - 1
                extremites += 2
                if pas is not None:
                    longueur += (segment[-1] - segment[0]) + pas
        if pas is None:
            pans_sans_pas.append(pan.get('libelle') or pan.get('repere'))

    if not modules:
        motif = ("Aucun module n'est posé sur la conception : aucune "
                 "quantité de fixation n'est calculée.")
        return {'valeurs': {base: None for base in BASES},
                'manquants': {base: motif for base in BASES}}

    valeurs = {'modules': modules, 'rangees': rangees, 'pans': pans,
               'jonctions': jonctions, 'extremites': extremites,
               'longueur_rangees_m': round(longueur, 2)}
    manquants = {}
    if pans_sans_pas:
        valeurs['longueur_rangees_m'] = None
        manquants['longueur_rangees_m'] = (
            "Longueur des rangées non publiée : sur le(s) pan(s) « "
            + '», «'.join(str(nom) for nom in pans_sans_pas)
            + " », aucun module n'a de voisin dans sa rangée — le pas "
            "entre modules n'y est pas lisible.")
    return {'valeurs': valeurs, 'manquants': manquants}


# ── Les lignes de la nomenclature ────────────────────────────────────────────

def _libelle_base(base):
    from .catalogue_fixation import BASES, PREFIXE_ROLE

    if isinstance(base, str) and base.startswith(PREFIXE_ROLE):
        return f'quantité de « {base[len(PREFIXE_ROLE):]} »'
    return BASES.get(base, str(base or ''))


def _texte_regle(regle):
    """La formule APPLIQUÉE, en clair — une valeur non saisie y figure par
    son libellé."""
    if not isinstance(regle, dict) or not regle.get('base'):
        return ''
    texte = _libelle_base(regle.get('base'))
    for cle, signe in (('facteur', '×'), ('diviseur', '÷')):
        if cle not in regle:
            continue
        libelle = str(regle.get(f'libelle_{cle}') or '').strip()
        valeur = _nombre(regle.get(cle))
        if valeur is None:
            texte += f' {signe} {libelle or cle}'
        else:
            texte += f' {signe} {_fr(valeur)}'
            if libelle:
                texte += f' ({libelle})'
    return texte


def _quantite(composant, regle, valeur_base):
    """``(quantite, manquant)`` — la quantité, ou ``None`` et CE qui manque."""
    nom = composant.libelle or composant.role
    quantite = valeur_base
    for cle in ('facteur', 'diviseur'):
        if cle not in regle:
            continue
        valeur = _nombre(regle.get(cle))
        if valeur is None or valeur <= 0:
            libelle = str(regle.get(f'libelle_{cle}') or '').strip() or cle
            return None, (f"« {_majuscule(libelle)} » non saisi sur le "
                          f"composant « {nom} » : la quantité n'est pas "
                          "calculée.")
        quantite = quantite * valeur if cle == 'facteur' else quantite / valeur
    if str(composant.unite or '').strip().lower() == UNITE_A_L_UNITE:
        return int(math.ceil(round(quantite, 2))), None
    return round(quantite, 2), None


def _lignes_de_fixation(composants, grandeurs, produits_valides=frozenset()):
    """Une ligne par composant, dans l'ordre du catalogue (PUR).

    ``composants`` : objets portant ``libelle, role, unite, regle,
    produit_id`` ; ``grandeurs`` : la sortie de ``_grandeurs_du_document`` ;
    ``produits_valides`` : les ``produit_id`` qui existent DANS la société
    (un identifiant étranger ou disparu est publié ``None``).
    """
    from .catalogue_fixation import PREFIXE_ROLE

    valeurs = grandeurs.get('valeurs') or {}
    motifs = grandeurs.get('manquants') or {}
    lignes = [None] * len(composants)
    calculees = {}

    def _ligne(composant, quantite, manquant):
        regle = composant.regle if isinstance(composant.regle, dict) else {}
        produit = composant.produit_id
        return {
            'composant': composant.libelle,
            'role': composant.role,
            'unite': composant.unite,
            'quantite': quantite,
            'regle': _texte_regle(regle),
            'produit_id': produit if produit in produits_valides else None,
            'manquant': manquant,
        }

    en_attente = list(range(len(composants)))
    for _tour in range(len(composants) + 1):
        restants = []
        for rang in en_attente:
            composant = composants[rang]
            regle = composant.regle if isinstance(composant.regle,
                                                  dict) else {}
            base = regle.get('base')
            nom = composant.libelle or composant.role
            if not base:
                lignes[rang] = _ligne(composant, None, (
                    f"Règle de quantité non saisie sur le composant « {nom} » "
                    ": la quantité n'est pas calculée."))
                continue
            if base.startswith(PREFIXE_ROLE):
                role = base[len(PREFIXE_ROLE):]
                if role not in calculees:
                    restants.append(rang)
                    continue
                valeur_base, motif = calculees[role]
                if valeur_base is None:
                    motif = (f"La quantité de « {role} » n'est pas calculée, "
                             f"donc celle de « {nom} » non plus. {motif}")
            else:
                valeur_base = valeurs.get(base)
                motif = motifs.get(base) or (
                    f"Grandeur « {_libelle_base(base)} » illisible sur le "
                    "document.")
            if valeur_base is None:
                quantite, manquant = None, motif
            else:
                quantite, manquant = _quantite(composant, regle, valeur_base)
            lignes[rang] = _ligne(composant, quantite, manquant)
            calculees.setdefault(composant.role, (quantite, manquant))
        if len(restants) == len(en_attente):
            break
        en_attente = restants
    for rang in en_attente:
        composant = composants[rang]
        if lignes[rang] is not None:
            continue
        role = (composant.regle or {}).get('base', '')[len(PREFIXE_ROLE):]
        nom = composant.libelle or composant.role
        present = any(c.role == role for c in composants)
        lignes[rang] = _ligne(composant, None, (
            f"« {nom} » se calcule sur la quantité de « {role} », "
            + ("qui dépend elle-même de lui (référence circulaire)"
               if present else "qu'aucun composant du système ne porte")
            + " : la quantité n'est pas calculée."))
    return lignes


# ── Le système appliqué, puis la réponse du contrat ─────────────────────────

def _refus(message, champ='systeme'):
    return {'champ': champ, 'message': message}


def resoudre_systeme(company, demande=None):
    """``(systeme | None, [refus])`` — celui demandé, sinon l'UNIQUE actif."""
    from .catalogue_fixation import systeme_de_societe, systemes_actifs

    texte = str(demande or '').strip()
    if texte:
        systeme = systeme_de_societe(company, texte)
        if systeme is None:
            return None, [_refus(
                f"Système de fixation introuvable : « {texte} » (identifiant "
                "d'un système du catalogue de la société attendu).")]
        return systeme, []
    actifs = systemes_actifs(company)
    if not actifs:
        return None, [_refus(
            "Aucun système de fixation n'est saisi dans le catalogue de la "
            "société : la nomenclature de fixation n'est pas calculée. "
            "Saisissez un système et ses composants (rôle, unité, règle de "
            "quantité, source) pour l'obtenir.")]
    if len(actifs) > 1:
        return None, [_refus(
            "Plusieurs systèmes de fixation sont actifs ("
            + ', '.join(f'« {s.code} »' for s in actifs)
            + ") : choisissez celui de ce calepinage.")]
    return actifs[0], []


def bom_de_fixation(calepinage, systeme, refus=()):
    """La réponse du contrat CALX335, ``{systeme, lignes, refus}``.

    ``systeme`` est celui que ``resoudre_systeme`` a retenu (déjà borné
    société) ; ``None`` ⇒ aucune ligne, et ``refus`` (sa sortie) dit
    pourquoi — jamais une nomenclature devinée.
    """
    if systeme is None:
        return {'systeme': None, 'lignes': [], 'refus': list(refus)}

    from apps.stock.selectors import valid_produit_ids

    from .catalogue_fixation import composants_du_systeme

    composants = composants_du_systeme(systeme)
    company = getattr(calepinage, 'company', None)
    identifiants = {c.produit_id for c in composants if c.produit_id}
    produits = (valid_produit_ids(company, identifiants)
                if identifiants else set())
    grandeurs = _grandeurs_du_document(getattr(calepinage, 'roof_layout',
                                               None))
    return {
        'systeme': {'id': systeme.pk, 'code': systeme.code,
                    'libelle': systeme.libelle},
        'lignes': _lignes_de_fixation(composants, grandeurs, produits),
        'refus': [],
    }


def table_fixation(calepinage):
    """La feuille « Fixation » du classeur, ou ``None`` (catalogue vide).

    ``(titre, entetes, lignes)`` — ``None`` quand la société n'a AUCUN
    système : le classeur reste alors EXACTEMENT celui d'aujourd'hui (D12).
    Plusieurs systèmes actifs sans choix : la feuille le DIT sur une ligne,
    elle ne choisit pas à la place de l'utilisateur.
    """
    from .catalogue_fixation import systemes_actifs

    company = getattr(calepinage, 'company', None)
    if not systemes_actifs(company):
        return None
    reponse = bom_de_fixation(calepinage, *resoudre_systeme(company))
    entetes = ['Composant', 'Rôle', 'Quantité', 'Unité', 'Règle appliquée',
               'Manquant']
    lignes = [[ligne['composant'], ligne['role'], ligne['quantite'],
               ligne['unite'], ligne['regle'], ligne['manquant'] or '']
              for ligne in reponse['lignes']]
    for refus in reponse['refus']:
        lignes.append(['', '', None, '', '', refus['message']])
    systeme = reponse['systeme']
    titre = 'Fixation'
    if systeme:
        lignes.insert(0, [f"Système : {systeme['libelle']} "
                          f"({systeme['code']})", '', None, '', '', ''])
    return titre, entetes, lignes
