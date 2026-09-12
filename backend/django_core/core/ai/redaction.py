"""NTAI3 — Masquage des données personnelles avant envoi à un LLM externe.

Le « Trust Layer » de la maison : ce qui PART chez un fournisseur tiers est
masqué ; ce qui est STOCKÉ chez nous ne change jamais. Un numéro de CIN, un
RIB, un téléphone ou un e-mail sont remplacés par un JETON stable
(``[PII_CIN_1]``) avant l'appel, et le jeton est re-substitué dans la réponse
— l'utilisateur lit un texte complet, le fournisseur n'a jamais vu la donnée.

TROIS GARANTIES :

  * **Réversible et fidèle** — ``unredact(redact_pii(t)[0], mapping) == t``
    tant que le texte n'a pas été réécrit entre-temps.
  * **Jamais destructif** — aucune écriture, aucune donnée modifiée en base :
    la substitution ne vit que dans la chaîne transmise.
  * **Débrayable** — drapeau ``settings.AI_PII_REDACTION``. Éteint, le chemin
    est octet-identique à l'existant (aucune regex n'est même compilée à
    l'exécution du prompt).

Module de FONDATION : aucune dépendance, aucun import d'app métier.
"""
from __future__ import annotations

import re

from django.conf import settings

#: Catégories masquées, dans l'ORDRE d'application. L'ordre compte : l'e-mail
#: est masqué avant le téléphone (un e-mail peut contenir une suite de
#: chiffres), et l'IBAN/RIB avant la CIN (un RIB contient des groupes que la
#: regex CIN ne doit pas rogner).
PII_CATEGORIES = ('EMAIL', 'IBAN', 'RIB', 'CNSS', 'CIN', 'TEL', 'ADRESSE')

#: E-mail — forme standard.
_RE_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

#: IBAN marocain : MA + 2 chiffres de contrôle + 24 caractères alphanumériques
#: (souvent écrits par groupes de 4).
_RE_IBAN = re.compile(r'\bMA\d{2}(?:[ -]?[A-Z0-9]{4}){5,7}\b', re.IGNORECASE)

#: RIB marocain : 24 chiffres (banque 3 + agence 3 + compte 16 + clé 2), avec
#: ou sans séparateurs. Tolérance 20-27 chiffres : aucun montant ni aucune
#: référence de devis n'atteint cette longueur, donc pas de faux positif.
_RE_RIB = re.compile(r'\b(?:\d[ .-]?){19,26}\d\b')

#: CNSS — masqué par CONTEXTE (le numéro seul est une suite de chiffres
#: banale ; masquer tout nombre de 9 chiffres mutilerait les montants et les
#: références de devis).
_RE_CNSS = re.compile(
    r'(?i)\b(?:c\.?n\.?s\.?s\.?)\s*(?:n[°o]?|num[ée]ro)?\s*[:=]?\s*(\d{6,12})\b')

#: CIN marocaine : 1 à 2 lettres suivies de 5 à 8 chiffres.
_RE_CIN = re.compile(r'\b[A-Za-z]{1,2}\d{5,8}\b')

#: Téléphone marocain : +212/00212/0 puis 5-7 et 8 chiffres.
_RE_TEL = re.compile(r'(?:\+212|00212|0)[ .-]?[5-7](?:[ .-]?\d{2}){4}\b')

#: Adresse — masquée par MOT-CLÉ de voie (masquer « toute suite de mots »
#: détruirait le texte utile).
_RE_ADRESSE = re.compile(
    r'(?i)\b(?:rue|avenue|av\.|bd|boulevard|lotissement|lot\.|quartier|'
    r'r[ée]sidence|immeuble|hay|douar)\s+[\wÀ-ÿ\'’\-\.]+'
    r'(?:\s+[\wÀ-ÿ\'’\-\.]+){0,4}')

