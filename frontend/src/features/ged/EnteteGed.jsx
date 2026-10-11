import { PageHeader } from '../../ui/PageHeader'

/* En-tête commun des écrans GED (navigateur, numérisation) : l'en-tête UNIQUE
   de l'app (VX28, APX32 (e)) avec l'espacement de ces pages. */
export default function EnteteGed(props) {
  return <PageHeader className="mb-4" {...props} />
}
