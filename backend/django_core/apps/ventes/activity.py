"""Chatter d'un devis (N25) — même patron que apps/installations/activity.py.

Notes manuelles + trace d'acceptation. Utilisateur et société toujours posés
côté serveur.
"""
from .models import DevisActivity


def log_devis_note(devis, user, body):
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.NOTE, body=body,
    )


def log_devis_a_facturer_reminder(devis, jours):
    """ZFAC12 — rappel de courtoisie « à facturer » : devis accepté depuis
    plus de N jours sans facture liée. Note SYSTÈME (user=None), une seule
    fois par jour calendaire (le cron peut tourner plusieurs fois/jour)."""
    from django.utils import timezone
    today = timezone.now().date().isoformat()
    deja = devis.activites.filter(
        field='a_facturer', new_value=today).exists()
    if deja:
        return None
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=None,
        kind=DevisActivity.Kind.NOTE,
        field='a_facturer', field_label='À facturer',
        new_value=today,
        body=(f'Devis accepté depuis {jours} jour(s) sans facture émise — '
              'à facturer.'),
    )


def log_devis_resynchronisation(devis, *, produit, modifications, user=None):
    """PVSYNC — chatter du devis : ses lignes ont suivi une RÉFÉRENCE modifiée.

    Posée UNIQUEMENT quand au moins une ligne a réellement bougé (une
    resynchronisation sans effet ne doit pas remplir le chatter de « rien n'a
    changé »). ``user`` est la personne qui a modifié le produit dans le
    Stock — jamais lue du corps d'une requête ; ``None`` = correction système.
    """
    quoi = ' / '.join(modifications) if modifications else 'fiche'
    nom = getattr(produit, 'nom', '') or getattr(produit, 'sku', '') or 'produit'
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='produit_resynchronise', field_label='Référence modifiée',
        new_value=nom,
        body=(f'Resynchronisé automatiquement — le produit « {nom} » a changé '
              f'({quoi}).'),
    )


def _montant_fr(valeur):
    """``Decimal`` → « 1 000,00 » (séparateur de milliers espace, virgule)."""
    from decimal import Decimal
    try:
        texte = f'{Decimal(str(valeur)):,.2f}'
    except (TypeError, ValueError, ArithmeticError):
        return str(valeur)
    return texte.replace(',', ' ').replace('.', ',')


def _note_unique(devis, *, field, field_label, new_value, body, user):
    """Crée la note sauf si la MÊME (champ + valeur) existe déjà : un rejeu
    du même événement catalogue ne duplique rien (livraison at-least-once)."""
    if devis.activites.filter(field=field, new_value=new_value).exists():
        return None
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.NOTE, field=field, field_label=field_label,
        new_value=new_value, body=body,
    )


def log_devis_catalogue_envoye_conserve(devis, *, produit, prix=None,
                                        nom=None, tva=None, forfait=None,
                                        user=None):
    """ASTK141 (D-ASTK-1) — un devis ENVOYÉ n'est PAS recalé sur une
    correction catalogue : la note persistée DIT l'écart et invite à réviser.

    ``prix`` / ``nom`` = ``(avant, après)`` du champ qui aurait bougé, ou
    ``None``. Une note par champ ; rejeu idempotent.
    """
    notes = []
    pid = getattr(produit, 'pk', '?')
    if prix is not None:
        avant, apres = prix
        notes.append(_note_unique(
            devis, field='catalogue_envoye_conserve',
            field_label='Catalogue modifié — devis envoyé conservé',
            new_value=f'{pid}:prix:{avant}->{apres}',
            body=(f'Prix catalogue passé de {_montant_fr(avant)} à '
                  f'{_montant_fr(apres)} — devis envoyé conservé ; réviser '
                  "pour l'appliquer."),
            user=user))
    if nom is not None:
        avant, apres = nom
        notes.append(_note_unique(
            devis, field='catalogue_envoye_conserve',
            field_label='Catalogue modifié — devis envoyé conservé',
            new_value=f'{pid}:nom:{avant}->{apres}',
            body=(f'Désignation catalogue passée de « {avant} » à « {apres} » '
                  "— devis envoyé conservé ; réviser pour l'appliquer."),
            user=user))
    if tva is not None:
        avant, apres = tva
        notes.append(_note_unique(
            devis, field='catalogue_envoye_conserve',
            field_label='Catalogue modifié — devis envoyé conservé',
            new_value=f'{pid}:tva:{avant}->{apres}',
            body=(f'TVA catalogue passée de {avant} % à {apres} % — devis '
                  "envoyé conservé ; réviser pour l'appliquer."),
            user=user))
    if forfait:
        detail = ' ; '.join(
            f'{nom_champ} {_montant_fr(a)} → {_montant_fr(n)}'
            for nom_champ, (a, n) in sorted(forfait.items()))
        notes.append(_note_unique(
            devis, field='catalogue_envoye_conserve',
            field_label='Catalogue modifié — devis envoyé conservé',
            new_value=f'{pid}:forfait:{detail}',
            body=(f'Barème forfaitaire catalogue modifié ({detail}) — devis '
                  "envoyé conservé ; réviser pour l'appliquer."),
            user=user))
    return [n for n in notes if n is not None]


