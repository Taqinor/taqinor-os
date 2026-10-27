# -*- coding: utf-8 -*-
"""RSIZ11 — « Prêt pour le devis RÉSIDENTIEL » : l'équivalent résidentiel du
tableau C&I (``apps/stock/contract_samples/pret_devis_ci.json``).

Demandé par la session CCAT (catalogue prêt pour le devis) : tout ce que
l'administrateur doit renseigner au catalogue pour que le composeur
résidentiel (``composition_residentielle``) chiffre entièrement un devis aux
DEUX options (« sans » = onduleur réseau, « avec » = onduleur hybride +
batterie), poste par poste.

Les règles d'éligibilité ne sont PAS inventées : chaque poste reprend le
filtre que le composeur applique à son vivier (voir ``_eligibilite_*``) —
catégorie par ``classer_produit`` (même classifieur que le composeur et le
moteur PDF), garde de prix ``_has_price``, wattage lu dans le nom
(``_parse_watt``), puissance lue dans le nom (``_parse_kw``), verrou de
complétude PVOND (``onduleur_specs_manquantes``), raccordement mono/tri
(``est_triphase_produit``), batterie en stock ET dans la plage de tension d'un
hybride servable (``_batterie_en_stock``/``_batterie_compatible``), câbles
vendus AU MÈTRE (``_est_au_metre``).

Fonction PURE en lecture : aucune écriture, aucun ``prix_achat`` lu ni rendu,
catalogue borné à la société (+ produits globaux, archivés exclus) par
``catalogue_de_la_societe``. Le stock n'est lu que par ses sélecteurs.
Forme de retour : celle du contrat C&I, ``{pret, nb_obligatoires_manquants,
postes: [{cle, libelle, groupe, obligatoire, statut, articles, action}]}``.
"""
from apps.stock.selectors import onduleur_specs_manquantes
from apps.ventes.compatibilites import est_triphase_produit
from apps.ventes.domain.catalogue import (
    _batterie_compatible,
    _batterie_en_stock,
    _est_au_metre,
    _has_price,
    _parse_kw,
    _parse_kwh,
    _parse_watt,
    _plage_batterie_de_l_onduleur,
    _sans_accents,
    catalogue_de_la_societe,
    classer_produit,
)

#: Postes : (clé, libellé, groupe, obligatoire, catégorie du composeur).
#: Obligatoire = le composeur ne peut pas chiffrer le devis sans (les deux
#: options). Facultatif = le devis se fait sans, l'offre est moins complète
#: (tri/alu : selon le raccordement ou le toggle du client ; Smart Meter et
#: clé Wifi : seulement derrière un onduleur Huawei).
POSTES_RESIDENTIEL = (
    ('panneau', 'Panneau solaire (puissance en Wc dans le nom, prix)',
     'materiel', True, 'panneau'),
    ('onduleur_reseau:mono', 'Onduleur réseau monophasé (option « sans batterie »)',
     'onduleur', True, 'onduleur_reseau'),
    ('onduleur_reseau:tri', 'Onduleur réseau triphasé',
     'onduleur', False, 'onduleur_reseau'),
    ('onduleur_hybride:mono', 'Onduleur hybride monophasé (option « avec batterie »)',
     'onduleur', True, 'onduleur_hybride'),
    ('onduleur_hybride:tri', 'Onduleur hybride triphasé',
     'onduleur', False, 'onduleur_hybride'),
    ('batterie', 'Batterie en stock compatible avec un onduleur hybride',
     'option_batterie', True, 'batterie'),
    ('structure:acier', 'Structure acier', 'materiel', True, 'structure'),
    ('structure:alu', 'Structure aluminium', 'materiel', False, 'structure'),
    ('socle', 'Socle', 'materiel', True, 'socle'),
    ('cable_dc', 'Câble solaire DC (vendu au mètre)', 'cable', True, 'cable_dc'),
    ('cable_terre', 'Câble de terre AC (vendu au mètre)', 'cable', True,
     'cable_terre'),
    ('tableau', 'Tableau de protection AC/DC', 'protection', True, 'tableau'),
    ('accessoires', 'Accessoires', 'forfait', True, 'accessoires'),
    ('installation', 'Installation (pose)', 'forfait', True, 'installation'),
    ('transport', 'Transport', 'forfait', True, 'transport'),
    ('smart_meter', 'Smart Meter (onduleur Huawei)', 'accessoire', False,
     'smart_meter'),
    ('wifi_dongle', 'Clé Wifi (onduleur Huawei)', 'accessoire', False,
     'wifi_dongle'),
)

