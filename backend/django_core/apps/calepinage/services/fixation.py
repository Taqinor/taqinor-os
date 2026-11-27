"""CALX359 — la NOMENCLATURE DE FIXATION d'un calepinage (contrat CALX335).

LE CONSTAT
----------
``services/lestage.py::_masse_du_layout`` savait compter les modules d'un
document, mais la masse de structure par module était UN nombre saisi en
réglage : aucune quantité de rail, de pince ou de crochet n'était jamais
dérivée, et ``services/export_tableur.py`` servait modules / chaînes /
nomenclature sans aucune ligne de fixation.

CE QUE CE MODULE FAIT, ET RIEN D'AUTRE
--------------------------------------
Il LIT le document de conception et en tire les GRANDEURS (``BASES`` de
``services/catalogue_fixation.py``) — modules posés, rangées, pans,
jonctions entre modules voisins, extrémités de rangées, longueur des rangées
— puis applique à chaque composant du système choisi la règle de quantité
SAISIE par la société (``{base, facteur?, diviseur?}``, CALX358).

* **Les rangées** : LA définition unique de ``services/rangees.py``
  (ACAL230 : même groupement au centimètre que le plan de pose et le tableur,
  ORIENTÉ par l'azimut du pan) — pour un pan plein sud c'est exactement le
  groupement par ordonnée ; pour un pan tourné, les modules d'une même
  rangée physique ne partagent plus la même ordonnée. Sans azimut connu,
  c'est le regroupement par ordonnée.
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
from .valeurs import nombre as _nombre

__all__ = ['resoudre_systeme', 'bom_de_fixation', 'table_fixation']

#: Les rôles dont la quantité « u » se commande à l'unité.
UNITE_A_L_UNITE = 'u'


def _fr(valeur):
    """Un nombre saisi, écrit à la française (« 0,8 », « 2 »)."""
    return f'{valeur:g}'.replace('.', ',')


def _majuscule(texte):
    texte = str(texte or '')
    return texte[:1].upper() + texte[1:]


# ── Les grandeurs lues sur le document ──────────────────────────────────────

def _rangees_orientees(modules, azimut_deg):
    """``[[t, …] par rangée]`` : positions le long de la rangée, par rangée.

    Délègue à ``rangees.positions_par_rangee`` : la MÊME définition que le
    plan de pose et le tableur (le centimètre ; axe de groupement = ligne de
    plus grande pente du pan, axe de position perpendiculaire).
    """
    from .rangees import positions_par_rangee

    return positions_par_rangee(modules, azimut_deg)


def _pas_du_pan(rangees):
    """Le pas centre à centre RELEVÉ : le plus petit écart entre voisins."""
    from .rangees import PAS_DE_RANGEE_M

    ecarts = [droite - gauche
              for positions in rangees
              for gauche, droite in zip(positions, positions[1:])
              if droite - gauche >= PAS_DE_RANGEE_M]
    return min(ecarts) if ecarts else None


def _segments(positions, pas):
    """Les segments CONTINUS d'une rangée (un trou coupe le rail)."""
    from .rangees import PAS_DE_RANGEE_M

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


def _grandeurs_d_un_pan(pan):
    """ACAL592 — les grandeurs d'UN pan : ``(rangees, jonctions, extremites,
    longueur, sans_pas)``. ``sans_pas`` : aucun module n'a de voisin, la
    longueur n'est pas lisible."""
    lignes = _rangees_orientees(pan.get('modules') or [],
                                pan.get('azimut_deg'))
    pas = _pas_du_pan(lignes)
    jonctions = extremites = 0
    longueur = 0.0
    for positions in lignes:
        for segment in _segments(positions, pas):
            jonctions += len(segment) - 1
            extremites += 2
            if pas is not None:
                longueur += (segment[-1] - segment[0]) + pas
    return len(lignes), jonctions, extremites, longueur, pas is None


