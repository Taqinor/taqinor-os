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
           'profil_depuis_import', 'profils_de_repli', 'profils_de_societe']


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


def _courbes_normalisees(courbe_brute):
    """``objet.courbe`` (forme plate OU segmentée, CALX258) → NORMALISÉE.

    Forme plate : ``{saison: [24]}`` → ``{saison: [24 fractions]}`` —
    inchangé depuis CAL149 (D12 : une société qui n'édite rien relit
    exactement ce qu'elle relisait avant CALX258).

    Forme segmentée : ``{saison: {jour_type: [24]}}`` →
    ``{saison: {jour_type: [24 fractions]}}`` : deux types de jour d'une
    même saison rendent deux courbes DISTINCTES, jamais moyennées entre eux
    (moyenner ouvré et week-end effacerait précisément l'écart saisi).

    Une valeur qui ne normalise pas (nulle, illisible) est simplement
    OMISE — jamais remplacée par une valeur supposée.
    """
    courbes = {}
    for saison, valeurs in (courbe_brute or {}).items():
        if isinstance(valeurs, dict):
            segmentee = {}
            for jour_type, brutes in valeurs.items():
                normalisee = _normaliser(brutes)
                if normalisee is not None:
                    segmentee[jour_type] = normalisee
            if segmentee:
                courbes[saison] = segmentee
        else:
            normalisee = _normaliser(valeurs)
            if normalisee is not None:
                courbes[saison] = normalisee
    return courbes


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
            courbes = _courbes_normalisees(objet.courbe)
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


#: CALX259 — la référence « année pleine » de l'import : ``apercu_courbe_csv``
#: (``services/consommation.py``) ramène TOUJOURS sa série au pas HORAIRE,
#: quel que soit le pas d'origine (15 min agrégé à l'heure) — donc la
#: longueur de ``apercu['valeurs']`` se compare toujours à 8 760, jamais à
#: 35 040 (qui ne vaudrait que pour une série restée au quart d'heure).
HEURES_ANNEE_PLEINE = 8760


def _moyenne_par_heure(valeurs):
    """La MOYENNE, heure du jour par heure du jour, d'une série horaire.

    ``valeurs[i]`` est l'heure ``i % 24`` de son jour — la série n'a pas
    besoin de couvrir un nombre entier de jours : chaque heure du jour reçoit
    la moyenne de tout ce qui a été relevé pour elle, rien de plus, rien
    d'extrapolé.
    """
    sommes = [0.0] * 24
    comptes = [0] * 24
    for indice, valeur in enumerate(valeurs):
        heure = indice % 24
        sommes[heure] += valeur
        comptes[heure] += 1
    return [sommes[h] / comptes[h] if comptes[h] else 0.0 for h in range(24)]


def _courbe_de_base(profil):
    """Une courbe 24 h PLATE, dérivée d'un profil société — jamais inventée.

    La saison ``annuel`` sert telle quelle si le profil en a une. À défaut,
    la MOYENNE heure par heure de toutes les courbes qu'il porte (saisons et
    types de jour confondus, CALX258) : une moyenne de valeurs RÉELLEMENT
    saisies par la société est une agrégation traçable, jamais un chiffre
    inventé.
    """
    courbes = (profil or {}).get('courbes') or {}
    annuel = courbes.get('annuel')
    if isinstance(annuel, list) and len(annuel) == 24:
        return list(annuel)
    aplaties = [valeur for valeur in courbes.values()
                if isinstance(valeur, list) and len(valeur) == 24]
    for valeur in courbes.values():
        if isinstance(valeur, dict):
            aplaties.extend(v for v in valeur.values()
                            if isinstance(v, list) and len(v) == 24)
    if not aplaties:
        return None
    return [sum(courbe[h] for courbe in aplaties) / len(aplaties)
            for h in range(24)]


def _profil_societe_du_segment(company, famille, *, exclure_cle=None):
    """Le profil déjà SAISI par la société pour cette famille — jamais un
    repli (un repli codé en dur ne serait pas « le profil société »)."""
    for profil in profils_de_societe(company, inclure_replis=False):
        if profil['famille'] == famille and profil['cle'] != exclure_cle:
            return profil
    return None


