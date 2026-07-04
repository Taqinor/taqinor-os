"""apps.pos.escpos — Pont matériel comptoir ESC/POS (XPOS18).

Générateur maison SANS nouvelle dépendance Python : construit un flux
d'octets ESC/POS brut (texte, décomposition TVA, commande coupe-papier,
impulsion ouverture tiroir-caisse). Rendu du même contenu que le ticket
XPOS3, en texte pur (largeur 42/48 colonnes selon l'imprimante).

Envoi réseau (IP:port 9100) est OPT-IN et GATED : sans
``ConfigMaterielPOS.imprimante_active`` + ``imprimante_ip`` renseignés,
``send_to_printer`` est un no-op qui ne tente AUCUNE connexion sortante.
"""
import socket
from decimal import Decimal

# Commandes ESC/POS standard.
ESC = b'\x1b'
GS = b'\x1d'
INIT = ESC + b'@'
CUT = GS + b'V' + b'\x00'          # Coupe totale.
CASH_DRAWER_KICK = ESC + b'p' + b'\x00' + b'\x19' + b'\xfa'  # Impulsion tiroir.
BOLD_ON = ESC + b'E' + b'\x01'
BOLD_OFF = ESC + b'E' + b'\x00'
ALIGN_CENTER = ESC + b'a' + b'\x01'
ALIGN_LEFT = ESC + b'a' + b'\x00'

_WIDTH = 42


def _line(text=''):
    return (text.encode('cp437', errors='replace') + b'\n')


def _rule():
    return _line('-' * _WIDTH)


def _kv(label, value, width=_WIDTH):
    label = str(label)
    value = str(value)
    pad = max(1, width - len(label) - len(value))
    return _line(f'{label}{" " * pad}{value}')


def build_ticket_escpos(vente, *, identite, paiements=None, timbre=None):
    """Construit le flux ESC/POS complet du ticket (XPOS18).

    ``identite`` : dict avec nom/adresse/telephone/ice/if_fiscal/rc/patente/
    cnss (même forme que ``pos.receipt._company_identity``). Renvoie des
    octets prêts à envoyer à une imprimante 80 mm ou à télécharger.
    """
    out = bytearray()
    out += INIT
    out += ALIGN_CENTER
    out += BOLD_ON
    out += _line(identite.get('nom', ''))
    out += BOLD_OFF
    out += _line(identite.get('adresse', ''))
    if identite.get('telephone'):
        out += _line(f"Tél : {identite['telephone']}")
    out += _line(f"ICE : {identite.get('ice', '')}  IF : {identite.get('if_fiscal', '')}")
    out += _line(f"RC : {identite.get('rc', '')}  Patente : {identite.get('patente', '')}")
    if identite.get('cnss'):
        out += _line(f"CNSS : {identite['cnss']}")
    out += ALIGN_LEFT
    out += _rule()
    out += _line(f'Ticket n° {vente.reference}')
    out += _rule()

    for ligne in vente.lignes.all():
        out += _line(ligne.designation[:_WIDTH])
        out += _kv(f'  {ligne.quantite} x {ligne.prix_unitaire_ttc}',
                   f'{ligne.total_ttc:.2f}')

    out += _rule()

    buckets = {}
    for ligne in vente.lignes.all():
        taux = ligne.taux_tva_effectif or Decimal('0')
        montant_tva = ligne.total_ttc - ligne.total_ht
        buckets[taux] = buckets.get(taux, Decimal('0')) + montant_tva
    for taux, montant in sorted(buckets.items()):
        out += _kv(f'TVA {taux}%', f'{montant:.2f}')

    out += _rule()
    out += BOLD_ON
    out += _kv('TOTAL TTC', f'{vente.total_ttc:.2f} MAD')
    out += BOLD_OFF
    out += _rule()

    if paiements:
        out += _line('Règlement(s) :')
        for p in paiements:
            mode = getattr(p, 'mode', None) or (
                p.get('mode') if isinstance(p, dict) else '')
            montant = getattr(p, 'montant', None) if not isinstance(p, dict) else p.get('montant')
            out += _kv(str(mode), f'{Decimal(montant or 0):.2f}')

    if timbre is not None:
        out += _rule()
        out += _kv('Droit de timbre', f'{timbre.montant:.2f} MAD')

    facture_ref = vente.facture.reference if vente.facture_id else ''
    if facture_ref:
        out += _rule()
        out += _line(f'Facture correspondante : {facture_ref}')

    out += _line('')
    out += _line('')
    out += CASH_DRAWER_KICK
    out += CUT
    return bytes(out)


def send_to_printer(payload, *, config):
    """Envoie ``payload`` (octets ESC/POS) vers l'imprimante réseau configurée.

    NO-OP si ``config`` est None, ``imprimante_active`` est faux, ou
    ``imprimante_ip`` est vide — AUCUNE connexion sortante n'est alors
    tentée. Renvoie True si l'envoi a été tenté et a réussi, False sinon
    (no-op ou erreur réseau — n'élève jamais)."""
    if config is None:
        return False
    if not getattr(config, 'imprimante_active', False):
        return False
    ip = (getattr(config, 'imprimante_ip', '') or '').strip()
    if not ip:
        return False
    port = getattr(config, 'imprimante_port', 9100) or 9100
    try:
        with socket.create_connection((ip, port), timeout=5) as sock:
            sock.sendall(payload)
        return True
    except OSError:
        return False