def _orientations_d_un_pan(pan):
    """ACAL569 — ``(valeurs, rangees_mixtes)`` : les quatre grandeurs
    d'orientation d'UN pan (clés de ``BASES_ORIENTATION``), ou ``None`` quand
    la pose d'un module n'est pas enregistrée (jamais un repli). Une rangée
    MIXTE compte dans ``modules_*`` selon ses modules, dans aucune
    ``rangees_*``."""
    from .planche import ORIENTATIONS
    from .rangees import rangees_du_pan

    pose = pan.get('orientation_modules')
    par_module = pan.get('orientations_par_module') or {}
    poses = {centre: par_module.get(centre) if pose == 'mixed' else pose
             for centre in pan['modules']}
    if any(valeur not in ORIENTATIONS for valeur in poses.values()):
        return None
    rangs = rangees_du_pan(pan['modules'], pan.get('azimut_deg'))
    par_rangee = {}
    for centre, valeur in poses.items():
        par_rangee.setdefault(rangs[centre], set()).add(valeur)
    ensembles = list(par_rangee.values())
    modules, rangees = list(poses.values()).count, ensembles.count
    return {'modules_portrait': modules('portrait'),
            'modules_paysage': modules('landscape'),
            'rangees_portrait': rangees({'portrait'}),
            'rangees_paysage': rangees({'landscape'}),
            }, sum(len(ensemble) > 1 for ensemble in ensembles)


def _motifs_orientation(sans_orientation, mixtes):
    """ACAL569 — ``{base: motif}`` des bases d'orientation non lisibles
    (pans sans pose enregistrée) ou approchées (rangées mixtes)."""
    from .catalogue_fixation import BASES_ORIENTATION

    if sans_orientation:
        motif = ("Orientation des modules non enregistrée sur le(s) pan(s) « "
                 + '», «'.join(str(nom) for nom in sans_orientation)
                 + " » : portrait ou paysage n'y est pas lisible.")
        return dict.fromkeys(BASES_ORIENTATION, motif)
    if mixtes:
        motif = ("Rangée(s) mixte(s) portrait et paysage : leurs modules "
                 "sont comptés par orientation, aucune des rangées « en "
                 "portrait » ou « en paysage ».")
        return {base: motif for base in BASES_ORIENTATION
                if base.startswith('rangees')}
    return {}


def _pans_a_commander(geometrie):
    """Les pans qui portent des modules à poser : un pan « existant » (ACAL575)
    ne se commande pas."""
    return [pan for pan in geometrie.get('pans') or ()
            if pan.get('modules') and not pan.get('existant')]


def _motif_sans_pas(noms):
    return ("Longueur des rangées non publiée : sur le(s) pan(s) « "
            + '», «'.join(str(nom) for nom in noms)
            + " », aucun module n'a de voisin dans sa rangée — le pas "
            "entre modules n'y est pas lisible.")


# ── ACAL578 — tables et poteaux des surfaces de pose, pieds à la portée saisie ─

def _grandeur_tables(geometrie):
    """Les tables du moteur (``engine.tables``) des champs au sol et ombrières."""
    return sum(len(surface['tables']) for surface in geometrie.get('surfaces_de_pose') or ()
               if surface['kind'] in ('sol', 'ombriere'))


def _positions_appuis(contour, pas):
    """Portage de ``poseSurfaces.ts::positionsAppuis`` (MÊME marche du contour
    fermé, un appui tous les ``pas`` mètres), sans le plafond de dessin :
    ``[(x, y)]`` — la nomenclature les compte, le plan de pose (ACAL580) les repère."""
    positions, reste = [], 0.0
    for rang, (ax, ay) in enumerate(contour):
        bx, by = contour[(rang + 1) % len(contour)]
        longueur, distance = math.hypot(bx - ax, by - ay), reste
        if not longueur > 0:
            continue
        while distance < longueur:
            positions.append((ax + (bx - ax) * distance / longueur, ay + (by - ay) * distance / longueur))
            distance += pas
        reste = math.fmod(math.fmod(reste - longueur, pas) + pas, pas)
    return positions


