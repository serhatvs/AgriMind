import type { RankedFieldRecommendation } from "../types/ranking";

interface FieldRankingCardProps {
  result: RankedFieldRecommendation;
}

function renderList(items: string[], emptyLabel: string) {
  if (items.length === 0) {
    return <li className="bullet-list__empty">{emptyLabel}</li>;
  }

  return items.map((item) => <li key={item}>{item}</li>);
}

export function FieldRankingCard({ result }: FieldRankingCardProps) {
  const { explanation } = result;

  return (
    <article className="result-card">
      <div className="result-card__header">
        <div>
          <p className="result-card__eyebrow">Rank #{result.rank}</p>
          <h3 className="result-card__title">{result.field_name}</h3>
        </div>
        <div className="score-pill">
          <span className="score-pill__value">{result.total_score.toFixed(1)}</span>
          <span className="score-pill__label">score</span>
        </div>
      </div>

      <p className="result-card__summary">{explanation.short_explanation}</p>

      <div className="result-card__grid">
        <section>
          <h4 className="result-card__section-title">Strengths</h4>
          <ul className="bullet-list bullet-list--positive">
            {renderList(explanation.strengths, "No clear strengths identified.")}
          </ul>
        </section>

        <section>
          <h4 className="result-card__section-title">Weaknesses</h4>
          <ul className="bullet-list bullet-list--warning">
            {renderList(explanation.weaknesses, "No material weaknesses identified.")}
          </ul>
        </section>
      </div>
    </article>
  );
}
