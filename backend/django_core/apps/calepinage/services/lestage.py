"""CAL163 — la FEUILLE DE LESTAGE, entièrement PARAMÉTRÉE par la société.

LE CONSTAT
----------
Le moteur le dit lui-même (``docs/moteur-calepinage.md``, non-objectif n°13) :
« pas de calcul de charges de vent/neige ni de ballast… aucune vérification de
tenue mécanique » — et le n°10 : « aucun texte normatif marocain n'est présent
dans ce dépôt ». Les outils du marché s'appuient, eux, sur un code de calcul
EXPLICITE (Solarius PV dimensionne selon IEC 60364 côté électrique).

LA DÉCISION FONDATEUR GRAVÉE ICI — AUCUN COEFFICIENT DANS LE CODE
-----------------------------------------------------------------
Ce module n'écrit AUCUNE valeur normative : ni vitesse de vent de référence,
ni coefficient de terrain, ni coefficient de pression, ni charge de neige, ni
coefficient de frottement — et pas même l'accélération de la pesanteur ni la
masse volumique de l'air. TOUT est SAISI par la société, avec la RÉFÉRENCE du
texte d'où elle le tire, et republié à côté de chaque résultat.

Conséquence directe, et c'est la garantie centrale de la tâche :

* **un paramètre non saisi ⇒ le résultat qui en dépend n'est PAS calculé**
  (``valeur`` vaut ``None`` et la ligne NOMME ce qui manque) — jamais une
  valeur par défaut, jamais un « au cas où » ;
* chaque résultat imprimable porte sa mention « paramètres saisis par
  <société>, référence <texte> » ;
* un test de surface (``tests/test_lestage_parametre.py``) relit CE fichier et
  refuse toute constante numérique hors des trois nombres de FORME des
  formules (0, 1, 2, ½ et le facteur kN→N), qui ne sont pas des coefficients
  normatifs mais l'écriture même des équations.

LES FORMULES, ÉCRITES UNE FOIS
------------------------------
* pression dynamique ``q = ½ · ρ · (c_terrain · v_réf)²`` [Pa]
* pression de soulèvement ``p_sou = q · c_p,soulèvement`` [Pa]
* effort de soulèvement par module ``F_sou = p_sou · S_module`` [N]
* lest anti-soulèvement ``m_lest = F_sou / g − m_module`` [kg], borné à 0
* effort horizontal par module ``F_h = q · c_p,horizontal · S_module`` [N]
* lest anti-glissement ``m_lest = F_h / (µ · g) − m_module`` [kg], borné à 0
* charge de neige par module ``F_neige = s · 1000 · S_module`` [N]

La SOCIÉTÉ fournit ρ, v_réf, c_terrain, c_p, µ, s et g ; le CALEPINAGE fournit
la surface et la masse du module (CAL164, depuis la fiche produit). Rien
d'autre n'entre dans ces lignes.
"""
from __future__ import annotations

from .parametres import ReglageInvalide

#: La section des réglages que ce module porte (CAL45 — une base, N sections).
SECTION = 'lestage'

#: Les paramètres ADMIS : ``clé -> (libellé, unité)``. Chacun se saisit sous
#: la forme ``{"valeur": <nombre>, "source": "<référence du texte>"}`` — une
#: valeur SANS source est refusée, en nommant le champ (règle « zéro chiffre
#: inventé » : un chiffre qu'on ne peut pas sourcer ne se défend pas).
PARAMETRES = {
    'masse_volumique_air_kg_m3': ("Masse volumique de l'air", 'kg/m³'),
    'vitesse_vent_reference_m_s': ('Vitesse de vent de référence', 'm/s'),
    'categorie_terrain': ('Catégorie de terrain', ''),
    'coefficient_terrain': ('Coefficient de terrain', ''),
    'coefficient_pression_soulevement': (
        'Coefficient de pression (soulèvement)', ''),
    'coefficient_pression_horizontal': (
        'Coefficient de pression (horizontal)', ''),
    'coefficient_frottement': ('Coefficient de frottement', ''),
    'charge_neige_kn_m2': ('Charge de neige', 'kN/m²'),
    'acceleration_pesanteur_m_s2': ('Accélération de la pesanteur', 'm/s²'),
    'masse_structure_kg_par_module': (
        'Masse de structure par module (kit)', 'kg'),
}

