"""NTI18N25 — Glossaire terminologique métier par langue (statuts).

Catalogue additionnel, PARTAGÉ entre le moteur `/proposal`
(`apps.ventes.quote_engine.i18n_labels`, NTI18N5) et le frontend : les
libellés d'AFFICHAGE des statuts métier (Devis/Facture/Ticket/Chantier) en
fr/en/ar. Ce fichier ne touche JAMAIS aux clés canoniques elles-mêmes
(`Devis.Statut`, `Facture.Statut`, `Ticket.Statut`, `Installation.Statut`)
ni à `STAGES.py` (entonnoir du lead, couche permanente et séparée, règle #2
fondateur) — uniquement leur LIBELLÉ d'affichage dans la langue d'interface
active.

Consommé par `apps.parametres.selectors.statut_libelle` (surcharge société
`StatutConfig` en premier, FR uniquement — un override manuel reste toujours
en français ; ce dictionnaire ensuite ; la clé canonique brute en tout
dernier recours, jamais une exception).

Câblage du composant frontend `StatusPill`/`StatutConfig` (écran) : HORS
périmètre de cette lane (frontend/src/ui, pas frontend/src/i18n) — ce
fichier fournit le socle backend, prêt à être consommé par un futur rollout
frontend.
"""
from __future__ import annotations

#: Langues supportées — mêmes trois que le reste du cadre i18n léger
#: (`i18n_resolver.LANGUES_SUPPORTEES`).
LANGUES_SUPPORTEES = ('fr', 'en', 'ar')

#: Libellés de statut par domaine métier. Les clés canoniques (colonne de
#: gauche) SUIVENT strictement les `TextChoices` des modèles source :
#: `ventes.Devis.Statut`, `facturation.Facture.Statut`, `sav.Ticket.Statut`,
#: `installations.Installation.Statut` (y compris ses statuts HÉRITÉS,
#: conservés pour ne jamais afficher une clé brute sur un chantier ancien).
STATUT_LABELS = {
    'devis': {
        'brouillon': {'fr': 'Brouillon', 'en': 'Draft', 'ar': 'مسودة'},
        'envoye': {'fr': 'Envoyé', 'en': 'Sent', 'ar': 'مُرسَل'},
        'accepte': {'fr': 'Accepté', 'en': 'Accepted', 'ar': 'مقبول'},
        'refuse': {'fr': 'Refusé', 'en': 'Declined', 'ar': 'مرفوض'},
        'expire': {'fr': 'Expiré', 'en': 'Expired', 'ar': 'منتهي الصلاحية'},
    },
    'facture': {
        'brouillon': {'fr': 'Brouillon', 'en': 'Draft', 'ar': 'مسودة'},
        'emise': {'fr': 'Émise', 'en': 'Issued', 'ar': 'صادرة'},
        'payee': {'fr': 'Payée', 'en': 'Paid', 'ar': 'مدفوعة'},
        'en_retard': {'fr': 'En retard', 'en': 'Overdue', 'ar': 'متأخرة'},
        'annulee': {'fr': 'Annulée', 'en': 'Cancelled', 'ar': 'ملغاة'},
    },
    'ticket': {
        'nouveau': {'fr': 'Nouveau', 'en': 'New', 'ar': 'جديد'},
        'planifie': {'fr': 'Planifié', 'en': 'Scheduled', 'ar': 'مجدوَل'},
        'en_cours': {'fr': 'En cours', 'en': 'In progress', 'ar': 'قيد التنفيذ'},
        'resolu': {'fr': 'Résolu', 'en': 'Resolved', 'ar': 'تم الحل'},
        'cloture': {'fr': 'Clôturé', 'en': 'Closed', 'ar': 'مغلق'},
    },
    'chantier': {
        # ── Entonnoir canonique (Installation.Statut, N1) ──
        'signe': {'fr': 'Signé', 'en': 'Signed', 'ar': 'موقّع'},
        'materiel_commande': {
            'fr': 'Matériel commandé', 'en': 'Materials ordered',
            'ar': 'تم طلب المعدات'},
        'planifie': {'fr': 'Planifié', 'en': 'Scheduled', 'ar': 'مجدوَل'},
        'en_cours': {'fr': 'En cours', 'en': 'In progress', 'ar': 'قيد التنفيذ'},
        'installe': {'fr': 'Installé', 'en': 'Installed', 'ar': 'مُركَّب'},
        'receptionne': {
            'fr': 'Réceptionné', 'en': 'Received', 'ar': 'تم الاستلام'},
        'cloture': {'fr': 'Clôturé', 'en': 'Closed', 'ar': 'مغلق'},
        # ── Statuts hérités (chantiers antérieurs au funnel N1) ──
        'a_planifier': {
            'fr': 'À planifier', 'en': 'To schedule', 'ar': 'قيد الجدولة'},
        'pose_en_cours': {
            'fr': 'Pose en cours', 'en': 'Installation in progress',
            'ar': 'التركيب جارٍ'},
        'pose': {'fr': 'Posé', 'en': 'Installed', 'ar': 'مُركَّب'},
        'raccordement_onee': {
            'fr': 'Raccordement ONEE', 'en': 'Grid connection (ONEE)',
            'ar': 'الربط بالشبكة'},
        'mise_en_service': {
            'fr': 'Mise en service', 'en': 'Commissioning', 'ar': 'التشغيل'},
    },
}


def statut_label(domaine: str, cle: str, langue: str = 'fr') -> str:
    """Libellé d'affichage de (domaine, cle) dans `langue`.

    Repli, jamais d'exception : langue non supportée → 'fr' ; couple
    (domaine, cle) absent du catalogue → la clé canonique brute (jamais une
    chaîne vide, jamais un crash sur un statut pas encore catalogué ici).
    """
    langue = langue if langue in LANGUES_SUPPORTEES else 'fr'
    entree = STATUT_LABELS.get(domaine, {}).get(cle)
    if not entree:
        return cle
    return entree.get(langue) or entree.get('fr') or cle


def variante_absente(domaine: str, cle: str, langue: str) -> bool:
    """NTI18N51 — le catalogue va-t-il devoir REPLIER pour cette demande ?

    Vrai quand `langue` est une langue supportée AUTRE que le français et que
    le couple (domaine, cle) n'a pas de valeur dans cette langue — soit parce
    que le couple est absent du catalogue, soit parce que son entrée ne porte
    pas cette langue. Prédicat pur : ne compte rien, n'écrit rien (le compteur
    vit dans `traductions_manquantes`), et ne juge JAMAIS une langue non
    supportée comme un manque (elle est traitée comme du français, ce qui est
    le comportement voulu, pas une lacune de traduction).
    """
    if langue == 'fr' or langue not in LANGUES_SUPPORTEES:
        return False
    entree = STATUT_LABELS.get(domaine, {}).get(cle)
    if not entree:
        return True
    return not entree.get(langue)
