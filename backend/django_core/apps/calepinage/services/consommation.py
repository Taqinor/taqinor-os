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
   sa raison, jamais un kWh dérivé d'un prix moyen supposé.
"""
from __future__ import annotations

__all__ = ['ImportCourbeInvalide', 'ProfilInvalide', 'SOURCES_MOIS',
           'UNITES', 'apercu_courbe_csv', 'interpoler_factures',
           'profil_depuis_lead', 'profil_mensuel']

#: D'où vient le montant d'un mois. ``None`` = mois vide (rien de connu).
SOURCES_MOIS = ('facture', 'interpole', 'saisi')

MOIS = tuple(range(1, 13))

#: Les deux mois que le CRM saisit RÉELLEMENT : janvier porte la facture
#: d'hiver, juillet la facture d'été (indices 0 et 6 de la règle de l'écran
#: devis, reprise à l'identique ci-dessous).
MOIS_FACTURE_HIVER = 1
MOIS_FACTURE_ETE = 7


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
    avertissements.append(
        'Les montants sont en MAD par mois. La conversion en kWh dépend du '
        'barème du distributeur : elle n\'est pas faite ici, et « kwh » reste '
        '« non calculé » plutôt qu\'estimé à partir d\'un prix moyen.')

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