_ACTION_CREER = {'texte': "Créer l'article en Stock", 'lien': '/stock'}
_ACTION_COMPLETER = {'texte': 'Compléter la fiche en Stock', 'lien': '/stock'}


def _motif_onduleur(produit):
    """Motif d'inéligibilité d'un onduleur (ou ``None``) : prix, puissance
    lisible dans le nom (``choisir_onduleur`` ignore sinon), fiche complète."""
    if not _has_price(produit):
        return 'prix de vente non saisi'
    if not (_parse_kw(produit.nom) or 0) > 0:
        return 'puissance (kW) absente du nom'
    manquantes = onduleur_specs_manquantes(produit)
    if manquantes:
        return 'fiche incomplète : %s' % ', '.join(manquantes)
    return None


def _motif_batterie(produit, hybrides):
    """Batterie : prix, stock réel > 0 (BATHOMO), capacité lisible dans le nom,
    et tension dans la plage d'au moins un hybride éligible."""
    if not _has_price(produit):
        return 'prix de vente non saisi'
    if not _batterie_en_stock(produit):
        return 'hors stock (quantité 0)'
    if not (_parse_kwh(produit.nom) or 0) > 0:
        return 'capacité (kWh) absente du nom'
    if not hybrides:
        return "aucun onduleur hybride chiffré pour la servir"
    if not any(_batterie_compatible(
            produit, _plage_batterie_de_l_onduleur(h)) for h in hybrides):
        return "tension hors plage de tous les onduleurs hybrides"
    return None


def _motif(categorie, produit, hybrides):
    """Motif pour lequel ``produit`` ne peut PAS servir le poste ``cle``, ou
    ``None`` s'il est éligible — le filtre de vivier du composeur."""
    if categorie == 'batterie':
        return _motif_batterie(produit, hybrides)
    if categorie in ('onduleur_reseau', 'onduleur_hybride'):
        return _motif_onduleur(produit)
    if not _has_price(produit):
        return 'prix de vente non saisi'
    if categorie == 'panneau' and _parse_watt(produit.nom) is None:
        return 'puissance (Wc) absente du nom'
    if categorie in ('cable_dc', 'cable_terre') and not _est_au_metre(
            produit.nom):
        return 'conditionné en rouleau (désignation sans « au mètre »)'
    return None


def _poste(cle, libelle, groupe, obligatoire, categorie, vivier, hybrides):
    """Un poste : ``ok`` / ``a_completer`` / ``absent`` + les articles en
    cause (id, nom, motif — jamais un prix)."""
    candidats = [p for p in vivier if classer_produit(p.nom) == categorie
                 and (not cle.startswith('onduleur_')
                      or est_triphase_produit(p) == cle.endswith(':tri'))
                 and (not cle.startswith('structure:')
                      or cle.split(':')[1] in _sans_accents(p.nom))]
    motifs = [(p, _motif(categorie, p, hybrides)) for p in candidats]
    if any(m is None for _p, m in motifs):
        statut, articles = 'ok', []
    else:
        statut = 'a_completer' if motifs else 'absent'
        articles = [{'id': p.pk, 'nom': p.nom, 'motif': m} for p, m in motifs]
    return {'cle': cle, 'libelle': libelle, 'groupe': groupe,
            'obligatoire': obligatoire, 'statut': statut, 'articles': articles,
            'action': _ACTION_COMPLETER if motifs else _ACTION_CREER}


def postes_pret_devis_residentiel(company):
    """RSIZ11 — ``{pret, nb_obligatoires_manquants, postes}`` : ce qu'il manque
    au catalogue de ``company`` pour que le composeur résidentiel chiffre un
    devis aux deux options. Lecture seule, aucune clé de prix d'achat."""
    vivier = catalogue_de_la_societe(company)
    hybrides = [p for p in vivier
                if classer_produit(p.nom) == 'onduleur_hybride'
                and _motif_onduleur(p) is None]
    postes = [_poste(cle, libelle, groupe, oblig, cat, vivier, hybrides)
              for cle, libelle, groupe, oblig, cat in POSTES_RESIDENTIEL]
    manquants = sum(1 for p in postes
                    if p['obligatoire'] and p['statut'] != 'ok')
    return {'pret': manquants == 0, 'nb_obligatoires_manquants': manquants,
            'postes': postes}
