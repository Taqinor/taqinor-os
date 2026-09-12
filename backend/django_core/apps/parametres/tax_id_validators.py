"""NTI18N19 — registre de validateurs d'identifiant fiscal/TVA par pays.

Framework EXTENSIBLE (un pays = une ou plusieurs fonctions) : MA (ICE,
formalise en fonction réutilisable la validation attendue de longue date),
FR (SIRET + TVA intracommunautaire), SN/CI (NINEA/RCCM), ES (NIF/CIF).
JAMAIS bloquant pour un pays/champ SANS validateur défini — un identifiant
inconnu passe SANS erreur (juste une absence de contrôle, jamais un 400) :
voir `validate_tax_id`.

Chaîne de dépendance (règle dure de la lane i18n — jamais de substitut
local pour une primitive absente) : ce module route par ``pack_pays``, le
champ ``CompanyProfile.pack_pays`` prévu par NTI18N16 — GATED-founder,
NON CONSTRUIT à ce jour. En attendant son arrivée :
  - les appelants (``CompanyProfileSerializer.validate_ice``,
    ``ClientSerializer.validate_ice``, apps.crm/apps.parametres) passent
    ``'MA'`` EN DUR — comportement historique inchangé, puisque toute
    société existante EST marocaine aujourd'hui (marché unique) ;
  - FR/SN_CI/ES sont IMPLÉMENTÉS et TESTÉS ici, prêts à être dispatchés par
    ``pack_pays`` dès que ce champ existera — aucune modification de CE
    fichier ne sera nécessaire à ce moment-là, seuls les appelants
    changeront leur valeur codée en dur pour ``instance.pack_pays``.

Critère d'acceptation de la tâche (saisir un ICE invalide sur pack_pays=MA
-> 400 ; le même champ sur pack_pays=FR valide un SIRET à la place) sera
intégralement démontrable UNE FOIS ``pack_pays`` posé — le framework
lui-même (ce fichier) est complet et testé pour les DEUX branches dès
aujourd'hui.
"""
from __future__ import annotations

import re


def _erreur(message: str) -> dict:
    return {'valide': False, 'message': message}


def _ok() -> dict:
    return {'valide': True, 'message': ''}


# ── Maroc — ICE (Identifiant Commun de l'Entreprise) ───────────────────────
# 15 chiffres exactement (format officiel marocain OMPIC) ; aucune clé de
# contrôle publiquement documentée — la règle vérifiable est longueur+type.
def validate_ice_ma(value) -> dict:
    value = (value or '').strip()
    if not value:
        return _ok()  # champ optionnel côté modèle : vide n'est jamais une erreur de format
    if not re.fullmatch(r'\d{15}', value):
        return _erreur(
            "L'ICE doit comporter exactement 15 chiffres "
            f'(reçu {len(value)} caractère(s)).')
    return _ok()


# ── France — SIRET (14 chiffres + clé de Luhn) ─────────────────────────────
def _luhn_valide(chiffres: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(chiffres)):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_siret_fr(value) -> dict:
    value = (value or '').strip().replace(' ', '')
    if not value:
        return _ok()
    if not re.fullmatch(r'\d{14}', value):
        return _erreur(
            f'Le SIRET doit comporter exactement 14 chiffres (reçu {len(value)}).')
    if not _luhn_valide(value):
        return _erreur('Le SIRET est invalide (clé de contrôle incorrecte).')
    return _ok()


# ── France — TVA intracommunautaire (FR + 2 caractères clé + SIREN 9 chiffres) ──
_TVA_FR_RE = re.compile(r'^FR([A-Z0-9]{2})(\d{9})$')


def validate_tva_intra_fr(value) -> dict:
    value = (value or '').strip().upper().replace(' ', '')
    if not value:
        return _ok()
    if not _TVA_FR_RE.fullmatch(value):
        return _erreur(
            'Le numéro de TVA intracommunautaire doit être au format FR + '
            '2 caractères clé + 9 chiffres (SIREN), ex. FR32123456789.')
    return _ok()


# ── Sénégal / Côte d'Ivoire — NINEA / RCCM ──────────────────────────────────
# Formats officiels variables selon l'administration émettrice ; garde de
# FORME large (alphanumérique, longueur plausible) plutôt qu'une regex trop
# stricte qui rejetterait un numéro réel non documenté ici.
def validate_ninea_rccm_sn_ci(value) -> dict:
    value = (value or '').strip()
    if not value:
        return _ok()
    if not re.fullmatch(r'[A-Za-z0-9-]{6,20}', value):
        return _erreur(
            'Le NINEA/RCCM doit être alphanumérique, entre 6 et 20 caractères.')
    return _ok()


# ── Espagne — NIF / CIF ──────────────────────────────────────────────────
# NIF (personne physique) : 8 chiffres + 1 lettre de contrôle vérifiable.
# CIF (personne morale) : 1 lettre + 7 chiffres + 1 caractère de contrôle —
# l'algorithme de clé diffère par catégorie de lettre ; on valide ici la
# FORME (jamais un faux-négatif sur un CIF réel faute d'implémenter les 2
# variantes de clé), cohérent avec la garde NINEA/RCCM ci-dessus.
_NIF_LETTRES_CONTROLE = 'TRWAGMYFPDXBNJZSQVHLCKE'


def validate_nif_cif_es(value) -> dict:
    value = (value or '').strip().upper().replace(' ', '').replace('-', '')
    if not value:
        return _ok()
    m_nif = re.fullmatch(r'(\d{8})([A-Z])', value)
    if m_nif:
        chiffres, lettre = m_nif.groups()
        attendue = _NIF_LETTRES_CONTROLE[int(chiffres) % 23]
        if lettre != attendue:
            return _erreur(
                f'NIF invalide (lettre de contrôle attendue : {attendue}).')
        return _ok()
    if re.fullmatch(r'[A-Z]\d{7}[0-9A-Z]', value):
        return _ok()
    return _erreur(
        'Le NIF/CIF doit être au format espagnol (ex. 12345678Z ou B12345674).')


# ── Registre extensible : pack_pays -> {champ_logique: validateur} ─────────
VALIDATEURS = {
    'MA': {'ice': validate_ice_ma},
    'FR': {'siret': validate_siret_fr, 'tva_intra': validate_tva_intra_fr},
    'SN_CI': {'ninea': validate_ninea_rccm_sn_ci, 'rccm': validate_ninea_rccm_sn_ci},
    'ES': {'nif_cif': validate_nif_cif_es},
}


def validate_tax_id(pack_pays: str, champ: str, value) -> dict:
    """Point d'entrée du framework.

    ``pack_pays`` : clé pays/pack (NTI18N16 — 'MA'/'FR'/'SN_CI'/'ES' ; passé
    en dur 'MA' par les appelants actuels tant que le champ modèle n'existe
    pas). ``champ`` : clé logique du champ validé (ex. 'ice', 'siret',
    'tva_intra', 'ninea', 'rccm', 'nif_cif'). ``value`` : la valeur saisie.

    Renvoie toujours ``{'valide': bool, 'message': str}`` — JAMAIS
    d'exception. Un ``pack_pays``/``champ`` sans validateur défini renvoie
    ``valide=True`` (comportement actuel préservé : absence de contrôle,
    jamais un blocage) — règle explicite de l'énoncé."""
    validateurs_pays = VALIDATEURS.get(pack_pays, {})
    validateur = validateurs_pays.get(champ)
    if validateur is None:
        return _ok()
    return validateur(value)
