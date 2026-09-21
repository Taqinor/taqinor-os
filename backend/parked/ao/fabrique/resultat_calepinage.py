"""AOF112 — le contrat `ResultatCalepinage` : CONSOMMÉ, jamais recalculé.

C'est la seule dépendance inter-lane forte du projet. Le moteur pur
(`core/calepinage/`) PRODUIT un plan ; la fabrique documentaire le LIT et
l'imprime. Si le schéma n'est pas gelé avant que les deux lanes avancent,
chacune invente le sien et la moitié de la fabrique se réécrit au fold.

**Ce que le contrat interdit, et pourquoi.** La fabrique n'a le droit de
DÉRIVER aucun compte. Le jour où une pièce recalcule « 314 modules » à partir
d'une surface et d'une emprise, le dossier a deux sources de vérité, elles
divergent, et c'est la pièce la plus lue qui ment (défaut réel de la session :
une note de synthèse annonçant 264 modules quand la donnée en disait 314).
Le test statique `test_aof_contrat_calepinage.TestFabriqueNeDeriveRien` rend
l'interdiction opposable : aucun module de `apps/ao/fabrique/` ne nomme le
vocabulaire de géométrie de pose, et aucun n'affecte le résultat d'un calcul à
un nom de comptage.

**Refus du sous-optimum.** `compte_retenu < compte_optimal` est REFUSÉ à
l'entrée : publier moins que l'optimum prouvé sans que le moteur l'ait décidé
signifie qu'une valeur a été recopiée à la main quelque part. Un choix
délibéré d'implanter moins (allée large, réserve de maintenance) se déclare
CÔTÉ MOTEUR — la politique de pas fait alors partie de l'entrée et l'optimum
publié est celui de cette politique. La fabrique, elle, n'arbitre rien.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

VERSION_CONTRAT = 1

#: Vocabulaire VERROUILLÉ des méthodes de preuve (miroir de
#: `core.calepinage.types.MethodePreuve` — recopié comme VALEURS, jamais
#: importé : la fabrique ne doit pas pouvoir appeler le moteur).
METHODES = {
    'dp_exact': True,
    'dp_exact_multi': True,
    'enumeration_exhaustive': True,
    'balayage_pas_fixe': False,
    'heuristique': False,
    'rangees_declarees': False,
}

#: Une méthode EXACTE peut seule prétendre à « optimum prouvé ».
METHODES_EXACTES = frozenset(m for m, exacte in METHODES.items() if exacte)


class ContratCalepinageInvalide(ValueError):
    """Le résultat présenté à la fabrique ne respecte pas le contrat gelé."""


def _entier(valeur, champ, *, mini=0, obligatoire=True):
    if valeur is None:
        if obligatoire:
            raise ContratCalepinageInvalide('%s manquant' % champ)
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise ContratCalepinageInvalide(
            '%s doit être un entier (reçu %r)' % (champ, valeur))
    if valeur < mini:
        raise ContratCalepinageInvalide(
            '%s doit être ≥ %d (reçu %d)' % (champ, mini, valeur))
    return valeur


def _reel(valeur, champ, *, mini=None, obligatoire=True):
    if valeur is None:
        if obligatoire:
            raise ContratCalepinageInvalide('%s manquant' % champ)
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ContratCalepinageInvalide(
            '%s doit être un nombre (reçu %r)' % (champ, valeur))
    valeur = float(valeur)
    if mini is not None and valeur < mini:
        raise ContratCalepinageInvalide(
            '%s doit être ≥ %s (reçu %s)' % (champ, mini, valeur))
    return valeur


@dataclass(frozen=True)
class Sensibilite:
    """Une variante DÉFAVORABLE recalculée par le moteur — pas une estimation."""

    code: str
    libelle: str
    modules: int
    delta: int
    tenu: bool = True

    def valider(self, compte_retenu):
        _entier(self.modules, 'sensibilite.%s.modules' % self.code)
        if self.modules - compte_retenu != self.delta:
            raise ContratCalepinageInvalide(
                'sensibilité %s : delta %d incohérent avec %d modules pour un '
                'retenu de %d — une valeur a été recopiée'
                % (self.code, self.delta, self.modules, compte_retenu))
        return self


@dataclass(frozen=True)
class Marche:
    """Une marche de l'échelle de décomposition (moteur `echelle.py`)."""

    code: str
    libelle: str
    modules: int
    delta: int
    attendu: Optional[int] = None


