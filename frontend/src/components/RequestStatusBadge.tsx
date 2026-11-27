// Badge de statut d'une demande (SC-35, ENF-16) : le libellé est toujours écrit,
// la couleur ne fait que le doubler (tableau 13 du cahier des charges).

import { REQUEST_STATUS_LABELS, type RequestStatus } from '../api/requests'
import './RequestStatusBadge.css'

export default function RequestStatusBadge({ status }: { status: RequestStatus }) {
  return (
    <span className={`badge request-status is-${status}`}>
      <span className="request-status-dot" aria-hidden="true" />
      {REQUEST_STATUS_LABELS[status]}
    </span>
  )
}