#: Le SEUL paramètre qui n'est pas un nombre : la catégorie de terrain est un
#: libellé (« rase campagne », « zone urbaine »…), saisi avec sa référence.
PARAMETRES_TEXTE = ('categorie_terrain',)

#: Les données que le CALEPINAGE apporte (jamais la société) : elles viennent
#: de la fiche produit (CAL164) ou de la géométrie du pan.
ENTREES_CALEPINAGE = ('surface_module_m2', 'masse_module_kg')

#: Les nombres de FORME admis dans ce fichier — aucun n'est un coefficient
#: normatif : ``0``/``1`` sont des bornes, ``2`` l'exposant du carré de la
#: vitesse, ``0.5`` le ½ de la pression dynamique et ``1000`` la conversion
#: kN → N. Le test de surface de CAL163 relit le fichier et refuse tout autre
#: littéral numérique.
NOMBRES_DE_FORME = (0, 1, 2, 0.5, 1000)

#: CALX361 — les ZONES DE VENT ET DE NEIGE par site (contrat CALX340). Deux
#: clés de STRUCTURE rejoignent la section, à côté des paramètres à plat :
#: ``zones`` (``[{code, libelle, commune_ou_region, parametres}]``) et
#: ``zone_par_defaut`` (le ``code`` d'une zone saisie). Absentes = le jeu
#: global d'aujourd'hui, servi tel quel (D12).
CLE_ZONES = 'zones'
CLE_ZONE_PAR_DEFAUT = 'zone_par_defaut'
CLES_DE_STRUCTURE = (CLE_ZONES, CLE_ZONE_PAR_DEFAUT)

#: Les paramètres qui DÉPENDENT du site : eux seuls se saisissent par zone.
#: Quand une zone s'applique, ils viennent d'ELLE et de nulle part ailleurs —
#: un paramètre de site qu'elle ne porte pas laisse sa ligne à ``None`` en le
#: nommant (le jeu global décrit peut-être une autre région). Les autres
#: (air, pressions, frottement, pesanteur, structure) restent globaux.
PARAMETRES_DE_SITE = ('vitesse_vent_reference_m_s', 'categorie_terrain',
                      'coefficient_terrain', 'charge_neige_kn_m2')

#: La clé, RACINE du document ``roof_layout`` (``additionalProperties``), par
#: laquelle un calepinage désigne SA zone. Absente = la zone par défaut.
CLE_ZONE_DOCUMENT = 'zoneLestage'

__all__ = [
    'SECTION', 'PARAMETRES', 'NOMBRES_DE_FORME', 'CLE_ZONES',
    'CLE_ZONE_PAR_DEFAUT', 'PARAMETRES_DE_SITE', 'CLE_ZONE_DOCUMENT',
    'normaliser_section_lestage', 'feuille_de_lestage',
    'surface_module_m2', 'masse_du_layout', 'masse_et_lestage',
]


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def normaliser_section_lestage(valeur):
    """La section ``lestage`` VALIDÉE — ``{}`` si la société n'a rien saisi.

    Args:
        valeur: la section telle que l'appelant l'envoie.

    Returns:
        ``{}`` quand rien n'est saisi (ÉQUIVALENCE : aucune feuille n'est
        calculée, exactement le comportement d'aujourd'hui), sinon les seuls
        paramètres saisis, chacun ``{'valeur', 'source'}`` — plus, CALX361,
        ``zones`` et ``zone_par_defaut`` quand la société en a saisi.

    Raises:
        ReglageInvalide: message FRANÇAIS nommant le champ fautif.
    """
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(
            "La section « lestage » doit être un objet "
            f"(reçu : {type(valeur).__name__}).", SECTION)
    if not valeur:
        return {}

    inconnues = sorted(set(valeur) - set(PARAMETRES) - set(CLES_DE_STRUCTURE))
    if inconnues:
        raise _refus(
            f"Paramètre de lestage inconnu : « {', '.join(inconnues)} ». "
            f"Paramètres admis : {', '.join(sorted(PARAMETRES))}.",
            inconnues[0])

    section = {}
    for cle, brut in valeur.items():
        if cle in CLES_DE_STRUCTURE:
            continue
        parametre = _parametre_saisi(cle, brut, cle)
        if parametre is not None:
            section[cle] = parametre

    zones = _zones_saisies(valeur.get(CLE_ZONES))
    if zones:
        section[CLE_ZONES] = zones
    defaut = valeur.get(CLE_ZONE_PAR_DEFAUT)
    if defaut not in (None, ''):
        codes = [zone['code'] for zone in zones]
        if not isinstance(defaut, str) or defaut.strip() not in codes:
            raise _refus(
                f"La zone par défaut « {defaut} » n'est aucune des zones "
                "saisies (" + (', '.join(f'« {code} »' for code in codes)
                               or 'aucune zone saisie') + ").",
                CLE_ZONE_PAR_DEFAUT)
        section[CLE_ZONE_PAR_DEFAUT] = defaut.strip()
    return section