def _grandeur_poteaux(roof_layout):
    """``(poteaux, motif)`` des ombrières : entraxe ET section saisis, sinon
    ``None`` et la grandeur NOMMÉE (comme l'atelier, qui ne dessine alors rien)."""
    from .planche import _points_metres

    total, motifs = 0, []
    brutes = (roof_layout or {}).get('poseSurfaces')
    for rang, surface in enumerate(brutes if isinstance(brutes, list) else [], start=1):
        if not isinstance(surface, dict) or surface.get('kind') != 'ombriere':
            continue
        nom = surface.get('label') or surface.get('id') or f'Ombrière {rang}'
        appuis = surface.get('appuis') if isinstance(surface.get('appuis'), dict) else {}
        pas, section = _nombre(appuis.get('pasM')), _nombre(appuis.get('sectionM'))
        contour = _points_metres(surface.get('contourM'))
        if pas is None or pas <= 0:
            motifs.append(f'entraxe des appuis non renseigné sur « {nom} »')
        elif section is None or section <= 0:
            motifs.append(f'section des appuis non renseignée sur « {nom} »')
        elif len(contour) <= 2:
            motifs.append(f'contour non enregistré sur « {nom} »')
        else:
            total += len(_positions_appuis(contour, pas))
    if motifs:
        return None, _majuscule(' ; '.join(motifs)) + " : aucun poteau n'est compté."
    return total, None


def _portee(zone):
    """La portée entre pieds SAISIE et sourcée (ACAL587), ou ``None``."""
    brut = zone.get('porteeEntrePieds')
    if not isinstance(brut, dict) or not str(brut.get('source') or '').strip():
        return None
    valeur = _nombre(brut.get('valeurM'))
    return valeur if valeur is not None and valeur > 0 else None


def _grandeur_pieds(roof_layout, pans):
    """``(pieds, motif)`` — par segment de rangée ⌈m ÷ k⌉ + 1, k = max(1,
    ⌊portée ÷ pas⌋) (règle d'ACAL587) ; ``(None, None)`` sans aucune portée."""
    from .planche import _zones

    portees = {str(zone.get('id') or f'PAN-{rang}'): _portee(zone)
               for rang, zone in enumerate(_zones(roof_layout), start=1)}
    if not any(portees.get(pan['repere']) for pan in pans):
        return None, None
    total, sans = 0, []
    for pan in pans:
        portee = portees.get(pan['repere'])
        if portee is None:
            sans.append(str(pan.get('libelle') or pan.get('repere')))
            continue
        lignes = _rangees_orientees(pan['modules'], pan.get('azimut_deg'))
        pas = _pas_du_pan(lignes)
        k = max(1, math.floor(portee / pas)) if pas else 1
        total += sum(math.ceil(len(segment) / k) + 1
                     for positions in lignes for segment in _segments(positions, pas))
    if sans:
        return None, ('Portée entre pieds non saisie sur le(s) pan(s) « ' + '», «'.join(sans)
                      + ' » (porteeEntrePieds) : les pieds ne sont pas comptés.')
    return total, None


