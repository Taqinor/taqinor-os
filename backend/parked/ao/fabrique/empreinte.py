"""AOF111 — empreinte canonique du contexte de dossier + péremption d'artefact.

Patron : `apps.ventes.services.layout_hash` (QJ17) — une **liste EXPLICITE de
clés signifiantes**, hachée en JSON canonique (clés triées, séparateurs
compacts). Ce qui n'est pas dans la liste ne peut pas faire bouger l'empreinte :
l'horodatage de génération, l'opérateur ou un compteur de rendu ne périment
donc rien. Le pendant du choix est un TRIPWIRE (`cles_hors_perimetre`) qui
signale toute section de contexte non classée, pour qu'une section ajoutée plus
tard soit versée sciemment dans l'un des deux camps et jamais oubliée en
silence.

Canonisation — les trois pièges qui font diverger deux postes :

* `Decimal` : sérialisé en **chaîne**, jamais en `float` (0.1 + 0.2 …). Un
  montant est un `Decimal` d'un bout à l'autre de la fabrique.
* `float` : arrondi à 1e-6 (les longueurs sont déjà arrondies au millimètre par
  `core.calepinage.serialisation`).
* dates : format ISO. Le poste est Windows, la CI et la prod sont Linux : la
  même entrée doit donner le même hexadécimal partout.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal
from types import MappingProxyType
from typing import Optional

VERSION_EMPREINTE = 1

#: Sections du contexte qui FONT le document. Une divergence sur l'une d'elles
#: périme tout artefact rendu depuis l'ancienne valeur.
CLES_SIGNIFIANTES = (
    'identite',
    'acheteur',
    'marche',
    'batiments',
    'calepinage',
    'equipements',
    'montants',
    'clauses',
    'dates',
    'engagements',
    'productible',
    'derivations',
)

#: Sections délibérément HORS empreinte : elles décrivent la fabrication, pas
#: le contenu. Les lister explicitement est ce qui rend le tripwire utile.
CLES_VOLATILES = (
    'version_contexte',
    'genere_le',
    'genere_par',
    'trace',
    'empreinte',
)


class ArtefactPerime(RuntimeError):
    """Un artefact est relu alors que son contexte a bougé depuis son rendu."""


def canoniser(valeur, _profondeur=0):
    """Rend une valeur DÉTERMINISTE et sérialisable en JSON.

    `Decimal` → chaîne (exactitude au centime), `float` → arrondi 1e-6,
    date/heure → ISO, mapping → dict à clés triées (chaînes), séquence → liste.
    """
    if _profondeur > 32:
        raise ValueError('contexte trop profond (cycle ?)')
    if valeur is None or isinstance(valeur, (bool, int, str)):
        return valeur
    if isinstance(valeur, Decimal):
        # str(Decimal) conserve l'exposant ; on normalise pour que
        # Decimal('2600') et Decimal('2600.00') donnent la MÊME empreinte.
        return _decimal_canonique(valeur)
    if isinstance(valeur, float):
        return round(valeur, 6)
    if isinstance(valeur, (datetime, date, time)):
        return valeur.isoformat()
    if isinstance(valeur, (MappingProxyType, dict)):
        return {str(cle): canoniser(val, _profondeur + 1)
                for cle, val in sorted(valeur.items(), key=lambda kv: str(kv[0]))}
    if isinstance(valeur, (list, tuple, set, frozenset)):
        items = sorted(valeur, key=repr) if isinstance(
            valeur, (set, frozenset)) else valeur
        return [canoniser(v, _profondeur + 1) for v in items]
    if hasattr(valeur, 'vers_dict'):
        return canoniser(valeur.vers_dict(), _profondeur + 1)
    return str(valeur)


def _decimal_canonique(valeur):
    """`Decimal` → chaîne stable ('2600', '2600.50'), zéro négatif neutralisé."""
    normalise = valeur.normalize()
    if normalise == 0:
        return '0'
    signe, chiffres, exposant = normalise.as_tuple()
    if isinstance(exposant, int) and exposant > 0:
        # normalize() écrit 2.6E+3 : on repasse en notation positionnelle.
        normalise = normalise.quantize(Decimal(1))
    return format(normalise, 'f')


def empreinte_document(document, cles=CLES_SIGNIFIANTES):
    """SHA-256 hexadécimal des SEULES clés signifiantes de `document`."""
    if not hasattr(document, 'items'):
        raise TypeError('empreinte_document attend un mapping')
    retenu = {cle: canoniser(document[cle]) for cle in cles if cle in document}
    blob = json.dumps(retenu, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True)
    return hashlib.sha256(blob.encode('ascii')).hexdigest()


def empreinte_contexte(contexte):
    """Empreinte d'un contexte de dossier (`contexte.construire_contexte`)."""
    return empreinte_document(contexte, CLES_SIGNIFIANTES)