@dataclass(frozen=True)
class Marges:
    """Marges de robustesse PUBLIÉES en centimètres — jamais reconverties."""

    troncon_min_cm: float
    bande_min_cm: float
    rangee_critique: str = ''
    obstacle_critique: str = ''


@dataclass(frozen=True)
class Planche:
    """L'identité de la planche A3 qui PORTE ce plan (code + indice)."""

    code: str
    indice: str = 'A'


@dataclass(frozen=True)
class ResultatCalepinage:
    """Schéma FIGÉ du résultat de calepinage d'UN bâtiment.

    Chaque champ est une valeur PUBLIÉE par le moteur. La fabrique n'en dérive
    aucun : `kwc` n'est pas recalculé depuis `compte_retenu`, `plancher` n'est
    pas recalculé depuis les sensibilités — ce sont les positions du moteur, et
    un désaccord est un BUG du moteur, pas quelque chose que le document
    corrige en silence.
    """

    batiment: str
    compte_retenu: int
    kwc: float
    methode: str
    pas_recherche_m: float
    hash_entree: str
    version_moteur: str
    compte_optimal: Optional[int] = None
    optimal: bool = False
    rangees: Tuple[Tuple[float, str], ...] = ()
    marges: Optional[Marges] = None
    sensibilites: Tuple[Sensibilite, ...] = ()
    echelle: Tuple[Marche, ...] = ()
    planche: Optional[Planche] = None
    plancher: Optional[int] = None
    verdict: str = ''
    engageable: bool = True
    motifs_non_engageable: Tuple[str, ...] = ()
    version_contrat: int = VERSION_CONTRAT

    # ------------------------------------------------------------ validation
    def valider(self):
        """Validation STRICTE à l'entrée de la fabrique. Lève ou retourne self."""
        if not str(self.batiment).strip():
            raise ContratCalepinageInvalide('batiment manquant')
        _entier(self.compte_retenu, 'compte_retenu')
        _reel(self.kwc, 'kwc', mini=0.0)
        _reel(self.pas_recherche_m, 'pas_recherche_m', mini=0.0)

        if self.methode not in METHODES:
            raise ContratCalepinageInvalide(
                'méthode inconnue : %r (attendues : %s)'
                % (self.methode, ', '.join(sorted(METHODES))))
        if self.compte_retenu > 0 and self.kwc <= 0:
            raise ContratCalepinageInvalide(
                '%d modules pour 0 kWc : le moteur n\'a pas publié la '
                'puissance' % self.compte_retenu)

        if self.compte_optimal is not None:
            _entier(self.compte_optimal, 'compte_optimal')
            if self.compte_retenu < self.compte_optimal:
                raise ContratCalepinageInvalide(
                    'compte retenu %d INFÉRIEUR à l\'optimum prouvé %d sur le '
                    'bâtiment %s — la fabrique n\'arbitre pas un sous-optimum : '
                    'déclarer la politique de pose côté moteur pour que '
                    'l\'optimum publié soit celui de cette politique'
                    % (self.compte_retenu, self.compte_optimal, self.batiment))

        if self.optimal:
            if self.methode not in METHODES_EXACTES:
                raise ContratCalepinageInvalide(
                    '« optimum prouvé » revendiqué sur la méthode non exacte '
                    '%r — inaccessible par construction' % self.methode)
            if self.compte_optimal is None or \
                    self.compte_retenu != self.compte_optimal:
                raise ContratCalepinageInvalide(
                    '« optimum prouvé » revendiqué alors que retenu=%s et '
                    'optimum=%s' % (self.compte_retenu, self.compte_optimal))

        if not _est_hexa(self.hash_entree):
            raise ContratCalepinageInvalide(
                'hash_entree absent ou non hexadécimal : sans lui aucun '
                'artefact ne peut être déclaré périmé')
        if not str(self.version_moteur).strip():
            raise ContratCalepinageInvalide('version_moteur manquante')

        for sensibilite in self.sensibilites:
            sensibilite.valider(self.compte_retenu)
        if self.plancher is not None:
            _entier(self.plancher, 'plancher')
            pire = min([self.compte_retenu]
                       + [s.modules for s in self.sensibilites])
            if self.plancher != pire:
                raise ContratCalepinageInvalide(
                    'plancher publié %d ≠ pire cas publié %d — le moteur et la '
                    'batterie de sensibilités ne disent pas la même chose'
                    % (self.plancher, pire))
        if not self.engageable and not self.motifs_non_engageable:
            raise ContratCalepinageInvalide(
                'bâtiment %s déclaré non engageable SANS motif' % self.batiment)
        return self

    # ------------------------------------------------------------- lectures
    @property
    def libelle_preuve(self):
        """Phrase GÉNÉRÉE — jamais un texte commercial écrit à la main."""
        if self.optimal:
            return 'optimum prouvé (%d modules)' % self.compte_retenu
        borne = self.compte_optimal
        if borne is None:
            return 'meilleur plan trouvé (%d modules)' % self.compte_retenu
        return ('meilleur plan trouvé (%d modules) — borne supérieure %d'
                % (self.compte_retenu, borne))

    @property
    def code_planche(self):
        if self.planche is None:
            return ''
        return '%s%s' % (self.planche.code, self.planche.indice)

    def vers_dict(self):
        return {
            'version_contrat': self.version_contrat,
            'batiment': self.batiment,
            'compte_retenu': self.compte_retenu,
            'compte_optimal': self.compte_optimal,
            'optimal': self.optimal,
            'kwc': self.kwc,
            'methode': self.methode,
            'pas_recherche_m': self.pas_recherche_m,
            'rangees': [list(r) for r in self.rangees],
            'marges': None if self.marges is None else {
                'troncon_min_cm': self.marges.troncon_min_cm,
                'bande_min_cm': self.marges.bande_min_cm,
                'rangee_critique': self.marges.rangee_critique,
                'obstacle_critique': self.marges.obstacle_critique},
            'sensibilites': [{'code': s.code, 'libelle': s.libelle,
                              'modules': s.modules, 'delta': s.delta,
                              'tenu': s.tenu} for s in self.sensibilites],
            'echelle': [{'code': m.code, 'libelle': m.libelle,
                         'modules': m.modules, 'delta': m.delta,
                         'attendu': m.attendu} for m in self.echelle],
            'planche': None if self.planche is None else {
                'code': self.planche.code, 'indice': self.planche.indice},
            'plancher': self.plancher,
            'verdict': self.verdict,
            'engageable': self.engageable,
            'motifs_non_engageable': list(self.motifs_non_engageable),
            'hash_entree': self.hash_entree,
            'version_moteur': self.version_moteur,
        }

    @classmethod
    def depuis_dict(cls, document, *, valider=True):
        """Construit depuis un document JSON — VALIDE par défaut."""
        if not hasattr(document, 'get'):
            raise ContratCalepinageInvalide(
                'ResultatCalepinage attend un mapping (reçu %r)'
                % type(document).__name__)
        version = document.get('version_contrat', VERSION_CONTRAT)
        if version > VERSION_CONTRAT:
            raise ContratCalepinageInvalide(
                'document en contrat v%s, fabrique en v%s : la fabrique est '
                'plus ancienne que le moteur' % (version, VERSION_CONTRAT))
        marges = document.get('marges')
        planche = document.get('planche')
        resultat = cls(
            batiment=str(document.get('batiment', '')),
            compte_retenu=document.get('compte_retenu'),
            kwc=document.get('kwc'),
            methode=document.get('methode', ''),
            pas_recherche_m=document.get('pas_recherche_m'),
            hash_entree=str(document.get('hash_entree', '')),
            version_moteur=str(document.get('version_moteur', '')),
            compte_optimal=document.get('compte_optimal'),
            optimal=bool(document.get('optimal', False)),
            rangees=tuple((float(r[0]), str(r[1]))
                          for r in document.get('rangees') or ()),
            marges=None if not marges else Marges(
                troncon_min_cm=float(marges.get('troncon_min_cm', 0.0)),
                bande_min_cm=float(marges.get('bande_min_cm', 0.0)),
                rangee_critique=str(marges.get('rangee_critique', '')),
                obstacle_critique=str(marges.get('obstacle_critique', ''))),
            sensibilites=tuple(
                Sensibilite(code=str(s.get('code', '')),
                            libelle=str(s.get('libelle', '')),
                            modules=s.get('modules'), delta=s.get('delta'),
                            tenu=bool(s.get('tenu', True)))
                for s in document.get('sensibilites') or ()),
            echelle=tuple(
                Marche(code=str(m.get('code', '')),
                       libelle=str(m.get('libelle', '')),
                       modules=m.get('modules'), delta=m.get('delta'),
                       attendu=m.get('attendu'))
                for m in document.get('echelle') or ()),
            planche=None if not planche else Planche(
                code=str(planche.get('code', '')),
                indice=str(planche.get('indice', 'A'))),
            plancher=document.get('plancher'),
            verdict=str(document.get('verdict', '')),
            engageable=bool(document.get('engageable', True)),
            motifs_non_engageable=tuple(
                str(m) for m in document.get('motifs_non_engageable') or ()),
            version_contrat=version)
        return resultat.valider() if valider else resultat

    @classmethod
    def depuis_moteur(cls, resultat, *, batiment, planche=None, valider=True):
        """Adapte une sortie du moteur pur SANS l'importer (duck-typing).

        La fabrique lit des ATTRIBUTS ; elle n'appelle aucune fonction du
        moteur et ne peut donc pas relancer un calcul par inadvertance.
        """
        preuve = getattr(resultat, 'preuve', None)
        marges = getattr(resultat, 'marges', None)
        document = {
            'batiment': batiment,
            'compte_retenu': getattr(resultat, 'modules', None),
            'kwc': getattr(resultat, 'kwc', None),
            'methode': _valeur_enum(getattr(preuve, 'methode', '')),
            'pas_recherche_m': getattr(preuve, 'pas_recherche_m', None),
            'compte_optimal': getattr(preuve, 'compte_optimal', None),
            'optimal': bool(getattr(preuve, 'optimal', False)),
            'rangees': [list(r) for r in getattr(resultat, 'rangees', ())
                        or ()],
            'hash_entree': getattr(resultat, 'hash_entree', ''),
            'version_moteur': getattr(resultat, 'version_moteur', ''),
            'plancher': getattr(resultat, 'plancher_sensibilites', None),
            'engageable': bool(getattr(resultat, 'engageable', True)),
            'motifs_non_engageable': list(
                getattr(resultat, 'motifs_non_engageable', ()) or ()),
            'sensibilites': [
                {'code': _valeur_enum(getattr(s, 'code', '')),
                 'libelle': getattr(s, 'libelle', ''),
                 'modules': getattr(s, 'modules', None),
                 'delta': getattr(s, 'delta', None),
                 'tenu': bool(getattr(s, 'tenu', True))}
                for s in getattr(resultat, 'sensibilites', ()) or ()],
            'planche': planche,
        }
        if marges is not None:
            document['marges'] = {
                'troncon_min_cm': getattr(marges, 'troncon_min_cm', 0.0),
                'bande_min_cm': getattr(marges, 'bande_min_cm', 0.0),
                'rangee_critique': getattr(marges, 'rangee_critique', ''),
                'obstacle_critique': getattr(marges, 'obstacle_critique', '')}
        return cls.depuis_dict(document, valider=valider)


