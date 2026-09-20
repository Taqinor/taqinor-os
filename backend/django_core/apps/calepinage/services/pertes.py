"""CAL139 — le module POSSÈDE ses pertes : chaque poste a sa valeur ET sa source.

LE CONSTAT
----------
Trois jeux de pertes se contredisaient, tous en CONSTANTES de code :
``DEFAULT_LOSS_FACTORS`` (``apps/ventes/solar_design.py`` — thermique 8 %,
salissure 3 %, câblage 2 %, onduleur 2,5 %, mismatch 2 %, indisponibilité 1 %),
la perte système totale et la perte dite « intégrée » du site public
(``apps/web/src/lib/systemLoss.ts``), et les constantes de l'écran devis
(``frontend/src/features/ventes/solar.js``). Trois chiffres pour une même
toiture, aucun affichable au client, aucun discutable avec lui.

CE QUE CE MODULE POSE
---------------------
1. **Un CATALOGUE de postes, sans aucune valeur.** La liste de référence est
   celle que PVsyst publie (IAM, salissure, irradiance, thermique, LID,
   qualité module, mismatch, vieillissement, ohmiques DC/AC, transformateur,
   auxiliaires, indisponibilité —
   https://www.pvsyst.com/help/project-design/array-and-system-losses/index.html),
   augmentée de la **consommation auxiliaire / nocturne** que la tâche exige.
   Le catalogue dit QUELS postes existent et comment les nommer en français ;
   il ne dit JAMAIS combien ils valent. Un poste hors catalogue reste admis
   (une installation peut avoir une perte qu'aucune liste ne prévoit) : il est
   simplement publié sans libellé de référence.
2. **Chaque poste porte sa SOURCE** (``pvgis``/``fiche``/``societe``/
   ``saisie``/``mesure``/``hypothese``, vocabulaire de CAL238). Un poste sans
   source n'est pas refusé — il est PUBLIÉ comme non sourcé, hachuré à
   l'écran : masquer un poste non sourcé serait pire que l'afficher.
3. **La salissure est MENSUELLE.** Un toit marocain se salit en été et se
   rince en novembre : douze valeurs, et la valeur annuelle du poste est la
   MOYENNE de ces douze mois — calculée ici, jamais saisie à côté (deux
   chiffres pour une même perte, c'est la contradiction qu'on vient de fermer).
4. **La somme est LA valeur ``loss`` envoyée à PVGIS** (CAL238,
   ``pertes_politique.politique_de_pertes``) : il n'y a qu'une addition dans
   tout le module, et elle est publiée poste par poste.
5. **AUCUN DÉFAUT.** Pas de poste ⇒ pas de politique ⇒ pas d'appel PVGIS ⇒ pas
   de production publiée.

Ce module ne calcule AUCUNE perte physique : il les range, les valide, les
persiste et les additionne. Le poste thermique CALCULÉ vient de CAL140
(``services/thermique.py``), le gain bifacial de CAL141.
"""
from __future__ import annotations

from .pertes_politique import (
    SOURCES_ADMISES, PertesInvalides, politique_de_pertes,
)

__all__ = [
    'CATALOGUE', 'CATALOGUE_PAR_POSTE', 'MOIS_LIBELLES', 'SOURCES_ADMISES',
    'PertesInvalides', 'enregistrer_pertes', 'moyenne_mensuelle',
    'politique_du_calepinage', 'postes_du_calepinage', 'valider_postes',
]