def _egouts_du_document(roof_layout, pans):
    """ACAL598 — ``(valeurs, motifs)`` de ``longueur_egouts_m`` et
    ``facade_egouts_m2`` : arêtes typées ``egout`` (CAL57) des pans à poser, par
    pan × la hauteur SAISIE et sourcée de son bâtiment (CALX84). Aucun égout
    typé dans le document : les deux valent ``None`` sans motif (rien n'a changé)."""
    from .planche import _zones

    zones = {str(zone.get('id') or f'PAN-{rang}'): zone for rang, zone in enumerate(_zones(roof_layout), start=1)}
    brutes = (roof_layout or {}).get('buildings')
    batiments = {str(b.get('id')): b for b in (brutes if isinstance(brutes, list) else []) if isinstance(b, dict)}
    aretes = {repere: [a for a in zone.get('edges') or () if isinstance(a, dict)] for repere, zone in zones.items()}
    if not any(a.get('type') == 'egout' for pan in pans for a in aretes.get(pan['repere'], ())):
        return {'longueur_egouts_m': None, 'facade_egouts_m2': None}, {}
    longueur, facade, sans_arete, sans_hauteur = 0.0, 0.0, [], []
    for pan in pans:
        zone, nom = zones.get(pan['repere']) or {}, pan.get('libelle') or pan['repere']
        points, egouts = pan['points'], [a for a in aretes.get(pan['repere'], ()) if a.get('type') == 'egout']
        rangs = [a.get('index') for a in egouts]
        if (not egouts and any(a.get('type') in (None, 'inconnue') for a in aretes.get(pan['repere'], ()) or [{}])) \
                or len(points) != len(zone.get('vertices') or ()) \
                or any(not isinstance(i, int) or not 0 <= i < len(points) for i in rangs):
            sans_arete.append(f"arêtes d'égout non typées ou sommet illisible sur le pan « {nom} »")
            continue
        metres = sum(math.dist(points[i], points[(i + 1) % len(points)]) for i in rangs)
        batiment = batiments.get(str(zone.get('buildingId'))) or {}
        hauteur = _nombre(batiment.get('hauteurM'))
        longueur += metres
        if hauteur is None or hauteur <= 0 or not str(batiment.get('source') or '').strip():
            if metres:
                sans_hauteur.append('hauteur du bâtiment « %s » non saisie' % (
                    batiment.get('label') or zone.get('buildingId') or nom))
        else:
            facade += metres * hauteur
    if sans_arete:
        motif = _majuscule(' ; '.join(sans_arete)) + " : l'échafaudage n'est pas calculé."
        return {'longueur_egouts_m': None, 'facade_egouts_m2': None}, dict.fromkeys(
            ('longueur_egouts_m', 'facade_egouts_m2'), motif)
    motifs = ({'facade_egouts_m2': _majuscule(' ; '.join(dict.fromkeys(sans_hauteur)))
               + " : la façade n'est pas calculée."} if sans_hauteur else {})
    return {'longueur_egouts_m': round(longueur, 2),
            'facade_egouts_m2': None if sans_hauteur else round(facade, 2)}, motifs


def _grandeurs_ajoutees(roof_layout, geometrie, pans):
    """ACAL578 — ``(valeurs, manquants)`` des bases ``tables``, ``poteaux``, ``pieds``
    (+ ACAL598 : ``longueur_egouts_m``, ``facade_egouts_m2``)."""
    poteaux, motif_poteaux = _grandeur_poteaux(roof_layout)
    pieds, motif_pieds = _grandeur_pieds(roof_layout, pans)
    egouts, motifs_egouts = _egouts_du_document(roof_layout, pans)
    motifs = {'poteaux': motif_poteaux, 'pieds': motif_pieds, **motifs_egouts}
    return ({'tables': _grandeur_tables(geometrie), 'poteaux': poteaux, 'pieds': pieds, **egouts},
            {base: motif for base, motif in motifs.items() if motif})


