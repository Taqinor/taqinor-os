import {
  useEffect, useMemo, useRef, useState,
} from 'react'
import { AlertTriangle, Check, Copy } from 'lucide-react'
import { Badge, Button, Checkbox } from '../../../ui'
import { svgVersPng, svgVersPngBlob, LARGEUR_EXPORT_DEFAUT } from '../studio/svgToPng'
import { detecterSurChamps } from '../sanitisation'

/* ============================================================================
   AOF107 (2/3) — Export « prêt à coller » : image annotée + liste numérotée.
   ----------------------------------------------------------------------------
   Contrainte technique RÉELLE, pas une préférence : depuis une session cloud,
   les pièces jointes classiques sont illisibles (SVG bloqué par la politique
   MIME, PNG en erreur Graph 400, PDF de plans = scans raster sans texte),
   alors qu'une image COLLÉE dans la conversation passe. D'où ce composant :
   il aplatit l'image annotée (AOF106) ET la liste numérotée des questions en
   UN SEUL bitmap, à 1 000 px de large (`svgToPng.js`, AOF75, brique déjà
   partagée), et propose de le COPIER dans le presse-papiers pour un Ctrl+V
   direct — pas un fichier à joindre.

   **Le contrôle de vocabulaire est une PORTE, pas un filtre silencieux.**
   `sanitisation.js` (3/3) détecte les mots interdits AVANT toute génération :
   tant qu'un mot reste détecté, l'export est BLOQUÉ ; une case à cocher
   « J'ai vérifié le vocabulaire, exporter quand même » lève le blocage —
   c'est la CONFIRMATION EXPLICITE exigée par le Done, jamais une correction
   automatique et silencieuse du texte.
   ========================================================================== */

export const MAX_CARACTERES_LIGNE = 78
const HAUTEUR_LIGNE_PX = 26
const MARGE_PX = 24
const TAILLE_POLICE_PX = 20

/** Retour à la ligne PUR, sans dépendance — coupe aux espaces. */
export function envelopperTexte(texte, maxCaracteres = MAX_CARACTERES_LIGNE) {
  const mots = String(texte ?? '').trim().split(/\s+/).filter(Boolean)
  if (mots.length === 0) return ['']
  const lignes = []
  let courante = ''
  for (const mot of mots) {
    const essai = courante ? `${courante} ${mot}` : mot
    if (essai.length > maxCaracteres && courante) {
      lignes.push(courante)
      courante = mot
    } else {
      courante = essai
    }
  }
  if (courante) lignes.push(courante)
  return lignes
}

/** Les lignes FINALES du bloc « liste numérotée », déjà enveloppées. */
export function construireLignesExport(questions = [], maxCaracteres = MAX_CARACTERES_LIGNE) {
  const lignes = []
  questions.forEach((q, i) => {
    const entete = `${i + 1}. Repère ${q.repere} — ${q.texte ?? ''}`
    lignes.push(...envelopperTexte(entete, maxCaracteres))
  })
  return lignes
}

/** Champs RÉELLEMENT rendus dans l'export, nommés par repère — c'est ce que
 * le contrôle de vocabulaire interroge (jamais la réponse/décision interne,
 * qui ne sort pas dans cet export). */
export function champsAControler(questions = []) {
  const champs = {}
  for (const q of questions) {
    if (q.texte) champs[`Repère ${q.repere}`] = q.texte
  }
  return champs
}

function LigneAlerte({ repere, trouvailles }) {
  return (
    <li className="flex flex-col gap-0.5">
      <span className="font-medium text-foreground">{repere}</span>
      {trouvailles.map((t, i) => (
        // eslint-disable-next-line react/no-array-index-key -- alertes en lecture seule, append-only par détection
        <span key={i} className="flex flex-wrap items-center gap-1 text-muted-foreground">
          <span className="font-medium text-foreground">{t.libelle}</span>
          <span>
            {t.remplacement ? `→ « ${t.remplacement} »` : '→ à retirer (aucune formulation de remplacement)'}
          </span>
        </span>
      ))}
    </li>
  )
}

