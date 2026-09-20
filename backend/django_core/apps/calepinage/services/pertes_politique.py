"""CAL238 — LA politique de pertes du module : ``loss`` est une ENTRÉE d'appel.

LE CONSTAT QUI JUSTIFIE CE FICHIER
----------------------------------
Le site public additionne aujourd'hui deux mondes — une « perte intégrée
PVGIS » et une « perte système totale », toutes deux en constantes dans
``apps/web/src/lib/systemLoss.ts`` (lignes 31 et 34), avec un facteur de
rattrapage entre les deux. Ces deux noms sont d'ailleurs INTERDITS de séjour
dans ce module : le test de surface de CAL238 les refuse. Or ``loss`` n'est
PAS une propriété de PVGIS : c'est un paramètre que l'APPELANT passe à
``PVcalc`` / ``seriescalc`` / ``TMY``. Les 14 % ne sont que le défaut de
l'INTERFACE WEB de PVGIS, pas une perte cachée dans la donnée.

LA POLITIQUE, ÉCRITE UNE FOIS POUR TOUT LE MODULE
--------------------------------------------------
1. Le module ne connaît qu'UNE addition : la somme des postes de pertes qu'on
   lui donne (CAL139 les possède et les rend éditables ; ici ils ARRIVENT en
   entrée, ce module ne les invente pas).
2. Cette somme est la valeur ``loss`` passée à PVGIS — telle quelle, à la
   virgule près.
3. La valeur passée est PUBLIÉE à côté du résultat, avec le détail poste par
   poste et la SOURCE de chaque poste.
4. Aucun poste ne peut donc être appliqué deux fois : il n'y a qu'une seule
   addition, et elle est visible.
5. AUCUN DÉFAUT. Pas de poste ⇒ pas de politique ⇒ pas d'appel PVGIS ⇒ pas de
   production publiée. Un 14 % ou un 20 % « au cas où » serait exactement le
   chiffre inventé que la règle fondateur interdit.

CE QUE CE MODULE NE FAIT PAS
----------------------------
Il ne persiste rien (CAL139 posera le modèle et sa migration), ne lit aucune
autre app, et ne connaît ni catalogue de postes imposé ni valeur par défaut :
il VALIDE, ADDITIONNE et PUBLIE.
"""
from __future__ import annotations

__all__ = [
    'PertesInvalides', 'PolitiquePertes', 'SOURCES_ADMISES',
    'politique_de_pertes',
]

#: Les provenances ADMISES d'un poste de perte — union de ce que nomment
#: l'échantillon de contrat ``contract_samples/calepinage_resultat.json``
#: (``fiche``, ``saisie``, ``pvgis``, ``mesure``, ``hypothese``) et la tâche
#: CAL139 (``pvgis``/``fiche``/``societe``/``saisie``). ``None`` reste admis et
#: veut dire « poste NON sourcé » : l'écran le hachure et le nomme, il ne
#: disparaît jamais (discipline du contrat).
SOURCES_ADMISES = ('pvgis', 'fiche', 'societe', 'saisie', 'mesure',
                   'hypothese')

#: Précision d'écriture de la valeur envoyée à PVGIS. Une seule décimale de
#: plus que ce que la chaîne de requête peut porter et la valeur publiée ne
#: serait plus EXACTEMENT celle qui est partie ; on fige donc le format ici,
#: et la valeur publiée est relue de cette chaîne (pas l'inverse).
DECIMALES_POURCENT = 3


