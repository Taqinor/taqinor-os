import { useState } from 'react'
import { KeyRound, Lock } from 'lucide-react'
import {
  Badge, Button, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { formatDate, formatMAD } from '../../../lib/format'
import { SOURCE_BADGE, quantiteVerrouillee, cadreAcheteur } from './LigneRow.utils'

/* ============================================================================
   AOF179 — Une ligne du bordereau des prix.
   ----------------------------------------------------------------------------
   **AUCUN TOTAL N'EST CALCULÉ ICI** (garde AOF94). Ni `quantité × PU`, ni un
   sous-total, ni une TVA : `total_ht` et `prix_unitaire_lettres` sont LUS du
   payload serveur, qui seul détient la cascade de prix à l'envers (AOF127) et
   l'invariant `Σ q×PU == cible` au centime. Le jour où l'écran « aide » en
   recalculant, il contredit le PDF — c'est exactement le défaut « fichier
   frère périmé », version client.

   **Provenance de la quantité (AOF120).** Trois régimes visibles, jamais
   implicites :
     • `calepinage` — la quantité vient d'une variante retenue : VERROUILLÉE
       (la modifier à la main casserait l'invariant « quantités bordereau ==
       engagements des planches ») ;
     • `acheteur`   — cadre BPU/DQE importé : la checklist partenaire interdit
       de toucher désignation, unité ou quantité ;
     • `manuelle`   — saisie libre, éditable.
   Un déverrouillage est POSSIBLE mais jamais silencieux : motif obligatoire,
   tracé côté serveur.

   Le PU est en LECTURE SEULE : il est produit par la cascade serveur. La
   bibliothèque de prix ne « remplit » donc pas un champ, elle PROPOSE une
   valeur (avec sa date et son dossier d'origine) qu'un clic fait appliquer
   PAR LE SERVEUR.
   ========================================================================== */

export default function LigneRow({
  ligne,
  sections = [],
  proposition,
  onModifier,
  onDeplacer,
  onDemanderDeverrouillage,
  onAppliquerPrix,
  occupe = false,
}) {
  const [quantite, setQuantite] = useState(String(ligne.quantite ?? ''))
  // La valeur de référence reste celle du serveur : on se recale dessus quand
  // elle change, en ajustant l'état AU RENDU (jamais dans un effet — évite le
  // rendu en cascade ; https://react.dev/learn/you-might-not-need-an-effect).
  const [quantitePrec, setQuantitePrec] = useState(ligne.quantite)
  if (ligne.quantite !== quantitePrec) {
    setQuantitePrec(ligne.quantite)
    setQuantite(String(ligne.quantite ?? ''))
  }

  const verrou = quantiteVerrouillee(ligne)
  const acheteur = cadreAcheteur(ligne)
  const badge = SOURCE_BADGE[ligne.quantite_source] ?? SOURCE_BADGE.manuelle
  const designation = ligne.designation || ligne.libelle || ''

  const commitQuantite = () => {
    if (verrou) return
    if (String(ligne.quantite ?? '') === quantite) return
    onModifier?.(ligne, { quantite })
  }

  const autresSections = sections.filter((s) => s.id !== ligne.section)

  return (
    <tr className="border-b border-border align-top">
      <td className="px-2 py-2 text-xs tabular-nums text-muted-foreground">{ligne.numero}</td>

      <td className="px-2 py-2">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">{designation}</span>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={badge.tone}>{badge.label}</Badge>
            {ligne.deverrouillee && (
              <Badge tone="danger">
                déverrouillée
                {ligne.deverrouillee_motif ? ` — ${ligne.deverrouillee_motif}` : ''}
              </Badge>
            )}
          </div>
          {proposition && (
            <p className="text-xs text-muted-foreground">
              PU proposé (bibliothèque de prix) : {formatMAD(proposition.prix_unitaire)}
              {proposition.date ? ` — relevé le ${formatDate(proposition.date)}` : ''}
              {proposition.dossier_origine ? ` — dossier ${proposition.dossier_origine}` : ''}
              {onAppliquerPrix && (
                <Button
                  size="sm" variant="link" className="ml-1 h-auto p-0"
                  disabled={occupe}
                  onClick={() => onAppliquerPrix(ligne, proposition)}
                >
                  Appliquer ce PU
                </Button>
              )}
            </p>
          )}
        </div>
      </td>

      <td className="px-2 py-2 text-xs">{ligne.unite || '—'}</td>

      <td className="px-2 py-2">
        <div className="flex items-center gap-1">
          <Input
            aria-label={`Quantité — ${designation}`}
            value={quantite}
            inputMode="decimal"
            readOnly={verrou}
            disabled={verrou || occupe}
            onChange={(e) => setQuantite(e.target.value)}
            onBlur={commitQuantite}
            className="h-8 w-24 text-right"
          />
          {verrou && (
            <>
              <Lock className="size-3.5 text-muted-foreground" aria-hidden="true" />
              {onDemanderDeverrouillage && (
                <Button
                  size="icon-sm" variant="ghost"
                  aria-label={`Déverrouiller la quantité — ${designation}`}
                  disabled={occupe}
                  onClick={() => onDemanderDeverrouillage(ligne)}
                >
                  <KeyRound aria-hidden="true" />
                </Button>
              )}
            </>
          )}
        </div>
      </td>

      {/* PU et PU en lettres : LECTURE SEULE, recalculés par le serveur. */}
      <td className="px-2 py-2 text-right text-sm tabular-nums">
        {ligne.prix_unitaire != null ? formatMAD(ligne.prix_unitaire) : '—'}
      </td>
      <td className="px-2 py-2 text-xs italic text-muted-foreground">
        {ligne.prix_unitaire_lettres || '—'}
      </td>
      <td className="px-2 py-2 text-right text-xs tabular-nums">
        {ligne.tva != null ? `${ligne.tva} %` : '—'}
      </td>
      <td className="px-2 py-2 text-right text-sm font-medium tabular-nums">
        {ligne.total_ht != null ? formatMAD(ligne.total_ht) : '—'}
      </td>

      <td className="px-2 py-2">
        {autresSections.length > 0 && onDeplacer ? (
          <Select
            value=""
            disabled={occupe || acheteur}
            onValueChange={(v) => onDeplacer(ligne, Number(v))}
          >
            <SelectTrigger
              className="h-8 w-44"
              aria-label={`Déplacer « ${designation} » vers une autre section`}
            >
              <SelectValue placeholder="Déplacer vers…" />
            </SelectTrigger>
            <SelectContent>
              {autresSections.map((s) => (
                <SelectItem key={s.id} value={String(s.id)}>
                  {s.numero ? `${s.numero} — ` : ''}{s.libelle}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}
      </td>
    </tr>
  )
}
