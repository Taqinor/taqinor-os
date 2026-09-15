"""VISITE-CADENCE — le VOCABULAIRE FERMÉ de la qualification de fin de visite.

Ordre fondateur du 15/09/2026. Le commercial terrain est le seul de la boîte à
avoir vu le client CHEZ LUI : ce qu'il a compris en une heure sur place — « il
est chaud », « il décide avec sa femme », « il compare deux devis », « ce qui
l'a accroché, ce sont les coupures » — ne s'écrit nulle part ailleurs, et c'est
exactement ce que le responsable doit savoir avant de rappeler.

Ce module est la SEULE autorité sur ce vocabulaire :

* il DÉCLARE les valeurs admises, champ par champ (aucune n'est devinée
  ailleurs, ni côté API, ni côté chatter) ;
* il VALIDE une saisie et rend ``{champ: [message FR]}`` — chaque refus NOMME
  son champ (règle fondateur du 08/09/2026), jamais un « non enregistré »
  générique ;
* il porte les LIBELLÉS FR validés par le fondateur, qui composent la phrase
  posée au chatter du lead. Les libellés vivent ICI et non dans ``apps.crm`` :
  c'est cette app qui possède le vocabulaire ; le CRM se contente de rendre la
  phrase (frontière M3 — il lit un sélecteur, il ne réinvente pas un référentiel).

Rien ici n'émet de JUGEMENT automatique : « Client chaud » est la lecture d'un
humain qui était sur place, pas un score calculé.
"""

#: Valeurs admises par champ à vocabulaire fermé, DANS L'ORDRE d'affichage.
CHOIX = {
    'temperature': ('chaud', 'tiede', 'froid'),
    'devis': ('convient', 'a_modifier', 'nouveau'),
    'decideur': ('seul', 'conjoint_famille', 'associe_direction'),
    'frein': ('aucun', 'prix', 'compare', 'timing', 'technique', 'confiance'),
    'declencheur': ('economies', 'coupures', 'ecologie', 'technologie'),
    'rappel': ('demain_matin', 'demain_soir', 'cette_semaine'),
}

#: Libellés FR validés par le fondateur. Ils composent, dans l'ordre des clés
#: de ``CHOIX``, la phrase « Qualification : … » du chatter.
LIBELLES = {
    'temperature': {
        'chaud': 'Client chaud — prêt à signer',
        'tiede': 'Client tiède',
        'froid': 'Client froid',
    },
    'devis': {
        # Les deux dernières portent un « {details} » : le détail saisi par le
        # terrain est OBLIGATOIRE dans ces deux cas (voir ``valider``) — « à
        # modifier » sans dire quoi ne serait pas une information.
        'convient': 'Le devis convient',
        'a_modifier': 'Devis à modifier : {details}',
        'nouveau': 'Veut un nouveau devis : {details}',
    },
    'decideur': {
        'seul': 'Décide seul',
        'conjoint_famille': 'Décide avec conjoint/famille',
        'associe_direction': 'Décide avec associé/direction',
    },
    'frein': {
        'aucun': 'Frein : aucun',
        'prix': 'Frein : prix',
        'compare': "Frein : compare d'autres devis",
        'timing': 'Frein : timing',
        'technique': 'Frein : technique',
        'confiance': 'Frein : confiance',
    },
    'declencheur': {
        'economies': "L'a accroché : les économies",
        'coupures': "L'a accroché : les coupures/autonomie",
        'ecologie': "L'a accroché : l'écologie",
        'technologie': "L'a accroché : la technologie",
    },
    'rappel': {
        'demain_matin': 'Rappeler demain matin',
        'demain_soir': 'Rappeler demain soir',
        'cette_semaine': 'Rappeler cette semaine',
    },
}

#: Les valeurs de ``devis`` qui EXIGENT un détail écrit — et qui changent la
#: suite commerciale : la prochaine chose à faire n'est plus de rappeler, c'est
#: de préparer le devis corrigé.
DEVIS_A_REPRENDRE = ('a_modifier', 'nouveau')

#: Bornes des deux champs LIBRES. Ce ne sont pas des limites techniques : une
#: qualification est une phrase de terrain, pas un rapport — et elle part dans
#: l'historique d'un lead, qui doit rester lisible.
MAX_DEVIS_DETAILS = 300
MAX_CONSEIL = 500

#: Champs libres, avec leur borne.
CHAMPS_LIBRES = {
    'devis_details': MAX_DEVIS_DETAILS,
    'conseil_closing': MAX_CONSEIL,
}

#: Étiquettes FR des champs, pour les messages d'erreur.
NOMS = {
    'temperature': 'température du client',
    'devis': 'sort du devis',
    'devis_details': 'détail du devis à reprendre',
    'decideur': 'qui décide',
    'frein': 'frein principal',
    'declencheur': 'ce qui a accroché',
    'rappel': 'moment du rappel',
    'conseil_closing': 'conseil de closing',
}

_CHAMPS_CONNUS = set(CHOIX) | set(CHAMPS_LIBRES)