class PertesInvalides(ValueError):
    """Un jeu de postes de pertes refusé, avec un message FRANÇAIS.

    ``champ`` nomme le poste (ou la clé) fautif pour que l'écran pointe LE
    champ concerné au lieu d'un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


class PolitiquePertes:
    """Le résultat de la politique : des postes publiés et UNE valeur ``loss``.

    ``valeur_loss`` est la CHAÎNE réellement placée dans la requête PVGIS ;
    ``total_pct`` est cette même chaîne relue en nombre. Les deux ne peuvent
    donc pas diverger — c'est ce que vérifie le test de CAL238 sur l'URL.
    """

    __slots__ = ('postes', 'valeur_loss', 'total_pct')

    def __init__(self, postes, valeur_loss):
        self.postes = tuple(postes)
        self.valeur_loss = valeur_loss
        self.total_pct = float(valeur_loss)

    def __repr__(self):  # pragma: no cover - confort de débogage
        return (f'<PolitiquePertes loss={self.valeur_loss} '
                f'postes={len(self.postes)}>')

    @property
    def postes_non_sources(self):
        """Les noms des postes sans source — nommés, jamais masqués."""
        return tuple(p['poste'] for p in self.postes if p['source'] is None)

    def publication(self):
        """Le bloc à publier À CÔTÉ du résultat (forme du contrat CAL244).

        ``pertes`` reprend poste/libellé/pct/source ; ``loss_passee_pct`` est
        la valeur réellement partie dans la requête.
        """
        return {
            'loss_passee_pct': self.total_pct,
            'pertes': [dict(poste) for poste in self.postes],
            'postes_non_sources': list(self.postes_non_sources),
            'commentaire': (
                'CAL238 — « loss » est une ENTRÉE d\'appel PVGIS : la valeur '
                'passée est la somme explicite des postes ci-dessus, jamais '
                'un défaut caché.'),
        }


def _nombre(valeur, *, champ):
    """Un pourcentage lisible, ou un refus NOMMANT le champ."""
    if isinstance(valeur, bool) or valeur is None:
        raise PertesInvalides(
            f'Le poste de perte « {champ} » doit porter un pourcentage '
            'chiffré.', champ=champ)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise PertesInvalides(
            f'Le pourcentage du poste de perte « {champ} » est illisible '
            f'(reçu : {valeur!r}).', champ=champ)
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        raise PertesInvalides(
            f'Le pourcentage du poste de perte « {champ} » est illisible '
            f'(reçu : {valeur!r}).', champ=champ)
    if nombre < 0 or nombre >= 100:
        raise PertesInvalides(
            f'Le poste de perte « {champ} » doit être un pourcentage entre '
            f'0 et 100 (reçu : {nombre}).', champ=champ)
    return nombre


def politique_de_pertes(postes):
    """Valide les postes, les additionne UNE fois, et rend la politique.

    Args:
        postes: une liste de dicts ``{poste, libelle, pct, source}``. Le
            module ne les invente pas : ils viennent des réglages de la
            société ou de la saisie du calepinage (CAL139).

    Returns:
        ``PolitiquePertes`` — postes publiés + la valeur ``loss`` à passer.

    Raises:
        PertesInvalides: liste vide (aucun défaut caché n'est fabriqué),
            poste sans nom, pourcentage illisible ou hors bornes, source
            inconnue, doublon de poste, somme ≥ 100 %.
    """
    if not postes:
        raise PertesInvalides(
            'Aucun poste de perte n\'a été fourni : le module passe TOUJOURS '
            'à PVGIS la somme explicite de ses postes et ne suppose jamais '
            'une perte par défaut. Renseignez les pertes avant de lancer une '
            'simulation.', champ='pertes')
    if isinstance(postes, dict):
        raise PertesInvalides(
            'Les postes de pertes se donnent en LISTE ordonnée '
            '(« pertes: [{poste, libelle, pct, source}, …] »).',
            champ='pertes')

    publies = []
    vus = set()
    total = 0.0
    for rang, brut in enumerate(postes):
        if not isinstance(brut, dict):
            raise PertesInvalides(
                f'Le poste de perte n°{rang + 1} doit être un objet '
                f'(reçu : {type(brut).__name__}).', champ=f'pertes[{rang}]')
        nom = str(brut.get('poste') or '').strip()
        if not nom:
            raise PertesInvalides(
                f'Le poste de perte n°{rang + 1} n\'a pas de nom : chaque '
                'perte est nommée pour pouvoir être affichée et discutée.',
                champ=f'pertes[{rang}].poste')
        if nom in vus:
            raise PertesInvalides(
                f'Le poste de perte « {nom} » apparaît deux fois : la somme '
                'passée à PVGIS le compterait deux fois.', champ=nom)
        vus.add(nom)

        source = brut.get('source')
        if source is not None:
            source = str(source).strip().lower()
            if source not in SOURCES_ADMISES:
                raise PertesInvalides(
                    f'Source inconnue pour le poste « {nom} » : '
                    f'« {source} ». Sources admises : '
                    f'{", ".join(SOURCES_ADMISES)} (ou aucune source, et le '
                    'poste est alors publié comme non sourcé).',
                    champ=nom)

        pct = _nombre(brut.get('pct'), champ=nom)
        total += pct
        publies.append({
            'poste': nom,
            'libelle': str(brut.get('libelle') or '').strip(),
            'pct': pct,
            'source': source,
        })

    if total >= 100:
        raise PertesInvalides(
            f'La somme des postes de pertes atteint {round(total, DECIMALES_POURCENT)} % : '
            'au-delà de 100 % il ne reste plus rien à produire. Corrigez les '
            'postes avant de simuler.', champ='pertes')

    # La valeur ÉCRITE fait foi : on la formate une fois, et le total publié
    # est cette chaîne relue — jamais un arrondi parallèle qui divergerait de
    # ce qui est réellement parti dans la requête.
    valeur_loss = f'{total:.{DECIMALES_POURCENT}f}'.rstrip('0').rstrip('.')
    if not valeur_loss:
        valeur_loss = '0'
    return PolitiquePertes(publies, valeur_loss)