_PATTERNS = (
    ('EMAIL', _RE_EMAIL),
    ('IBAN', _RE_IBAN),
    ('RIB', _RE_RIB),
    ('CNSS', _RE_CNSS),
    ('CIN', _RE_CIN),
    ('TEL', _RE_TEL),
    ('ADRESSE', _RE_ADRESSE),
)

#: Forme d'un jeton de substitution.
TOKEN_FORMAT = '[PII_{categorie}_{index}]'


def _jeton(categorie: str, index: int) -> str:
    return TOKEN_FORMAT.format(categorie=categorie, index=index)


def redact_pii(text: str) -> tuple[str, dict]:
    """Masque les données personnelles de ``text``.

    Renvoie ``(texte_masqué, mapping)`` où ``mapping`` est ``{jeton: valeur
    d'origine}``. Une même valeur reçoit TOUJOURS le même jeton dans un texte
    donné, pour que le modèle puisse raisonner dessus (« relancer
    [PII_TEL_1] ») sans jamais la lire.

    Texte vide ou non-``str`` : renvoyé tel quel avec un mapping vide (jamais
    d'exception — cette fonction est sur le chemin de CHAQUE prompt)."""
    if not text or not isinstance(text, str):
        return text, {}

    mapping: dict[str, str] = {}
    deja_vu: dict[str, str] = {}
    compteurs: dict[str, int] = {}

    def _remplacer(categorie, valeur):
        if valeur in deja_vu:
            return deja_vu[valeur]
        compteurs[categorie] = compteurs.get(categorie, 0) + 1
        jeton = _jeton(categorie, compteurs[categorie])
        deja_vu[valeur] = jeton
        mapping[jeton] = valeur
        return jeton

    masque = text
    for categorie, pattern in _PATTERNS:
        def _sub(match, _cat=categorie):
            # Les motifs à CONTEXTE (CNSS) capturent le numéro en groupe 1 :
            # on ne masque que le numéro, pas le mot « CNSS » qui l'annonce.
            if _cat == 'CNSS' and match.groups():
                valeur = match.group(1)
                return match.group(0).replace(
                    valeur, _remplacer(_cat, valeur))
            return _remplacer(_cat, match.group(0))

        masque = pattern.sub(_sub, masque)
    return masque, mapping


def unredact(text: str, mapping: dict) -> str:
    """Re-substitue les valeurs d'origine dans ``text``.

    Best-effort : un jeton que le modèle aurait réécrit (casse, ponctuation)
    reste tel quel — mieux vaut un jeton visible qu'une donnée inventée."""
    if not text or not isinstance(text, str) or not mapping:
        return text
    for jeton, valeur in mapping.items():
        text = text.replace(jeton, valeur)
    return text


def redaction_enabled(provider_key: str = '') -> bool:
    """Le masquage est-il actif pour ce fournisseur ?

    ``settings.AI_PII_REDACTION`` :

      * ``'auto'`` (DÉFAUT) — actif dès qu'un fournisseur RÉEL est utilisé,
        sauf s'il est déclaré auto-hébergé (``AI_SELF_HOSTED_PROVIDERS``) :
        une donnée qui ne quitte pas l'infrastructure n'a pas à être masquée ;
      * vrai (``True``/``'1'``) — toujours actif ;
      * faux (``False``/``'0'``) — jamais actif ; le chemin redevient
        octet-identique à l'existant.
    """
    reglage = getattr(settings, 'AI_PII_REDACTION', 'auto')
    if isinstance(reglage, str):
        valeur = reglage.strip().lower()
        if valeur in ('0', 'false', 'off', 'non'):
            return False
        if valeur in ('1', 'true', 'on', 'oui'):
            return True
    elif reglage is not None and not isinstance(reglage, str):
        return bool(reglage)

    auto_heberges = getattr(settings, 'AI_SELF_HOSTED_PROVIDERS', None) or ()
    if provider_key and provider_key in auto_heberges:
        return False
    return bool(provider_key) and provider_key != 'noop'