def _parametre_saisi(cle, brut, champ):
    """``{'valeur', 'source'}`` VALIDÉ, ``None`` si vide — refus nommant
    ``champ`` (le nom nu du paramètre, ou son chemin dans une zone)."""
    libelle = PARAMETRES[cle][0]
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise _refus(
            f"« {libelle} » se saisit avec sa source : "
            '{"valeur": …, "source": "référence du texte"} '
            f"(reçu : {type(brut).__name__}).", champ)
    surplus = sorted(set(brut) - {'valeur', 'source'})
    if surplus:
        raise _refus(
            f"« {libelle} » n'accepte que « valeur » et « source » "
            f"(reçu en plus : {', '.join(surplus)}).", champ)
    source = brut.get('source')
    if not isinstance(source, str) or not source.strip():
        raise _refus(
            f"« {libelle} » doit porter la RÉFÉRENCE du texte d'où elle "
            "vient : aucun coefficient n'est admis sans sa source.", champ)
    return {
        'valeur': _valeur_saisie(brut.get('valeur'), cle, libelle, champ),
        'source': source.strip(),
    }


def _zones_saisies(zones):
    """CALX361 — la liste ``zones`` VALIDÉE (``[]`` si rien n'est saisi).

    Chaque zone porte un ``code`` unique et un ``libelle`` ; ses
    ``parametres`` ne sont que des paramètres DE SITE, chacun avec sa
    source (même exigence que le jeu global, ``_parametre_saisi``).
    """
    if zones in (None, []):
        return []
    if not isinstance(zones, list):
        raise _refus(
            "Les zones de lestage se saisissent en liste "
            f"(reçu : {type(zones).__name__}).", CLE_ZONES)
    propres, codes = [], set()
    for rang, zone in enumerate(zones):
        prefixe = f'{CLE_ZONES}[{rang}]'
        if not isinstance(zone, dict):
            raise _refus(
                f"Chaque zone de lestage est un objet (zone n° {rang + 1}).",
                prefixe)
        surplus = sorted(set(zone) - {'code', 'libelle',
                                      'commune_ou_region', 'parametres'})
        if surplus:
            raise _refus(
                f"Zone n° {rang + 1} : clé(s) inconnue(s) "
                f"« {', '.join(surplus)} ».", f'{prefixe}.{surplus[0]}')
        code = zone.get('code')
        code = code.strip() if isinstance(code, str) else ''
        if not code:
            raise _refus(
                f"Zone n° {rang + 1} : le « code » est obligatoire.",
                f'{prefixe}.code')
        if code in codes:
            raise _refus(
                f"Deux zones portent le même code « {code} ».",
                f'{prefixe}.code')
        codes.add(code)
        libelle = zone.get('libelle')
        libelle = libelle.strip() if isinstance(libelle, str) else ''
        if not libelle:
            raise _refus(
                f"Zone « {code} » : le « libelle » est obligatoire.",
                f'{prefixe}.libelle')
        region = zone.get('commune_ou_region')
        region = region.strip() if isinstance(region, str) else ''
        parametres = zone.get('parametres')
        if parametres is None:
            parametres = {}
        if not isinstance(parametres, dict):
            raise _refus(
                f"Zone « {code} » : « parametres » est un objet.",
                f'{prefixe}.parametres')
        hors_site = sorted(set(parametres) - set(PARAMETRES_DE_SITE))
        if hors_site:
            raise _refus(
                f"Zone « {code} » : « {hors_site[0]} » n'est pas un paramètre "
                "de site — seuls se saisissent par zone : "
                f"{', '.join(PARAMETRES_DE_SITE)}.",
                f'{prefixe}.parametres.{hors_site[0]}')
        propres_parametres = {}
        for cle, brut in parametres.items():
            parametre = _parametre_saisi(
                cle, brut, f'{prefixe}.parametres.{cle}')
            if parametre is not None:
                propres_parametres[cle] = parametre
        propres.append({'code': code, 'libelle': libelle,
                        'commune_ou_region': region,
                        'parametres': propres_parametres})
    return propres


