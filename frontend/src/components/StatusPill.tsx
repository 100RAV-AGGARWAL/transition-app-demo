export default function StatusPill({ value }: { value: string }) {
  return <span className={`pill pill-${value.replace(/_/g, '-')}`}>{value.replace(/_/g, ' ')}</span>;
}