def cles_hors_perimetre(contexte):
    """TRIPWIRE : sections du contexte classées ni signifiantes ni volatiles.

    Retourne un tuple trié. Un test le veut VIDE : une section ajoutée sans
    décision explicite serait sinon exclue de l'empreinte en silence — donc
    modifiable sans jamais périmer une seule pièce.
    """
    connues = set(CLES_SIGNIFIANTES) | set(CLES_VOLATILES)
    return tuple(sorted(cle for cle in contexte if cle not in connues))


@dataclass(frozen=True)
class Artefact:
    """Une pièce RENDUE et l'empreinte du contexte qui l'a produite.

    `empreinte_source` n'est pas décoratif : c'est le seul moyen mécanique de
    savoir qu'un PDF posé sur un disque partagé décrit encore le dossier. Le
    défaut réel de la session FRDISI — une note de synthèse annonçant 264
    modules quand la donnée en disait 314 — est exactement ce que ce champ
    rend impossible à ignorer.
    """

    code: str
    empreinte_source: str
    version_empreinte: int = VERSION_EMPREINTE
    produit_le: Optional[datetime] = None
    format: str = ''
    visibilite: str = 'client'
    cle_stockage: str = ''

    def est_perime(self, contexte_ou_empreinte):
        """`True` dès que l'empreinte courante diverge de celle du rendu."""
        return self.empreinte_courante(contexte_ou_empreinte) != \
            self.empreinte_source

    @staticmethod
    def empreinte_courante(contexte_ou_empreinte):
        if isinstance(contexte_ou_empreinte, str):
            return contexte_ou_empreinte
        return empreinte_contexte(contexte_ou_empreinte)

    def verifier(self, contexte_ou_empreinte):
        """Lève `ArtefactPerime` si la pièce ne décrit plus le dossier."""
        if self.est_perime(contexte_ou_empreinte):
            raise ArtefactPerime(
                "l'artefact %r a été rendu sur l'empreinte %s ; le dossier est "
                "aujourd'hui en %s — le régénérer avant de le déposer"
                % (self.code, self.empreinte_source[:12],
                   self.empreinte_courante(contexte_ou_empreinte)[:12]))
        return self

    def rafraichi(self, contexte, produit_le=None):
        """Copie estampillée de l'empreinte COURANTE (après régénération)."""
        return replace(self, empreinte_source=empreinte_contexte(contexte),
                       produit_le=produit_le or self.produit_le)

    def vers_dict(self):
        return {'code': self.code, 'empreinte_source': self.empreinte_source,
                'version_empreinte': self.version_empreinte,
                'produit_le': self.produit_le.isoformat()
                if self.produit_le else None,
                'format': self.format, 'visibilite': self.visibilite,
                'cle_stockage': self.cle_stockage}


def estampiller(contexte, code, *, format='', visibilite='client',
                produit_le=None, cle_stockage=''):
    """Crée l'`Artefact` d'une pièce qu'on vient de rendre depuis `contexte`."""
    return Artefact(code=code, empreinte_source=empreinte_contexte(contexte),
                    format=format, visibilite=visibilite,
                    produit_le=produit_le, cle_stockage=cle_stockage)


def artefacts_perimes(artefacts, contexte):
    """Les artefacts d'un dossier qui ne décrivent plus le contexte courant."""
    courante = empreinte_contexte(contexte)
    return tuple(a for a in artefacts if a.empreinte_source != courante)


def sections_divergentes(contexte_a, contexte_b):
    """Les sections signifiantes qui diffèrent entre deux contextes.

    Sert au message d'explication (« périmé PARCE QUE les montants ont
    changé ») : un bandeau rouge sans motif s'apprend à ignorer.
    """
    divergentes = []
    for cle in CLES_SIGNIFIANTES:
        if canoniser(contexte_a.get(cle)) != canoniser(contexte_b.get(cle)):
            divergentes.append(cle)
    return tuple(divergentes)