def log_devis_forfait_abstention(devis, *, produit, message, user=None):
    """ASTK142 — une ligne de forfait d'un brouillon n'a PAS été retarifée
    (prix manuel, deux options divergentes) : la note persistée le dit."""
    return _note_unique(
        devis, field='forfait_abstention',
        field_label='Forfait non retarifé',
        new_value=f'{getattr(produit, "pk", "?")}:{message}',
        body=message, user=user)


def log_devis_prix_negocie_conserve(devis, *, ligne, ancien, nouveau,
                                    user=None):
    """ASTK141 — une ligne NÉGOCIÉE d'un brouillon garde son prix lors d'une
    correction catalogue : la note persistée le dit (rejeu idempotent)."""
    prix = getattr(ligne, 'prix_unitaire', None)
    return _note_unique(
        devis, field='prix_negocie_conserve',
        field_label='Prix négocié conservé',
        new_value=f'{getattr(ligne, "pk", "?")}:{ancien}->{nouveau}',
        body=(f'Prix négocié {_montant_fr(prix)} conservé (catalogue '
              f'{_montant_fr(ancien)} → {_montant_fr(nouveau)}).'),
        user=user)


def log_devis_correction_apres_envoi(devis, user, resume):
    """QJR518 (D-QJR5-1) — chatter du devis : un devis ENVOYÉ a été corrigé
    sur place (même référence, même lien public, statut inchangé). ``resume``
    NOMME ce qui a changé (lignes, en-tête, note, option recommandée).
    Posée seulement quand un contenu VISIBLE du client a réellement changé."""
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='correction_apres_envoi', field_label='Corrigé après envoi',
        new_value=resume,
        body=f'Corrigé après envoi — {resume}.',
    )


def log_devis_credit_hold_override(devis, user, motif):
    """XFAC28 — chatter du devis : un responsable/admin a débloqué un client
    en hold crédit dur pour laisser passer cette action (accepter/facturer)."""
    qui = getattr(user, 'username', '?') if user else '?'
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='credit_hold', field_label='Blocage crédit',
        new_value='override',
        body=f'Blocage crédit débloqué par {qui} — {motif}.',
    )


def log_devis_sale_warning_override(devis, user, motif):
    """ZSAL9 — chatter du devis : un responsable/admin a passé outre un
    avertissement de vente BLOQUANT (produit/client) pour laisser passer cette
    action (accepter/facturer)."""
    qui = getattr(user, 'username', '?') if user else '?'
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='avertissement_vente', field_label='Avertissement de vente',
        new_value='override',
        body=f'Avertissement de vente bloquant passé outre par {qui} — {motif}.',
    )


def log_devis_acceptance(devis, user, nom, date_acceptation, option=''):
    """Consigne l'acceptation du devis (qui + quand + option) dans son chatter.

    ``option`` est la valeur OptionAcceptee retenue (A1) ; on l'affiche en clair
    (« Sans batterie » / « Avec batterie ») quand elle est renseignée.
    """
    from .models import Devis
    qui = (nom or '').strip() or getattr(user, 'username', '?')
    opt_label = dict(Devis.OptionAcceptee.choices).get(option or '', '')
    suffixe = f" — option : {opt_label}" if opt_label else ''
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='statut', field_label='Acceptation',
        old_value='',
        new_value=f"Accepté le {date_acceptation} par {qui}{suffixe}",
        body=f"Devis accepté le {date_acceptation} par {qui}{suffixe}.",
    )


