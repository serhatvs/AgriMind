import type { RankFieldsResponse } from "../types/ranking";

interface RankingSummaryProps {
  response: RankFieldsResponse;
}

export function RankingSummary({ response }: RankingSummaryProps) {
  return (
    <section className="summary-card">
      <div>
        <p className="summary-card__eyebrow">Selected crop</p>
        <h2 className="summary-card__title">{response.crop.crop_name}</h2>
        <p className="summary-card__subtitle">
          {response.crop.scientific_name ?? "Scientific name not available"}
        </p>
      </div>

      <div className="summary-card__stat">
        <span className="summary-card__stat-value">{response.total_fields_evaluated}</span>
        <span className="summary-card__stat-label">fields evaluated</span>
      </div>
    </section>
  );
}
