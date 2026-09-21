"""CAD167 — les SRM régionales, et comment on les DÉDUIT au lieu de les demander.

DÉCISION FONDATEUR DU 21/09/2026 (Q16) : « il n'y a plus désormais que SRM au
Maroc ». La liste des distributeurs devient donc les **Sociétés Régionales
Multiservices, une par région**, et la SRM d'un lead se DÉDUIT de sa ville
plutôt que d'être posée comme question. ONEE, Lydec, Redal et Amendis restent
des libellés HISTORIQUES en lecture seule, pour les fiches déjà saisies.

CE QUE LA VALEUR NE FAIT PAS : elle ne change AUCUN prix. Le barème est
NATIONAL et unique (décision déjà prise dans le code, Q7 du 20/08/2026) ; le
distributeur est un LIBELLÉ. Ce module ne contient donc aucun tarif.

ZÉRO FAIT INVENTÉ — les deux tables ci-dessous sont des faits administratifs,
pas des estimations :

* les douze régions et leurs chefs-lieux sont ceux du découpage régional de
  2015 (douze régions, en vigueur) ;
* la table ville → région ne contient QUE des rattachements administratifs non
  équivoques (chefs-lieux de région, chefs-lieux de province et grandes villes
  dont la province est publique). Une ville absente de la table ne produit
  AUCUNE déduction — jamais un « plus proche voisin » qui inventerait un
  rattachement au bord d'une limite régionale. C'est une OMISSION assumée, et
  c'est la règle « checked facts » appliquée telle quelle.

La normalisation des noms de ville réutilise celle du gazetier
(``apps.parametres.villes_maroc._normaliser``) : accents, casse et tirets y
sont déjà traités — on ne réécrit pas une seconde normalisation.
"""

#: Code de choix ``crm.Lead.distributeur`` → libellé français de la SRM.
#: Un code par région du découpage de 2015 ; le libellé porte le nom officiel
#: de la région pour qu'aucune lecture d'écran n'ait à le deviner.
SRM_PAR_REGION = {
    'srm_tanger': 'SRM Tanger-Tétouan-Al Hoceïma',
    'srm_oriental': 'SRM de l’Oriental',
    'srm_fes': 'SRM Fès-Meknès',
    'srm_rabat': 'SRM Rabat-Salé-Kénitra',
    'srm_beni_mellal': 'SRM Béni Mellal-Khénifra',
    'srm_casablanca': 'SRM Casablanca-Settat',
    'srm_marrakech': 'SRM Marrakech-Safi',
    'srm_draa': 'SRM Drâa-Tafilalet',
    'srm_souss': 'SRM Souss-Massa',
    'srm_guelmim': 'SRM Guelmim-Oued Noun',
    'srm_laayoune': 'SRM Laâyoune-Sakia El Hamra',
    'srm_dakhla': 'SRM Dakhla-Oued Ed-Dahab',
}

#: Libellés HISTORIQUES, gardés en LECTURE SEULE pour les fiches déjà saisies :
#: une valeur enregistrée ne doit jamais disparaître d'une fiche existante.
#: Aucune de ces valeurs n'est proposée à la saisie d'une nouvelle fiche.
DISTRIBUTEURS_HISTORIQUES = {
    'onee': 'ONEE (historique)',
    'lydec': 'Lydec (historique)',
    'redal': 'Redal (historique)',
    'amendis': 'Amendis (historique)',
    'autre': 'Autre (historique)',
}