def _valeur_saisie(valeur, cle, libelle, champ=None):
    """Un nombre (ou un texte pour la catégorie de terrain), jamais vide."""
    champ = champ or cle
    if cle in PARAMETRES_TEXTE:
        if not isinstance(valeur, str) or not valeur.strip():
            raise _refus(
                f"« {libelle} » doit être un texte non vide.", champ)
        return valeur.strip()
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise _refus(
            f"« {libelle} » doit être un nombre "
            f"(reçu : {type(valeur).__name__}).", champ)
    if float(valeur) < 0:
        raise _refus(
            f"« {libelle} » ne peut pas être négative (reçu : {valeur}).",
            champ)
    return float(valeur)


# ── la feuille de calcul ────────────────────────────────────────────────────

def _nombre(section, cle):
    """La valeur SAISIE de ``cle``, ou ``None`` si la société ne l'a pas."""
    entree = (section or {}).get(cle)
    if not isinstance(entree, dict):
        return None
    valeur = entree.get('valeur')
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _ligne(code, libelle, unite, formule, entrees, calcul, valeurs):
    """Une ligne de la feuille : calculée, ou NON calculée en le disant.

    ``entrees`` est la liste des clés dont la ligne dépend ; toute clé sans
    valeur fait que la ligne n'est PAS calculée et la NOMME.
    """
    manquants = [cle for cle in entrees if valeurs.get(cle) is None]
    if manquants:
        libelles = [PARAMETRES[cle][0] if cle in PARAMETRES else cle
                    for cle in manquants]
        return {
            'code': code, 'libelle': libelle, 'valeur': None, 'unite': unite,
            'formule': formule, 'entrees': list(entrees),
            'manquants': manquants,
            'mention': 'paramètres à saisir : ' + ', '.join(libelles),
        }
    return {
        'code': code, 'libelle': libelle,
        'valeur': calcul(valeurs), 'unite': unite,
        'formule': formule, 'entrees': list(entrees), 'manquants': [],
        'mention': '',
    }


def _mention_impression(section, societe):
    """« paramètres saisis par <société>, référence <texte> »."""
    if not section:
        return ('Aucun paramètre de lestage n\'a été saisi : aucun résultat '
                'n\'est calculé.')
    references = []
    for cle in sorted(section):
        source = (section[cle] or {}).get('source')
        if source and source not in references:
            references.append(source)
    nom = str(societe or '').strip() or 'la société'
    return ('paramètres saisis par %s, référence %s'
            % (nom, ' ; '.join(references)))


