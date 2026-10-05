"""CIQ428 — indicateur INTERNE « audit énergétique obligatoire probable ».

Loi 47-09 (efficacité énergétique) et décret 2-17-746 : un établissement dont
la consommation d'énergie ACHETÉE dépasse un seuil annuel doit faire réaliser
un audit énergétique. Cet indicateur est calculé sur la seule ÉLECTRICITÉ
DÉCLARÉE du lead, vu par le vendeur seulement — jamais sur une sortie client
(PDF, /proposition, message, questionnaire), jamais une amende ni une
échéance, jamais une promesse (Q22), aucune question ajoutée à l'appel
(D-CIQ-7, CAD175).

Source primaire, relue par deux vérificateurs le 03/10/2026 : ministère de
l'Énergie, « Audit énergétique obligatoire — recueil juridique »
(``SOURCE_URL``). Les carburants ne sont PAS comptés (aucun coefficient
litre → tep sourcé) : l'électricité seule n'est qu'une BORNE BASSE. Le statut
vaut donc ``seuil_atteint_electricite_seule`` ou ``non_determine``, jamais
« non soumis ».

Module PUR : aucune requête, aucun import de modèle.
"""

#: Décret 2-17-746, art. 2 — seuil annuel (tep) pour l'INDUSTRIE.
SEUIL_TEP_INDUSTRIE = 1500
#: Décret 2-17-746, art. 2 — seuil annuel (tep) pour le TERTIAIRE (art. 1 :
#: tourisme, santé, éducation, enseignement, commerce et services — les 9
#: catégories commerciales en relèvent).
SEUIL_TEP_TERTIAIRE = 500
#: Décret 2-17-746, annexe — électricité : 1 GWh = 86 tep.
TEP_PAR_GWH_ELECTRICITE = 86

SOURCE_URL = ('https://www.mem.gov.ma/Lists/Lst_Textes_Reglementaires/'
              'Attachments/201/AEO-RecueilJuridique201120.pdf')
SOURCE_RELEVEE_LE = '2026-10-03'
SOURCE = {
    'texte': 'Loi 47-09 ; décret 2-17-746 (art. 1, art. 2 et annexe)',
    'url': SOURCE_URL,
    'releve_le': SOURCE_RELEVEE_LE,
}

#: Segment du lead → (secteur, seuil tep).
_SECTEURS = {
    'industriel': ('industrie', SEUIL_TEP_INDUSTRIE),
    'commercial': ('tertiaire', SEUIL_TEP_TERTIAIRE),
}

STATUT_ATTEINT = 'seuil_atteint_electricite_seule'
STATUT_NON_DETERMINE = 'non_determine'

MOTIF_NON_DETERMINE = ("l'électricité déclarée n'atteint pas le seuil ; les "
                       "carburants ne sont pas comptés")
MOTIF_SANS_KWH = ('aucune consommation en kWh déclarée (une facture en '
                  'dirhams ou une tranche ne sont jamais converties)')
MOTIF_RELEVE_INCOMPLET = ('relevé de moins de 12 mois et aucun kWh mensuel '
                          'déclaré')


def _nombre(valeur):
    if valeur is None or valeur == '' or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre >= 0 else None


def conso_annuelle_declaree(entrees_ci):
    """La consommation annuelle en kWh lue dans ``entrees_ci`` (CIQ405) :
    ``(kwh, provenance, motif)``.

    * ``releve_conso`` sur 12 mois → leur somme ;
    * sinon le kWh mensuel déclaré (``conso_mensuelle_kwh`` ou ``bill_kwh``)
      × 12 ;
    * JAMAIS une conso inversée depuis des dirhams (``facture_hiver``) ni une
      tranche Meta : ``(None, None, motif)``.
    """
    entrees = (entrees_ci or {}).get('entrees') or []
    par_colonne = {e.get('colonne'): e for e in entrees}
    releve = par_colonne.get('releve_conso')
    if releve is not None:
        mois = [m for m in (releve.get('valeur') or [])
                if _nombre(m.get('kwh')) is not None]
        if len(mois) >= 12:
            total = sum(_nombre(m['kwh']) for m in mois[-12:])
            return total, releve.get('provenance'), None
        return None, None, MOTIF_RELEVE_INCOMPLET
    for colonne in ('conso_mensuelle_kwh', 'bill_kwh'):
        entree = par_colonne.get(colonne)
        if entree is not None and _nombre(entree.get('valeur')) is not None:
            return (_nombre(entree['valeur']) * 12, entree.get('provenance'),
                    None)
    return None, None, MOTIF_SANS_KWH


def indicateur_audit_47_09(conso_annuelle_kwh, provenance, segment, *,
                           motif=None):
    """``{statut, tep_electricite, seuil_tep, secteur, motif, provenance,
    source}`` — ou ``None`` hors commercial / industriel.

    Sans kWh déclarés : ``statut`` ``None`` et le ``motif`` qui le dit."""
    secteur = _SECTEURS.get(segment)
    if secteur is None:
        return None
    nom_secteur, seuil = secteur
    base = {'seuil_tep': seuil, 'secteur': nom_secteur, 'source': SOURCE,
            'provenance': provenance}
    if conso_annuelle_kwh is None:
        return {**base, 'statut': None, 'tep_electricite': None,
                'motif': motif or MOTIF_SANS_KWH}
    tep = round(conso_annuelle_kwh / 1_000_000 * TEP_PAR_GWH_ELECTRICITE, 1)
    if tep >= seuil:
        return {**base, 'statut': STATUT_ATTEINT, 'tep_electricite': tep,
                'motif': (f"l'électricité déclarée seule atteint {tep:g} tep "
                          f'pour un seuil de {seuil} tep')}
    return {**base, 'statut': STATUT_NON_DETERMINE, 'tep_electricite': tep,
            'motif': MOTIF_NON_DETERMINE}


def indicateur_du_lead(segment, entrees_ci):
    """L'indicateur d'un lead, depuis ses ``entrees_ci`` (CIQ405)."""
    if segment not in _SECTEURS:
        return None
    kwh, provenance, motif = conso_annuelle_declaree(entrees_ci)
    return indicateur_audit_47_09(kwh, provenance, segment, motif=motif)
