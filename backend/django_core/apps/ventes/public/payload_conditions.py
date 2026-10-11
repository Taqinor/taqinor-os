"""Conditions, acompte et validité de la proposition publique (SPL251, déplacé de ``public_views.py``).

Moyens de règlement proposables, acompte (échéancier du devis), clauses CGV
remplies, date de validité, confirmation par courriel — assemblés par
``public_views.proposal_data`` et relus par le paiement public. Aucune vue
ici. Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_pv_conditions.json``.
"""


#: PREVIEW-V3 (16/09/2026) — moyens de règlement PROPOSABLES au client avant
#: signature. Constante, jamais dérivée d'une saisie : l'art. 193 du CGI
#: interdit d'encaisser plus de 20 000 MAD en espèces (amende de 6 % à la
#: charge DU VENDEUR), donc « espèces » n'apparaît nulle part côté client.
#: Le RIB reste POST-signature (`_deposit_success_payload`) : rien à virer
#: tant que la commande n'est pas ferme.
PAIEMENT_MOYENS_PUBLICS = ('virement', 'cheque')


def _acompte_publique(devis, lignes=None):
    """PREVIEW-V3 — la PREMIÈRE tranche de l'échéancier, telle qu'elle sera
    facturée, ou ``None`` si elle n'est pas calculable.

    SOURCE UNIQUE : ``apps.ventes.utils.echeancier.next_tranche`` — exactement
    la fonction qui alimentait déjà l'écran de succès POST-signature
    (``_deposit_success_payload``, QX33be) et la facturation. Jamais
    ``deposit.compute_deposit()`` (30 % forfaitaires, échafaudage PSP) : la
    page client ne montre QUE le chiffre que le devis facturera vraiment.

    Best-effort : toute exception rend ``None`` (clé ABSENTE côté payload,
    jamais ``null`` — règle `additif_vs_null` du contrat).

    PREVIEW-V3-FIX (16/09/2026) — L'ACOMPTE SUIT L'OPTION QUE LE CLIENT COCHE.
    L'audit C1 : ``ttc`` n'existait que pour UNE option (celle du total
    affiché) et la page DEVINAIT laquelle (``reco``) — un vendeur qui
    recommande « Sans batterie » sur un devis à deux options faisait donc lire
    au client l'acompte de l'option AVEC, à l'endroit exact où il décide. Le
    serveur publie désormais :

    * ``option``   — l'option sur laquelle l'ERP a calculé ``ttc``
      (``options.option_effective``, la MÊME que la facturation), ``''`` quand
      le devis n'en distingue aucune ;
    * ``montants`` — le montant de la PREMIÈRE tranche pour CHAQUE option
      servable, calculé par le MÊME ``next_tranche`` (donc le même arrondi au
      centime, jamais une règle recopiée) : la page lit la case cochée au lieu
      de deviner. Devis mono-option ⇒ une seule entrée, sous la clé de
      l'option effective (défaut ``sans_batterie``) — le montant ne dépend
      alors d'aucune option, toutes les lignes sont facturées.

    ``libelle`` a été RETIRÉ (audit C9) : servi, jamais lu — la phrase de la
    page porte ses trois langues (« Acompte » / « deposit » / « تسبيق »), un
    libellé FR d'échéancier ne peut pas s'y substituer sans casser l'arabe.
    """
    from decimal import Decimal
    try:
        from ..utils.echeancier import next_tranche
        from ..utils.options import (AVEC_BATTERIE, SANS_BATTERIE,
                                     deux_options_declarees, option_effective)
        tr = next_tranche(devis, lignes=lignes)
        if tr is None:
            return None
        # PREVIEW-V3-FIX (audit C7) — UN ACOMPTE DE 0,00 N'EST PAS UN ACOMPTE.
        # Un devis sans ligne (ou à total nul) servait `{"ttc": "0.00"}` :
        # le contrat annonce l'ABSENCE de la clé quand il n'y a rien à
        # montrer (règle `additif_vs_null`), et le test d'alors acceptait les
        # deux issues — il ne prouvait donc pas ce que le contrat promet.
        if Decimal(str(tr['ttc'])) <= 0:
            return None
        effective = option_effective(devis) or ''
        if deux_options_declarees(devis):
            cles = (SANS_BATTERIE, AVEC_BATTERIE)
        else:
            cles = (effective or SANS_BATTERIE,)
        montants = {}
        for cle in cles:
            tr_opt = next_tranche(devis, lignes=lignes, option=cle)
            if tr_opt is None:
                continue
            montant = Decimal(str(tr_opt['ttc']))
            if montant > 0:
                montants[cle] = str(montant)
        return {
            'pourcentage': str(Decimal(str(tr.get('pourcentage')))),
            'ttc': str(Decimal(str(tr['ttc']))),
            'option': effective,
            'montants': montants,
        }
    except Exception:  # noqa: BLE001 — best-effort
        return None


