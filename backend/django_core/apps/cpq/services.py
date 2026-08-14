"""Services (écritures / orchestration) de l'app CPQ.

Toute écriture cross-app (créer des ``LigneDevis``, lire un ``Devis``…) passe
par des imports LOCAUX (fonction-locaux) des modèles ventes/crm pour éviter les
cycles — l'app cpq est en aval de ventes dans le graphe d'apps."""
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    LigneOffreGroupee, RegleApprobationRemise, EtapeApprobationDevis,
    PrixContractuel,
)

_CENT = Decimal('0.01')


def appliquer_offre_groupee(*, offre, devis, user=None):
    """NTCPQ3 — Insère les ``LigneDevis`` d'une offre groupée dans un devis.

    Si ``offre.prix_total`` est renseigné et qu'au moins une ligne est en mode
    ``FIXE``, le total du bundle PRIME : il est réparti au prorata du prix
    catalogue (``produit.prix_vente`` × quantité) sur les lignes, le reste de
    centime étant absorbé par la dernière ligne pour que le sous-total HT égale
    exactement ``prix_total``. Sinon chaque ligne est valorisée par son propre
    ``mode_prix`` (``REMISE_PCT`` / ``PRIX_COMPOSANT``).

    Renvoie la liste des ``LigneDevis`` créées. Écriture cross-app ventes via
    import local (aucun import de ``ventes.models`` au niveau module)."""
    from apps.ventes.models import LigneDevis

    lignes = list(offre.lignes.select_related('produit').all())
    if not lignes:
        return []

    fixe = LigneOffreGroupee.ModePrix.FIXE
    use_bundle_total = (
        offre.prix_total is not None
        and any(li.mode_prix == fixe for li in lignes))

    created = []
    if use_bundle_total:
        poids = [
            (li, (li.produit.prix_vente or Decimal('0')) * (li.quantite or Decimal('1')))
            for li in lignes]
        base = sum((w for _, w in poids), Decimal('0')) or Decimal('1')
        prix_total = Decimal(str(offre.prix_total))
        running = Decimal('0')
        n = len(poids)
        for i, (li, w) in enumerate(poids):
            if i < n - 1:
                part = (prix_total * (w / base)).quantize(_CENT, ROUND_HALF_UP)
                running += part
            else:
                part = prix_total - running  # dernière ligne absorbe le reste
            qte = li.quantite or Decimal('1')
            pu = (part / qte).quantize(_CENT, ROUND_HALF_UP)
            created.append(LigneDevis.objects.create(
                devis=devis, produit=li.produit,
                designation=li.produit.nom, quantite=qte,
                prix_unitaire=pu, remise=Decimal('0')))
    else:
        for li in lignes:
            qte = li.quantite or Decimal('1')
            if li.mode_prix == LigneOffreGroupee.ModePrix.REMISE_PCT:
                pu = li.produit.prix_vente
                remise = li.valeur if li.valeur is not None else Decimal('0')
            elif li.mode_prix == LigneOffreGroupee.ModePrix.PRIX_COMPOSANT:
                pu = li.valeur if li.valeur is not None else li.produit.prix_vente
                remise = Decimal('0')
            else:  # FIXE sans prix_total → repli prix catalogue
                pu = li.produit.prix_vente
                remise = Decimal('0')
            created.append(LigneDevis.objects.create(
                devis=devis, produit=li.produit,
                designation=li.produit.nom, quantite=qte,
                prix_unitaire=pu, remise=remise))
    return created


def _resoudre_client_import(company, ref):
    """NTCPQ41 — résout un client par ID numérique, email exact, ou nom exact
    (insensible à la casse), scopé société. ``None`` si introuvable."""
    from apps.crm.models import Client
    ref = (ref or '').strip()
    if not ref:
        return None
    if ref.isdigit():
        client = Client.objects.filter(company=company, id=int(ref)).first()
        if client is not None:
            return client
    client = Client.objects.filter(
        company=company, email__iexact=ref).first()
    if client is not None:
        return client
    return Client.objects.filter(company=company, nom__iexact=ref).first()


def _resoudre_produit_import(company, ref):
    """NTCPQ41 — résout un produit par ID numérique, SKU exact, ou nom exact
    (insensible à la casse), scopé société. ``None`` si introuvable."""
    from apps.stock.models import Produit
    ref = (ref or '').strip()
    if not ref:
        return None
    if ref.isdigit():
        produit = Produit.objects.filter(company=company, id=int(ref)).first()
        if produit is not None:
            return produit
    produit = Produit.objects.filter(company=company, sku__iexact=ref).first()
    if produit is not None:
        return produit
    return Produit.objects.filter(company=company, nom__iexact=ref).first()


