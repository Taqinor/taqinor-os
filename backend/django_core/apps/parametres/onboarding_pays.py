"""NTI18N31 — Assistant « Onboarding pays » à la création d'une société.

Enchaîne, en UN seul appel, les réglages de localisation d'une société
(devise, fuseau horaire, langue de secours) et le seed des jours fériés du
pays choisi — au lieu de réglages épars sur plusieurs écrans.

DÉPENDANCE NON RÉSOLUE (COMPOSITION GUARD — jamais de substitut local pour
une primitive absente) : le wizard décrit par NTI18N31 prévoit aussi une
étape « Pays » persistée (``CompanyProfile.pays``) et une étape « Pack pays »
(``CompanyProfile.pack_pays``). Ces DEUX champs sont respectivement du
ressort de NTI18N13 et NTI18N16 (COST, GATED-founder) — NI L'UN NI L'AUTRE
N'EXISTE À CE JOUR sur ``CompanyProfile`` (vérifié : absents de
``models_company.py``/``serializers_company.py``). Cette fonction ACCEPTE
donc ``pays`` uniquement pour choisir QUEL SEEDER DE FÉRIÉS lancer
aujourd'hui — elle ne le PERSISTE nulle part (rien à écrire). Le jour où
NTI18N13 pose le champ, seul un appelant (jamais ce fichier) aura besoin
d'être adapté pour aussi le sauvegarder.

Seeders de jours fériés (NTI18N13) : seul ``seed_ma_holidays`` existe
aujourd'hui. Le mapping ci-dessous nomme aussi les trois autres
(``seed_holidays_fr``/``seed_holidays_sn``/``seed_holidays_ci``) par leur nom
FUTUR : tant qu'ils n'existent pas, ils sont ignorés SANS erreur (vérifié via
``django.core.management.get_commands`` — jamais un import direct qui
lèverait ``ImportError``). Cette fonction n'a besoin d'AUCUNE modification
le jour où NTI18N13 les livre.
"""
from __future__ import annotations

#: Pays -> nom de la commande de seed des jours fériés (NTI18N13). Seul 'MA'
#: est actionnable aujourd'hui ; les autres sont des noms FUTURS, ignorés
#: sans erreur tant qu'ils ne sont pas livrés.
SEEDERS_FERIES_PAR_PAYS = {
    'MA': 'seed_ma_holidays',
    'FR': 'seed_holidays_fr',
    'SN': 'seed_holidays_sn',
    'CI': 'seed_holidays_ci',
}


def seeder_disponible(pays: str) -> bool:
    """True si le seeder de jours fériés de ``pays`` est déployé aujourd'hui."""
    from django.core.management import get_commands
    nom = SEEDERS_FERIES_PAR_PAYS.get(pays)
    return bool(nom) and nom in get_commands()


def provisionner_localisation(
        company, *, pays='MA', devise=None,
        fuseau_horaire=None, langue_repli=None):
    """Configure en un seul appel les réglages de localisation de ``company``
    puis enchaîne le seed des jours fériés du ``pays`` choisi.

    Chaque réglage (``devise``, ``fuseau_horaire``, ``langue_repli``) est
    optionnel : un ``None`` laisse la valeur actuelle du profil inchangée
    (jamais écrasée par une valeur absente). Renvoie un dict décrivant ce qui
    a été fait, pour affichage synchrone dans l'assistant (« configurée en
    un seul flux, sans quitter l'écran »).
    """
    from django.core.management import call_command
    from apps.parametres.models_company import CompanyProfile

    profile = CompanyProfile.get(company)
    champs_modifies = []
    if devise:
        profile.devise_defaut = devise
        champs_modifies.append('devise_defaut')
    if fuseau_horaire:
        profile.fuseau_horaire = fuseau_horaire
        champs_modifies.append('fuseau_horaire')
    if langue_repli:
        profile.langue_repli = langue_repli
        champs_modifies.append('langue_repli')
    if champs_modifies:
        profile.save(update_fields=champs_modifies)

    feries_seedes = False
    seeder_utilise = None
    if seeder_disponible(pays):
        seeder_utilise = SEEDERS_FERIES_PAR_PAYS[pays]
        call_command(seeder_utilise, company_id=company.id)
        feries_seedes = True

    return {
        'profile': profile,
        'champs_modifies': champs_modifies,
        'pays': pays,
        'feries_seedes': feries_seedes,
        'seeder_utilise': seeder_utilise,
    }
