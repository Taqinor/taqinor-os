"""Parseur de relevé bancaire au format CFONB120 (NTTRE1).

Le format CFONB-120 (« relevé de compte ») est un fichier texte à lignes FIXES
de 120 caractères, une norme interbancaire française largement supportée par les
portails bancaires marocains. Chaque ligne porte un code enregistrement en tête :

  * ``01`` — solde ancien (ignoré ici, informatif) ;
  * ``04`` — MOUVEMENT (une opération) → devient une ligne de relevé ;
  * ``05`` — complément de libellé rattaché au mouvement ``04`` précédent ;
  * ``07`` — solde nouveau (ignoré ici, informatif).

Le montant CFONB est encodé sur 14 caractères dont le DERNIER est « sur-perforé »
(overpunch COBOL) : il encode à la fois le dernier chiffre ET le signe.
  * positif : ``{ A B C D E F G H I`` pour les unités 0..9 ;
  * négatif : ``} J K L M N O P Q R`` pour les unités 0..9.
Le nombre de décimales par défaut est 2 (usage MAD/EUR).

``parser_cfonb120(file_bytes) -> list[dict]`` renvoie une liste de dicts
``{date_operation, libelle, montant, reference}`` — ``montant`` SIGNÉ (positif =
crédit/encaissement). Lève ``ValueError`` (message FR clair) si une ligne ne fait
pas la longueur fixe attendue.
"""

from datetime import datetime
from decimal import Decimal

LONGUEUR_LIGNE = 120

# Décodage de la sur-perforation CFONB (dernier caractère du montant).
_OVERPUNCH_POSITIF = {'{': '0', 'A': '1', 'B': '2', 'C': '3', 'D': '4',
                      'E': '5', 'F': '6', 'G': '7', 'H': '8', 'I': '9'}
_OVERPUNCH_NEGATIF = {'}': '0', 'J': '1', 'K': '2', 'L': '3', 'M': '4',
                      'N': '5', 'O': '6', 'P': '7', 'Q': '8', 'R': '9'}


def _decoder_montant(zone, *, decimales=2):
    """Décode une zone montant CFONB (14 car, dernier sur-perforé) → Decimal signé."""
    zone = (zone or '').strip()
    if not zone:
        return Decimal('0')
    corps, dernier = zone[:-1], zone[-1]
    signe = Decimal('1')
    if dernier in _OVERPUNCH_POSITIF:
        chiffre = _OVERPUNCH_POSITIF[dernier]
    elif dernier in _OVERPUNCH_NEGATIF:
        chiffre = _OVERPUNCH_NEGATIF[dernier]
        signe = Decimal('-1')
    elif dernier.isdigit():
        # Tolérance : dernier caractère non sur-perforé (montant positif brut).
        chiffre = dernier
    else:
        raise ValueError(
            "Caractère de montant CFONB invalide : « %s »." % dernier)
    chiffres = (corps + chiffre).lstrip('0') or '0'
    if not chiffres.isdigit():
        raise ValueError("Zone de montant CFONB non numérique.")
    valeur = Decimal(chiffres) / (Decimal(10) ** decimales)
    return signe * valeur


def _decoder_date(zone):
    """Décode une date CFONB ``JJMMAA`` → ``date`` (fenêtre 2000-2099)."""
    zone = (zone or '').strip()
    if len(zone) != 6 or not zone.isdigit():
        return None
    try:
        return datetime.strptime(zone, '%d%m%y').date()
    except ValueError:
        return None


def parser_cfonb120(file_bytes):
    """Parse un relevé CFONB120 → liste de dicts de lignes de relevé (NTTRE1).

    ``file_bytes`` : ``bytes`` (ou ``str``) du fichier. Chaque ligne DOIT faire
    120 caractères (hors saut de ligne) sinon ``ValueError`` explicite. Seuls les
    enregistrements ``04`` (mouvements) deviennent des lignes ; les ``05``
    complètent le libellé du mouvement précédent.
    """
    if isinstance(file_bytes, bytes):
        texte = file_bytes.decode('latin-1')
    else:
        texte = file_bytes or ''
    lignes = [ligne.rstrip('\r\n') for ligne in texte.splitlines() if ligne.strip()]
    resultats = []
    for numero, ligne in enumerate(lignes, start=1):
        if len(ligne) != LONGUEUR_LIGNE:
            raise ValueError(
                "Ligne %d : longueur %d ≠ %d attendue (format CFONB120 "
                "invalide)." % (numero, len(ligne), LONGUEUR_LIGNE))
        code = ligne[0:2]
        if code == '05' and resultats:
            # Complément de libellé rattaché au dernier mouvement.
            complement = ligne[48:79].strip()
            if complement:
                resultats[-1]['libelle'] = (
                    resultats[-1]['libelle'] + ' ' + complement).strip()
            continue
        if code != '04':
            continue  # 01/07 = soldes, ignorés (informatifs).
        date_op = _decoder_date(ligne[34:40])
        libelle = ligne[48:79].strip()
        reference = ligne[80:88].strip()
        montant = _decoder_montant(ligne[90:104])
        resultats.append({
            'date_operation': date_op,
            'libelle': libelle,
            'montant': montant,
            'reference': reference,
        })
    return resultats