def feuille_de_lestage(section, *, surface_module_m2=None,
                       masse_module_kg=None, societe=''):
    """La feuille de lestage d'UN module, paramètres saisis + résultats.

    Args:
        section: la section ``lestage`` des réglages société (CAL45).
        surface_module_m2: la surface d'un module POSÉ (fiche produit).
        masse_module_kg: la masse d'un module POSÉ (fiche produit, CAL164).
        societe: le nom de la société, pour la mention imprimable.

    Returns:
        ``{'parametres', 'manquants', 'lignes', 'mention', 'calculable'}`` —
        ``lignes`` porte TOUJOURS les sept lignes de la feuille ; celles dont
        un paramètre manque valent ``None`` et disent lequel.
    """
    section = section or {}
    valeurs = {cle: _nombre(section, cle) for cle in PARAMETRES
               if cle not in PARAMETRES_TEXTE}
    valeurs['surface_module_m2'] = (
        float(surface_module_m2) if isinstance(surface_module_m2, (int, float))
        and not isinstance(surface_module_m2, bool) else None)
    valeurs['masse_module_kg'] = (
        float(masse_module_kg) if isinstance(masse_module_kg, (int, float))
        and not isinstance(masse_module_kg, bool) else None)
    # La masse totale qui S'OPPOSE au soulèvement = module + structure, quand
    # la société a saisi la masse de son kit (sinon la structure est ignorée,
    # ce qui est le côté SÛR : moins de masse résistante, donc plus de lest).
    structure = valeurs.get('masse_structure_kg_par_module') or 0
    if valeurs['masse_module_kg'] is not None:
        valeurs['masse_resistante_kg'] = valeurs['masse_module_kg'] + structure
    else:
        valeurs['masse_resistante_kg'] = None

    def _q(v):
        vitesse = v['coefficient_terrain'] * v['vitesse_vent_reference_m_s']
        return 0.5 * v['masse_volumique_air_kg_m3'] * vitesse ** 2

    def _p_sou(v):
        return _q(v) * v['coefficient_pression_soulevement']

    def _f_sou(v):
        return _p_sou(v) * v['surface_module_m2']

    def _lest_sou(v):
        besoin = (_f_sou(v) / v['acceleration_pesanteur_m_s2']
                  - v['masse_resistante_kg'])
        return max(0, besoin)

    def _f_h(v):
        return _q(v) * v['coefficient_pression_horizontal'] \
            * v['surface_module_m2']

    def _lest_glissement(v):
        resistance = (v['coefficient_frottement']
                      * v['acceleration_pesanteur_m_s2'])
        if resistance <= 0:
            return None
        return max(0, _f_h(v) / resistance - v['masse_resistante_kg'])

    def _f_neige(v):
        return v['charge_neige_kn_m2'] * 1000 * v['surface_module_m2']

    vent = ('masse_volumique_air_kg_m3', 'vitesse_vent_reference_m_s',
            'coefficient_terrain')
    lignes = [
        _ligne('pression_dynamique', 'Pression dynamique', 'Pa',
               'q = ½ · ρ · (c_terrain · v_réf)²', vent, _q, valeurs),
        _ligne('pression_soulevement', 'Pression de soulèvement', 'Pa',
               'p = q · c_p,soulèvement',
               vent + ('coefficient_pression_soulevement',), _p_sou, valeurs),
        _ligne('effort_soulevement_module',
               'Effort de soulèvement par module', 'N',
               'F = p · S_module',
               vent + ('coefficient_pression_soulevement',
                       'surface_module_m2'), _f_sou, valeurs),
        _ligne('lest_anti_soulevement', 'Lest requis (soulèvement)', 'kg',
               'm_lest = F / g − m_résistante',
               vent + ('coefficient_pression_soulevement',
                       'surface_module_m2', 'acceleration_pesanteur_m_s2',
                       'masse_resistante_kg'), _lest_sou, valeurs),
        _ligne('effort_horizontal_module',
               'Effort horizontal par module', 'N',
               'F_h = q · c_p,horizontal · S_module',
               vent + ('coefficient_pression_horizontal',
                       'surface_module_m2'), _f_h, valeurs),
        _ligne('lest_anti_glissement', 'Lest requis (glissement)', 'kg',
               'm_lest = F_h / (µ · g) − m_résistante',
               vent + ('coefficient_pression_horizontal',
                       'surface_module_m2', 'coefficient_frottement',
                       'acceleration_pesanteur_m_s2',
                       'masse_resistante_kg'), _lest_glissement, valeurs),
        _ligne('charge_neige_module', 'Charge de neige par module', 'N',
               'F_neige = s · 1000 · S_module',
               ('charge_neige_kn_m2', 'surface_module_m2'), _f_neige,
               valeurs),
    ]

    parametres = []
    for cle in PARAMETRES:
        entree = section.get(cle)
        if isinstance(entree, dict) and entree.get('source'):
            libelle, unite = PARAMETRES[cle]
            parametres.append({
                'cle': cle, 'libelle': libelle, 'unite': unite,
                'valeur': entree.get('valeur'), 'source': entree['source'],
            })
    manquants = [cle for cle in PARAMETRES
                 if not isinstance(section.get(cle), dict)]
    return {
        'parametres': parametres,
        'manquants': manquants,
        'lignes': lignes,
        'mention': _mention_impression(section, societe),
        'calculable': any(ligne['valeur'] is not None for ligne in lignes),
    }