def _parse_date_import(valeur):
    """NTCPQ41 — parse une date CSV (ISO ``AAAA-MM-JJ``). ``None`` si vide."""
    from datetime import date
    valeur = (valeur or '').strip()
    if not valeur:
        return None
    return date.fromisoformat(valeur)


def importer_prix_contractuels_csv(company, csv_text, *, user=None):
    """NTCPQ41 — import CSV en masse de ``PrixContractuel``, auto-suffisant
    (jamais un passage par ``apps/dataimport``, hors périmètre de cette app —
    même patron que les exports ``apps.ventes.exports``).

    Colonnes attendues (en-tête) : ``client_ref``, ``produit_ref``,
    ``prix_ht``, ``date_debut``, ``date_fin``, ``motif``. ``client_ref``/
    ``produit_ref`` acceptent un ID numérique, ou (client) l'email/le nom
    exact, ou (produit) le SKU/le nom exact — toujours scopés à ``company``.

    Valide chaque ligne INDÉPENDAMMENT : les lignes valides sont importées
    même si d'autres échouent (comportement additif standard). Renvoie
    ``{'importees': int, 'total': int, 'erreurs': [{'ligne': int, 'motif':
    str}, ...]}`` — ``ligne`` compte depuis 2 (1 = en-tête)."""
    import csv
    import io
    from decimal import Decimal, InvalidOperation

    reader = csv.DictReader(io.StringIO(csv_text))
    importees = 0
    total = 0
    erreurs = []
    for i, row in enumerate(reader, start=2):
        total += 1
        try:
            client = _resoudre_client_import(company, row.get('client_ref'))
            if client is None:
                raise ValueError('Client introuvable (client_ref).')
            produit = _resoudre_produit_import(
                company, row.get('produit_ref'))
            if produit is None:
                raise ValueError('Produit introuvable (produit_ref).')
            prix_brut = (row.get('prix_ht') or '').strip()
            if not prix_brut:
                raise ValueError('prix_ht requis.')
            prix_ht = Decimal(prix_brut)
            date_debut = _parse_date_import(row.get('date_debut'))
            date_fin = _parse_date_import(row.get('date_fin'))
            if date_debut and date_fin and date_debut > date_fin:
                raise ValueError('date_debut postérieure à date_fin.')
            PrixContractuel.objects.create(
                company=company, client=client, produit=produit,
                prix_ht=prix_ht, date_debut=date_debut, date_fin=date_fin,
                motif=(row.get('motif') or '').strip(), created_by=user)
            importees += 1
        except (ValueError, InvalidOperation, KeyError) as exc:
            erreurs.append({'ligne': i, 'motif': str(exc)})

    return {'importees': importees, 'total': total, 'erreurs': erreurs}


def verifier_compatibilite_envoyable(devis):
    """NTCPQ31 — lève ``ValidationError`` si le mode de compatibilité de la
    société est ``BLOQUANT`` (``ParametresCPQ.compatibilite_mode``) ET que la
    configuration du devis porte encore une violation bloquante (NTCPQ1/NTCPQ21).

    Par défaut (``AVERTISSEMENT``, comportement historique) : ne lève jamais —
    la violation reste un simple badge (NTCPQ21), l'envoi n'est jamais
    empêché. Isolation multi-tenant stricte : le réglage lu est celui de LA
    société du devis, jamais une autre."""
    from rest_framework.exceptions import ValidationError
    from .models import ParametresCPQ
    from .selectors import etat_configuration_devis

    parametres = ParametresCPQ.get_or_default(devis.company)
    if parametres.compatibilite_mode != ParametresCPQ.ModeCompatibilite.BLOQUANT:
        return
    etat = etat_configuration_devis(devis)
    if etat['bloquant']:
        bloquantes = [v for v in etat['violations'] if v['bloquante']]
        detail = bloquantes[0]['message'] if bloquantes else (
            'Violation de compatibilité bloquante.')
        raise ValidationError({'statut': (
            f"Configuration incompatible ({detail}) : l'envoi est bloqué "
            "(réglage société « compatibilité stricte »).")})


def resoudre_regle_remise(*, company, remise):
    """NTCPQ7 — Résout la règle d'approbation de remise la plus SPÉCIFIQUE
    couvrant ``remise`` (%) pour la société. Renvoie une
    ``RegleApprobationRemise`` ou ``None`` (aucune règle → aucune approbation)."""
    candidates = [
        r for r in RegleApprobationRemise.objects.filter(
            company=company, actif=True)
        if r.couvre(remise)]
    if not candidates:
        return None

    def _cle(r):
        largeur = r.largeur_intervalle()
        # None (intervalle ouvert) = moins spécifique → trié après les bornés.
        largeur_key = (1, Decimal('0')) if largeur is None else (0, largeur)
        return (largeur_key, -int(r.priorite), -r.id)

    candidates.sort(key=_cle)
    return candidates[0]