def log_devis_sent(devis, user):
    """U4 — Consigne l'envoi du devis (passage brouillon → envoyé) au chatter.

    Posé lors d'un partage client (ex. lien WhatsApp). Acteur et société
    toujours posés côté serveur, jamais lus du corps de la requête.
    """
    qui = getattr(user, 'username', '?')
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='statut', field_label='Statut',
        old_value='Brouillon', new_value='Envoyé',
        body=f"Devis envoyé au client par {qui}.",
    )


def log_devis_refusal(devis, user, motif, date_refus, note=''):
    """FG44 — Consigne le refus du devis (qui + quand + motif) dans son chatter.

    ADEV44 — ``note`` : le détail libre saisi à l'écran, ajouté au corps."""
    qui = getattr(user, 'username', '?')
    motif_part = f" — motif : {motif}" if motif else ''
    note_part = f" Détail : {note}" if note else ''
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='statut', field_label='Refus',
        old_value='',
        new_value=f"Refusé le {date_refus} par {qui}{motif_part}",
        body=f"Devis refusé le {date_refus} par {qui}{motif_part}.{note_part}",
    )


def log_facture_avoir(facture, user, avoir):
    """Consigne la création d'un avoir dans le chatter de la facture.

    Acteur et société toujours posés côté serveur (jamais du corps de requête).
    """
    from .models import FactureActivity
    montant = getattr(avoir, 'total_ttc', None)
    detail = f"Avoir {avoir.reference} créé"
    if montant is not None:
        detail += f" ({montant} MAD TTC)"
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='avoir', field_label='Avoir',
        new_value=avoir.reference, body=detail + '.',
    )


def log_facture_whatsapp(facture, user, modele='facture'):
    """Consigne la génération d'un lien WhatsApp dans le chatter de la facture.

    L'app n'envoie RIEN (ouvre wa.me) ; on trace que le commercial a préparé le
    message. Acteur et société posés côté serveur, jamais du corps de requête.
    """
    from .models import FactureActivity
    quoi = 'rappel' if modele == 'relance' else 'facture'
    qui = getattr(user, 'username', '?')
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.NOTE,
        body=f'Lien WhatsApp ({quoi}) généré pour {facture.reference} '
             f'par {qui}.',
    )


def log_facture_paiement(facture, user, paiement):
    """Consigne l'encaissement d'un paiement dans le chatter de la facture."""
    from .models import FactureActivity
    mode = paiement.get_mode_display() if hasattr(paiement, 'get_mode_display') \
        else (getattr(paiement, 'mode', '') or '')
    detail = f"Paiement encaissé : {paiement.montant} MAD"
    if mode:
        detail += f" ({mode})"
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='paiement', field_label='Paiement',
        new_value=str(paiement.montant), body=detail + '.',
    )


def log_facture_paiement_rejete(facture, user, paiement, motif):
    """YLEDG5 — consigne le rejet d'un paiement (chèque impayé / virement
    rejeté) dans le chatter de la facture rouverte."""
    from .models import FactureActivity
    detail = (f"Paiement rejeté : {paiement.montant} MAD — motif : {motif}")
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='paiement_rejete', field_label='Paiement rejeté',
        new_value=str(paiement.montant), body=detail + '.',
    )


def log_facture_remise_brouillon(facture, user, ancien_statut):
    """ZFAC1 — consigne la remise en brouillon (Reset to Draft) d'une facture
    émise dans son chatter. Le numéro/référence reste inchangé."""
    from .models import FactureActivity
    qui = getattr(user, 'username', '?')
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='statut', field_label='Remise en brouillon',
        old_value=ancien_statut, new_value='brouillon',
        body=(f"Facture {facture.reference} remise en brouillon par {qui} "
              f"(référence conservée)."),
    )


