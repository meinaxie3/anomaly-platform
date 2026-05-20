import { Inbox } from 'lucide-react'

interface Props {
  title?: string
  description?: string
}

export function EmptyState({
  title = 'No data yet',
  description = 'Data will appear here once the pipeline has processed events.',
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white py-16 text-center">
      <Inbox className="mb-3 h-10 w-10 text-slate-400" aria-hidden="true" />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
    </div>
  )
}