def _profondeur_remise(devis):
    """Profondeur de remise réelle du devis (en %). Utilise ``remise_globale``
    (déjà un pourcentage). Repli 0."""
    return Decimal(str(getattr(devis, 'remise_globale', 0) or 0))


def _echapper(texte):
    """Échappement HTML minimal (la feuille technique est un document INTERNE
    généré hors gabarit Django)."""
    from html import escape
    return escape(str(texte if texte is not None else ''))


def donnees_feuille_configuration(devis):
    """NTCPQ22 — Données de la FEUILLE DE CONFIGURATION technique (INTERNE).

    Document de bureau d'études : il porte volontairement le prix d'achat et la
    marge par ligne — données INTERNES qui ne doivent JAMAIS apparaître dans un
    document client. Il est donc généré exclusivement ici (``apps.cpq``), jamais
    par ``quote_engine`` (réservé au PDF client via ``/proposal`` — règle #4),
    et n'est jamais nommé « devis » ni « proposition ».

    Renvoie ``{reference, date, mode_installation, lignes, totaux,
    regles_declenchees, violations}``."""
    from django.utils import timezone
    from .selectors import etat_configuration_devis

    lignes = []
    total_ht = Decimal('0')
    total_achat = Decimal('0')
    for ligne in devis.lignes.all().select_related('produit'):
        if not ligne.compte_dans_totaux:
            continue
        qte = Decimal(str(ligne.quantite or 0))
        pu = Decimal(str(ligne.prix_unitaire or 0))
        ht = Decimal(str(ligne.total_ht or 0))
        achat_unitaire = Decimal(
            str(getattr(ligne.produit, 'prix_achat', None) or 0))
        achat = achat_unitaire * qte
        marge = ht - achat
        marge_pct = ((marge / ht * Decimal('100')).quantize(_CENT, ROUND_HALF_UP)
                     if ht > 0 else Decimal('0'))
        total_ht += ht
        total_achat += achat
        lignes.append({
            'designation': ligne.designation,
            'quantite': qte,
            'prix_unitaire': pu,
            'total_ht': ht.quantize(_CENT, ROUND_HALF_UP),
            'prix_achat': achat_unitaire,
            'cout_total': achat.quantize(_CENT, ROUND_HALF_UP),
            'marge': marge.quantize(_CENT, ROUND_HALF_UP),
            'marge_pct': marge_pct,
        })

    marge_totale = total_ht - total_achat
    etat = etat_configuration_devis(devis)
    return {
        'reference': devis.reference,
        'date': timezone.now().date().isoformat(),
        'mode_installation': devis.mode_installation or '',
        'lignes': lignes,
        'totaux': {
            'total_ht': total_ht.quantize(_CENT, ROUND_HALF_UP),
            'cout_total': total_achat.quantize(_CENT, ROUND_HALF_UP),
            'marge': marge_totale.quantize(_CENT, ROUND_HALF_UP),
            'marge_pct': ((marge_totale / total_ht * Decimal('100')).quantize(
                _CENT, ROUND_HALF_UP) if total_ht > 0 else Decimal('0')),
        },
        'configuration_valide': etat['configuration_valide'],
        'violations': etat['violations'],
    }