def _conditions_publiques(data, devis=None):
    """PREVIEW-V3 — les puces « Conditions générales du devis » du PDF, en texte.

    QJR668 (décision fondateur 01/10/2026, « figer le texte CGV à l'envoi ») —
    la page de signature (« J'accepte … les conditions générales ») sert
    EXACTEMENT ce que le PDF de CE devis imprime, par LA fonction de
    remplissage du moteur (``clauses_cgv.cgv_bullets_remplies`` →
    ``remplir_cgv_bullets``, celle que ``_cgv_bullets_html`` appelle). Plus
    aucune copie locale du remplissage (l'ancien ``.format`` +
    ``_pct_lisible`` écrivait « 33,5 » là où le PDF imprime « 33.5 », et
    relisait l'échéancier sans les lignes du devis) :

    * devis portant des CGV GELÉES (``Devis.clauses_appliquees``, entrée
      ``cgv_gelees`` posée à l'envoi par ``domain/cycle_vie.
      figer_clauses_devis``) → CES puces : ``build_quote_data`` les a déjà
      substituées dans ``data['doc_texts']['cgv_bullets']``, la source même
      du bloc CGV du PDF. Modifier ensuite les CGV société ne change plus ce
      que le client accepte ;
    * sinon (brouillon, aperçu) → les puces VIVES de la société (ou le
      littéral par défaut), remplies par la même fonction.

    Mêmes valeurs que le rendu : ``data['payment_terms']`` (échéancier du
    devis rabattu par le builder, QJR623), ``tva_note``, ``valid_until``. Les
    entités HTML sont dé-échappées pour le JSON ; une puce vide est omise,
    comme dans le PDF. Forme inchangée (liste de textes, ``None`` si rien).

    Le sens de l'import est celui du repo : l'app lit le moteur, JAMAIS
    l'inverse. Lecture seule (règle #4) ; rien n'est lu hors du ``data`` de CE
    devis (multi-tenant). ``devis`` reste accepté pour la signature d'appel :
    la correspondance échéancier → créneaux est déjà faite dans ``data``.

    APDF19 (C-APDF-005) — les puces sont celles de
    ``clauses_cgv.cgv_imprimees(data)`` (APDF12), LA source que le
    PDF imprime : un devis C&I à variante sert SA variante (gelée à l'envoi
    ou vive en brouillon, marqueurs {echeancier}/{retenue} substitués par le
    builder) — plus les puces résidentielles par défaut, plus un
    « Echeancier {echeancier} » brut ; sinon les puces société gelées ou
    vives, comme avant (``cgv_bullets_remplies`` en est un détail).
    """
    import html as _html
    try:
        from ..quote_engine.clauses_cgv import cgv_imprimees
        out = [txt for txt in (_html.unescape(str(puce)).strip()
                               for puce in cgv_imprimees(data or {})["puces"])
               if txt]
        return out or None
    except Exception:  # noqa: BLE001 — best-effort
        return None


