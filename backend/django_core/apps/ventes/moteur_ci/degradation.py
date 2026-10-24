"""AMOT99 (D-ACI-18=a) — dégradation des modules selon la courbe de garantie
de LEUR fiche, année par année, pour le flux 25 ans C&I.

La fiche technique d'un module (``stock.FicheTechnique``, CAL113) publie
``degradation_annee1_pct`` (perte de la 1re année, ≈ 1 %) et
``degradation_annuelle_pct`` (perte LINÉAIRE des années suivantes,
≈ 0,4 %/an). Quand elle les publie, la production de l'année t vaut, en
fraction de celle de l'année 1 du moteur (puissance garantie au DÉBUT de
l'année, la même convention que la dégradation composée d'hier) :

* t = 1 : 1 (l'économie de l'année 1 reste celle de la valorisation) ;
* t ≥ 2 : 1 − perte an 1 − taux annuel × (t − 2).

Fiche muette (aucun taux annuel publié, ou aucun module à fiche) : le défaut
0,5 %/an (``quote_engine.pricing.PANEL_DEGRADATION``), composé comme avant —
mêmes chiffres, source « défaut, fiche muette ». Aucun autre chiffre n'est
supposé : une 1re année non publiée prend le taux annuel DE LA FICHE, dit.

Module PUR (paquet ``moteur_ci``) : il reçoit les blocs ``specs_for_produit``
déjà lus par l'appelant (façade ``apps.stock.selectors``).
"""

#: Les sources servies (texte français) et leur code stable (AMOT84) : le
#: document en imprime le libellé ``ci_code_<code>`` dans sa langue.
SOURCE_FICHE = ("fiche module : courbe de garantie de performance du "
                "fabricant")
SOURCE_FICHE_SANS_ANNEE1 = ("fiche module : 1re année non publiée, taux "
                            "annuel de la fiche appliqué dès la 1re année")
SOURCE_DEFAUT = ("défaut, fiche muette : la fiche du module ne publie pas "
                 "sa courbe de garantie")
CODES_SOURCES = {
    SOURCE_FICHE: 'degradation_fiche_module',
    SOURCE_FICHE_SANS_ANNEE1: 'degradation_fiche_sans_annee1',
    SOURCE_DEFAUT: 'degradation_defaut_fiche_muette',
}
CHAMP_ANNUEL = 'degradation_annuelle_pct'
CHAMP_ANNEE1 = 'degradation_annee1_pct'


def _pct(valeur):
    """Un pourcentage publié dans [0, 100[, ou None (vide, illisible)."""
    try:
        nombre = float(str(valeur).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return nombre if 0 <= nombre < 100 else None


def defaut_pct():
    from apps.ventes.quote_engine import pricing
    return pricing.PANEL_DEGRADATION * 100.0


def courbe_depuis_fiches(fiches):
    """La courbe retenue ``{annuelle_pct, annee1_pct, source,
    source_annee1}`` depuis les blocs ``specs_for_produit`` des MODULES du
    devis. Plusieurs courbes publiées : la plus pénalisante (prudence).
    Aucune publiée : le défaut, ``annee1_pct`` None (composé, comme avant)."""
    courbes = []
    for fiche in fiches or []:
        annuel = _pct((fiche or {}).get(CHAMP_ANNUEL))
        if annuel is None:
            continue
        annee1 = _pct(fiche.get(CHAMP_ANNEE1))
        courbes.append({
            'annuelle_pct': annuel,
            'annee1_pct': annuel if annee1 is None else annee1,
            'source': SOURCE_FICHE,
            'source_annee1': (SOURCE_FICHE_SANS_ANNEE1 if annee1 is None
                              else SOURCE_FICHE)})
    if not courbes:
        return {'annuelle_pct': defaut_pct(), 'annee1_pct': None,
                'source': SOURCE_DEFAUT, 'source_annee1': None}
    return max(courbes, key=lambda c: (c['annuelle_pct'], c['annee1_pct']))


def entrees_flux(courbe, source_historique):
    """Les entrées ``degradation_pct`` (+ ``degradation_annee1_pct`` d'une
    fiche) de ``economie.flux_de_tresorerie``. ``courbe`` None (devis aux
    règles d'origine, appelant sans devis) : le calcul d'hier, octet pour
    octet — défaut composé sous ``source_historique``."""
    if not isinstance(courbe, dict):
        return {'degradation_pct': {'valeur': defaut_pct(),
                                    'source': source_historique}}
    entrees = {'degradation_pct': {'valeur': courbe['annuelle_pct'],
                                   'source': courbe['source']}}
    if courbe.get('annee1_pct') is not None:
        entrees['degradation_annee1_pct'] = {
            'valeur': courbe['annee1_pct'], 'source': courbe['source_annee1']}
    return entrees


def _valeur(entree):
    return None if not isinstance(entree, dict) else entree.get('valeur')


def production_par_annee(bloc, production_annee1, entrees):
    """AMOT94 — la production de CHAQUE année du flux servi
    (``production_kwh`` ; ``None`` en année 0) : production de l'année 1 du
    moteur × le MÊME facteur de dégradation que ``flux_de_tresorerie``
    applique à l'économie (AMOT99 : la courbe de la fiche). Lue par le
    tableau 25 ans du document industriel (jamais recalculée par un
    gabarit)."""
    from apps.ventes.economie import facteur_degradation
    try:
        prod = float(production_annee1) if production_annee1 else None
    except (TypeError, ValueError):
        prod = None
    deg = float(_valeur(entrees.get('degradation_pct')) or 0) / 100.0
    annee1 = _valeur(entrees.get('degradation_annee1_pct'))
    annee1 = None if annee1 is None else float(annee1) / 100.0
    for ligne in bloc.get('flux') or []:
        annee = ligne.get('annee')
        ligne['production_kwh'] = (
            None if not prod or not annee else
            int(round(prod * facteur_degradation(annee, deg, annee1))))