# ── CAL164 — LA MASSE INSTALLÉE ET LA SURCHARGE DE TOITURE ─────────────────
#
# Le poids d'un module existe sur sa fiche (``FicheTechnique.poids_kg``, exposé
# par ``apps.stock.selectors.dimensions_de_pose``, CAL119) mais AUCUNE masse
# posée, AUCUNE surcharge n'était jamais publiée. Les trois règles :
#
# * une fiche SANS ``poids_kg`` ⇒ la masse n'est PAS publiée pour ce produit,
#   qui est LISTÉ comme manquant (jamais un poids « moyen » de catalogue) ;
# * la masse par m² se calcule sur la surface RÉELLE DU PAN (``result.areaM2``
#   du document), jamais sur l'emprise du bâtiment ; un pan sans surface
#   connue ne publie pas de masse/m² et le dit ;
# * chaque ligne CITE le poids unitaire employé et son ORIGINE (fiche produit
#   pour le module, saisie société pour la structure du kit).

def _surface_du_pan(zone):
    """La surface du PAN telle que le document la porte, ou ``None``.

    ``result.areaM2`` est l'aire du pan DESSINÉ. Aucune correction n'est
    inventée ici : si le document ne la porte pas, la masse par m² n'est pas
    publiée — c'est très exactement la règle « zéro chiffre inventé ».
    """
    resultat = zone.get('result') if isinstance(zone, dict) else None
    if not isinstance(resultat, dict):
        return None
    aire = resultat.get('areaM2')
    if isinstance(aire, bool) or not isinstance(aire, (int, float)):
        return None
    aire = float(aire)
    return aire if aire > 0 else None


def surface_module_m2(cotes):
    """La surface d'un module depuis ses cotes de pose (mm), ou ``None``.

    ``cotes`` est le dict de ``apps.stock.selectors.dimensions_de_pose``.
    Une cote absente ⇒ ``None`` : la feuille de lestage ne calcule alors
    aucun effort, plutôt que d'en calculer un sur une surface supposée.
    """
    cotes = cotes if isinstance(cotes, dict) else {}
    longueur, largeur = cotes.get('longueur_mm'), cotes.get('largeur_mm')
    for valeur in (longueur, largeur):
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return None
    return float(longueur) * float(largeur) / (1000 * 1000)


def _mention_pan(masse, surface):
    if masse is None:
        return ("Masse non publiée : le poids unitaire du module n'est pas "
                "renseigné sur sa fiche.")
    if not surface:
        return ("Masse par m² non publiée : le document ne porte pas la "
                "surface de ce pan.")
    return ''


