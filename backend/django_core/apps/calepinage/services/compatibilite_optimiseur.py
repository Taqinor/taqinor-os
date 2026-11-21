"""ACAL662 — l'onduleur retenu figure-t-il dans la liste des onduleurs
compatibles de l'optimiseur désigné ?

La liste est une donnée de FICHE (``opt_onduleurs_compatibles``, SKU saisis
par le responsable catalogue, ACAL659), jamais une règle de marque codée. Le
contrôle compare des SKU, jamais des noms.
"""
from __future__ import annotations

CODE_COMPATIBILITE = 'optimiseur_onduleur_compatible'
LIBELLE_COMPATIBILITE = ("onduleur retenu déclaré compatible par la fiche de "
                         "l'optimiseur")


def verdict_compatibilite(optimiseur_specs, nom_optimiseur, onduleur_sku):
    """``(ligne de verdict, borne non vérifiable | '')``.

    Liste vide ou absente, ou onduleur sans SKU : ``conforme`` nul et la borne
    est nommée (même forme qu'une borne de fiche non publiée)."""
    liste = (optimiseur_specs or {}).get('onduleurs_compatibles')
    skus = ([str(s).strip() for s in liste if str(s).strip()]
            if isinstance(liste, (list, tuple)) else [])
    ligne = {'code': CODE_COMPATIBILITE, 'libelle': LIBELLE_COMPATIBILITE,
             'bloquant': True}
    sku = str(onduleur_sku or '').strip()
    if skus and sku:
        conforme = sku in skus
        detail = ("l'optimiseur %s est déclaré compatible avec %s par sa fiche"
                  if conforme else "l'optimiseur %s n'est pas déclaré "
                  "compatible avec %s par sa fiche") % (nom_optimiseur, sku)
        return dict(ligne, conforme=conforme, source='fiche',
                    detail=detail), ''
    motif = ('non vérifiable : la fiche ne publie pas de liste' if not skus
             else 'non vérifiable : onduleur non désigné')
    return (dict(ligne, conforme=None, source=None, detail=motif),
            "compatibilité de l'optimiseur %s avec l'onduleur retenu : %s"
            % (nom_optimiseur, motif))