def _grandeurs_du_document(roof_layout):
    """``{'valeurs': {base: nombre|None}, 'manquants': {base: motif}}``.

    Lecture PURE du document. Une grandeur illisible vaut ``None`` et son
    motif est NOMMÉ ; aucune n'est complétée.
    """
    from .catalogue_fixation import BASES, BASES_ORIENTATION
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
    orientation = dict.fromkeys(BASES_ORIENTATION, 0)
    sans_orientation, mixtes = [], 0
    for pan in _pans_a_commander(geometrie):
        pans += 1
        modules += len(pan['modules'])
        lue = _orientations_d_un_pan(pan)
        if lue is None:
            sans_orientation.append(pan.get('libelle') or pan.get('repere'))
        else:
            mixtes += lue[1]
            for base, nombre in lue[0].items():
                orientation[base] += nombre
        (n_rangees, n_jonctions, n_extremites, metres,
         sans_pas) = _grandeurs_d_un_pan(pan)
        rangees += n_rangees
        jonctions += n_jonctions
        extremites += n_extremites
        longueur += metres
        if sans_pas:
            pans_sans_pas.append(pan.get('libelle') or pan.get('repere'))

    ajout, motifs_ajout = _grandeurs_ajoutees(roof_layout, geometrie, _pans_a_commander(geometrie))
    if not modules:
        motif = ("Aucun module n'est posé sur la conception : aucune "
                 "quantité de fixation n'est calculée.")
        sortie = {'valeurs': {base: None for base in BASES},
                  'manquants': {base: motif for base in BASES}}
        if geometrie.get('surfaces_de_pose'):  # ACAL578 — un champ au sol seul garde ses tables
            for base in ('tables', 'poteaux'):
                sortie['valeurs'][base] = ajout[base]
                sortie['manquants'].pop(base)
                sortie['manquants'].update({base: motifs_ajout[base]} if base in motifs_ajout else {})
        return sortie

    valeurs = {'modules': modules, 'rangees': rangees, 'pans': pans,
               'jonctions': jonctions, 'extremites': extremites,
               'longueur_rangees_m': round(longueur, 2)}
    manquants = {}
    if pans_sans_pas:
        valeurs['longueur_rangees_m'] = None
        manquants['longueur_rangees_m'] = _motif_sans_pas(pans_sans_pas)
    valeurs.update({base: None if sans_orientation else nombre
                    for base, nombre in orientation.items()})
    manquants.update(_motifs_orientation(sans_orientation, mixtes))
    valeurs.update(ajout)
    manquants.update(motifs_ajout)
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


#: ACAL81 — d'où vient le système appliqué (clé ``systeme_source`` du
#: contrat ``calepinage_fixation_bom.json``).
SOURCE_CALEPINAGE = 'calepinage'
SOURCE_PARAMETRE = 'parametre'
#: ACAL566 — retenu d'après le ``type_toiture`` du lead.
SOURCE_COUVERTURE = 'couverture'


def _couverture_du_lead(company, calepinage):
    """Le ``type_toiture`` du lead du calepinage, par le sélecteur du CRM
    (jamais ses modèles) ; ``''`` s'il est inconnu."""
    lead_id = getattr(calepinage, 'lead_id', None)
    if company is None or not lead_id:
        return ''
    from apps.crm.selectors import get_company_lead

    lead = get_company_lead(company, lead_id)
    return str(getattr(lead, 'type_toiture', '') or '')


def _selon_la_couverture(actifs, couverture):
    """``(systeme | None, [refus] | None, source)`` d'après la couverture ;
    ``None`` en refus = aucune décision (la règle d'aujourd'hui s'applique)."""
    declarants = [s for s in actifs if couverture in (s.couvertures or [])]
    if len(declarants) == 1:
        return declarants[0], [], SOURCE_COUVERTURE
    if len(declarants) > 1:
        return None, [_refus(
            "Plusieurs systèmes de fixation sont actifs ("
            + ', '.join(f'« {s.code} »' for s in declarants)
            + ") : choisissez celui de ce calepinage.")], None
    vides = [s for s in actifs if not s.couvertures]
    if len(vides) == 1 and len(actifs) > 1:
        return vides[0], [], SOURCE_PARAMETRE
    return None, None, None


def _systeme_persiste(company, calepinage):
    """Le système CHOISI sur le calepinage (ACAL81), borné société."""
    systeme = getattr(calepinage, 'systeme_fixation', None)
    if systeme is None or company is None:
        return None
    return systeme if systeme.company_id == company.pk else None


