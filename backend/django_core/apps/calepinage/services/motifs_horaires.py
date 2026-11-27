"""Les motifs HORAIRES de la chaîne, sortis de ``chaine_pertes.py`` (ACAL711)
pour que ce fichier ne grossisse pas ; ``chaine_pertes`` les ré-importe sous
les mêmes noms, aucun lecteur ne change."""
from __future__ import annotations

#: CALX59 — LE MOTIF, mot pour mot, quand le fuseau du site n'est pas saisi
#: (D-CALX 15). La simulation TOURNE quand même : c'est la production qui est
#: publiée, pas le croisement horaire.
MOTIF_FUSEAU_ABSENT = (
    "fuseau du site non renseigné : aucun croisement horaire n'est possible")

#: Le motif publié quand la série ne DIT PAS dans quelle base elle est
#: indexée : la ré-indexer reviendrait à deviner de quoi on part.
MOTIF_BASE_HORAIRE_INCONNUE = (
    "la base horaire de la série météo n'est pas déclarée "
    '(« meteo.heure.base ») : sans elle, ré-indexer reviendrait à deviner '
    'de quelle heure on part')

#: Le pas MESURÉ de la série fait foi face au réglage (CALX192).
MOTIF_RESOLUTION_DIVERGENTE = (
    'Le réglage « parametres.simulation.resolution_minutes » annonce {reglage} '
    'min, mais la série météo servie est au pas de {mesure} min : c\'est le '
    'pas mesuré qui fait foi, et aucune interpolation n\'est faite pour '
    'atteindre le pas réglé.')

__all__ = ['MOTIF_FUSEAU_ABSENT', 'MOTIF_BASE_HORAIRE_INCONNUE',
           'MOTIF_RESOLUTION_DIVERGENTE']
