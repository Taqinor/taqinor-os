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
        # APDF26 (C-APDF-008) — date de livraison / prestation.
        'date_livraison': 'Date de livraison / prestation',
        # APDF28 — numérotation des pages.
        'page': 'Page',
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
        'date_livraison': 'تاريخ التسليم / الخدمة',
        'page': 'صفحة',
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
    # APDF31 (D-APDF-3 a) — avoir, note de débit, reçu, relance.
    'AVOIR': 'إشعار دائن',
    'NOTE DE DÉBIT': 'إشعار مدين',
    'Note de crédit — sur facture': 'إشعار دائن — على الفاتورة',
    'Majoration — sur facture': 'زيادة — على الفاتورة',
    'Tél': 'الهاتف',
    'Émetteur': 'المُصدر',
    'Avoir au profit de': 'إشعار دائن لفائدة',
    'Note de débit à charge de': 'إشعار مدين على عاتق',
    "Date d'émission": 'تاريخ الإصدار',
    "Facture d'origine": 'الفاتورة الأصلية',
    'Statut': 'الحالة',
    'Émis': 'صادر',
    'Annulé': 'ملغى',
    'Désignation': 'البيان',
    'Qté': 'الكمية',
    'P.U HT': 'سعر الوحدة (خ.ض)',
    'Remise': 'الخصم',
    'Total HT': 'المجموع (خ.ض)',
    'Avoir sur facture': 'إشعار دائن على الفاتورة',
    'Note de débit sur facture': 'إشعار مدين على الفاتورة',
    'Motif': 'السبب',
    'Sous-total HT crédité': 'المجموع الفرعي الدائن (خ.ض)',
    'Sous-total HT': 'المجموع الفرعي (خ.ض)',
    'Remise globale': 'الخصم الإجمالي',
    'Arrondi commercial': 'التقريب التجاري',
    'Base HT': 'الأساس (خ.ض)',
    'TVA': 'الضريبة على القيمة المضافة',
    'Total crédité TTC': 'المجموع الدائن شامل الضريبة',
    'Total dû en supplément (TTC)': 'المبلغ الإضافي المستحق شامل الضريبة',
    'Conditions de paiement': 'شروط الأداء',
    'Signature & Cachet': 'التوقيع والختم',
    'Avoir (note de crédit) lié à la facture': 'إشعار دائن مرتبط بالفاتورة',
    'Note de débit liée à la facture': 'إشعار مدين مرتبط بالفاتورة',
    'généré le': 'أُنشئ بتاريخ',
    'générée le': 'أُنشئت بتاريخ',
    'QUITTANCE': 'وصل أداء',
    'Reçu de paiement n°': 'وصل الأداء رقم',
    'Reçu de': 'تم التوصل من',
    'Date du règlement': 'تاريخ الأداء',
    'Mode': 'طريقة الأداء',
    'Référence': 'المرجع',
    'N° chèque': 'رقم الشيك',
    'Banque tirée': 'البنك المسحوب عليه',
    'Facture réglée': 'الفاتورة المؤداة',
    'Montant affecté': 'المبلغ المخصص',
    'Solde restant dû': 'الرصيد المتبقي المستحق',
    'sur': 'على',
    'Quittance générée automatiquement le': 'وصل مُنشأ تلقائيا بتاريخ',
    'Objet': 'الموضوع',
    'Relance': 'تذكير',
    'facture': 'الفاتورة',
    'Madame, Monsieur,': 'سيدتي، سيدي،',
    'Sauf erreur de notre part, la facture ci-dessous reste en attente de règlement. Nous vous remercions de bien vouloir procéder à son paiement.': 'ما لم يكن هناك خطأ من جانبنا، فإن الفاتورة أدناه لا تزال في انتظار الأداء. نشكركم على التفضل بأدائها.',
    'Facture': 'الفاتورة',
    'Échéance': 'تاريخ الاستحقاق',
    'en retard de': 'متأخرة بـ',
    'jour(s)': 'يوم (أيام)',
    'Montant restant dû': 'المبلغ المتبقي المستحق',
    'Pénalité de retard indicative': 'غرامة التأخير الإرشادية',
    'Nous restons à votre disposition pour toute information.': 'نبقى رهن إشارتكم لأي معلومة.',
    'Cordialement,': 'مع خالص التحيات،',
    'Courrier généré le': 'رسالة مُنشأة بتاريخ',
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


#: APDF31 (D-APDF-3 a, tranché le 08/10/2026) — documents TRADUITS en
#: arabe : facture, avoir, note de débit, reçu, lettre de relance. Les
#: autres (bon de commande, pro-forma, relevé, bordereau) restent en
#: français AVEC une mention de repli imprimée ; une langue sans
#: dictionnaire (« en ») aussi — jamais un repli silencieux.
MENTIONS_REPLI = {
    'ar': ('Document disponible en français uniquement — '
           'هذه الوثيقة متوفرة باللغة الفرنسية فقط.'),
    'en': ('Document disponible en français uniquement — '
           'This document is available in French only.'),
}
_MENTION_REPLI_DEFAUT = 'Document disponible en français uniquement.'


def mention_repli(langue_demandee, langue_rendue):
    """APDF31 — la mention imprimée quand le document n'est PAS rendu dans
    la langue demandée (``''`` sinon)."""
    demandee = (langue_demandee or 'fr').lower()
    if demandee == (langue_rendue or 'fr').lower() or demandee == 'fr':
        return ''
    return MENTIONS_REPLI.get(demandee, _MENTION_REPLI_DEFAUT)


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
    """APDF25 (C-APDF-002) — PLUS AUCUN ``@font-face`` vendorisé : renvoie
    toujours ``''``.

    Le woff2 « Noto Sans Arabic » embarqué était HOMONYME de la police
    système de l'image (``fonts-noto-core``, Dockerfile) : WeasyPrint
    mélangeait les deux et la colonne Total de la facture arabe sortait en
    glyphes illisibles (« MAD صنعى », sonde PLANG-1). La police système sert
    désormais seule, comme pour le moteur devis (APDF6,
    ``premium_base.css_arabe``). Appelants : ``utils/pdf.generate_facture_pdf``
    et ``documents/builders`` (BL arabe) — inchangés, ils reçoivent ``''``.
    ``_load_font_base64`` reste (retrait des woff2 : APDF47)."""
    return ''


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