#: Ville (nom usuel) → code SRM. Rattachements administratifs non équivoques
#: uniquement — une ville absente ne se déduit PAS.
VILLES_PAR_SRM = {
    'srm_tanger': (
        'tanger', 'tetouan', 'al hoceima', 'larache', 'ksar el kebir',
        'chefchaouen', 'fnideq', 'mdiq', 'asilah', 'ouezzane', 'martil',
    ),
    'srm_oriental': (
        'oujda', 'nador', 'berkane', 'taourirt', 'jerada', 'driouch',
        'guercif', 'figuig', 'saidia', 'bouarfa', 'ahfir', 'zaio',
    ),
    'srm_fes': (
        'fes', 'meknes', 'taza', 'sefrou', 'ifrane', 'el hajeb',
        'moulay yacoub', 'boulemane', 'taounate', 'azrou',
    ),
    'srm_rabat': (
        'rabat', 'sale', 'kenitra', 'temara', 'skhirat', 'khemisset',
        'sidi kacem', 'sidi slimane', 'souk el arbaa', 'tiflet',
    ),
    'srm_beni_mellal': (
        'beni mellal', 'khenifra', 'khouribga', 'fquih ben salah', 'azilal',
        'kasba tadla', 'oued zem',
    ),
    'srm_casablanca': (
        'casablanca', 'mohammedia', 'settat', 'el jadida', 'berrechid',
        'benslimane', 'sidi bennour', 'bouskoura', 'azemmour', 'nouaceur',
        'mediouna', 'had soualem', 'dar bouazza', 'bouznika',
    ),
    'srm_marrakech': (
        'marrakech', 'safi', 'essaouira', 'el kelaa des sraghna',
        'youssoufia', 'chichaoua', 'benguerir', 'rehamna',
    ),
    'srm_draa': (
        'errachidia', 'ouarzazate', 'zagora', 'tinghir', 'midelt', 'erfoud',
        'rissani',
    ),
    'srm_souss': (
        'agadir', 'inezgane', 'ait melloul', 'taroudant', 'tiznit', 'tata',
        'chtouka ait baha', 'oulad teima', 'biougra',
    ),
    'srm_guelmim': (
        'guelmim', 'tan tan', 'sidi ifni', 'assa', 'zag',
    ),
    'srm_laayoune': (
        'laayoune', 'boujdour', 'es semara', 'smara', 'tarfaya',
    ),
    'srm_dakhla': (
        'dakhla', 'aousserd',
    ),
}


def _normaliser(texte):
    """Normalisation du gazetier (accents, casse, séparateurs), réutilisée.

    Repli minimal quand le gazetier n'est pas importable (il charge un fichier
    de données) : minuscules + séparateurs ramenés à l'espace. Ne lève jamais.
    """
    try:
        from apps.parametres.villes_maroc import _normaliser as _norm
        return _norm(texte)
    except Exception:  # noqa: BLE001 — la déduction n'arrête jamais un écran
        brut = (texte or '').strip().lower()
        for separateur in ('-', '_', "'", '’', '.'):
            brut = brut.replace(separateur, ' ')
        return ' '.join(brut.split())


def _index():
    """``{ville normalisée: code SRM}`` — construit une fois, à la demande."""
    global _INDEX_VILLES
    if _INDEX_VILLES is None:
        _INDEX_VILLES = {
            _normaliser(ville): code
            for code, villes in VILLES_PAR_SRM.items()
            for ville in villes
        }
    return _INDEX_VILLES


_INDEX_VILLES = None


def srm_depuis_ville(ville):
    """Code SRM de cette ville, ou ``None`` si le rattachement n'est pas su.

    ``None`` n'est PAS un échec : c'est la règle « checked facts » — on
    n'invente pas un rattachement régional pour une ville qu'on ne connaît
    pas. L'appelant laisse alors le distributeur vide, et le barème NATIONAL
    s'applique de toute façon (la valeur ne change aucun prix)."""
    if not ville:
        return None
    return _index().get(_normaliser(ville))


def libelle_distributeur(code):
    """Libellé français d'un code (SRM ou historique), ou ``''``."""
    if not code:
        return ''
    return (SRM_PAR_REGION.get(code)
            or DISTRIBUTEURS_HISTORIQUES.get(code) or '')


def est_historique(code):
    """Ce code est-il un libellé HISTORIQUE (lecture seule) ?"""
    return bool(code) and code in DISTRIBUTEURS_HISTORIQUES