def log_facture_marquee_payee(facture, user, motif):
    """AUD124 — chatter de la facture : bascule MANUELLE en « payée ».

    Ce geste solde une facture sans encaissement enregistré : il la sort de
    la balance âgée et des relances (le recouvrement filtre sur le STATUT).
    Il ne laissait AUCUNE trace — ni motif, ni auteur, ni écriture. Le
    chatter est désormais systématique et nomme les deux.
    """
    from .models import FactureActivity
    qui = getattr(user, 'username', '?') if user else '?'
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='statut', field_label='Marquée payée (manuel)',
        new_value='payee',
        body=(f"Facture {facture.reference} marquée payée manuellement par "
              f"{qui} — motif : {motif}."),
    )


def log_facture_acompte_transfere_sortie(facture, user, cible, montant, nb):
    """FG50 — chatter de la facture ANNULÉE : l'acompte part vers une autre.

    Tracé sur la facture source (celle qu'on annule) : où va l'acompte et
    combien. Acteur et société posés côté serveur, jamais lus du corps."""
    from .models import FactureActivity
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='acompte', field_label='Acompte transféré',
        old_value=str(montant),
        body=(f"Acompte de {montant} MAD ({nb} paiement(s)) transféré vers la "
              f"facture {cible.reference} à l'annulation."),
    )


def log_facture_acompte_transfere_entree(facture, user, source, montant, nb):
    """FG50 — chatter de la facture CIBLE : elle reçoit l'acompte transféré."""
    from .models import FactureActivity
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='acompte', field_label='Acompte reçu',
        new_value=str(montant),
        body=(f"Acompte de {montant} MAD ({nb} paiement(s)) reçu depuis la "
              f"facture {source.reference} annulée."),
    )


def log_facture_acompte_rembourse(facture, user, montant):
    """FG50 — chatter de la facture annulée : l'acompte est remboursable.

    Trace l'écriture d'un paiement négatif (contre-passation) qui solde
    l'acompte resté sur la facture morte : l'obligation de remboursement est
    désormais matérialisée et l'acompte n'est plus « coincé »."""
    from .models import FactureActivity
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='acompte', field_label='Acompte remboursable',
        old_value=str(montant),
        body=(f"Acompte de {montant} MAD marqué remboursable à l'annulation "
              f"(écriture négative de contre-passation)."),
    )


def log_facture_avance_affectee(facture, user, paiement, montant):
    """XFAC1 — chatter de la facture : ventilation d'une avance client reçue."""
    from .models import FactureActivity
    qui = getattr(user, 'username', '?')
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='avance', field_label='Avance affectée',
        new_value=str(montant),
        body=(f"Avance de {montant} MAD affectée par {qui} "
              f"(paiement #{paiement.id})."),
    )


def log_facture_penalite_facturee(facture, user, facture_penalite, montant):
    """XFAC6 — chatter de la facture d'origine : pénalités de retard
    facturées séparément (nouvelle facture de frais dédiée)."""
    from .models import FactureActivity
    qui = getattr(user, 'username', '?')
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='penalite', field_label='Pénalité facturée',
        new_value=facture_penalite.reference,
        body=(f"Pénalités de retard ({montant} MAD) facturées séparément "
              f"par {qui} — {facture_penalite.reference}."),
    )


def log_facture_retenue_subie(facture, user, retenue):
    """XFAC4 — chatter de la facture : retenue à la source subie constatée."""
    from .models import FactureActivity
    qui = getattr(user, 'username', '?')
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='retenue', field_label='Retenue à la source',
        new_value=str(retenue.montant),
        body=(f"Retenue à la source ({retenue.get_type_retenue_display()}) "
              f"de {retenue.montant} MAD constatée par {qui}."),
    )


def log_facture_abandon(facture, user, montant, motif_label, auto=False):
    """XFAC13 — chatter de la facture : abandon de créance (write-off)."""
    from .models import FactureActivity
    qui = getattr(user, 'username', '?') if user else 'automatique'
    origine = 'automatique (tolérance société)' if auto else f'par {qui}'
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='abandon', field_label='Abandon de créance',
        new_value=str(montant),
        body=(f"Solde résiduel de {montant} MAD abandonné {origine} "
              f"— motif : {motif_label}."),
    )