def masse_du_layout(layout, *, poids_module_kg=None,
                    designation_module='', section=None):
    """La masse POSÉE, pan par pan, et la surcharge par m² de pan.

    Args:
        layout: le document ``roof_layout`` v2.
        poids_module_kg: le poids UNITAIRE du module posé, tel que sa fiche
            le publie (``dimensions_de_pose['poids_kg']``). ``None`` = fiche
            sans poids : rien n'est publié, le produit est listé manquant.
        designation_module: le nom du produit, pour le nommer s'il manque.
        section: la section ``lestage`` (CAL163) — sa
            ``masse_structure_kg_par_module`` SAISIE ajoute la masse du kit ;
            absente, la structure est listée manquante, jamais estimée.

    Returns:
        ``{'pans', 'total_modules', 'masse_totale_kg', 'poids_unitaire',
        'manquants'}``.
    """
    from .production import pans_du_layout

    section = section or {}
    poids = (float(poids_module_kg)
             if isinstance(poids_module_kg, (int, float))
             and not isinstance(poids_module_kg, bool) else None)
    structure = _nombre(section, 'masse_structure_kg_par_module')

    manquants = []
    if poids is None:
        manquants.append({
            'quoi': 'poids_module',
            'libelle': designation_module or 'Module posé',
            'message': ("La fiche de ce produit ne publie aucun poids "
                        "(« poids_kg ») : la masse posée n'est pas publiée "
                        "pour ce module."),
        })
    if structure is None:
        manquants.append({
            'quoi': 'masse_structure',
            'libelle': 'Structure de pose (kit)',
            'message': ("La masse de structure par module n'est pas saisie "
                        "dans les réglages de lestage : la masse du kit "
                        "n'est pas comptée."),
        })

    zones = ((layout or {}).get('zones')
             if isinstance(layout, dict) else None) or []
    surfaces = {}
    for rang, zone in enumerate(zones, start=1):
        if not isinstance(zone, dict):
            continue
        cle = str(zone.get('label') or zone.get('id') or 'PAN-%d' % rang)
        surfaces[cle] = _surface_du_pan(zone)

    pans, total_modules, masse_totale = [], 0, None
    for pan in pans_du_layout(layout):
        modules = int(pan.get('modules') or 0)
        total_modules += modules
        surface = surfaces.get(pan['pan'])
        masse_modules = (poids * modules) if poids is not None else None
        masse_structure = ((structure * modules)
                           if structure is not None else None)
        masse_pan = None
        if masse_modules is not None:
            masse_pan = masse_modules + (masse_structure or 0)
            masse_totale = (masse_totale or 0) + masse_pan
        par_m2 = (masse_pan / surface
                  if masse_pan is not None and surface else None)
        pans.append({
            'pan': pan['pan'],
            'modules': modules,
            'surface_pan_m2': surface,
            'masse_modules_kg': masse_modules,
            'masse_structure_kg': masse_structure,
            'masse_kg': masse_pan,
            'masse_par_m2_kg': par_m2,
            'mention': _mention_pan(masse_pan, surface),
        })

    saisie_structure = section.get('masse_structure_kg_par_module')
    return {
        'pans': pans,
        'total_modules': total_modules,
        'masse_totale_kg': masse_totale,
        'poids_unitaire': {
            'module_kg': poids,
            'module_source': ('fiche produit' if poids is not None else None),
            'module_designation': designation_module or '',
            'structure_kg_par_module': structure,
            'structure_source': (
                (saisie_structure or {}).get('source')
                if structure is not None else None),
        },
        'manquants': manquants,
    }


def masse_et_lestage(calepinage, *, produit_module_id=None, layout=None):
    """CAL164 — la masse posée + (si CAL163 est paramétré) le lest requis.

    Lecture PURE et cross-app par SÉLECTEURS uniquement
    (``apps.stock.selectors``) : ce module n'importe aucun modèle étranger.
    Le produit module est celui que l'appelant désigne ; sans lui, la masse
    n'est pas publiée et il est listé comme manquant (jamais un poids
    supposé).
    """
    from apps.stock.selectors import dimensions_de_pose, get_produit_scoped

    from ..selectors import parametres_de_societe

    company = getattr(calepinage, 'company', None)
    brute = (parametres_de_societe(company) or {}).get(SECTION) or {}
    layout = layout if layout is not None else getattr(
        calepinage, 'roof_layout', None)
    # CALX361 — la zone du site. Sans zones saisies, ``section`` EST la
    # section d'aujourd'hui, octet pour octet, et ``zone`` vaut ``None`` :
    # la sortie ne change pas d'une clé (D12).
    section, zone = _section_du_site(brute, layout)

    cotes, designation = {}, ''
    if produit_module_id:
        produit = get_produit_scoped(company, produit_module_id)
        if produit is not None:
            cotes = dimensions_de_pose(produit) or {}
            designation = getattr(produit, 'nom', '') or ''

    societe = getattr(company, 'nom', '') or ''
    masse = masse_du_layout(layout, poids_module_kg=cotes.get('poids_kg'),
                            designation_module=designation, section=section)
    feuille = feuille_de_lestage(
        section, surface_module_m2=surface_module_m2(cotes),
        masse_module_kg=cotes.get('poids_kg'), societe=societe)
    if zone is not None:
        feuille['zone'] = zone
        _mentionner_chaque_ligne(feuille, section, societe, zone)
    return {'masse': masse, 'lestage': feuille}


# ── CALX361 — LA ZONE DE VENT ET DE NEIGE DU SITE ───────────────────────────