def _conditions_titre_publique(data):
    """APDF19 (C-APDF-005) — le titre que le PDF de CE devis imprime au-dessus
    des puces de :func:`_conditions_publiques` : ``cgv_imprimees(data)["titre"]``
    (titre de la variante C&I gelée ou vive, sinon surcharge société, sinon
    celui du moteur dans la langue du document), dé-échappé pour le JSON.

    Clé ADDITIVE ``conditions_titre``, posée avec ``conditions`` seulement :
    toujours un texte, jamais ``null`` (le moteur rend toujours un titre, au
    pire le sien ; une lecture impossible rend ``''``). Lecture seule
    (règle #4)."""
    import html as _html
    try:
        from ..quote_engine.clauses_cgv import cgv_imprimees
        return _html.unescape(str(cgv_imprimees(data or {})["titre"])).strip()
    except Exception:  # noqa: BLE001 — best-effort
        return ''


def _date_validite_publique(devis):
    """PREVIEW-V3 — échéance RÉELLE du devis en ISO, ou ``None``.

    ``apps.ventes.utils.expiry.date_expiration`` est déjà LA règle (date posée
    sur le devis, sinon création + ``CompanyProfile.quote_validity_days``) :
    elle décidait jusqu'ici du statut « expiré » sans jamais sortir la date.
    DOC art. 65-4 §2 : sans date affichée, l'offre engage tant que le lien vit.
    """
    try:
        from ..utils.expiry import date_expiration
        exp = date_expiration(devis)
        return exp.isoformat() if exp else None
    except Exception:  # noqa: BLE001 — best-effort
        return None


#: PREVIEW-V3-FIX (audit C6) — LES BACKENDS D'E-MAIL QUI N'ENVOIENT NULLE PART.
#: ``console`` (le DÉFAUT du projet, settings/base.py : « SANS clé […] l'envoi
#: est un NO-OP ») imprime dans les logs ; ``dummy`` jette. Dans les deux cas
#: ``send_mail`` ne lève pas, ``email_service._send`` journalise « envoyé », et
#: la page promettait un accusé de réception que le client n'a jamais reçu.
#: ``locmem`` n'y figure PAS volontairement : ce n'est pas un réglage de
#: production, c'est celui que le lanceur de tests Django impose (il capture
#: dans ``mail.outbox``) — l'exclure rendrait tout test aveugle à la
#: distinction que cette fonction existe pour faire.
EMAIL_BACKENDS_SANS_ENVOI = (
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.dummy.EmailBackend',
)


def _confirmation_email_publique(devis):
    """PREVIEW-V3 — ce client recevra-t-il VRAIMENT un e-mail à l'acceptation ?

    DEUX conditions, pas une :

    * ``domain.cycle_vie._send_acceptance_emails`` n'envoie que ``if dest:``,
      où ``dest = devis.client.email`` — il faut donc une adresse ;
    * PREVIEW-V3-FIX (audit C6) — et il faut un backend d'e-mail qui ENVOIE.
      ``EMAIL_BACKEND`` vaut *console* par défaut dans ce projet : sans
      ``EMAIL_BACKEND=anymail…`` + clé Brevo/SendGrid dans le ``.env`` de
      production, rien ne part, ``send_mail`` ne lève pas et le service
      journalise « envoyé » quand même. La page promettait alors « Une
      confirmation vous est envoyée par e-mail » dans le vide — exactement ce
      que cette clé devait empêcher.

    Loi 31-08 art. 32 : c'est la confirmation ÉCRITE qui plafonne la
    rétractation à 7 jours. La promettre sans qu'elle parte ne raccourcit
    aucun délai — cela ajoute seulement une phrase fausse sur un document
    contractuel."""
    # ADEP34 — UNE seule règle : ``email_service.is_email_configured`` (clé
    # d'envoi posée ET backend chargé qui envoie). La clé seule sur le backend
    # console ne promet plus rien ; un backend « qui envoie » sans clé non
    # plus.
    try:
        from apps.ventes.email_service import is_email_configured
        if not is_email_configured():
            return False
        client = getattr(devis, 'client', None)
        return bool((getattr(client, 'email', '') or '').strip())
    except Exception:  # noqa: BLE001 — best-effort
        return False
