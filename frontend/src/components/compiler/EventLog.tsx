import type { CompilerEvent } from "../../types/compiler";

interface Props {
  events: CompilerEvent[];
}

export function EventLog({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-xs text-text-dim">
        No compiler events yet.
      </div>
    );
  }

  return (
    <ul className="space-y-1 px-3 py-2 font-mono text-[11px]">
      {events.map((e) => (
        <li key={e.id} className="flex gap-3 text-text-secondary">
          <span className="text-text-dim">{e.timestamp}</span>
          <span>{e.message}</span>
        </li>
      ))}
    </ul>
  );
}
