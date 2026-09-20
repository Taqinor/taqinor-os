"""CAL149 — les profils types : SAISIS par la société, ou repli ÉTIQUETÉ.

LE CONSTAT
----------
Les profils de charge du dépôt sont des constantes : ``DAY_USAGE_DEFAULTS`` /
``COMMERCIAL_DAY_SHARE`` (``frontend/src/features/ventes/solar.js``) et
``_scaled_typical_load(profile_key='residential')``
(``apps/ventes/solar_design.py``). Aucun n'est sourçable, aucun n'est
modifiable par la société — et pourtant c'est ce profil qui décide du taux
d'autoconsommation, donc de la taille du champ et de la batterie vendus.

LA RÈGLE POSÉE ICI
------------------
1. **La société saisit ses profils** (``ProfilTypeConsommation``, CAL149) et
   chacun porte sa PROVENANCE, obligatoire en base.
2. **Les profils codés restent en repli — ÉTIQUETÉS.** Ils sont relus dans
   ``apps.ventes.solar_design`` (jamais recopiés : deux copies divergeraient)
   et publiés avec ``source='hypothese_interne'`` et une provenance qui le
   DIT. Un repli annoncé est honnête ; un repli silencieux ne l'est pas.
3. **Les valeurs sont des POIDS**, normalisés à la lecture : la courbe donne
   la FORME de la journée, l'énergie vient d'ailleurs (facture, comptage).
   C'est ce qui fait d'un profil un profil TYPE et non la consommation d'un
   client.
4. **Aucune saison n'est extrapolée.** Une saison absente de la courbe
   retombe sur ``annuel`` si la société l'a saisie ; sinon le profil ne rend
   RIEN pour cette saison, et le dit.

Module PUR côté calcul ; les lectures en base passent par le modèle du module
(même app), jamais par une app tierce.
"""
from __future__ import annotations

__all__ = ['ProfilInvalide', 'SOURCE_REPLI', 'SOURCE_SOCIETE',
           'courbe_journaliere', 'enregistrer_profils', 'profil_de_repli',
           'profils_de_repli', 'profils_de_societe']


