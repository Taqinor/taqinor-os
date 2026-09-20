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

__all__ = [
    'SECTION', 'PARAMETRES', 'NOMBRES_DE_FORME',
    'normaliser_section_lestage', 'feuille_de_lestage',
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
        paramètres saisis, chacun ``{'valeur', 'source'}``.

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

    inconnues = sorted(set(valeur) - set(PARAMETRES))
    if inconnues:
        raise _refus(
            f"Paramètre de lestage inconnu : « {', '.join(inconnues)} ». "
            f"Paramètres admis : {', '.join(sorted(PARAMETRES))}.",
            inconnues[0])

    section = {}
    for cle, brut in valeur.items():
        libelle = PARAMETRES[cle][0]
        if brut is None:
            continue
        if not isinstance(brut, dict):
            raise _refus(
                f"« {libelle} » se saisit avec sa source : "
                '{"valeur": …, "source": "référence du texte"} '
                f"(reçu : {type(brut).__name__}).", cle)
        surplus = sorted(set(brut) - {'valeur', 'source'})
        if surplus:
            raise _refus(
                f"« {libelle} » n'accepte que « valeur » et « source » "
                f"(reçu en plus : {', '.join(surplus)}).", cle)
        source = brut.get('source')
        if not isinstance(source, str) or not source.strip():
            raise _refus(
                f"« {libelle} » doit porter la RÉFÉRENCE du texte d'où elle "
                "vient : aucun coefficient n'est admis sans sa source.", cle)
        section[cle] = {
            'valeur': _valeur_saisie(brut.get('valeur'), cle, libelle),
            'source': source.strip(),
        }
    return section


def _valeur_saisie(valeur, cle, libelle):
    """Un nombre (ou un texte pour la catégorie de terrain), jamais vide."""
    if cle in PARAMETRES_TEXTE:
        if not isinstance(valeur, str) or not valeur.strip():
            raise _refus(
                f"« {libelle} » doit être un texte non vide.", cle)
        return valeur.strip()
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise _refus(
            f"« {libelle} » doit être un nombre "
            f"(reçu : {type(valeur).__name__}).", cle)
    if float(valeur) < 0:
        raise _refus(
            f"« {libelle} » ne peut pas être négative (reçu : {valeur}).", cle)
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
