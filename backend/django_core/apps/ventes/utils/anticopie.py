"""L-NIV — dégradation « niveau standard » des surfaces CLIENT (anticopie).

SOURCE UNIQUE de la règle d'agrégation « kit » : la charge utile JSON de la
proposition (``public_views.proposal_data``), le PDF public rendu par le moteur
(``quote_engine.builder.build_quote_data``) et le comparatif de gammes lisent
TOUS ce module. Deux implémentations parallèles auraient dérivé — c'est
exactement la panne que ce module supprime : le JSON masquait la nomenclature,
le PDF servi par le même lien la publiait en entier.

Le moteur ne fait que RENDRE (règle #4) : rien ici ne touche un statut, ne
persiste quoi que ce soit, ni n'invente un chiffre. L'agrégation regroupe des
lignes existantes à leur SOUS-TOTAL EXACT — la somme HT/TTC est préservée à la
décimale près (testé), seule la granularité d'affichage change.
"""
from decimal import Decimal

#: L-NIV (fondateur 24/08/2026) — mots-clés identifiant une ligne « kit »
#: (structure de fixation, câblage, protection) parmi les lignes du devis.
#: Alignés sur le vocabulaire du générateur de nomenclature accessoire
#: (``solar_design.compute_bom`` : catégories « Structure », « Protection AC/
#: DC », « Coffret », « Mise à la terre », « Batterie »/« Protection
#: batterie ») — même discipline que ``solar.js`` vs ``quote_engine/
#: builder.py`` (CLAUDE.md) : les deux vocabulaires restent alignés à la main.
KIT_KEYWORDS = (
    'fixation', 'rail', 'crochet', 'pince',
    'câblage', 'cablage', 'câble', 'cable', 'gaine', 'goulotte',
    'presse-étoupe', 'presse étoupe', 'connecteur mc4',
    'protection', 'disjoncteur', 'parafoudre', 'sectionneur', 'fusible',
    'différentiel', 'coffret', 'mise à la terre', 'terre',
)

#: Libellé UNIQUE de la ligne agrégée — identique dans le JSON, le PDF et le
#: comparatif de gammes (le client lit la même chose partout).
LIBELLE_KIT = 'Kit de fixation, câblage et protection complet'


def est_ligne_kit(designation):
    d = (designation or '').lower()
    return any(mot in d for mot in KIT_KEYWORDS)


def agreger_lignes_kit(items):
    """Regroupe les lignes fixation/câblage/protection d'``items`` en UNE ligne
    ``LIBELLE_KIT``, au sous-total EXACT (somme HT/TTC préservée — testé). Les
    autres lignes (panneaux, onduleur, batterie…) restent inchangées, à leur
    place. Moins de deux lignes « kit » → ``items`` inchangé (rien à agréger).

    ``items`` = les dicts du builder (``designation``/``quantite``/
    ``prix_unit_ht``/``prix_unit_ttc``/``taux_tva``/``ordre``).
    """
    if not items:
        return items
    kit_indices = [i for i, it in enumerate(items)
                   if est_ligne_kit(it.get('designation'))]
    if len(kit_indices) < 2:
        return items
    kit = [items[i] for i in kit_indices]
    total_ht = sum(
        (Decimal(str(it.get('quantite', 0) or 0))
         * Decimal(str(it.get('prix_unit_ht', 0) or 0))) for it in kit)
    total_ttc = sum(
        (Decimal(str(it.get('quantite', 0) or 0))
         * Decimal(str(it.get('prix_unit_ttc', 0) or 0))) for it in kit)
    ligne_agregee = {
        'designation': LIBELLE_KIT,
        'marque': '', 'description': '', 'garantie': '',
        'garantie_mois': None, 'garantie_production_mois': None,
        'quantite': 1.0,
        'prix_unit_ht': float(round(total_ht, 2)),
        'prix_unit_ttc': float(round(total_ttc, 2)),
        'taux_tva': kit[0].get('taux_tva', 20),
        'ordre': min((it.get('ordre', 0) or 0) for it in kit),
        '_produit_nom': '',
    }
    kit_set = set(kit_indices)
    out = []
    inserted = False
    for i, it in enumerate(items):
        if i in kit_set:
            if not inserted:
                out.append(ligne_agregee)
                inserted = True
            continue
        out.append(it)
    return out


def agreger_designations_kit(lignes):
    """Même règle, sur des lignes SANS prix (``designation``/``quantite``) —
    le comparatif de gammes, qui ne publie jamais de prix ligne à ligne.

    La ligne agrégée porte ``quantite = 1.0`` : c'est UN kit, exactement comme
    la ligne agrégée à prix ci-dessus. Aucun autre chiffre n'est produit.
    """
    if not lignes:
        return lignes
    kit_indices = [i for i, ln in enumerate(lignes)
                   if est_ligne_kit(ln.get('designation'))]
    if len(kit_indices) < 2:
        return lignes
    kit_set = set(kit_indices)
    out = []
    inserted = False
    for i, ln in enumerate(lignes):
        if i in kit_set:
            if not inserted:
                out.append({'designation': LIBELLE_KIT, 'quantite': 1.0})
                inserted = True
            continue
        out.append(ln)
    return out
