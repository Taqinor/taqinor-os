"""YHARD10 — export anonymisé du parc de données (clone UAT/staging).

Couche de FONDATION : produit un jeu de fixtures Django (JSON, rechargeable
via ``loaddata``) où TOUTES les colonnes PII connues sont scrubbées, en
préservant l'intégrité relationnelle (les FK restent cohérentes — seules les
VALEURS des champs PII changent, jamais les lignes ni leurs identifiants).

Différent de ``core.dsr`` (FG394/XPLT23) : le registre DSR répond à une
demande d'EFFACEMENT/EXPORT ciblée sur une PERSONNE (droits RGPD/loi 09-08),
avec ses propres règles légales (ex. RH REFUSE l'effacement — obligations
CNSS/AMO/fiscales). Ce module répond à un besoin différent : fabriquer un
CLONE COMPLET anonymisé de TOUTES les sociétés pour un environnement de
test/UAT, où aucune règle de rétention légale ne s'applique (rien n'est
"effacé" au sens légal — tout est simplement remplacé par des valeurs
factices déterministes AVANT export, jamais en base de production).

Registre : chaque app PII peut enregistrer un « masque » via
:func:`register_mask` — ``{model_label: {field: scrubber_fn}}``. Un scrubber
reçoit la valeur ORIGINALE et renvoie la valeur ANONYMISÉE (ou ``None``/`''`
pour nullifier). ``core`` ne connaît AUCUN modèle métier au chargement — les
masques sont enregistrés par les apps elles-mêmes (même motif que
``core.dsr.register_dsr_provider``), jamais l'inverse.
"""
from __future__ import annotations

import hashlib
from typing import Callable, Dict

# Registre : { 'app_label.ModelName': { field_name: scrubber_fn } }
_MASKS: Dict[str, Dict[str, Callable]] = {}


def register_mask(model_label: str, field_scrubbers: Dict[str, Callable]):
    """Enregistre (fusionne, idempotent) un masque de champs PII pour un
    modèle. ``model_label`` = ``"app_label.ModelName"`` (comme
    ``ContentType``/``dumpdata``)."""
    existing = _MASKS.setdefault(model_label, {})
    existing.update(field_scrubbers)


def registered_models():
    return sorted(_MASKS.keys())


def mask_for(model_label: str) -> Dict[str, Callable]:
    return dict(_MASKS.get(model_label, {}))


# ---------------------------------------------------------------------------
# Scrubbers génériques réutilisables — déterministes (même entrée → même
# sortie dans UN MÊME run, via un compteur croissant) pour garder des valeurs
# lisibles/uniques dans le clone (ex. deux employés distincts gardent des
# noms distincts, utile pour repérer des bugs d'affichage sans exposer les
# vraies identités).
# ---------------------------------------------------------------------------

_counter = {'n': 0}


def _next_n():
    _counter['n'] += 1
    return _counter['n']


def reset_counter():
    """Remet le compteur à zéro — utile pour des tests déterministes."""
    _counter['n'] = 0


def scrub_name(_value):
    return f'Anonyme{_next_n()}'


def scrub_email(_value):
    return f'anonyme{_next_n()}@example-uat.invalid'


def scrub_phone(_value):
    return f'+2126{_next_n():07d}'[:13]


def scrub_null(_value):
    """Nullifie complètement (RIB, CIN, CNSS, secrets…) — aucune valeur
    plausible n'est nécessaire pour un test UAT."""
    return None


def scrub_hash(value):
    """Remplace par une empreinte courte STABLE dans le run (utile pour un
    champ qui doit rester identique entre deux lignes liées, ex. un identifiant
    externe réutilisé) sans exposer la valeur réelle."""
    if not value:
        return value
    digest = hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:12]
    return f'anon_{digest}'


# ---------------------------------------------------------------------------
# Masques PAR DÉFAUT pour les champs PII listés (YHARD10) — déclarés ici en
# STRING (jamais un import de modèle au chargement du module : ``core`` reste
# fondation pure) plutôt que dans chaque app via ``ready()``, pour ne pas
# élargir le rayon de cette tâche à 5 apps de domaine en parallèle d'autres
# lanes qui peuvent éditer les mêmes ``apps.py``. Une app métier PEUT toujours
# enrichir/remplacer ces masques via :func:`register_mask` si elle a besoin
# de règles plus fines — ce socle par défaut garantit une couverture correcte
# même sans enregistrement explicite.
# ---------------------------------------------------------------------------

def _install_default_masks():
    register_mask('authentication.CustomUser', {
        'totp_secret': scrub_null,
    })
    register_mask('paie.ProfilPaie', {
        'salaire_base': scrub_null,
        'numero_cnss': scrub_null,
        'numero_amo': scrub_null,
        'numero_cimr': scrub_null,
        'rib': scrub_null,
        'banque': scrub_null,
    })
    register_mask('rh.DossierEmploye', {
        'cin': scrub_null,
        'cnss': scrub_null,
        'amo': scrub_null,
        'rib': scrub_null,
        'groupe_sanguin': scrub_null,
        'nom': scrub_name,
        'prenom': scrub_name,
        'email': scrub_email,
        'email_perso': scrub_email,
        'telephone': scrub_phone,
        'telephone_perso': scrub_phone,
    })
    register_mask('rh.Remuneration', {
        'montant': scrub_null,
    })
    register_mask('notifications.VapidKeyPair', {
        'private_key': scrub_null,
    })
    register_mask('publicapi.Webhook', {
        'secret': scrub_null,
    })
    register_mask('crm.Client', {
        'nom': scrub_name,
        'prenom': scrub_name,
        'email': scrub_email,
        'telephone': scrub_phone,
        'adresse': scrub_null,
    })
    register_mask('crm.Lead', {
        'nom': scrub_name,
        'prenom': scrub_name,
        'email': scrub_email,
        'telephone': scrub_phone,
        'whatsapp': scrub_phone,
        'adresse': scrub_null,
    })


_install_default_masks()