def valider(brut):
    """Valide une qualification. Renvoie ``(propre, erreurs)``.

    ``erreurs`` est le dict ``{champ: [message FR]}`` servi tel quel en 400 —
    chaque message NOMME son champ. Rien n'est écrit tant qu'une seule valeur
    est refusée : la qualification part entière ou pas du tout.

    Les six champs à vocabulaire fermé sont OBLIGATOIRES (l'écran les pose
    tous, avec ses propres défauts : une qualification à trous ne dirait rien
    au responsable qui la lit). ``devis_details`` est obligatoire — et non vide
    — dès que le devis est « à modifier » ou « nouveau » ; ``conseil_closing``
    reste facultatif.

    Un champ INCONNU est refusé plutôt qu'ignoré : l'écran et le serveur
    doivent parler exactement le même vocabulaire, sinon une case cochée sur le
    téléphone se perd en silence.
    """
    if not isinstance(brut, dict):
        return None, {'qualification': [
            'La qualification doit être un objet {champ: valeur}.']}

    erreurs = {}
    for champ in sorted(set(brut) - _CHAMPS_CONNUS):
        erreurs[champ] = [
            f'Champ inconnu dans la qualification « {champ} ».']

    propre = {}
    for champ, valeurs in CHOIX.items():
        valeur = brut.get(champ)
        if valeur in (None, ''):
            erreurs[champ] = [f'Le champ « {NOMS[champ]} » est obligatoire.']
            continue
        if valeur not in valeurs:
            erreurs[champ] = [
                f'Valeur inconnue pour « {NOMS[champ]} » : « {valeur} ». '
                'Choix possibles : ' + ', '.join(valeurs) + '.']
            continue
        propre[champ] = valeur

    for champ, borne in CHAMPS_LIBRES.items():
        texte = brut.get(champ)
        if texte in (None, ''):
            propre[champ] = ''
            continue
        if not isinstance(texte, str):
            erreurs[champ] = [f'Le champ « {NOMS[champ]} » attend du texte.']
            continue
        texte = texte.strip()
        if len(texte) > borne:
            erreurs[champ] = [
                f'Le champ « {NOMS[champ]} » dépasse {borne} caractères '
                f'({len(texte)}).']
            continue
        propre[champ] = texte

    if (propre.get('devis') in DEVIS_A_REPRENDRE
            and not propre.get('devis_details')
            and 'devis_details' not in erreurs):
        erreurs['devis_details'] = [
            'Dites ce qu\'il faut reprendre dans le devis : « à modifier » '
            'sans le détail ne dit rien à qui rappellera.']

    if erreurs:
        return None, erreurs
    return propre, {}


def phrase(qualification):
    """La phrase FR « Qualification : … » posée au chatter du lead, ou ``''``.

    Composée ICI parce que le vocabulaire vit ici : le CRM ne doit jamais
    redéclarer une table de libellés qui dériverait du jour où le fondateur
    reformule un choix. Une qualification absente rend une chaîne VIDE, et
    l'appelant n'écrit alors aucune ligne — jamais une phrase à trous.
    """
    if not isinstance(qualification, dict) or not qualification:
        return ''
    details = (qualification.get('devis_details') or '').strip()
    morceaux = []
    for champ in CHOIX:
        valeur = qualification.get(champ)
        libelle = LIBELLES[champ].get(valeur)
        if not libelle:
            continue
        morceaux.append(libelle.replace('{details}', details))
    if not morceaux:
        return ''
    return 'Qualification : ' + ' · '.join(morceaux) + '.'


def conseil(qualification):
    """La ligne « Conseil : … », ou ``''`` quand le terrain n'en a pas laissé."""
    if not isinstance(qualification, dict):
        return ''
    texte = (qualification.get('conseil_closing') or '').strip()
    return f'Conseil : {texte}' if texte else ''


def devis_a_reprendre(qualification):
    """Vrai si le devis doit être repris (modifié ou refait)."""
    if not isinstance(qualification, dict):
        return False
    return qualification.get('devis') in DEVIS_A_REPRENDRE


def jours_avant_rappel(qualification, defaut=1):
    """Dans combien de jours rappeler, selon le moment choisi sur place.

    « demain matin » et « demain soir » valent tous deux DEMAIN : la file de
    relance a un grain JOUR (``due_date``), et l'heure exacte se recale de
    toute façon sur la fenêtre d'appel de la société. « cette semaine » vaut
    trois jours — le client a dit qu'il ne fallait pas le presser."""
    if not isinstance(qualification, dict):
        return defaut
    return {'demain_matin': 1, 'demain_soir': 1,
            'cette_semaine': 3}.get(qualification.get('rappel'), defaut)


def rappel_explicite(qualification):
    """Vrai si le terrain a explicitement choisi le moment du rappel.

    C'est ce choix — convenu DEVANT le client — qui autorise le CRM à
    déplacer un débrief déjà posé dans LES DEUX SENS, y compris le repousser
    (« cette semaine » = ne pas presser). Sans lui, un débrief n'est jamais
    repoussé."""
    if not isinstance(qualification, dict):
        return False
    return qualification.get('rappel') in CHOIX['rappel']