#: Le catalogue de RÉFÉRENCE — des noms et des libellés, AUCUNE valeur.
#: ``reference`` nomme la source doctrinale du poste pour que l'écran puisse
#: la citer ; ``mensuel`` dit si le poste se saisit mois par mois.
CATALOGUE = (
    {'poste': 'iam', 'libelle': "Incidence (IAM)",
     'reference': 'PVsyst — array and system losses', 'mensuel': False},
    {'poste': 'salissure', 'libelle': 'Salissure',
     'reference': 'PVsyst — soiling loss', 'mensuel': True},
    {'poste': 'irradiance', 'libelle': 'Niveau d’irradiance',
     'reference': 'PVsyst — irradiance level loss', 'mensuel': False},
    {'poste': 'thermique', 'libelle': 'Échauffement des modules',
     'reference': 'PVsyst — thermal loss (calculé par CAL140)',
     'mensuel': False},
    {'poste': 'lid', 'libelle': 'LID (première exposition)',
     'reference': 'PVsyst — light induced degradation', 'mensuel': False},
    {'poste': 'qualite_module', 'libelle': 'Qualité module',
     'reference': 'PVsyst — module quality loss', 'mensuel': False},
    {'poste': 'mismatch', 'libelle': 'Dispersion (mismatch)',
     'reference': 'PVsyst — module mismatch loss', 'mensuel': False},
    {'poste': 'vieillissement', 'libelle': 'Vieillissement',
     'reference': 'PVsyst — ageing / degradation', 'mensuel': False},
    {'poste': 'ohmique_dc', 'libelle': 'Pertes ohmiques DC',
     'reference': 'PVsyst — DC wiring loss', 'mensuel': False},
    {'poste': 'ohmique_ac', 'libelle': 'Pertes ohmiques AC',
     'reference': 'PVsyst — AC wiring loss', 'mensuel': False},
    {'poste': 'onduleur', 'libelle': 'Rendement onduleur',
     'reference': 'PVsyst — inverter loss', 'mensuel': False},
    {'poste': 'transformateur', 'libelle': 'Transformateur',
     'reference': 'PVsyst — transformer loss', 'mensuel': False},
    {'poste': 'auxiliaires', 'libelle': 'Auxiliaires',
     'reference': 'PVsyst — auxiliaries (fans, other)', 'mensuel': False},
    {'poste': 'auxiliaires_nocturnes',
     'libelle': 'Consommation auxiliaire / nocturne',
     'reference': "CAL139 — onduleur la nuit et auxiliaires permanents : "
                  "une énergie réellement soutirée, jamais un arrondi",
     'mensuel': False},
    {'poste': 'indisponibilite', 'libelle': 'Indisponibilité',
     'reference': 'PVsyst — system unavailability', 'mensuel': False},
)

CATALOGUE_PAR_POSTE = {entree['poste']: entree for entree in CATALOGUE}

MOIS_LIBELLES = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre',
                 'décembre')


def _pourcentage(valeur, *, champ):
    """Un pourcentage lisible et borné, ou un refus NOMMANT le champ."""
    if isinstance(valeur, bool) or valeur is None or valeur == '':
        raise PertesInvalides(
            f'Le poste de perte « {champ} » doit porter un pourcentage '
            'chiffré : un poste sans valeur ne peut pas entrer dans la somme '
            'envoyée à PVGIS.', champ=champ)
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
            f'Le poste de perte « {champ} » doit être un pourcentage entre 0 '
            f'et 100 (reçu : {nombre}).', champ=champ)
    return nombre


def moyenne_mensuelle(mensuel, *, champ):
    """La valeur ANNUELLE d'un poste mensuel : la moyenne de ses douze mois.

    Douze valeurs sont exigées — onze mois et un trou, ce serait une moyenne
    calculée sur une année incomplète présentée comme une année.
    """
    if not isinstance(mensuel, (list, tuple)):
        raise PertesInvalides(
            f'Les valeurs mensuelles du poste « {champ} » se donnent en liste '
            f'de 12 nombres (reçu : {type(mensuel).__name__}).',
            champ=f'{champ}.mensuel')
    if len(mensuel) != 12:
        raise PertesInvalides(
            f'Le poste mensuel « {champ} » attend 12 valeurs, une par mois '
            f'(reçu : {len(mensuel)}). Une moyenne calculée sur une année '
            'incomplète se lirait comme une année complète.',
            champ=f'{champ}.mensuel')
    valeurs = [
        _pourcentage(valeur, champ=f'{champ} ({MOIS_LIBELLES[rang]})')
        for rang, valeur in enumerate(mensuel)
    ]
    return sum(valeurs) / 12.0, valeurs