class ProfilInvalide(ValueError):
    """Une saisie de profil refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


SOURCE_SOCIETE = 'societe'
SOURCE_REPLI = 'hypothese_interne'

#: La mention que TOUT profil de repli porte, partout où il sert.
MENTION_REPLI = (
    'Profil codé en dur dans le dépôt (apps/ventes/solar_design.py) — '
    'HYPOTHÈSE INTERNE, jamais une mesure : la société n’a pas encore saisi '
    'de profil pour cette famille.')

#: Les profils de repli, par clé. La COURBE est relue dans le moteur de
#: ventes à l'appel — jamais recopiée ici (deux copies divergent).
REPLIS = (
    ('residentiel', 'Résidentiel (repli)', 'residentiel',
     'TYPICAL_LOAD_PROFILE_RESIDENTIAL'),
    ('commercial', 'Commercial / tertiaire (repli)', 'commercial',
     'TYPICAL_LOAD_PROFILE_COMMERCIAL'),
)


def _normaliser(valeurs):
    """Des poids → des FRACTIONS de la journée (somme = 1), ou ``None``."""
    try:
        nombres = [max(0.0, float(valeur)) for valeur in valeurs]
    except (TypeError, ValueError):
        return None
    total = sum(nombres)
    if not nombres or total <= 0:
        return None
    return [nombre / total for nombre in nombres]


def profils_de_repli():
    """Les profils codés du dépôt, ÉTIQUETÉS « hypothèse interne »."""
    from apps.ventes import solar_design

    profils = []
    for cle, libelle, famille, nom_constante in REPLIS:
        courbe = _normaliser(getattr(solar_design, nom_constante))
        if courbe is None:  # pragma: no cover - défensif
            continue
        profils.append({
            'cle': cle,
            'libelle': libelle,
            'famille': famille,
            'source': SOURCE_REPLI,
            'provenance': MENTION_REPLI,
            'courbes': {'annuel': courbe},
            'saisons': ['annuel'],
            'id': None,
        })
    return profils


def profil_de_repli(cle):
    """Le profil de repli de cette clé, ou ``None`` s'il n'y en a pas."""
    for profil in profils_de_repli():
        if profil['cle'] == cle:
            return profil
    return None


def profils_de_societe(company, *, inclure_replis=True):
    """Les profils SAISIS par la société, puis les replis étiquetés.

    Un profil de repli dont la clé est déjà saisie par la société n'est PAS
    servi : la saisie de la société l'emporte toujours sur une hypothèse
    interne. La société est celle passée en argument, jamais lue d'un corps
    de requête.
    """
    from ..models import ProfilTypeConsommation

    profils = []
    if company is not None:
        for objet in (ProfilTypeConsommation.objects
                      .filter(company=company, actif=True)
                      .order_by('famille', 'libelle', 'id')):
            courbes = {}
            for saison, valeurs in (objet.courbe or {}).items():
                normalisee = _normaliser(valeurs)
                if normalisee is not None:
                    courbes[saison] = normalisee
            profils.append({
                'id': objet.pk,
                'cle': objet.cle,
                'libelle': objet.libelle,
                'famille': objet.famille,
                'source': SOURCE_SOCIETE,
                'provenance': objet.provenance,
                'courbes': courbes,
                'saisons': sorted(courbes),
            })
    if not inclure_replis:
        return profils

    saisies = {profil['cle'] for profil in profils}
    profils.extend(profil for profil in profils_de_repli()
                   if profil['cle'] not in saisies)
    return profils


def enregistrer_profils(company, profils, *, utilisateur=None):
    """Remplace les profils SAISIS de la société par ceux fournis.

    La société vient de l'appelant (jamais d'un corps de requête) et est
    forcée sur chaque ligne. Chaque profil passe par ``full_clean()`` : c'est
    le modèle qui refuse une provenance vide ou une courbe mal formée, en
    nommant le champ — une seule définition du refus, pas deux.

    Raises:
        ProfilInvalide: corps mal formé, clé manquante ou en double, profil
            refusé par le modèle — toujours en NOMMANT le champ fautif.
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from ..models import ProfilTypeConsommation

    if company is None:
        raise ProfilInvalide(
            'Aucune société : les profils types sont toujours ceux d’une '
            'société, jamais des profils globaux.', champ='company')
    if not isinstance(profils, list):
        raise ProfilInvalide(
            'Les profils types se donnent en liste ordonnée '
            '(« profils: [{cle, libelle, famille, courbe, provenance}, …] »).',
            champ='profils')

    lignes = []
    vues = set()
    for rang, brut in enumerate(profils):
        if not isinstance(brut, dict):
            raise ProfilInvalide(
                f'Le profil n°{rang + 1} doit être un objet '
                f'(reçu : {type(brut).__name__}).', champ=f'profils[{rang}]')
        cle = str(brut.get('cle') or '').strip().lower()
        if not cle:
            raise ProfilInvalide(
                f'Le profil n°{rang + 1} n’a pas de clé : elle sert de repère '
                'stable aux écrans et aux calculs.',
                champ=f'profils[{rang}].cle')
        if cle in vues:
            raise ProfilInvalide(
                f'La clé de profil « {cle} » apparaît deux fois.', champ=cle)
        vues.add(cle)
        objet = ProfilTypeConsommation(
            company=company, cle=cle,
            libelle=str(brut.get('libelle') or '').strip() or cle,
            famille=str(brut.get('famille') or 'residentiel').strip().lower(),
            courbe=brut.get('courbe'),
            provenance=str(brut.get('provenance') or ''),
            actif=bool(brut.get('actif', True)),
            saisi_par=utilisateur if getattr(utilisateur, 'pk', None) else None,
        )
        try:
            objet.full_clean(exclude=['company', 'saisi_par'])
        except ValidationError as refus:
            champ, messages = next(iter(refus.message_dict.items()))
            raise ProfilInvalide(f'Profil « {cle} » : {messages[0]}',
                                 champ=f'{cle}.{champ}')
        lignes.append(objet)

    with transaction.atomic():
        ProfilTypeConsommation.objects.filter(company=company).delete()
        ProfilTypeConsommation.objects.bulk_create(lignes)
    return profils_de_societe(company)


def courbe_journaliere(profil, *, saison='annuel', total_kwh=None):
    """La journée du profil pour cette saison — forme, ou énergie calée.

    Args:
        profil: un dict rendu par :func:`profils_de_societe`.
        saison: la saison demandée ; absente, on retombe sur ``annuel`` SI la
            courbe annuelle existe — jamais sur une autre saison (interpoler
            l'hiver depuis l'été serait un chiffre inventé).
        total_kwh: l'énergie de la journée (facture, comptage). Absente ⇒ la
            courbe est rendue en FRACTIONS, jamais en kWh supposés.

    Returns:
        ``(courbe | None, diagnostic)`` — ``diagnostic`` porte ``saison_lue``,
        ``source``, ``provenance`` et ``motif``.
    """
    courbes = (profil or {}).get('courbes') or {}
    saison_lue = saison if saison in courbes else (
        'annuel' if 'annuel' in courbes else None)
    if saison_lue is None:
        return None, {
            'saison_lue': None,
            'source': (profil or {}).get('source'),
            'provenance': (profil or {}).get('provenance', ''),
            'motif': (
                f'Le profil « {(profil or {}).get("cle", "")} » ne porte pas '
                f'de courbe pour la saison « {saison} » et n’a pas de courbe '
                'annuelle : rien n’est publié pour cette saison (aucune '
                'saison n’est extrapolée depuis une autre).'),
        }

    fractions = courbes[saison_lue]
    if total_kwh is None:
        courbe = list(fractions)
        motif = ('Courbe publiée en FRACTIONS de la journée : aucune énergie '
                 'n’est supposée.')
    else:
        try:
            total = float(total_kwh)
        except (TypeError, ValueError):
            total = 0.0
        courbe = [fraction * max(0.0, total) for fraction in fractions]
        motif = 'Courbe calée sur l’énergie journalière fournie.'
    return courbe, {
        'saison_lue': saison_lue,
        'source': (profil or {}).get('source'),
        'provenance': (profil or {}).get('provenance', ''),
        'motif': motif,
    }