def _resoudre_avec_source(company, demande=None, calepinage=None):
    """``(systeme | None, [refus], source | None)``.

    Ordre : le ``demande`` explicite (``?systeme=``) ; à défaut le système
    PERSISTÉ sur le calepinage (ACAL81, source ``'calepinage'``) ; à défaut
    l'UNIQUE système actif de la société (source ``'parametre'``).
    """
    from .catalogue_fixation import systeme_de_societe, systemes_actifs

    texte = str(demande or '').strip()
    if texte:
        systeme = systeme_de_societe(company, texte)
        if systeme is None:
            return None, [_refus(
                f"Système de fixation introuvable : « {texte} » (identifiant "
                "d'un système du catalogue de la société attendu).")], None
        return systeme, [], SOURCE_PARAMETRE
    persiste = _systeme_persiste(company, calepinage)
    if persiste is not None:
        return persiste, [], SOURCE_CALEPINAGE
    actifs = systemes_actifs(company)
    if not actifs:
        return None, [_refus(
            "Aucun système de fixation n'est saisi dans le catalogue de la "
            "société : la nomenclature de fixation n'est pas calculée. "
            "Saisissez un système et ses composants (rôle, unité, règle de "
            "quantité, source) pour l'obtenir.")], None
    couverture = _couverture_du_lead(company, calepinage)
    if couverture:
        systeme, refus, source = _selon_la_couverture(actifs, couverture)
        if refus is not None:
            return systeme, refus, source
    if len(actifs) > 1:
        return None, [_refus(
            "Plusieurs systèmes de fixation sont actifs ("
            + ', '.join(f'« {s.code} »' for s in actifs)
            + ") : choisissez celui de ce calepinage.")], None
    return actifs[0], [], SOURCE_PARAMETRE


def resoudre_systeme(company, demande=None, calepinage=None, *,
                     avec_source=False):
    """``(systeme | None, [refus])`` — celui demandé, sinon celui CHOISI sur
    le calepinage (ACAL81), sinon l'UNIQUE actif. ``avec_source=True`` rend
    aussi la source (``'calepinage'`` / ``'parametre'`` / ``None``)."""
    systeme, refus, source = _resoudre_avec_source(company, demande,
                                                   calepinage)
    if avec_source:
        return systeme, refus, source
    return systeme, refus


class FixationRefusee(ValueError):
    """ACAL81 — refus d'un choix de système, champ fautif nommé."""

    def __init__(self, message, *, champ='systeme_id'):
        super().__init__(message)
        self.champ = champ


def appliquer_systeme(calepinage, systeme_id):
    """ACAL81 — persiste (ou efface, ``None``) le système CHOISI.

    Un id d'une autre société et un id absent reçoivent le MÊME refus : on ne
    confirme jamais l'existence de la donnée d'autrui. Rend
    ``{systeme, systeme_source}`` (contrat ``fixation_post``).
    """
    from .catalogue_fixation import systeme_de_societe
    from .verrou import verifier_ecriture_autorisee

    # Lot 2 critique #10 — le verrou unique (D-ACAL : devis accepté ⇒
    # « révisez-le », 409) AVANT toute lecture du choix ou écriture.
    verifier_ecriture_autorisee(calepinage, champ='systeme_id')
    company = getattr(calepinage, 'company', None)
    if systeme_id is None:
        systeme = None
    else:
        systeme = systeme_de_societe(company, systeme_id)
        if systeme is None:
            raise FixationRefusee(
                f"Système de fixation introuvable : « {systeme_id} » "
                "(identifiant d'un système du catalogue de la société "
                "attendu).")
    calepinage.systeme_fixation = systeme
    calepinage.save(update_fields=['systeme_fixation', 'updated_at'])
    return {
        'systeme': ({'id': systeme.pk, 'code': systeme.code,
                     'libelle': systeme.libelle} if systeme else None),
        'systeme_source': SOURCE_CALEPINAGE if systeme else None,
    }


def bom_de_fixation(calepinage, systeme, refus=(), source=None):
    """La réponse du contrat CALX335, ``{systeme, lignes, refus,
    systeme_source}``.

    ``systeme`` est celui que ``resoudre_systeme`` a retenu (déjà borné
    société) ; ``None`` ⇒ aucune ligne, et ``refus`` (sa sortie) dit
    pourquoi — jamais une nomenclature devinée. ``source`` (ACAL81) dit d'où
    il vient : ``'calepinage'`` (choix persisté), ``'parametre'``, ou
    ``None`` quand aucun système n'est retenu.
    """
    if systeme is None:
        return {'systeme': None, 'lignes': [], 'refus': list(refus),
                'systeme_source': None, 'alertes': []}

    from apps.stock.selectors import valid_produit_ids

    from .catalogue_fixation import composants_du_systeme
    from .controles_pose import alertes_du_systeme

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
        'systeme_source': source,
        'alertes': alertes_du_systeme(calepinage, systeme),  # ACAL568
    }