def _section_du_site(section, layout):
    """``(section effective, zone | None)`` pour le calepinage de ``layout``.

    * Aucune zone saisie ⇒ ``(section, None)`` : le jeu global tel quel.
    * Zones saisies ⇒ la zone DÉSIGNÉE par le document (``zoneLestage``),
      sinon la zone par défaut de la société. Les paramètres de SITE viennent
      alors de la zone et d'elle seule ; les autres restent globaux. Aucune
      zone désignable ⇒ le jeu global, et ``zone`` le DIT (``motif``) ; une
      zone désignée mais inconnue ⇒ aucun paramètre de site (les lignes qui
      en dépendent sortent à ``None`` en le nommant).
    """
    section = section if isinstance(section, dict) else {}
    zones = section.get(CLE_ZONES)
    globale = {cle: valeur for cle, valeur in section.items()
               if cle not in CLES_DE_STRUCTURE}
    if not isinstance(zones, list) or not zones:
        return globale, None

    demande = (layout or {}).get(CLE_ZONE_DOCUMENT) \
        if isinstance(layout, dict) else None
    demande = demande.strip() if isinstance(demande, str) else ''
    origine = 'document' if demande else 'defaut'
    code = demande or str(section.get(CLE_ZONE_PAR_DEFAUT) or '').strip()
    if not code:
        return globale, {
            'code': None, 'libelle': None, 'commune_ou_region': None,
            'origine': None, 'sources': [],
            'motif': ("Aucune zone de lestage n'est désignée pour ce "
                      "calepinage et la société n'a pas de zone par défaut : "
                      "le jeu global de la société s'applique."),
        }

    hors_site = {cle: valeur for cle, valeur in globale.items()
                 if cle not in PARAMETRES_DE_SITE}
    retenue = next((zone for zone in zones
                    if isinstance(zone, dict) and zone.get('code') == code),
                   None)
    if retenue is None:
        return hors_site, {
            'code': code, 'libelle': None, 'commune_ou_region': None,
            'origine': origine, 'sources': [],
            'motif': (f"La zone « {code} » "
                      + ("désignée par ce calepinage"
                         if origine == 'document' else "par défaut")
                      + " n'existe pas dans les réglages de lestage : "
                      "aucun paramètre de site n'est appliqué."),
        }

    parametres = retenue.get('parametres') or {}
    effective = dict(hors_site)
    for cle in PARAMETRES_DE_SITE:
        if isinstance(parametres.get(cle), dict):
            effective[cle] = parametres[cle]
    sources = []
    for cle in PARAMETRES_DE_SITE:
        source = (parametres.get(cle) or {}).get('source')
        if source and source not in sources:
            sources.append(source)
    absents = [PARAMETRES[cle][0] for cle in PARAMETRES_DE_SITE
               if cle not in parametres]
    return effective, {
        'code': code,
        'libelle': retenue.get('libelle') or None,
        'commune_ou_region': retenue.get('commune_ou_region') or None,
        'origine': origine,
        'sources': sources,
        'motif': ('' if not absents else
                  f"Paramètre(s) de site non saisi(s) pour la zone « {code} » "
                  f": {', '.join(absents)} — les lignes qui en dépendent ne "
                  "sont pas calculées."),
    }


def _mentionner_chaque_ligne(feuille, section, societe, zone):
    """« paramètres saisis par <société>, référence <texte> » sur CHAQUE
    ligne calculée (en mode zone) ; une ligne non calculée garde ce qui
    manque et nomme la zone."""
    nom = str(societe or '').strip() or 'la société'
    nom_zone = zone.get('libelle') or zone.get('code')
    for ligne in feuille.get('lignes') or []:
        if ligne.get('valeur') is None:
            if nom_zone and any(cle in PARAMETRES_DE_SITE
                                for cle in ligne.get('manquants') or []):
                ligne['mention'] = (f"{ligne.get('mention') or ''} "
                                    f"(zone « {nom_zone} »)").strip()
            continue
        references = []
        for cle in ligne.get('entrees') or []:
            source = (section.get(cle) or {}).get('source') \
                if isinstance(section.get(cle), dict) else None
            if source and source not in references:
                references.append(source)
        if references:
            ligne['mention'] = ('paramètres saisis par %s, référence %s'
                                % (nom, ' ; '.join(references)))
