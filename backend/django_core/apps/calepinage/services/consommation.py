"""CAL147 — le profil de CONSOMMATION du module, depuis les factures du lead.

LE CONSTAT
----------
Le lead porte déjà les factures (``facture_hiver``, ``facture_ete``) et le
drapeau ``ete_differente`` (profil énergie CRM), et l'écran devis sait déjà en
dériver douze mois (``interpolerFactures`` / ``estimerMois``,
``frontend/src/features/ventes/solar.js``). Le module Calepinage, lui, n'avait
AUCUNE consommation.

LES RÈGLES POSÉES ICI
---------------------
1. **Le CRM se lit par son sélecteur, jamais par ses modèles**
   (``apps.crm.selectors.get_company_lead``) — frontière inter-apps tenue par
   ``lint-imports``. La société est celle que l'appelant passe, jamais un
   identifiant venu du corps d'une requête.
2. **Aucune facture moyenne n'est inventée.** Lead sans facture d'hiver ⇒ les
   douze mois sont VIDES (``null``) et l'avertissement le dit. Un « 900 MAD
   par défaut » serait exactement le chiffre inventé que la règle fondateur
   interdit.
3. **Chaque mois porte sa SOURCE** — ``facture`` (un montant réellement saisi
   au CRM), ``interpole`` (dérivé des deux factures par la règle de l'écran
   devis, reprise à l'identique) ou ``saisi`` (corrigé à la main dans le
   module). Le profil est donc ÉDITABLE sans jamais perdre la trace de ce qui
   vient du client.
4. **La conversion MAD → kWh n'est PAS faite ici.** Elle dépend du barème du
   distributeur ; tant qu'elle n'est pas branchée, ``kwh`` vaut ``null`` avec
   sa raison, jamais un kWh dérivé d'un prix moyen supposé. CALX257 : elle est
   écrite dans le barème SOCIÉTÉ (``apps.parametres.tariff.
   kwh_depuis_facture``) ; :func:`publier_kwh` ne fait que l'appeler et
   publier ``kwh`` avec son motif — cette règle reste vraie (D5).
"""
from __future__ import annotations

import math

__all__ = ['AVIS_KWH_NON_CONVERTIS', 'ImportCourbeInvalide',
           'PROVENANCES_APPAREIL', 'ProfilInvalide', 'SOURCES_MOIS', 'UNITES',
           'apercu_courbe_csv', 'appliquer_ramadan', 'courbe_appareils',
           'interpoler_factures', 'profil_depuis_lead',
           'profil_depuis_layout', 'profil_mensuel', 'publier_kwh']

#: D'où vient le montant d'un mois. ``None`` = mois vide (rien de connu).
SOURCES_MOIS = ('facture', 'interpole', 'saisi')

#: Les douze mois calendaires, 1 (janvier) à 12 (décembre) — convention
#: universelle, jamais un défaut de source de données.
MOIS = tuple(range(1, 13))

#: Les deux mois que le CRM saisit RÉELLEMENT : janvier porte la facture
#: d'hiver, juillet la facture d'été (indices 0 et 6 de la règle de l'écran
#: devis, reprise à l'identique ci-dessous).
MOIS_FACTURE_HIVER = 1
MOIS_FACTURE_ETE = 7

#: L'avertissement d'un profil dont les kWh ne sont pas convertis — retiré par
#: :func:`publier_kwh` dès que le barème société a été consulté.
AVIS_KWH_NON_CONVERTIS = (
    'Les montants sont en MAD par mois. La conversion en kWh dépend du '
    'barème du distributeur : elle n\'est pas faite ici, et « kwh » reste '
    '« non calculé » plutôt qu\'estimé à partir d\'un prix moyen.')


