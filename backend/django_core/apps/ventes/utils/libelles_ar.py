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
        # AFAC58 (C-AFAC-050) — libellés ajoutés après XSAL13.
        'deja_paye': 'Déjà payé',
        'total_deja_paye': 'Total déjà payé',
        'facture_soldee': 'Facture soldée',
        'reste_a_payer': 'Reste à payer',
        'arrondi_commercial': 'Arrondi commercial',
        'base_ht': 'Base HT',
        'arrondi_especes': 'Arrondi espèces',
        'periode_service': 'Période de service',
        'votre_commande': 'Votre commande',
        'tel': 'Tél',
        'instructions_paiement': 'Instructions de paiement',
        'conditions_generales': 'Conditions générales',
        'conditions_paiement': 'Conditions de paiement',
        'facture_generee_le': 'Facture générée automatiquement le',
        'note_debit': 'Note de débit',
        'voir_ventilation': 'voir ventilation',
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
        'deja_paye': 'المبالغ المدفوعة',
        'total_deja_paye': 'مجموع المبالغ المدفوعة',
        'facture_soldee': 'فاتورة مسددة بالكامل',
        'reste_a_payer': 'المبلغ المتبقي للأداء',
        'arrondi_commercial': 'التقريب التجاري',
        'base_ht': 'الأساس (خ.ض)',
        'arrondi_especes': 'تقريب الأداء نقدا',
        'periode_service': 'فترة الخدمة',
        'votre_commande': 'طلبيتكم',
        'tel': 'الهاتف',
        'instructions_paiement': 'تعليمات الأداء',
        'conditions_generales': 'الشروط العامة',
        'conditions_paiement': 'شروط الأداء',
        'facture_generee_le': 'فاتورة مُنشأة تلقائيا بتاريخ',
        'note_debit': 'إشعار مدين',
        'voir_ventilation': 'انظر التفصيل',
    },
}


#: AFAC58 — textes DYNAMIQUES du PDF facture (libellés d'affichage des
#: statuts et des modes de paiement, lignes du bloc « Déjà payé ») : la clé
#: est le texte français lui-même ; hors arabe, ``libelle`` le rend tel quel.
TEXTES_AR = {
    'Brouillon': 'مسودة',
    'Émise': 'صادرة',
    'Payée': 'مؤداة',
    'En retard': 'متأخرة',
    'Annulée': 'ملغاة',
    'Espèces': 'نقدا',
    'Virement': 'تحويل بنكي',
    'Chèque': 'شيك',
    'Carte bancaire': 'بطاقة بنكية',
    'Prélèvement': 'اقتطاع بنكي',
    'Autre': 'أخرى',
    'Escompte pour règlement anticipé': 'خصم الأداء المسبق',
    'Avoir': 'إشعار دائن',
    'Abandon de créance': 'التخلي عن الدين',
    'Arrondi espèces': 'تقريب الأداء نقدا',
}

_SUFFIXE_AVANCE = ' (avance)'
_PREFIXE_RETENUE = 'Retenue à la source ('


def _texte_ar(texte):
    """Traduction arabe d'un texte d'affichage dynamique, ou ``None``."""
    if texte in TEXTES_AR:
        return TEXTES_AR[texte]
    if texte.endswith(_SUFFIXE_AVANCE):
        base = _texte_ar(texte[:-len(_SUFFIXE_AVANCE)])
        if base:
            return f'{base} (تسبيق)'
    if texte.startswith(_PREFIXE_RETENUE):
        return 'اقتطاع من المنبع (' + texte[len(_PREFIXE_RETENUE):]
    return None


def libelle(cle, langue='fr'):
    """Traduction d'une clé de libellé. FR par défaut (comportement inchangé
    quand `langue` n'est pas 'ar' ou que la clé est absente du dictionnaire
    AR — retombe alors sur le FR, jamais une clé brute affichée au client).

    AFAC58 — une clé qui est un TEXTE d'affichage dynamique (statut, mode de
    paiement) est traduite par ``TEXTES_AR`` en arabe et rendue telle quelle
    sinon."""
    table = LIBELLES.get(langue) or LIBELLES['fr']
    if langue == 'ar' and cle not in table and isinstance(cle, str):
        traduit = _texte_ar(cle)
        if traduit:
            return traduit
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


def document_langue(client, *, langue_explicite=None, company=None):
    """Langue du document — 'ar' ou 'fr' pour ce dictionnaire (voir
    ``libelle`` ci-dessous), pas plus large ('en' retomberait déjà
    silencieusement sur le FR faute d'entrée dans ``LIBELLES``).

    NTI18N4 — délègue désormais à la résolution PARTAGÉE
    ``apps.parametres.i18n_resolver.resolve_langue_sortie`` (priorité :
    explicite > ``Client.langue_document`` > repli société > FR), qui
    GÉNÉRALISE cette fonction (ajout du repli société et de l'override
    explicite, absents avant cette tâche) sans changer sa signature
    historique : un appel ``document_langue(client)`` reste identique
    caractère pour caractère pour tout appelant existant. Best-effort :
    aucune exception ne remonte jamais (comportement historique préservé)."""
    from apps.parametres.i18n_resolver import resolve_langue_sortie
    return resolve_langue_sortie(
        langue_explicite=langue_explicite, client=client, company=company)