def _valeur_enum(valeur):
    return getattr(valeur, 'value', valeur) or ''


def _est_hexa(texte):
    texte = str(texte or '')
    if len(texte) != 64:
        return False
    try:
        int(texte, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class LotCalepinage:
    """Les résultats de TOUS les bâtiments d'un dossier, validés ensemble."""

    resultats: Tuple[ResultatCalepinage, ...] = field(default_factory=tuple)

    def valider(self):
        codes = [r.batiment for r in self.resultats]
        doublons = sorted({c for c in codes if codes.count(c) > 1})
        if doublons:
            raise ContratCalepinageInvalide(
                'deux résultats pour le(s) même(s) bâtiment(s) : %s'
                % ', '.join(doublons))
        versions = {r.version_moteur for r in self.resultats}
        if len(versions) > 1:
            raise ContratCalepinageInvalide(
                'résultats produits par des versions de moteur différentes '
                '(%s) — un dossier ne mélange pas deux moteurs'
                % ', '.join(sorted(versions)))
        for resultat in self.resultats:
            resultat.valider()
        return self

    def par_batiment(self, code):
        for resultat in self.resultats:
            if resultat.batiment == code:
                return resultat
        raise ContratCalepinageInvalide('aucun résultat pour le bâtiment %r'
                                        % code)

    def vers_dict(self):
        return [r.vers_dict() for r in self.resultats]


def valider_lot(documents):
    """Point d'entrée de la fabrique : documents bruts → lot VALIDÉ."""
    resultats = tuple(
        d if isinstance(d, ResultatCalepinage)
        else ResultatCalepinage.depuis_dict(d, valider=False)
        for d in documents or ())
    return LotCalepinage(resultats=resultats).valider()