class ProfilInvalide(ValueError):
    """Une saisie de profil refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def interpoler_factures(hiver, ete):
    """Les douze montants dérivés de (hiver, été) — PORT EXACT de l'écran devis.

    ``frontend/src/features/ventes/solar.js`` : sept valeurs de janvier à
    juillet en pente vers l'été, puis cinq valeurs de août à décembre en pente
    de retour vers l'hiver. Aucune autre forme n'est inventée ici : deux
    courbes différentes pour le même client, c'est une contradiction visible
    par le client lui-même.
    """
    if hiver is None:
        return [None] * 12
    if not ete or ete <= 0:
        return [float(hiver)] * 12
    hiver, ete = float(hiver), float(ete)
    premiere = [hiver + (ete - hiver) / 6 * rang for rang in range(7)]
    seconde = [ete - (ete - hiver) / 4 * rang for rang in range(5)]
    return premiere + seconde


def _montant(valeur, *, champ):
    if valeur in (None, ''):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise ProfilInvalide(
            f'Le montant du mois « {champ} » est illisible '
            f'(reçu : {valeur!r}).', champ=champ)
    if nombre < 0:
        raise ProfilInvalide(
            f'Le montant du mois « {champ} » ne peut pas être négatif '
            f'(reçu : {nombre}).', champ=champ)
    return nombre


def profil_mensuel(*, facture_hiver, facture_ete=None, ete_differente=False,
                   saisies=None, conso_mensuelle_kwh=None):
    """Les douze mois du profil, chacun avec sa source.

    Args:
        facture_hiver / facture_ete: les montants du CRM (MAD/mois).
        ete_differente: le drapeau du lead. Faux ⇒ la facture d'hiver vaut
            pour toute l'année (convention du CRM).
        saisies: ``{mois: montant}`` corrigés à la main — ils PRIMENT et sont
            marqués ``saisi``.
        conso_mensuelle_kwh: la consommation mensuelle saisie au CRM, publiée
            telle quelle (jamais répartie sur les mois : personne n'a mesuré
            cette répartition).
    """
    avertissements = []
    hiver = _montant(facture_hiver, champ='facture_hiver')
    ete = _montant(facture_ete, champ='facture_ete') if ete_differente else None
    if ete_differente and ete is None:
        avertissements.append(
            'Le lead est marqué « été différent » mais aucune facture d\'été '
            "n'est renseignée : les douze mois reprennent la facture d'hiver.")

    montants = interpoler_factures(hiver, ete)
    saisies = {int(mois): valeur for mois, valeur in (saisies or {}).items()}

    lignes = []
    for rang, mois in enumerate(MOIS):
        if mois in saisies:
            lignes.append({
                'mois': mois,
                'facture_mad': _montant(saisies[mois], champ=f'mois[{mois}]'),
                'kwh': None,
                'source': 'saisi',
            })
            continue
        montant = montants[rang]
        if montant is None:
            source = None
        elif mois == MOIS_FACTURE_HIVER:
            source = 'facture'
        elif mois == MOIS_FACTURE_ETE and ete is not None:
            source = 'facture'
        else:
            source = 'interpole'
        lignes.append({
            'mois': mois,
            'facture_mad': (round(montant, 2) if montant is not None
                            else None),
            'kwh': None,
            'source': source,
        })

    if hiver is None and not saisies:
        avertissements.append(
            "Aucune facture n'est renseignée sur ce lead : le profil de "
            'consommation reste VIDE et attend une saisie — aucune facture '
            "moyenne n'est inventée.")
    avertissements.append(AVIS_KWH_NON_CONVERTIS)

    connus = [ligne['facture_mad'] for ligne in lignes
              if ligne['facture_mad'] is not None]
    return {
        'mois': lignes,
        'annuel_mad': round(sum(connus), 2) if len(connus) == 12 else None,
        'ete_differente': bool(ete_differente),
        'conso_mensuelle_kwh_saisie': _montant(
            conso_mensuelle_kwh, champ='conso_mensuelle_kwh'),
        'source': 'lead' if hiver is not None else None,
        'avertissements': avertissements,
    }


def _lire_lead(company, lead_id):
    """Le lead, par le SÉLECTEUR du CRM — jamais par ses modèles."""
    from apps.crm.selectors import get_company_lead
    return get_company_lead(company, lead_id)


def profil_depuis_lead(company, lead_id, *, saisies=None, lire_lead=None):
    """Le profil pré-rempli depuis le lead d'un calepinage, ou VIDE.

    Args:
        company: la société — posée côté serveur, jamais lue d'une requête.
        lead_id: l'identifiant du lead rattaché au calepinage.
        saisies: corrections manuelles ``{mois: montant}``.
        lire_lead: point d'injection (tests) ; par défaut le sélecteur CRM.

    Returns:
        Le profil de ``profil_mensuel``. Lead introuvable dans la société ⇒
        profil VIDE avec son avertissement (jamais une erreur silencieuse ni
        une facture inventée).
    """
    lecteur = lire_lead or _lire_lead
    lead = lecteur(company, lead_id) if lead_id else None
    if lead is None:
        profil = profil_mensuel(facture_hiver=None, saisies=saisies)
        profil['avertissements'].insert(0, (
            "Aucun lead n'est rattaché à ce calepinage (ou il appartient à "
            'une autre société) : le profil de consommation part vide.'))
        return profil
    return profil_mensuel(
        facture_hiver=getattr(lead, 'facture_hiver', None),
        facture_ete=getattr(lead, 'facture_ete', None),
        ete_differente=bool(getattr(lead, 'ete_differente', False)),
        saisies=saisies,
        conso_mensuelle_kwh=getattr(lead, 'conso_mensuelle_kwh', None),
    )


# ── CALX257 — les kWh publiés par le barème de la SOCIÉTÉ ─────────────────
#
# LE CONSTAT : la règle 4 de l'en-tête laissait ``kwh: null`` sur les douze
# mois alors que le barème existe en réglage société (Paramètres →
# Tarification & ROI). Parité : OpenSolar, le tarif porte la conversion
# facture ↔ énergie.
#
# LA RÈGLE (D5) : l'inversion vit dans ``apps.parametres.tariff`` (app de
# FONDATION — import direct autorisé), à côté des jumeaux kWh → MAD. Ce module
# ne fait QUE l'appeler et recopier ``kwh`` + son motif : aucune arithmétique
# de montant ici (garde de source : ``tests/test_calx257_kwh_publie.py``). La
# classe tarifaire est SAISIE ; sans société, aucun réglage n'est lu — jamais
# le réglage de repli « sans société » — et ``kwh`` reste ``null`` avec le
# motif qui nomme le réglage manquant.

def _lire_reglages_tarif(company):
    """Le réglage « Tarification & ROI » DE LA SOCIÉTÉ (fondation parametres)."""
    from apps.parametres.models_tariff import TariffSettings
    return TariffSettings.get(company=company)


def publier_kwh(profil, company, *, classe, lire_reglages=None):
    """Renseigne ``kwh`` de chaque mois par le barème SOCIÉTÉ, avec son motif.

    Args:
        profil: un profil de :func:`profil_mensuel` / :func:`profil_depuis_lead`
            (modifié EN PLACE et rendu).
        company: la société — posée côté serveur. ``None`` ⇒ aucun réglage
            n'est lu et chaque ``kwh`` reste ``None`` avec le motif.
        classe: ``residentiel`` | ``force_motrice`` — SAISIE, jamais supposée.
        lire_reglages: point d'injection (tests) ; par défaut
            ``TariffSettings.get(company=...)``.

    Returns:
        Le profil : chaque mois porte ``kwh`` et ``kwh_motif`` (vide quand la
        conversion a abouti) ; ``conversion_kwh`` publie la classe, le réglage
        et sa version, le périmètre du montant inversé et les motifs.

    Raises:
        ProfilInvalide: classe absente ou inconnue (``champ='classe'``).
    """
    from apps.parametres.tariff import (
        PERIMETRE_INVERSION, REGLAGE_TARIF, FactureInvalide,
        kwh_depuis_facture,
    )

    reglages = None
    if company is not None:
        reglages = (lire_reglages or _lire_reglages_tarif)(company)

    motifs = []
    converti = False
    for ligne in profil['mois']:
        try:
            conversion = kwh_depuis_facture(
                reglages, ligne['facture_mad'], classe=classe)
        except FactureInvalide as refus:
            raise ProfilInvalide(refus.motif, champ=refus.champ) from refus
        ligne['kwh'] = (None if conversion['kwh'] is None
                        else float(conversion['kwh']))
        ligne['kwh_motif'] = conversion['motif']
        if conversion['kwh'] is not None:
            converti = True
        elif conversion['motif'] not in motifs:
            motifs.append(conversion['motif'])

    profil['conversion_kwh'] = {
        'classe': classe,
        'reglage': REGLAGE_TARIF,
        'reglage_version': getattr(reglages, 'version', None),
        'perimetre': PERIMETRE_INVERSION,
        'motifs': motifs,
    }
    avertissements = [avis for avis in profil['avertissements']
                      if avis != AVIS_KWH_NON_CONVERTIS]
    avertissements.extend(motifs)
    if converti:
        avertissements.append(PERIMETRE_INVERSION)
    profil['avertissements'] = avertissements
    return profil


# ── CALX255 — le profil de consommation depuis le DOCUMENT (atelier) ─────
#
# LE CONSTAT : ce module ne savait partir que des factures du lead
# (``profil_depuis_lead``) ou d'un CSV importé (``apercu_courbe_csv``) ;
# rien ne lisait ``Calepinage.roof_layout``, donc la courbe horaire SAISIE
# dans l'atelier (CALX251 : clé racine ``consumption`` du contrat
# ``roof_layout`` v2 — ``courbe24``, ``saisons``, ``appareils``, ``methode``,
# ``source``) n'atteignait jamais les services de charges
# (``autoconsommation.py`` / ``batterie.py``). Parité : HelioScope importe une
# courbe de consommation en CSV et la republie telle quelle (aucune moyenne
# inventée) — https://help-center.helioscope.com/hc/en-us/articles/
# 8644788320659-How-to-create-a-CSV-with-consumption-data.
#
# LA RÈGLE : la courbe de l'atelier est déjà une SAISIE — rien n'est déduit
# ni moyenné ici. Un document sans ``consumption`` (ou sans ``courbe24``)
# rend un profil VIDE (``courbe24: None``) avec son motif, JAMAIS un repli
# sur une autre source. Une courbe dont la longueur n'est pas 24 est REFUSÉE
# en NOMMANT le champ fautif (``consumption.courbe24``).

def _verifier_courbe24(courbe24, *, champ, quoi=''):
    """Refuse une courbe horaire qui ne compte pas 24 valeurs, en NOMMANT le
    champ — jamais tronquée ni complétée (règle CALX255, partagée CALX260)."""
    if courbe24 is not None and len(courbe24) != 24:
        raise ProfilInvalide(
            f'La courbe horaire {quoi}(« {champ} ») '
            f'compte {len(courbe24)} valeur(s) au lieu de 24 : elle est '
            'refusée plutôt que tronquée ou complétée.',
            champ=champ)


def profil_depuis_layout(layout, *, saisies=None):
    """Le profil de consommation depuis le document ATELIER (``roof_layout``).

    Args:
        layout: le document du calepinage (``dict``) — porte, s'il existe,
            la clé racine ``consumption`` du contrat v2 (CALX251) :
            ``courbe24`` (24 valeurs horaires kWh/h), ``methode``
            (``'facture'``/``'courbe'``/``'appareils'``), ``saisons``,
            ``appareils``, ``source``.
        saisies: réservé pour la cohérence de signature avec
            :func:`profil_depuis_lead` — la courbe de l'atelier EST déjà la
            saisie du client, aucune correction manuelle n'est câblée ici
            (aucun comportement n'est inventé pour ce paramètre tant qu'un
            besoin réel ne le motive pas).

    Returns:
        dict — ``courbe24`` (les 24 valeurs horaires, ou ``None``),
        ``pas_minutes`` (60 dès qu'une courbe existe, sinon ``None``),
        ``total_kwh``, ``methode`` (reprise TELLE QUELLE du document),
        ``source`` (toujours ``'layout'`` — la provenance de ce profil),
        ``avertissements``.

    Raises:
        ProfilInvalide: ``consumption.courbe24`` d'une longueur différente
            de 24, en NOMMANT le champ — jamais tronquée ni complétée.
    """
    consumption = (layout or {}).get('consumption') or {}
    courbe24 = consumption.get('courbe24')

    _verifier_courbe24(courbe24, champ='consumption.courbe24',
                       quoi="de l'atelier ")

    if not consumption or courbe24 is None:
        return {
            'courbe24': None,
            'pas_minutes': None,
            'total_kwh': None,
            'methode': consumption.get('methode'),
            'source': 'layout',
            'avertissements': [
                "Aucune courbe de consommation saisie dans l'atelier "
                "(document sans « consumption.courbe24 ») : le profil "
                'reste VIDE — aucun repli sur une autre source ni aucune '
                'moyenne inventée.'],
        }

    return {
        'courbe24': [float(valeur) for valeur in courbe24],
        'pas_minutes': 60,
        'total_kwh': round(sum(float(valeur) for valeur in courbe24), 4),
        'methode': consumption.get('methode'),
        'source': 'layout',
        'avertissements': [],
    }


# ── CALX256 — la méthode « somme d'appareils », provenance par appareil ──
#
# LE CONSTAT : le calculateur d'appareils vivait entièrement dans le
# navigateur (``apps/web/src/scripts/roofPro11/consumption.ts``, table
# ``APPLIANCE_TYPICALS``) ; aucun appareil n'atteignait le serveur et ce
# module n'avait aucune agrégation. Parité : PV*SOL, méthode « sum of
# pre-defined individual appliances ».
#
# LES RÈGLES :
#   * chaque appareil DÉCLARE sa provenance — ``saisi`` (le client l'a
#     donnée) ou ``table_atelier`` (valeur type de la table de l'atelier) —
#     et la seconde est publiée comme telle, jamais présentée comme un relevé ;
#   * l'énergie d'un appareil est répartie UNIFORMÉMENT sur son créneau
#     ``[startHour, endHour[`` (même convention que ``windowHours`` côté
#     atelier : le créneau peut traverser minuit, début = fin ⇒ la journée) ;
#   * frontière d'Aurora : ajouter ou retirer un appareil ne touche PAS le
#     total annuel déjà saisi — la courbe d'appareils est NORMALISÉE sur ce
#     total et ne fournit que la répartition horaire ; l'écart entre la somme
#     des appareils et ce total est PUBLIÉ (les deux nombres et le pourcentage),
#     jamais absorbé en silence.

#: Provenances admises pour un appareil.
PROVENANCES_APPAREIL = ('saisi', 'table_atelier')

#: Ce que chaque provenance veut dire, publié avec l'appareil.
MENTIONS_PROVENANCE = {
    'saisi': 'valeur saisie',
    'table_atelier': "valeur type de l'atelier, non mesurée",
}


def _energie_positive(valeur, *, champ, quoi):
    """Une énergie lisible, finie et ≥ 0 — sinon refus NOMMANT le champ."""
    refus = ProfilInvalide(
        f'« {champ} » doit être {quoi} positive ou nulle (reçu : '
        f'{valeur!r}).', champ=champ)
    if isinstance(valeur, bool) or valeur in (None, ''):
        raise refus
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise refus
    if not math.isfinite(nombre) or nombre < 0:
        raise refus
    return nombre


def _entier_appareil(appareil, cle, *, rang, borne_max):
    champ = f'appareils[{rang}].{cle}'
    valeur = appareil.get(cle)
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ProfilInvalide(
            f'« {champ} » doit être un entier (reçu : {valeur!r}).',
            champ=champ)
    if valeur != int(valeur) or not 0 <= valeur <= borne_max:
        raise ProfilInvalide(
            f'« {champ} » doit être un entier entre 0 et {borne_max} '
            f'(reçu : {valeur!r}).', champ=champ)
    return int(valeur)


def _creneau(debut, fin, longueur):
    """Pas couverts par ``[debut, fin[`` — port de ``windowHours`` (atelier)."""
    duree = (fin - debut) % longueur or longueur
    return [(debut + pas) % longueur for pas in range(duree)]


def _appareil_valide(appareil, *, rang, longueur):
    if not isinstance(appareil, dict):
        raise ProfilInvalide(
            f'« appareils[{rang}] » doit être un objet (reçu : '
            f'{appareil!r}).', champ=f'appareils[{rang}]')
    provenance = appareil.get('provenance')
    if provenance not in PROVENANCES_APPAREIL:
        raise ProfilInvalide(
            f'« appareils[{rang}].provenance » est obligatoire, parmi '
            f'{", ".join(PROVENANCES_APPAREIL)} (reçu : {provenance!r}).',
            champ=f'appareils[{rang}].provenance')
    energie = _energie_positive(
        appareil.get('dailyKwh'), champ=f'appareils[{rang}].dailyKwh',
        quoi='une énergie journalière')
    debut = _entier_appareil(appareil, 'startHour', rang=rang,
                             borne_max=longueur - 1)
    fin = _entier_appareil(appareil, 'endHour', rang=rang,
                           borne_max=longueur)
    return {
        'kind': appareil.get('kind'),
        'label': appareil.get('label'),
        'dailyKwh': energie,
        'startHour': debut,
        'endHour': fin,
        'billing': appareil.get('billing'),
        'source': provenance,
        'mention': MENTIONS_PROVENANCE[provenance],
        'creneau': _creneau(debut, fin, longueur),
    }


def courbe_appareils(appareils, *, longueur=24, total_annuel_kwh=None):
    """La courbe journalière composée par la somme des appareils déclarés.

    Args:
        appareils: ``[{kind, label, dailyKwh, startHour, endHour, billing,
            provenance}]`` — ``provenance`` ∈ :data:`PROVENANCES_APPAREIL`
            OBLIGATOIRE pour chacun. Les heures sont des indices de pas
            (des heures quand ``longueur`` vaut 24).
        longueur: le nombre de pas de la journée type.
        total_annuel_kwh: le total annuel DÉJÀ SAISI par ailleurs (facture,
            relevé). Présent ⇒ la courbe est normalisée sur lui (les appareils
            ne donnent que la répartition) et l'écart est publié ; absent ⇒ la
            courbe est la somme brute des appareils.

    Returns:
        dict — ``courbe`` (``longueur`` valeurs kWh, ou ``None``),
        ``total_appareils_kwh_jour``, ``total_journalier_kwh``,
        ``normalisation`` (``None`` sans total saisi), ``appareils`` (chacun
        publié avec ``source``, ``mention`` et ``creneau``),
        ``avertissements``.

    Raises:
        ProfilInvalide: appareil sans ``provenance`` valide, énergie ou heure
            illisible, total saisi négatif — en NOMMANT le champ
            (``appareils[0].provenance``…).
    """
    if isinstance(longueur, bool) or not isinstance(longueur, int) \
            or longueur <= 0:
        raise ProfilInvalide(
            f'« longueur » doit être un entier positif (reçu : '
            f'{longueur!r}).', champ='longueur')
    publies = [_appareil_valide(appareil, rang=rang, longueur=longueur)
               for rang, appareil in enumerate(appareils or [])]

    avertissements = []
    brute = [0.0] * longueur
    for appareil in publies:
        part = appareil['dailyKwh'] / len(appareil['creneau'])
        for pas in appareil['creneau']:
            brute[pas] += part
    somme_jour = sum(appareil['dailyKwh'] for appareil in publies)

    if not publies:
        avertissements.append(
            'Aucun appareil déclaré : aucune répartition horaire à publier.')
        courbe = None
    else:
        courbe = brute

    normalisation = None
    if total_annuel_kwh is not None:
        total_annuel_kwh = _energie_positive(
            total_annuel_kwh, champ='total_annuel_kwh',
            quoi='une énergie annuelle')
        from .pompage import JOURS_PAR_MOIS
        jours = sum(JOURS_PAR_MOIS)
        somme_annuelle = somme_jour * jours
        ecart_pct = (round((somme_annuelle - total_annuel_kwh)
                           / total_annuel_kwh * 100, 1)
                     if total_annuel_kwh > 0 else None)
        normalisation = {
            'total_annuel_saisi_kwh': total_annuel_kwh,
            'total_appareils_annuel_kwh': round(somme_annuelle, 4),
            'ecart_pct': ecart_pct,
            'jours_par_an': jours,
        }
        if courbe is not None and somme_jour <= 0:
            courbe = None
            avertissements.append(
                "Les appareils déclarés ne consomment rien : ils ne donnent "
                'aucune répartition horaire du total saisi.')
        elif courbe is not None:
            facteur = total_annuel_kwh / jours / somme_jour
            courbe = [valeur * facteur for valeur in brute]
            if ecart_pct:
                avertissements.append(
                    f'La somme des appareils ({round(somme_annuelle, 1)} '
                    f"kWh/an) s'écarte de {ecart_pct:+.1f} % du total saisi "
                    f'({total_annuel_kwh} kWh/an) : la courbe garde '
                    'le total saisi, les appareils ne donnent que la '
                    'répartition horaire.')

    if any(appareil['source'] == 'table_atelier' for appareil in publies):
        avertissements.append(
            "Certains appareils portent une valeur type de l'atelier, non "
            'mesurée : elle ne remplace pas un relevé.')

    return {
        'courbe': (None if courbe is None
                   else [round(valeur, 4) for valeur in courbe]),
        'longueur': longueur,
        'total_appareils_kwh_jour': round(somme_jour, 4),
        'total_journalier_kwh': (None if courbe is None
                                 else round(sum(courbe), 4)),
        'normalisation': normalisation,
        'appareils': publies,
        'avertissements': avertissements,
    }


# ── CALX260 — le Ramadan décale la courbe, sans un seul chiffre neuf ─────
#
# LE CONSTAT : ``apps/ventes/ramadan.py`` porte les plages 2025→2033, le
# calcul solaire de l'imsak/iftar et ``part_ramadan_par_mois`` ; aucun module
# du calepinage ne l'importait — la consommation ignorait un mois entier de
# décalage d'horloge. Parité : PV*SOL, variation des profils de charge selon
# les jours particuliers.
#
# LA RÈGLE : TOUT est relu — la plage dans ``apps.ventes.ramadan`` (jamais
# une seconde table ; aucun sélecteur de ``ventes`` ne l'expose, d'où l'import
# fonction-local de ce module utilitaire PUR), l'heure légale dans la base de
# fuseaux par ``ramadan.decalage_maroc_h``. Aucune heure n'est écrite ici
# (garde : ``tests/test_calx260_ramadan_conso.py``).
#
# LE DÉCALAGE est l'écart d'HORLOGE entre le jour demandé et l'horloge
# ORDINAIRE : un foyer garde ses habitudes à l'heure de sa montre ; quand la
# montre recule, ces habitudes tombent plus tard sur l'horloge ordinaire. La
# date d'horloge ordinaire est prise AUTANT DE JOURS AVANT le début du
# Ramadan qu'il en dure : hors de la fenêtre de changement d'heure (qui ne
# l'encadre que de quelques jours) et loin du Ramadan précédent. Depuis le
# 20/09/2026 (décret n° 2.26.530) la base de fuseaux ne connaît plus de
# changement d'heure : l'écart est alors nul et la courbe rendue telle quelle.
#
# LE REPÈRE : la courbe rendue est exprimée sur l'horloge ORDINAIRE. Une série
# météo déjà alignée date par date sur l'heure LÉGALE (CALX59) porte déjà ce
# changement d'heure : elle ne doit pas recevoir une courbe décalée ici.

def _tourner(courbe, decalage):
    """Rotation circulaire : la valeur du pas ``h`` passe au pas ``h + decalage``.

    PERMUTATION PURE — aucune valeur créée ni perdue, l'intégrale est
    conservée à l'identique.
    """
    longueur = len(courbe)
    return [courbe[(pas - decalage) % longueur] for pas in range(longueur)]


def appliquer_ramadan(courbe24, *, jour, lat=None, lon=None):
    """La courbe 24 h du jour ``jour``, décalée si ce jour tombe en Ramadan.

    Args:
        courbe24: les 24 valeurs horaires (kWh/h) sur l'horloge de la montre.
        jour: la date (``datetime.date``) à simuler.
        lat / lon: le point du chantier — servent la fenêtre imsak/iftar
            publiée (``ramadan.fenetre_ramadan``, repli documenté sans GPS).

    Returns:
        dict — ``courbe24`` (hors Ramadan : la MÊME liste de valeurs),
        ``dans_ramadan``, ``decalage_h`` (lu dans la base de fuseaux ;
        ``None`` hors Ramadan — aucun décalage n'y est calculé),
        ``hijri``, ``part_du_mois`` (part du mois de ``jour`` passée en
        Ramadan, ``ramadan.part_ramadan_par_mois``), ``fuseau`` (nom + mention
        du décalage légal), ``fenetre`` (imsak/iftar ou ``None``), ``repere``,
        ``avertissements``.

    Raises:
        ProfilInvalide: ``courbe24`` d'une autre longueur que 24 ou ``jour``
            qui n'est pas une date — en NOMMANT le champ.
    """
    from datetime import date

    from apps.parametres.pvgis_profils import FUSEAU_MAROC
    from apps.ventes import ramadan

    _verifier_courbe24(courbe24, champ='courbe24')
    if courbe24 is None:
        raise ProfilInvalide(
            '« courbe24 » est obligatoire : aucune courbe à décaler.',
            champ='courbe24')
    if not isinstance(jour, date):
        raise ProfilInvalide(
            f'« jour » doit être une date (reçu : {jour!r}).', champ='jour')

    parts = ramadan.part_ramadan_par_mois(jour)
    trouve = ramadan.plage_ramadan_pour(jour)
    resultat = {
        'courbe24': list(courbe24),
        'dans_ramadan': False,
        'decalage_h': None,
        'hijri': None,
        'part_du_mois': (dict(zip(MOIS, parts)).get(jour.month)
                         if parts else None),
        'fuseau': None,
        'fenetre': None,
        'repere': "horloge ordinaire (heure légale hors Ramadan)",
        'avertissements': [],
    }
    if trouve is None:
        resultat['avertissements'].append(
            'Date au-delà de la table des plages du Ramadan '
            '(apps.ventes.ramadan) : la courbe est rendue telle quelle.')
        return resultat
    plage, dedans = trouve
    if not dedans:
        return resultat

    ordinaire = plage['debut'] - (plage['fin'] - plage['debut'])
    heure_jour = ramadan.decalage_maroc_h(jour)
    heure_ordinaire = ramadan.decalage_maroc_h(ordinaire)
    decalage = heure_ordinaire - heure_jour
    resultat.update({
        'dans_ramadan': True,
        'decalage_h': decalage,
        'hijri': plage['hijri'],
        'fuseau': {
            'nom': FUSEAU_MAROC,
            'utc_jour_h': heure_jour,
            'utc_ordinaire_h': heure_ordinaire,
            'mention': (
                f'Heure légale « {FUSEAU_MAROC} » : UTC{heure_jour:+d} ce '
                f'jour-là, UTC{heure_ordinaire:+d} en temps ordinaire '
                '(base de fuseaux IANA).'),
        },
        'fenetre': ramadan.fenetre_ramadan(jour, lat=lat, lon=lon),
    })
    if decalage:
        resultat['courbe24'] = _tourner(list(courbe24), decalage)
    else:
        resultat['avertissements'].append(
            "La base de fuseaux ne prévoit aucun changement d'heure pendant "
            'ce Ramadan : la courbe est rendue telle quelle.')
    return resultat


# ── CAL148 — import d'une courbe de charge HORAIRE en CSV ────────────────
#
# LE CONSTAT : ``load_curve_from_xlsx`` (``apps/ventes/solar_design.py``)
# n'accepte qu'un classeur Excel, alors que les relevés de compteur arrivent
# en CSV, au pas horaire ou au pas de 15 minutes, avec des séparateurs et des
# décimales qui changent d'un distributeur à l'autre.
#
# LES RÈGLES :
#   * le séparateur et la décimale sont DÉTECTÉS puis PUBLIÉS (on dit ce
#     qu'on a compris, pour qu'un import de travers se voie tout de suite) ;
#   * la colonne est CHOISIE (par son nom) ; plusieurs colonnes chiffrées et
#     aucun choix ⇒ refus EN LES LISTANT ;
#   * une ligne illisible ⇒ erreur NOMMANT la ligne et la colonne. Jamais un
#     zéro silencieux : un zéro se lit « ce client n'a rien consommé » ;
#   * un pas de 15 minutes est agrégé à l'heure, et l'unité (kWh par pas, ou
#     kW instantané) est DÉCLARÉE — pas devinée : additionner des kW gonfle le
#     total d'un facteur 4 sans qu'aucun contrôle ne le voie ;
#   * APERÇU d'abord : ``apercu_courbe_csv`` analyse et rend le total annuel
#     pour contrôle. Rien n'est écrit.

#: Les séparateurs candidats, dans l'ordre où on les essaie.
SEPARATEURS_CANDIDATS = (';', '\t', ',', '|')

#: Nombre de points attendus selon le pas (année pleine ou bissextile).
POINTS_ATTENDUS = {
    60: (8760, 8784),
    15: (35040, 35136),
}

#: Les unités ADMISES pour la colonne de valeurs.
UNITES = ('kwh', 'kw')


class ImportCourbeInvalide(ValueError):
    """Un import de courbe refusé — ligne et colonne NOMMÉES."""

    def __init__(self, message, *, champ='', ligne=None):
        super().__init__(message)
        self.champ = champ
        self.ligne = ligne
        self.motif = message


def _est_chiffre(cellule):
    texte = (cellule or '').strip().replace(' ', '').replace(',', '.')
    if not texte:
        return False
    try:
        float(texte)
    except ValueError:
        return False
    return True


def _cellule(ligne, rang):
    return ligne[rang] if rang < len(ligne) else ''


def _detecter_separateur(lignes_brutes):
    """Le séparateur qui découpe le plus de colonnes, de façon CONSTANTE."""
    echantillon = [ligne for ligne in lignes_brutes[:20] if ligne.strip()]
    if not echantillon:
        raise ImportCourbeInvalide(
            'Le fichier est vide : aucune courbe de charge à importer.',
            champ='fichier')
    meilleur, colonnes_max = None, 1
    for candidat in SEPARATEURS_CANDIDATS:
        comptes = {ligne.count(candidat) for ligne in echantillon}
        if len(comptes) == 1 and comptes != {0}:
            colonnes = comptes.pop() + 1
            if colonnes > colonnes_max:
                meilleur, colonnes_max = candidat, colonnes
    # Fichier à UNE colonne : aucun séparateur ne départage, on en pose un
    # pour le lecteur CSV — et on le publie quand même, sans prétendre
    # l'avoir détecté.
    return meilleur or ';'


def _detecter_decimale(cellules, separateur):
    """``,`` ou ``.`` — déduit des cellules lues, jamais supposé.

    Quand le séparateur EST la virgule, la décimale ne peut pas l'être.
    """
    if separateur == ',':
        return '.'
    avec_virgule = sum(1 for cellule in cellules if ',' in cellule)
    avec_point = sum(1 for cellule in cellules if '.' in cellule)
    return ',' if avec_virgule > avec_point else '.'


def _nombre_de_cellule(cellule, *, decimale, ligne, colonne):
    texte = (cellule or '').strip().replace(' ', '').replace(' ', '')
    if texte == '':
        raise ImportCourbeInvalide(
            f'Ligne {ligne}, colonne « {colonne} » : la valeur est vide. '
            'Une ligne sans mesure est refusée — elle ne devient jamais un '
            'zéro de consommation.', champ=colonne, ligne=ligne)
    if decimale == ',':
        texte = texte.replace('.', '').replace(',', '.')
    try:
        nombre = float(texte)
    except ValueError:
        raise ImportCourbeInvalide(
            f'Ligne {ligne}, colonne « {colonne} » : valeur illisible '
            f'(« {cellule} »).', champ=colonne, ligne=ligne)
    if nombre != nombre:
        raise ImportCourbeInvalide(
            f'Ligne {ligne}, colonne « {colonne} » : valeur illisible '
            f'(« {cellule} »).', champ=colonne, ligne=ligne)
    if nombre < 0:
        raise ImportCourbeInvalide(
            f'Ligne {ligne}, colonne « {colonne} » : une consommation ne '
            f'peut pas être négative (« {cellule} »).',
            champ=colonne, ligne=ligne)
    return nombre


def _entete_et_corps(table, colonne_demandee):
    """Repère l'en-tête, choisit la colonne : ``(nom, rang, corps, décalage)``.

    ``décalage`` est le numéro de la PREMIÈRE ligne de mesure dans le fichier
    — c'est lui qui rend les messages d'erreur pointables à l'œil.
    """
    premiere = table[0]
    sans_entete = all(_est_chiffre(cellule) for cellule in premiere
                      if cellule.strip())
    if sans_entete:
        if isinstance(colonne_demandee, str) and colonne_demandee.strip():
            raise ImportCourbeInvalide(
                "Le fichier n'a pas d'en-tête : la colonne "
                f'« {colonne_demandee} » ne peut pas être désignée par son '
                'nom. Donnez son rang (0, 1, …).', champ='colonne')
        rang = int(colonne_demandee or 0)
        if rang >= len(premiere):
            raise ImportCourbeInvalide(
                f'Le fichier ne porte que {len(premiere)} colonne(s) : le '
                f'rang {rang} n\'existe pas.', champ='colonne')
        return f'colonne {rang}', rang, table, 1

    entetes = [cellule.strip() for cellule in premiere]
    corps = table[1:]
    if colonne_demandee not in (None, ''):
        nom = str(colonne_demandee).strip()
        if nom not in entetes:
            raise ImportCourbeInvalide(
                f'Colonne « {nom} » absente du fichier. Colonnes présentes : '
                f'{", ".join(entetes)}.', champ='colonne')
        return nom, entetes.index(nom), corps, 2
    candidates = [rang for rang in range(len(entetes))
                  if corps and _est_chiffre(_cellule(corps[0], rang))]
    if len(candidates) != 1:
        presentes = ', '.join(entetes[rang] for rang in candidates)
        raise ImportCourbeInvalide(
            'Plusieurs colonnes chiffrées sont présentes '
            f'({presentes or "aucune"}) : précisez laquelle porte la '
            'consommation.', champ='colonne')
    return entetes[candidates[0]], candidates[0], corps, 2


def apercu_courbe_csv(contenu, *, colonne=None, unite='kwh', origine=''):
    """APERÇU d'un import de courbe de charge — analyse, rien n'est écrit.

    Args:
        contenu: le texte du CSV (déjà décodé).
        colonne: le nom de la colonne de consommation (ou son rang si le
            fichier n'a pas d'en-tête). Absent ⇒ déduit s'il n'y a qu'une
            seule colonne chiffrée, refusé sinon.
        unite: ``kwh`` (énergie PAR PAS — le cas des relevés) ou ``kw``
            (puissance instantanée). Déclarée, jamais devinée.
        origine: d'où vient le fichier (nom, distributeur…) — republiée telle
            quelle avec la courbe.

    Returns:
        dict — ``valeurs`` (série HORAIRE), ``pas_minutes`` d'origine,
        ``total_annuel_kwh`` pour contrôle, ``separateur``, ``decimale``,
        ``colonne``, ``unite``, ``origine``.

    Raises:
        ImportCourbeInvalide: fichier vide, colonne ambiguë ou absente, ligne
            illisible (ligne ET colonne nommées), nombre de points inattendu.
    """
    import csv as _csv
    import io as _io

    if unite not in UNITES:
        raise ImportCourbeInvalide(
            f'Unité inconnue : « {unite} ». Unités admises : '
            f'{", ".join(UNITES)}.', champ='unite')
    texte = (contenu or '').lstrip('﻿')
    separateur = _detecter_separateur(texte.splitlines())
    table = [ligne for ligne in
             _csv.reader(_io.StringIO(texte), delimiter=separateur)
             if any(cellule.strip() for cellule in ligne)]
    if not table:
        raise ImportCourbeInvalide(
            'Le fichier est vide : aucune courbe de charge à importer.',
            champ='fichier')

    nom_colonne, rang, corps, decalage = _entete_et_corps(table, colonne)
    if not corps:
        raise ImportCourbeInvalide(
            'Le fichier ne porte aucune ligne de mesure.', champ='fichier')
    decimale = _detecter_decimale(
        [_cellule(ligne, rang) for ligne in corps[:50]], separateur)

    valeurs = [
        _nombre_de_cellule(_cellule(ligne, rang), decimale=decimale,
                           ligne=numero + decalage, colonne=nom_colonne)
        for numero, ligne in enumerate(corps)
    ]

    pas_minutes = None
    for pas, tailles in POINTS_ATTENDUS.items():
        if len(valeurs) in tailles:
            pas_minutes = pas
            break
    if pas_minutes is None:
        attendus = sorted(taille for tailles in POINTS_ATTENDUS.values()
                          for taille in tailles)
        raise ImportCourbeInvalide(
            f'Le fichier porte {len(valeurs)} mesures : une courbe de charge '
            f'annuelle en compte {" ou ".join(str(n) for n in attendus)} '
            "(pas horaire ou pas de 15 minutes). Aucune valeur n'est "
            'complétée ni tronquée automatiquement.', champ='fichier')

    horaires = _a_lheure(valeurs, pas_minutes=pas_minutes, unite=unite)
    return {
        'valeurs': horaires,
        'pas_minutes': pas_minutes,
        'unite': unite,
        'colonne': nom_colonne,
        'separateur': separateur,
        'decimale': decimale,
        'origine': origine or 'non renseignée',
        'points_lus': len(valeurs),
        'total_annuel_kwh': round(sum(horaires), 1),
        'avertissements': [
            "Aperçu seulement : rien n'est enregistré tant que l'import "
            "n'est pas confirmé.",
        ],
    }


def _a_lheure(valeurs, *, pas_minutes, unite):
    """Ramène la série au pas HORAIRE, selon l'unité DÉCLARÉE.

    * ``kwh`` (énergie par pas) : les quatre quarts d'heure s'ADDITIONNENT ;
    * ``kw`` (puissance instantanée) : ils se MOYENNENT (kW moyen × 1 h =
      kWh de l'heure).
    """
    if pas_minutes == 60:
        return [round(valeur, 4) for valeur in valeurs]
    heures = []
    for depart in range(0, len(valeurs), 4):
        paquet = valeurs[depart:depart + 4]
        heures.append(round(sum(paquet) if unite == 'kwh'
                            else sum(paquet) / len(paquet), 4))
    return heures