def profil_depuis_import(company, apercu, *, cle, libelle, famille, origine):
    """Enregistre une courbe IMPORTÉE comme profil société — CALX259.

    ``apercu`` est la forme rendue par
    :func:`apps.calepinage.services.consommation.apercu_courbe_csv` (ou
    équivalente) : au moins ``valeurs`` (série HORAIRE) et, si connus,
    ``pas_minutes`` et ``points_lus``. ``origine`` DIT d'où vient le fichier
    (nom, distributeur…) et nourrit la ``provenance`` écrite en base, à côté
    du nombre de points, du pas détecté et de la date d'import.

    Un fichier qui ne couvre pas les douze mois d'une année (``valeurs`` plus
    courte que :data:`HEURES_ANNEE_PLEINE`) est ACCEPTÉ : les heures
    manquantes sont complétées par le profil déjà SAISI par la société pour
    ce même segment (``famille``) — jamais par des relevés d'un autre foyer,
    ce qui serait le chiffre inventé que la règle fondateur interdit. La part
    d'heures ainsi complétée et la clé du profil qui a servi sont publiées
    dans la ``provenance``. Sans profil société disponible pour ce segment,
    l'import est refusé en le disant.

    Le même import rejoué (même ``cle``) MET À JOUR le profil existant : il
    n'en crée jamais un second — ``cle`` est le repère stable de la société.

    Raises:
        ProfilInvalide: pas de société, pas de clé, provenance vide
            (``champ='provenance'`` — la règle du modèle,
            ``models.py`` CAL149), courbe importée vide ou entièrement
            nulle, ou import partiel sans profil société pour compléter
            (``champ='provenance'`` aussi : c'est elle qui, faute de source,
            ne peut pas s'écrire).
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils import timezone

    from ..models import ProfilTypeConsommation

    if company is None:
        raise ProfilInvalide(
            'Aucune société : un profil importé est toujours celui d’une '
            'société, jamais un profil global.', champ='company')
    cle = str(cle or '').strip().lower()
    if not cle:
        raise ProfilInvalide(
            'L’import n’a pas de clé : elle sert de repère stable aux '
            'écrans et aux calculs.', champ='cle')
    if not (origine or '').strip():
        raise ProfilInvalide(
            'La provenance est obligatoire : un profil importé sans savoir '
            'd’où vient le fichier ne peut être ni défendu devant un '
            'client ni distingué d’une hypothèse interne.',
            champ='provenance')

    famille = str(famille or 'residentiel').strip().lower()
    brutes = (apercu or {}).get('valeurs') or []
    try:
        valeurs = [float(valeur) for valeur in brutes]
    except (TypeError, ValueError):
        raise ProfilInvalide(
            'Le fichier importé contient une valeur illisible : rien n’est '
            'enregistré.', champ='apercu')
    if not valeurs:
        raise ProfilInvalide(
            'Le fichier importé ne porte aucune mesure : rien à '
            'enregistrer.', champ='apercu')

    poids_import = _normaliser(_moyenne_par_heure(valeurs))
    if poids_import is None:
        raise ProfilInvalide(
            'La courbe importée est entièrement nulle : elle ne décrit '
            'aucune journée.', champ='courbe')

    fraction_lue = min(1.0, len(valeurs) / HEURES_ANNEE_PLEINE)
    cle_source = None
    if fraction_lue < 1.0:
        profil_source = _profil_societe_du_segment(
            company, famille, exclure_cle=cle)
        if profil_source is None:
            raise ProfilInvalide(
                f'Le fichier ne porte que {len(valeurs)} des '
                f'{HEURES_ANNEE_PLEINE} heures d’une année pleine : pour '
                'compléter le reste, il faut un profil déjà SAISI par la '
                f'société pour le segment « {famille} ». Aucun n’existe — '
                'saisissez-en un d’abord, ou importez un fichier annuel '
                'complet.', champ='provenance')
        cle_source = profil_source['cle']
        poids_base = _courbe_de_base(profil_source)
        if poids_base is None:  # pragma: no cover - défensif
            raise ProfilInvalide(
                f'Le profil société « {cle_source} » ne porte aucune '
                'courbe exploitable pour compléter cet import.',
                champ='provenance')
        poids_final = [
            fraction_lue * poids_h + (1 - fraction_lue) * base_h
            for poids_h, base_h in zip(poids_import, poids_base)
        ]
    else:
        poids_final = poids_import

    points_lus = (apercu or {}).get('points_lus') or len(valeurs)
    pas_minutes = (apercu or {}).get('pas_minutes') or 60
    date_import = timezone.now().strftime('%Y-%m-%d')
    provenance = (
        f'Import CSV « {origine} » — {points_lus} points, pas '
        f'{pas_minutes} min, importé le {date_import}.'
    )
    if cle_source:
        part_pct = round((1 - fraction_lue) * 100)
        provenance += (
            f' {part_pct} % des heures complétées par le profil société '
            f'« {cle_source} ».'
        )

    with transaction.atomic():
        objet = (ProfilTypeConsommation.objects
                 .filter(company=company, cle=cle)
                 .first())
        if objet is None:
            objet = ProfilTypeConsommation(company=company, cle=cle)
        objet.libelle = str(libelle or '').strip() or cle
        objet.famille = famille
        objet.courbe = {'annuel': poids_final}
        objet.provenance = provenance
        objet.actif = True
        try:
            objet.full_clean(exclude=['company', 'saisi_par'])
        except ValidationError as refus:
            champ, messages = next(iter(refus.message_dict.items()))
            raise ProfilInvalide(f'Profil « {cle} » : {messages[0]}',
                                 champ=champ)
        objet.save()

    for profil_enregistre in profils_de_societe(company,
                                                inclure_replis=False):
        if profil_enregistre['cle'] == cle:
            return profil_enregistre
    return None  # pragma: no cover - défensif : vient d'être enregistré


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
