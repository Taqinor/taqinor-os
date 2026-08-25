"""Normalisation d'un numéro marocain au format international wa.me.

Objectif : produire `2126XXXXXXXX` (sans + ni espaces) à partir de ce que les
commerciaux saisissent réellement (06…, +212…, 00212…, espaces, tirets,
parenthèses). Utilisé pour construire les liens https://wa.me/<number>.

25/08/2026 — LANE NUMÉROS INTERNATIONAUX (ordre fondateur : « i want my
system to accept non moroccan phone numbers ») : `normalize_ma_phone` ne
FABRIQUE PLUS JAMAIS un préfixe '212' pour un numéro qui n'est pas
reconnaissable comme marocain. Avant cette date, tout ce qui ne matchait
aucun format marocain retombait quand même dans le moule '212' + reste,
CORROMPANT silencieusement un numéro étranger (ex. +33612345678 devenait
'21233612345678'). Un numéro non reconnaissable renvoie désormais `None`.
Pour un numéro étranger, voir `normalize_phone_e164` ci-dessous — port du
contrat `apps/web/src/lib/phone.ts` (WJ64, DIASPORA) côté backend.
"""
import re

# 9 chiffres locaux : fixe (5) ou mobile (6, 7) — les seuls préfixes
# marocains valides une fois l'indicatif/zéro initial retiré.
_MA_LOCAL_RE = re.compile(r'^[5-7]\d{8}$')

# E.164 générique (hors Maroc) : indicatif pays 1 à 3 chiffres (jamais 212,
# déjà couvert par le chemin marocain) + numéro national, total borné à la
# longueur E.164 max (15 chiffres, recommandation UIT). Garde-fou anti-garbage
# minimal — pas une validation par-pays complète, juste un format plausible.
_FOREIGN_E164_RE = re.compile(r'^[1-9]\d{6,14}$')


def normalize_ma_phone(raw):
    """Renvoie le numéro marocain en `212XXXXXXXXX`, ou None si non
    reconnaissable comme marocain (vide, invalide, OU étranger — voir
    `normalize_phone_e164` pour un numéro à indicatif explicite non-212).

    Formats marocains reconnus : local 0[5-7]XXXXXXXX (10 chiffres) ; ou
    212/+212/00212 + 9 chiffres [5-7]XXXXXXXX — y COMPRIS quand l'usager
    retape le zéro local après l'indicatif (« +212 (0)6 12 34 56 78 »,
    « +212 06… », « 00212 0… », graphies réelles très courantes) : les 0 de
    tête du reste sont retirés après reconnaissance du préfixe 212, AVANT le
    test à 9 chiffres (25/08/2026 — régression de la lane numéros
    internationaux : l'ancienne normalisation faisait ce `lstrip('0')`
    inconditionnellement ; la réécriture qui a introduit `_MA_LOCAL_RE` l'a
    perdu, rejetant ces fiches réelles). Ne force JAMAIS un préfixe '212'
    sur une suite de chiffres qui ne matche aucun de ces formats.
    """
    if not raw:
        return None
    digits = re.sub(r'\D', '', str(raw))  # ne garde que les chiffres
    if not digits:
        return None
    if digits.startswith('00'):  # préfixe international 00
        digits = digits[2:]
    if digits.startswith('212'):
        local = digits[3:].lstrip('0')
    elif digits.startswith('0'):
        local = digits[1:]
    else:
        local = digits
    if _MA_LOCAL_RE.match(local):
        return '212' + local
    return None


def normalize_phone_e164(raw):
    """Normalisation E.164 GÉNÉRALE : marocain reconnu → `212XXXXXXXXX` (même
    forme que `normalize_ma_phone`) ; sinon, si un indicatif international
    est EXPLICITE ('+' ou '00' en tête) et que le reste matche un E.164
    plausible (``[1-9]\\d{6,14}``) → les chiffres tels quels (sans '+'),
    prêts pour un lien wa.me ou un hash Meta ; sinon `None`.

    Port du contrat `apps/web/src/lib/phone.ts` (WJ64, DIASPORA) côté
    backend, 25/08/2026 (LANE NUMÉROS INTERNATIONAUX) — mêmes règles : un
    marocain reste le chemin PRINCIPAL, un étranger à indicatif explicite est
    accepté EN PLUS, un local ambigu (0XXXXXXXXX à 10 chiffres) reste rejeté
    (jamais pris pour un numéro étranger sans indicatif tapé).

    Nettoyage : ne garde que les chiffres (comme `normalize_ma_phone`), le
    seul '+' de tête servant de signal d'indicatif explicite — un numéro
    marocain valide saisi avec `/`, « Tel: » ou toute autre ponctuation
    parasite est reconnu (délégation à `normalize_ma_phone` ci-dessus, donc
    le correctif lstrip('0') post-212 s'applique ici aussi).
    """
    if not raw:
        return None
    had_plus = str(raw).strip().startswith('+')
    digits = re.sub(r'\D', '', str(raw))  # ne garde que les chiffres
    if not digits:
        return None

    ma = normalize_ma_phone(digits)
    if ma:
        return ma

    if had_plus:
        candidate = digits
    elif digits.startswith('00'):
        candidate = digits[2:]
    else:
        return None  # pas d'indicatif explicite → jamais traité comme étranger

    if candidate.startswith('212'):
        return None  # 212 est l'indicatif EXCLUSIF du Maroc — déjà tenté ci-dessus
    if _FOREIGN_E164_RE.match(candidate):
        return candidate
    return None