def valider_postes(postes):
    """Valide et NORMALISE les postes saisis — la forme qui sera persistée.

    Returns:
        la liste ``[{poste, libelle, pct, source, reference, mensuel}]``,
        ``mensuel`` valant ``None`` pour un poste annuel.

    Raises:
        PertesInvalides: forme, valeur, doublon ou source invalides — toujours
            en français et en NOMMANT le poste fautif.
    """
    if isinstance(postes, dict):
        raise PertesInvalides(
            'Les postes de pertes se donnent en LISTE ordonnée '
            '(« pertes: [{poste, libelle, pct, source}, …] »).',
            champ='pertes')
    if postes is None:
        postes = []
    if not isinstance(postes, (list, tuple)):
        raise PertesInvalides(
            'Les postes de pertes se donnent en liste ordonnée '
            f'(reçu : {type(postes).__name__}).', champ='pertes')

    normalises = []
    vus = set()
    for rang, brut in enumerate(postes):
        if not isinstance(brut, dict):
            raise PertesInvalides(
                f'Le poste de perte n°{rang + 1} doit être un objet '
                f'(reçu : {type(brut).__name__}).', champ=f'pertes[{rang}]')
        nom = str(brut.get('poste') or '').strip()
        if not nom:
            raise PertesInvalides(
                f'Le poste de perte n°{rang + 1} n’a pas de nom : chaque '
                'perte est nommée pour pouvoir être affichée et discutée.',
                champ=f'pertes[{rang}].poste')
        if nom in vus:
            raise PertesInvalides(
                f'Le poste de perte « {nom} » apparaît deux fois : la somme '
                'passée à PVGIS le compterait deux fois.', champ=nom)
        vus.add(nom)

        source = brut.get('source')
        if source is not None and str(source).strip() != '':
            source = str(source).strip().lower()
            if source not in SOURCES_ADMISES:
                raise PertesInvalides(
                    f'Source inconnue pour le poste « {nom} » : '
                    f'« {source} ». Sources admises : '
                    f'{", ".join(SOURCES_ADMISES)} (ou aucune source, et le '
                    'poste est alors publié comme NON sourcé).', champ=nom)
        else:
            source = None

        reference_catalogue = CATALOGUE_PAR_POSTE.get(nom, {})
        mensuel = brut.get('mensuel')
        if mensuel is not None:
            pct, mensuel = moyenne_mensuelle(mensuel, champ=nom)
        else:
            pct = _pourcentage(brut.get('pct'), champ=nom)

        normalises.append({
            'poste': nom,
            'libelle': (str(brut.get('libelle') or '').strip()
                        or reference_catalogue.get('libelle', '')),
            'pct': pct,
            'source': source,
            'reference': (str(brut.get('reference') or '').strip()
                          or reference_catalogue.get('reference', '')),
            'mensuel': mensuel,
        })
    return normalises


def postes_du_calepinage(calepinage):
    """Les postes PERSISTÉS du calepinage, normalisés — jamais complétés.

    Un calepinage sans poste rend une liste VIDE : le module n'ajoute aucun
    poste « manquant » avec une valeur de référence, c'est précisément ce que
    CAL139 supprime.
    """
    return valider_postes(getattr(calepinage, 'pertes', None) or [])


def enregistrer_pertes(calepinage, postes):
    """Valide puis PERSISTE les postes de pertes d'un calepinage.

    La société n'est jamais touchée ici : le calepinage est déjà borné par le
    queryset de son viewset. Seul le champ ``pertes`` est écrit (``update_fields``),
    pour qu'un enregistrement de pertes ne réécrive jamais une conception.
    """
    normalises = valider_postes(postes)
    calepinage.pertes = normalises
    calepinage.save(update_fields=['pertes', 'updated_at'])
    return normalises


def politique_du_calepinage(calepinage):
    """La ``PolitiquePertes`` (CAL238) construite sur les postes PERSISTÉS.

    C'est le SEUL chemin par lequel une simulation du module obtient sa valeur
    ``loss`` : il n'y a donc qu'une addition, et elle est publiée.

    Raises:
        PertesInvalides: aucun poste renseigné (le refus nomme le champ
            ``pertes``) — jamais une perte de repli.
    """
    return politique_de_pertes(postes_du_calepinage(calepinage))
