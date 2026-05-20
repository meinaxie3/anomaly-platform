import { AlertTriangle } from 'lucide-react'

interface Props {
  message?: string
}

export function ErrorBanner({ message = 'Failed to load data. Retrying…' }: Props) {
  return (
    <div
      role="alert"
      className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
      {message}
    </div>
  )
}