def rendre_feuille_configuration_html(devis):
    """NTCPQ22 — HTML de la feuille de configuration technique (INTERNE).

    Gabarit dédié à ``apps.cpq`` : aucun appel à ``quote_engine`` (règle #4)."""
    data = donnees_feuille_configuration(devis)
    lignes = ''.join(
        '<tr>'
        f'<td>{_echapper(li["designation"])}</td>'
        f'<td class="n">{li["quantite"]}</td>'
        f'<td class="n">{li["prix_unitaire"]}</td>'
        f'<td class="n">{li["total_ht"]}</td>'
        f'<td class="n">{li["prix_achat"]}</td>'
        f'<td class="n">{li["cout_total"]}</td>'
        f'<td class="n">{li["marge"]}</td>'
        f'<td class="n">{li["marge_pct"]} %</td>'
        '</tr>'
        for li in data['lignes'])
    violations = ''.join(
        f'<li>{_echapper(v["message"])}</li>' for v in data['violations'])
    bloc_violations = (
        f'<h2>Points à vérifier</h2><ul>{violations}</ul>' if violations
        else '<p>Configuration conforme aux règles en vigueur.</p>')
    t = data['totaux']
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Feuille de configuration technique {_echapper(data['reference'])}</title>
<style>
 body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; }}
 h1 {{ font-size: 14pt; margin-bottom: 2mm; }}
 .interne {{ color: #b00; font-weight: bold; }}
 table {{ width: 100%; border-collapse: collapse; margin-top: 4mm; }}
 th, td {{ border: 1px solid #999; padding: 1.5mm; text-align: left; }}
 td.n, th.n {{ text-align: right; }}
</style></head><body>
<h1>Feuille de configuration technique — {_echapper(data['reference'])}</h1>
<p class="interne">DOCUMENT INTERNE — bureau d'études. Ne pas transmettre au
client.</p>
<p>Date : {_echapper(data['date'])} · Marché :
{_echapper(data['mode_installation'] or 'non précisé')}</p>
<table>
<thead><tr><th>Désignation</th><th class="n">Qté</th><th class="n">P.U. HT</th>
<th class="n">Total HT</th><th class="n">Prix d'achat</th>
<th class="n">Coût total</th><th class="n">Marge</th>
<th class="n">Marge %</th></tr></thead>
<tbody>{lignes}</tbody>
<tfoot><tr><th colspan="3">Totaux</th><th class="n">{t['total_ht']}</th>
<th class="n"></th><th class="n">{t['cout_total']}</th>
<th class="n">{t['marge']}</th><th class="n">{t['marge_pct']} %</th></tr></tfoot>
</table>
{bloc_violations}
</body></html>"""


def generer_feuille_configuration_pdf(devis):
    """NTCPQ22 — Rend la feuille de configuration technique en PDF (INTERNE).

    Passe par ``core.pdf.render_pdf`` (ARC11 — le seul point d'entrée PDF, qui
    encapsule l'import paresseux de WeasyPrint), JAMAIS par ``quote_engine``
    (réservé au PDF client, règle #4). N'écrit rien, ne persiste aucun
    fichier : le PDF est renvoyé en flux à un utilisateur staff."""
    from core.pdf import render_pdf
    return render_pdf(html=rendre_feuille_configuration_html(devis))


def donnees_comparaison_variantes(devis):
    """NTCPQ26 — Données de la FEUILLE DE COMPARAISON DE VARIANTES (INTERNE).

    Une colonne par tier (``économique``/``standard``/``premium``,
    NTCPQ16) avec totaux HT + marge (prix d'achat inclus — INTERNE, ne
    doit JAMAIS apparaître dans un document client, règle #4) — outil de
    préparation d'entretien commercial, distinct du fichier généré par
    ``/proposal``. Un tier sans variante générée est marqué
    ``disponible: False`` (pas d'erreur).

    Renvoie ``{reference_base, date, colonnes}``."""
    from django.utils import timezone
    from .models import ProduitEquivalent

    variantes = {
        v.variante_tier: v
        for v in devis.variantes_cpq.all().select_related(None)}

    colonnes = []
    for tier in ProduitEquivalent.Tier.values:
        variante = variantes.get(tier)
        if variante is None:
            colonnes.append({'tier': tier, 'disponible': False})
            continue
        total_ht = Decimal('0')
        total_achat = Decimal('0')
        produits = []
        for ligne in variante.lignes.all().select_related('produit'):
            if not ligne.compte_dans_totaux:
                continue
            ht = Decimal(str(ligne.total_ht or 0))
            qte = Decimal(str(ligne.quantite or 0))
            achat_unitaire = Decimal(
                str(getattr(ligne.produit, 'prix_achat', None) or 0))
            total_ht += ht
            total_achat += achat_unitaire * qte
            produits.append(ligne.designation)
        marge = total_ht - total_achat
        marge_pct = ((marge / total_ht * Decimal('100')).quantize(
            _CENT, ROUND_HALF_UP) if total_ht > 0 else Decimal('0'))
        colonnes.append({
            'tier': tier, 'disponible': True,
            'devis_id': variante.id, 'reference': variante.reference,
            'statut': variante.statut,
            'total_ht': str(total_ht.quantize(_CENT, ROUND_HALF_UP)),
            'marge': str(marge.quantize(_CENT, ROUND_HALF_UP)),
            'marge_pct': str(marge_pct),
            'produits': produits,
        })

    return {
        'reference_base': devis.reference,
        'date': timezone.now().date().isoformat(),
        'colonnes': colonnes,
    }


def rendre_comparaison_variantes_html(devis):
    """NTCPQ26 — HTML de la feuille de comparaison de variantes (INTERNE).

    Gabarit dédié à ``apps.cpq`` : aucun appel à ``quote_engine`` (règle #4)."""
    data = donnees_comparaison_variantes(devis)
    disponibles = [c for c in data['colonnes'] if c['disponible']]
    if not disponibles:
        corps = '<p>Aucune variante générée pour ce devis.</p>'
    else:
        entetes = ''.join(f'<th>{_echapper(c["tier"].capitalize())}</th>'
                          for c in disponibles)
        refs = ''.join(f'<td>{_echapper(c["reference"])}</td>'
                       for c in disponibles)
        totaux = ''.join(f'<td class="n">{c["total_ht"]}</td>'
                         for c in disponibles)
        marges = ''.join(f'<td class="n">{c["marge"]}</td>'
                         for c in disponibles)
        marges_pct = ''.join(f'<td class="n">{c["marge_pct"]} %</td>'
                             for c in disponibles)
        max_produits = max(len(c['produits']) for c in disponibles)
        lignes_produits = ''
        for i in range(max_produits):
            cellules = ''.join(
                f'<td>{_echapper(c["produits"][i]) if i < len(c["produits"]) else ""}</td>'
                for c in disponibles)
            lignes_produits += f'<tr><td></td>{cellules}</tr>'
        corps = f"""<table>
<thead><tr><th>Variante</th>{entetes}</tr></thead>
<tbody>
<tr><th>Référence</th>{refs}</tr>
<tr><th colspan="{len(disponibles) + 1}">Produits</th></tr>
{lignes_produits}
</tbody>
<tfoot>
<tr><th>Total HT</th>{totaux}</tr>
<tr><th>Marge</th>{marges}</tr>
<tr><th>Marge %</th>{marges_pct}</tr>
</tfoot>
</table>"""
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Comparaison de variantes {_echapper(data['reference_base'])}</title>
<style>
 body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; }}
 h1 {{ font-size: 14pt; margin-bottom: 2mm; }}
 .interne {{ color: #b00; font-weight: bold; }}
 table {{ width: 100%; border-collapse: collapse; margin-top: 4mm; }}
 th, td {{ border: 1px solid #999; padding: 1.5mm; text-align: left; }}
 td.n {{ text-align: right; }}
</style></head><body>
<h1>Comparaison de variantes — {_echapper(data['reference_base'])}</h1>
<p class="interne">DOCUMENT INTERNE — préparation d'entretien commercial.
Ne pas transmettre au client.</p>
<p>Date : {_echapper(data['date'])}</p>
{corps}
</body></html>"""


def generer_comparaison_variantes_pdf(devis):
    """NTCPQ26 — Rend la feuille de comparaison de variantes en PDF (INTERNE).

    Passe par ``core.pdf.render_pdf`` (ARC11), JAMAIS par ``quote_engine``
    (réservé au PDF client, règle #4)."""
    from core.pdf import render_pdf
    return render_pdf(html=rendre_comparaison_variantes_html(devis))


def generer_variantes_devis(devis, *, user=None, tiers=None):
    """NTCPQ16 — Génère les variantes d'un devis par SUBSTITUTION de produits.

    Pour chaque tier (``économique`` / ``standard`` / ``premium`` par défaut),
    crée un devis BROUILLON complet lié par ``variante_de`` : chaque ligne
    produit est remplacée par le ``ProduitEquivalent`` configuré pour ce tier
    (au prix courant résolu par ``ventes.services.prix_applicable``), les
    autres lignes étant reprises à l'identique. Un tier sans substitution
    reproduit la configuration de base — jamais d'erreur.

    Idempotent : les variantes BROUILLON précédemment générées pour ce devis
    sont remplacées (jamais un empilement de doublons). Ne change AUCUN statut
    et ne génère aucun PDF (règle #4). Renvoie la liste des devis créés."""
    from rest_framework.exceptions import ValidationError
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.services import prix_applicable
    from apps.ventes.utils.company_settings import create_numbered
    from .models import ProduitEquivalent

    if devis.variante_de_id is not None:
        raise ValidationError({'detail': (
            "Ce devis est déjà une variante — générez les variantes depuis le "
            "devis de base.")})

    tiers = list(tiers or [t.value for t in ProduitEquivalent.Tier])
    inconnus = [t for t in tiers if t not in ProduitEquivalent.Tier.values]
    if inconnus:
        raise ValidationError({'tiers': f'Tier inconnu : {inconnus[0]}.'})

    company = devis.company
    # Remplace les variantes brouillon existantes (jamais de doublon empilé).
    anciennes_variantes_ids = list(Devis.objects.filter(
        company=company, variante_de=devis,
        statut=Devis.Statut.BROUILLON).values_list('pk', flat=True))
    Devis.objects.filter(pk__in=anciennes_variantes_ids).delete()
    if anciennes_variantes_ids:
        # NTCPQ20 : le récepteur post_delete de LigneDevis (ventes/receivers.py)
        # capture un instantané de configuration AVANT que le Devis parent
        # soit lui-même supprimé (les lignes sont purgées en premier dans
        # l'ordre de cascade) — un instantané orphelin peut donc être recréé
        # pour une variante qui vient de disparaître. La contrainte FK
        # Postgres étant différée, on peut encore purger ces orphelins avant
        # la vérification de fin de transaction.
        from apps.ventes.models import ConfigurationDevisSnapshot
        ConfigurationDevisSnapshot.objects.filter(
            devis_id__in=anciennes_variantes_ids).delete()

    substitutions = {}
    for eq in ProduitEquivalent.objects.filter(
            company=company, actif=True).select_related('produit_substitut'):
        substitutions.setdefault(eq.tier, {}).setdefault(
            eq.produit_source_id, eq.produit_substitut)

    lignes_source = list(devis.lignes.all().select_related('produit'))
    crees = []
    for tier in tiers:
        par_produit = substitutions.get(tier, {})
        cree = {}

        def _save(ref, _tier=tier):
            cree['obj'] = Devis.objects.create(
                company=company, reference=ref, client=devis.client,
                lead=devis.lead, statut=Devis.Statut.BROUILLON,
                taux_tva=devis.taux_tva, remise_globale=devis.remise_globale,
                note=devis.note, mode_installation=devis.mode_installation,
                etude_params=devis.etude_params,
                prix_cible_kwc=devis.prix_cible_kwc, devise=devis.devise,
                taux_change=devis.taux_change, entite=devis.entite,
                created_by=user, variante_de=devis, variante_tier=_tier)
            return cree['obj']

        create_numbered(Devis, company, 'devis', _save)
        variante = cree['obj']
        for ligne in lignes_source:
            produit = ligne.produit
            designation = ligne.designation
            prix = ligne.prix_unitaire
            substitut = par_produit.get(ligne.produit_id)
            if substitut is not None:
                produit = substitut
                designation = substitut.nom
                try:
                    prix = prix_applicable(
                        produit=substitut, client=devis.client,
                        quantite=ligne.quantite)['prix']
                except Exception:  # noqa: BLE001 — repli prix catalogue
                    prix = substitut.prix_vente
            LigneDevis.objects.create(
                devis=variante, produit=produit, designation=designation,
                quantite=ligne.quantite, prix_unitaire=prix,
                remise=ligne.remise, taux_tva=ligne.taux_tva,
                type_ligne=ligne.type_ligne, ordre=ligne.ordre,
                groupe_index=ligne.groupe_index,
                groupe_label=ligne.groupe_label,
                optionnelle=ligne.optionnelle)
        crees.append(variante)

    if crees:
        from apps.ventes import activity
        activity.log_devis_note(
            devis, user,
            'Variantes générées : '
            + ', '.join(f'{v.variante_tier} ({v.reference})' for v in crees)
            + '.')
    return crees


def taux_remise_global(devis):
    """NTCPQ14 — Taux de remise GLOBAL réel du devis (%).

    Combine les remises de LIGNE et la ``remise_globale`` du devis :
    ``100 × (brut − net) / brut`` où ``brut`` = Σ(quantité × P.U.) des lignes
    comptées dans les totaux et ``net`` = total HT après remises de ligne puis
    remise globale. Aucun prix d'achat / aucune marge n'entre dans le calcul.
    Devis sans ligne valorisée ⇒ 0."""
    brut = Decimal('0')
    for ligne in devis.lignes.all():
        if not ligne.compte_dans_totaux:
            continue
        if ligne.quantite is None or ligne.prix_unitaire is None:
            continue
        brut += Decimal(str(ligne.quantite)) * Decimal(str(ligne.prix_unitaire))
    if brut <= 0:
        return Decimal('0')
    net = Decimal(str(devis.total_ht or 0))
    remise_globale = Decimal(str(devis.remise_globale or 0))
    net = net * (Decimal('1') - remise_globale / Decimal('100'))
    return ((brut - net) / brut * Decimal('100')).quantize(_CENT, ROUND_HALF_UP)


def appliquer_avenant_devis(devis, *, lignes_ajoutees=None,
                            lignes_retirees=None, motif='', user=None):
    """NTCPQ14 — Applique un avenant à un devis DÉJÀ ACCEPTÉ.

    ``lignes_ajoutees`` : liste de dicts ``{produit(id)?, designation,
    quantite, prix_unitaire, remise?, taux_tva?}``. ``lignes_retirees`` : liste
    d'IDs de ``LigneDevis`` du devis. Les totaux sont recalculés (propriétés) ;
    l'approbation NTCPQ7 n'est REDÉCLENCHÉE que si le nouveau taux de remise
    global dépasse le seuil configuré (règle couvrante avec au moins un
    approbateur) — sinon l'avenant reste libre.

    Renvoie l'``AvenantDevis`` créé. Écritures cross-app ventes par imports
    LOCAUX (aucun import de ``ventes.models`` au niveau module)."""
    from rest_framework.exceptions import ValidationError
    from apps.ventes.models import AvenantDevis, Devis, LigneDevis
    from apps.ventes import activity
    from apps.stock.models import Produit

    if devis.statut != Devis.Statut.ACCEPTE:
        raise ValidationError({'statut': (
            "Un avenant ne s'applique qu'à un devis accepté "
            "(un devis en cours se modifie directement).")})

    lignes_ajoutees = lignes_ajoutees or []
    lignes_retirees = lignes_retirees or []
    if not lignes_ajoutees and not lignes_retirees:
        raise ValidationError(
            {'detail': 'Un avenant doit ajouter ou retirer au moins une ligne.'})

    company = devis.company
    snap_ajout = []
    for spec in lignes_ajoutees:
        if not isinstance(spec, dict):
            continue
        produit = None
        produit_id = spec.get('produit') or spec.get('produit_id')
        if produit_id:
            produit = Produit.objects.filter(
                id=produit_id, company=company).first()
            if produit is None:
                raise ValidationError({'produit': 'Produit inconnu.'})
        designation = (spec.get('designation')
                       or (produit.nom if produit else '')).strip()
        if not designation:
            raise ValidationError({'designation': 'Désignation requise.'})
        quantite = Decimal(str(spec.get('quantite', 1) or 1))
        prix = spec.get('prix_unitaire')
        if prix is None:
            prix = produit.prix_vente if produit else Decimal('0')
        prix = Decimal(str(prix or 0))
        remise = Decimal(str(spec.get('remise', 0) or 0))
        ligne = LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=quantite, prix_unitaire=prix, remise=remise,
            taux_tva=spec.get('taux_tva'))
        snap_ajout.append({
            'ligne_id': ligne.id, 'designation': designation,
            'quantite': str(quantite), 'prix_unitaire': str(prix),
            'remise': str(remise),
        })

    snap_retrait = []
    for ligne_id in lignes_retirees:
        ligne = LigneDevis.objects.filter(
            id=ligne_id, devis=devis).first()
        if ligne is None:
            raise ValidationError({'lignes_retirees': 'Ligne inconnue.'})
        snap_retrait.append({
            'ligne_id': ligne.id, 'designation': ligne.designation,
            'quantite': str(ligne.quantite),
            'prix_unitaire': str(ligne.prix_unitaire),
            'remise': str(ligne.remise),
        })
        ligne.delete()

    # Totaux recalculés (propriétés) → nouveau taux de remise global.
    devis.refresh_from_db()
    taux = taux_remise_global(devis)
    regle = resoudre_regle_remise(company=company, remise=taux)
    approbation = regle is not None and regle.nombre_approbateurs >= 1
    if approbation:
        lancer_approbation_devis(devis, user=user, force=True, remise=taux)

    avenant = AvenantDevis.objects.create(
        company=company, devis=devis, lignes_ajoutees=snap_ajout,
        lignes_retirees=snap_retrait, motif=motif or '',
        taux_remise_global=taux, approbation_requise=approbation,
        auteur=user)
    activity.log_devis_note(
        devis, user,
        f'Avenant #{avenant.id} appliqué ({len(snap_ajout)} ligne(s) ajoutée(s), '
        f'{len(snap_retrait)} retirée(s)) — remise globale {taux} %'
        + (' — approbation redéclenchée.' if approbation else '.')
        + (f' Motif : {motif}' if motif else ''))
    return avenant


def lancer_approbation_devis(devis, *, user=None, force=False, remise=None):
    """NTCPQ7 — Instancie les étapes d'approbation d'un devis selon la
    profondeur de remise réelle.

    Résout la règle par ``remise_globale``. Aucune règle (ou
    ``nombre_approbateurs`` = 0) ⇒ aucune étape (envoi libre). Sinon crée
    ``nombre_approbateurs`` étapes ``en_attente`` (niveaux 1..N). Idempotent :
    si des étapes non rejetées existent déjà pour ce devis, les renvoie sans en
    recréer. Renvoie la liste des étapes (existantes ou créées).

    NTCPQ14 — ``force=True`` REDÉCLENCHE un nouveau tour d'approbation même si
    un tour précédent est déjà approuvé (avenant au-dessus du seuil) ; ``remise``
    permet d'imposer la profondeur à considérer (taux global recalculé) au lieu
    de ``remise_globale``."""
    from .models import ParametresCPQ
    if not ParametresCPQ.get_or_default(devis.company).approbation_active:
        # NTCPQ30 — approbation désactivée pour CETTE société : envoi
        # libre, jamais de blocage NTCPQ7, sans affecter les autres sociétés.
        return []

    existantes = list(EtapeApprobationDevis.objects.filter(
        devis_id=devis.id).exclude(
            statut=EtapeApprobationDevis.Statut.REJETE))
    if existantes and not force:
        return existantes
    if force and any(e.statut == EtapeApprobationDevis.Statut.EN_ATTENTE
                     for e in existantes):
        # Un tour est déjà en attente : ne pas en empiler un second.
        return [e for e in existantes
                if e.statut == EtapeApprobationDevis.Statut.EN_ATTENTE]

    if remise is None:
        remise = _profondeur_remise(devis)
    regle = resoudre_regle_remise(company=devis.company, remise=remise)
    if regle is None or regle.nombre_approbateurs < 1:
        return []

    etapes = []
    for niveau in range(1, regle.nombre_approbateurs + 1):
        etapes.append(EtapeApprobationDevis.objects.create(
            company=devis.company, devis=devis, regle=regle,
            niveau=niveau, niveau_approbation=regle.niveau_approbation,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE))
    return etapes


def approuver_etape_devis(devis, *, user, commentaire=''):
    """NTCPQ8 — Approuve la PREMIÈRE étape en attente du devis.

    Pose ``approbateur``/``decision_le``, passe la statut à ``approuve``, logue
    l'événement dans le chatter du devis (DevisActivity). Renvoie
    ``(etape, toutes_approuvees)`` où ``toutes_approuvees`` est True quand plus
    aucune étape n'est en attente. Lève ``ValidationError`` s'il n'y a aucune
    étape en attente."""
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    from apps.ventes import activity

    etape = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()
    if etape is None:
        raise ValidationError({'detail': 'Aucune étape en attente.'})
    etape.statut = EtapeApprobationDevis.Statut.APPROUVE
    etape.approbateur = user
    etape.decision_le = timezone.now()
    if commentaire:
        etape.commentaire = commentaire
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire'])
    activity.log_devis_note(
        devis, user,
        f"Approbation de remise — étape {etape.niveau} approuvée"
        + (f" : {commentaire}" if commentaire else ""))
    reste = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE).exists()
    return etape, not reste


def rejeter_etape_devis(devis, *, user, motif=''):
    """NTCPQ8 — Rejette la première étape en attente : passe la statut à
    ``rejete`` (approbateur/motif), remet le devis en ``brouillon`` et logue
    l'événement (auteur + motif) dans le chatter. Renvoie l'étape rejetée."""
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    from apps.ventes import activity
    from apps.ventes.models import Devis

    etape = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()
    if etape is None:
        raise ValidationError({'detail': 'Aucune étape en attente.'})
    etape.statut = EtapeApprobationDevis.Statut.REJETE
    etape.approbateur = user
    etape.decision_le = timezone.now()
    etape.commentaire = motif or ''
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire'])
    # Renvoie le devis en brouillon (jamais envoyé tant que la remise n'est pas
    # approuvée / revue à la baisse).
    if devis.statut != Devis.Statut.BROUILLON:
        devis.statut = Devis.Statut.BROUILLON
        devis.save(update_fields=['statut'])
    activity.log_devis_note(
        devis, user,
        f"Approbation de remise — étape {etape.niveau} REJETÉE"
        + (f" : {motif}" if motif else "")
        + " — devis renvoyé en brouillon.")
    return etape


def _ligne_depuis_action(action, devis, company):
    """NTCPQ10 — Traduit une action de règle résolue en LigneDevis (ou
    application de bundle). Ignore les actions purement consultatives."""
    from apps.ventes.models import LigneDevis
    if not isinstance(action, dict):
        return
    produit_id = action.get('produit_id')
    offre_id = action.get('offre_id')
    if produit_id:
        from apps.stock.models import Produit
        produit = Produit.objects.filter(
            id=produit_id, company=company).first()
        if produit is None:
            return
        qte = Decimal(str(action.get('quantite', 1) or 1))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=qte, prix_unitaire=produit.prix_vente,
            remise=Decimal('0'))
    elif offre_id:
        from .models import OffreGroupee
        offre = OffreGroupee.objects.filter(
            id=offre_id, company=company).first()
        if offre is not None:
            appliquer_offre_groupee(offre=offre, devis=devis)


def generer_devis_depuis_configurateur(session, *, user=None, lead=None,
                                       client=None):
    """NTCPQ10 — Transforme le résultat résolu d'une session configurateur en
    Devis BROUILLON éditable (lignes pré-remplies). Ne génère JAMAIS le PDF.

    Le client est résolu depuis le lead via ``crm.services.resolve_client_for_lead``
    (réutilise le lien/le match existant, jamais de doublon) quand seul le lead
    est fourni. Renvoie le Devis créé."""
    from rest_framework.exceptions import ValidationError
    from apps.ventes.models import Devis
    from apps.ventes.utils.company_settings import create_numbered
    from .selectors import resoudre_configurateur

    company = session.company
    if client is None and lead is not None:
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(lead)
    if client is None:
        raise ValidationError(
            {'client': 'Un client ou un lead est requis.'})

    def _save(ref):
        return Devis.objects.create(
            reference=ref, company=company, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=user)

    devis = create_numbered(Devis, company, 'devis', _save)

    result = resoudre_configurateur(session)
    for regle in result['actions_declenchees']:
        for action in regle.get('actions', []):
            _ligne_depuis_action(action, devis, company)

    session.devis = devis
    session.save(update_fields=['devis', 'updated_at'])
    return devis
