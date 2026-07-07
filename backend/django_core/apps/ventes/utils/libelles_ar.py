"""XSAL13 — Libellés arabes + police RTL pour les documents client-facing.

Couvre la facture legacy (`templates/pdf/facture.html`, chemin autorisé, hors
moteur premium — règle #4). Le devis one-page (moteur premium, RULE #4 :
rendu seul) est HORS PÉRIMÈTRE de cette lane ventes-pricing — laissé à une
revue dédiée `apps/ventes/quote_engine/` (voir docs/PLAN.md XSAL13).

Le dictionnaire ci-dessous ne modifie AUCUN comportement quand
`Client.langue_document != 'ar'` : le FR reste octet-identique (les gabarits
appellent `libelle(cle, langue)` qui renvoie le FR d'origine par défaut).
"""
from pathlib import Path
import base64

# Police Noto Sans Arabic déjà vendue localement pour le moteur premium
# (apps/ventes/quote_engine/assets/fonts/) — RÉFÉRENCÉE en lecture seule ici,
# jamais copiée ni le fichier ni la logique du moteur. Aucune dépendance
# réseau : le woff2 est lu depuis le disque du repo.
_FONT_DIR = (
    Path(__file__).resolve().parent.parent
    / 'quote_engine' / 'assets' / 'fonts'
)

LIBELLES = {
    'fr': {
        'facture': 'FACTURE',
        'emetteur': 'Émetteur',
        'facture_a': 'Facturé à',
        'date_emission': "Date d'émission",
        'echeance': 'Échéance',
        'tva': 'TVA',
        'statut': 'Statut',
        'designation': 'Désignation',
        'qte': 'Qté',
        'pu_ht': 'P.U HT',
        'remise': 'Remise',
        'total_ht': 'Total HT',
        'sous_total_ht': 'Sous-total HT',
        'remise_globale': 'Remise globale',
        'total_ttc': 'Total TTC',
        'note': 'Note',
        'coordonnees_bancaires': 'Coordonnées bancaires',
        'signature_cachet': 'Signature & Cachet',
    },
    'ar': {
        'facture': 'فاتورة',
        'emetteur': 'المُصدر',
        'facture_a': 'موجهة إلى',
        'date_emission': 'تاريخ الإصدار',
        'echeance': 'تاريخ الاستحقاق',
        'tva': 'الضريبة على القيمة المضافة',
        'statut': 'الحالة',
        'designation': 'البيان',
        'qte': 'الكمية',
        'pu_ht': 'سعر الوحدة (خ.ض)',
        'remise': 'الخصم',
        'total_ht': 'المجموع (خ.ض)',
        'sous_total_ht': 'المجموع الفرعي (خ.ض)',
        'remise_globale': 'الخصم الإجمالي',
        'total_ttc': 'المجموع شامل الضريبة',
        'note': 'ملاحظة',
        'coordonnees_bancaires': 'المعلومات البنكية',
        'signature_cachet': 'التوقيع والختم',
    },
}


def libelle(cle, langue='fr'):
    """Traduction d'une clé de libellé. FR par défaut (comportement inchangé
    quand `langue` n'est pas 'ar' ou que la clé est absente du dictionnaire
    AR — retombe alors sur le FR, jamais une clé brute affichée au client)."""
    table = LIBELLES.get(langue) or LIBELLES['fr']
    return table.get(cle) or LIBELLES['fr'].get(cle, cle)


def _load_font_base64(filename):
    """Lit le woff2 vendored (aucun appel réseau). None si absent —
    l'appelant retombe alors sur une police système (dégradation propre,
    jamais de crash PDF)."""
    path = _FONT_DIR / filename
    if not path.exists():
        return None
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:  # pragma: no cover - défensif, jamais de crash PDF
        return None


def arabic_font_face_css():
    """CSS `@font-face` embarquant Noto Sans Arabic (regular + bold), ou une
    chaîne vide si les fichiers sont absents (le gabarit retombe alors sur une
    police système — dégradation propre, jamais de crash)."""
    b64_400 = _load_font_base64('NotoSansArabic-400.woff2')
    b64_700 = _load_font_base64('NotoSansArabic-700.woff2')
    faces = []
    if b64_400:
        faces.append(
            '@font-face{font-family:"Noto Sans Arabic";font-style:normal;'
            'font-weight:400;font-display:block;'
            f'src:url("data:font/woff2;base64,{b64_400}") format("woff2");}}')
    if b64_700:
        faces.append(
            '@font-face{font-family:"Noto Sans Arabic";font-style:normal;'
            'font-weight:700;font-display:block;'
            f'src:url("data:font/woff2;base64,{b64_700}") format("woff2");}}')
    return ''.join(faces)


def document_langue(client):
    """Langue du document pour ce client — 'ar' ou 'fr' (défaut historique).
    Best-effort : un client sans champ (anciens objets en mémoire) retombe
    sur 'fr', jamais d'exception."""
    return getattr(client, 'langue_document', None) or 'fr'
