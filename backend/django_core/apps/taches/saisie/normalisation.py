"""Normalisation de saisie (regles.md §1.1) — code PUR, sans Django.

`normaliser` rend une copie d'analyse de MEME LONGUEUR que l'original : les
positions des jetons y valent aussi dans le texte original (le titre garde ses
apostrophes, ses accents et sa casse).
"""
import unicodedata

_APOSTROPHES = {'’', '‘', 'ʼ', '′'}
_ESPACES = {' ', ' ', ' ', ' ', '\t'}
_TRAITS_UNION = {'‐', '‑'}


def _sans_accent(car):
    """Lettre accentuée -> lettre de base (1er caractère de sa forme NFD)."""
    decomposee = unicodedata.normalize('NFD', car)
    if len(decomposee) > 1 and unicodedata.combining(decomposee[1]):
        return decomposee[0]
    return car


def _normaliser_car(car):
    if car in _APOSTROPHES:
        return "'"
    if car in _ESPACES:
        return ' '
    if car in _TRAITS_UNION:
        return '-'
    minuscule = car.lower()
    if len(minuscule) != 1:
        return car
    return _sans_accent(minuscule)


def normaliser(texte):
    """Copie d'analyse : apostrophes, espaces, traits d'union, casse, accents."""
    return ''.join(_normaliser_car(car) for car in texte)


def cle_nom(nom):
    """Clé d'unicité d'un nom : `normaliser` sans espaces, `-` ni `_` (I2)."""
    return ''.join(
        car for car in normaliser(nom)
        if not car.isspace() and car not in '-_')