#: ACAL1722 — les bases du projet (``_grandeurs_ajoutees``) et leurs renvois.
BASES_DU_PROJET = ('tables', 'poteaux', 'pieds', 'longueur_egouts_m',
                   'facade_egouts_m2')
RENVOI_AU_PROJET = 'Quantité du projet : voir la nomenclature'
MOTIF_EGOUT_DU_PAN = ("Arêtes d'égout non typées sur ce pan : l'échafaudage "
                      "n'est pas calculé.")


def _lignes_par_pan(roof_layout, composants):
    """ACAL592 — ``{repere de pan: lignes}`` : la MÊME règle et le même
    arrondi que ``_lignes_de_fixation``, sur les grandeurs de CHAQUE pan à
    poser (PUR ; ``[]`` sans conception lisible)."""
    from .catalogue_fixation import BASES_ORIENTATION
    from .planche import PlancheRefusee, geometrie_de_planche

    try:
        geometrie = geometrie_de_planche(roof_layout)
    except PlancheRefusee:
        return {}
    # ACAL1722 — une grandeur du PROJET (égouts, tables, poteaux, pieds) ne se
    # lit pas par pan : l'encart renvoie à la nomenclature, ou nomme la saisie.
    du_projet = _grandeurs_du_document(roof_layout)
    projet = _lignes_de_fixation(composants, du_projet)
    renvois = {base: du_projet['manquants'].get(base) or (
        MOTIF_EGOUT_DU_PAN if 'egouts' in base else RENVOI_AU_PROJET + '.')
        for base in BASES_DU_PROJET}
    sortie = {}
    for pan in _pans_a_commander(geometrie):
        (rangees, jonctions, extremites, longueur,
         sans_pas) = _grandeurs_d_un_pan(pan)
        valeurs = {'modules': len(pan['modules']), 'rangees': rangees,
                   'pans': 1, 'jonctions': jonctions,
                   'extremites': extremites,
                   'longueur_rangees_m': None if sans_pas
                   else round(longueur, 2)}
        motifs = ({'longueur_rangees_m': _motif_sans_pas(
            [pan.get('libelle') or pan.get('repere')])} if sans_pas else {})
        lue = _orientations_d_un_pan(pan)  # ACAL569
        valeurs.update(lue[0] if lue else dict.fromkeys(BASES_ORIENTATION))
        motifs.update(_motifs_orientation(
            [] if lue else [pan.get('libelle') or pan.get('repere')],
            lue[1] if lue else 0))
        lignes = _lignes_de_fixation(
            composants, {'valeurs': valeurs, 'manquants': {**renvois, **motifs}})
        sortie[pan['repere']] = [
            dict(ligne, manquant='%s (%s %s).' % (
                RENVOI_AU_PROJET, _fr(globale['quantite']), globale['unite']))
            if ligne['quantite'] is None and globale['quantite'] is not None
            else ligne for ligne, globale in zip(lignes, projet)]
    return sortie


def fixation_par_pan(calepinage):
    """ACAL592 — la nomenclature PAR PAN du système retenu, ou ``None`` sans
    société, sans système choisi ni actif unique (l'encart est alors
    ABSENT de la feuille du pan)."""
    from .catalogue_fixation import composants_du_systeme

    company = getattr(calepinage, 'company', None)
    if company is None:
        return None
    systeme, _refus = resoudre_systeme(company, calepinage=calepinage)
    if systeme is None:
        return None
    return _lignes_par_pan(getattr(calepinage, 'roof_layout', None),
                           composants_du_systeme(systeme))


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
    reponse = bom_de_fixation(
        calepinage, *resoudre_systeme(company, calepinage=calepinage,
                                      avec_source=True))
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