export function ExportQR({
  imageSrc, questions = [], date, onExporte,
}) {
  const svgRef = useRef(null)
  const [dimsImage, setDimsImage] = useState({ largeur: LARGEUR_EXPORT_DEFAUT, hauteur: Math.round(LARGEUR_EXPORT_DEFAUT * 0.75) })
  const [confirme, setConfirme] = useState(false)
  const [resultat, setResultat] = useState(null) // { dataUrl, largeur, hauteur }
  const [copie, setCopie] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => { setConfirme(false); setResultat(null); setCopie(false) }, [imageSrc, questions])

  const alertesParChamp = useMemo(
    () => detecterSurChamps(champsAControler(questions), { date }),
    [questions, date],
  )
  const champsFautifs = Object.keys(alertesParChamp)
  const bloque = champsFautifs.length > 0 && !confirme

  const lignes = useMemo(() => construireLignesExport(questions), [questions])
  const hauteurListe = MARGE_PX * 2 + lignes.length * HAUTEUR_LIGNE_PX
  const hauteurTotale = dimsImage.hauteur + hauteurListe

  const genererApercu = async () => {
    if (bloque || !svgRef.current) return
    setEnCours(true)
    setErreur(null)
    try {
      const r = await svgVersPng(svgRef.current, { largeur: LARGEUR_EXPORT_DEFAUT })
      setResultat(r)
      onExporte?.(r)
    } catch {
      setErreur('Impossible de générer l’image — réessayez.')
    } finally {
      setEnCours(false)
    }
  }

  const copierImage = async () => {
    if (!svgRef.current) return
    setEnCours(true)
    setErreur(null)
    try {
      const { blob } = await svgVersPngBlob(svgRef.current, { largeur: LARGEUR_EXPORT_DEFAUT })
      if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
        setCopie(true)
      } else {
        setErreur('Le presse-papiers n’est pas disponible sur ce navigateur — utilisez « Générer l’aperçu » puis un clic droit ▸ Copier l’image.')
      }
    } catch {
      setErreur('Copie impossible — réessayez.')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="flex flex-col gap-3" data-export-qr>
      {imageSrc && (
        // Image cachée, uniquement pour lire ses dimensions NATURELLES et
        // caler la hauteur du SVG d'export sur le bon ratio (préserve la
        // lisibilité à 1 000 px de large — Done AOF107).
        <img
          src={imageSrc}
          alt=""
          aria-hidden="true"
          style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', opacity: 0 }}
          onLoad={(e) => {
            const w = e.target.naturalWidth
            const h = e.target.naturalHeight
            if (w > 0 && h > 0) {
              setDimsImage({ largeur: LARGEUR_EXPORT_DEFAUT, hauteur: Math.round(LARGEUR_EXPORT_DEFAUT * (h / w)) })
            }
          }}
        />
      )}

      {champsFautifs.length > 0 && (
        <div role="alert" className="flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2">
          <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            Vocabulaire à revoir avant export
          </p>
          <ul className="flex flex-col gap-2 text-xs">
            {champsFautifs.map((nom) => (
              <LigneAlerte key={nom} repere={nom} trouvailles={alertesParChamp[nom]} />
            ))}
          </ul>
          <label className="flex items-center gap-2 text-xs font-medium text-foreground" htmlFor="ao-export-confirmer-vocabulaire">
            <Checkbox
              id="ao-export-confirmer-vocabulaire"
              checked={confirme}
              onCheckedChange={(v) => setConfirme(v === true)}
            />
            J’ai vérifié le vocabulaire, exporter quand même
          </label>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={bloque || enCours} loading={enCours} onClick={genererApercu}>
          Générer l’aperçu
        </Button>
        <Button size="sm" variant="outline" disabled={bloque || enCours} onClick={copierImage}>
          <Copy className="size-3.5" aria-hidden="true" />
          Copier l’image (coller dans la conversation)
        </Button>
        {copie && (
          <Badge tone="success">
            <Check className="size-3.5" aria-hidden="true" />
            Copiée
          </Badge>
        )}
      </div>

      {erreur && <p role="alert" className="text-xs text-destructive">{erreur}</p>}

      {resultat && (
        <img
          src={resultat.dataUrl}
          alt="Aperçu de l’export — image annotée et liste numérotée des questions"
          className="max-w-[min(100%,1000px)] rounded-md border border-border"
          width={resultat.largeur}
          height={resultat.hauteur}
        />
      )}

      {/* Le SVG source de l'export : hors écran, jamais affiché — seul le
          PNG produit par `svgVersPng` (thème clair, fond opaque, tokens
          résolus) est montré à l'utilisateur. */}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${LARGEUR_EXPORT_DEFAUT} ${hauteurTotale}`}
        width={LARGEUR_EXPORT_DEFAUT}
        height={hauteurTotale}
        aria-hidden="true"
        style={{ position: 'absolute', left: -99999, top: 0, pointerEvents: 'none' }}
      >
        <rect x={0} y={0} width={LARGEUR_EXPORT_DEFAUT} height={hauteurTotale} fill="#ffffff" />
        {imageSrc && (
          <image
            href={imageSrc}
            x={0}
            y={0}
            width={LARGEUR_EXPORT_DEFAUT}
            height={dimsImage.hauteur}
            preserveAspectRatio="xMidYMid meet"
          />
        )}
        <g transform={`translate(${MARGE_PX}, ${dimsImage.hauteur + MARGE_PX + TAILLE_POLICE_PX})`}>
          {lignes.map((ligne, i) => (
            <text
              // eslint-disable-next-line react/no-array-index-key -- lignes déjà enveloppées, ordre stable, aucune clé métier disponible
              key={i}
              x={0}
              y={i * HAUTEUR_LIGNE_PX}
              fontSize={TAILLE_POLICE_PX}
              fontFamily="sans-serif"
              fill="#111111"
            >
              {ligne}
            </text>
          ))}
        </g>
      </svg>
    </div>
  )
}

export default ExportQR
