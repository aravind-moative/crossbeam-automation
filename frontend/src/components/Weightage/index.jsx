import React, { useEffect, useState } from "react";
import "./style.css";

const OPPORTUNITY_FIELDS = [
  { label: "Opportunity Size", key: "opportunity_size" },
  { label: "Relationship Status", key: "relationship_status" },
  { label: "Engagement Score", key: "engagement_score" },
  { label: "Opportunity Stage", key: "opportunity_stage" },
  { label: "Winnability", key: "winnability_opinion" }
];

const PARTNER_FIELDS = [
  { label: "Relationship Strength", key: "relationship_strength_score" },
  { label: "Recent Deal Support", key: "recent_deal_support" },
  { label: "Stickiness Score", key: "stickiness_score" }
];

export default function Weightage() {
  const [weights, setWeights] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fetchWeights = () => {
    setLoading(true);
    fetch("/viz/api/weights")
      .then(res => res.json())
      .then(data => {
        const w = {};
        data.forEach(row => {
          w[row.name] = { ...row };
        });
        setWeights(w);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load weights.");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchWeights();
  }, []);

  const getWeight = key => weights[key]?.weight ?? 0;

  const handleChange = (key, value) => {
    const num = parseFloat(value);
    const clampedValue = isNaN(num) || num < 0 ? 0 : num;

    setWeights(prev => ({
      ...prev,
      [key]: { ...prev[key], weight: clampedValue }
    }));

    setSuccess("");
    setError("");
  };

  const opportunityTotal = OPPORTUNITY_FIELDS.reduce(
    (sum, f) => sum + (parseFloat(getWeight(f.key)) || 0),
    0
  );
  const partnerTotal = PARTNER_FIELDS.reduce(
    (sum, f) => sum + (parseFloat(getWeight(f.key)) || 0),
    0
  );

  const opportunityValid = opportunityTotal === 100;
  const partnerValid = partnerTotal === 100;
  const canSave = opportunityValid && partnerValid && !saving;

  const handleSave = async e => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    const data = { opportunity: {}, partner: {} };
    OPPORTUNITY_FIELDS.forEach(f => {
      data.opportunity[f.key] = { weight: parseFloat(getWeight(f.key)) || 0 };
    });
    PARTNER_FIELDS.forEach(f => {
      data.partner[f.key] = { weight: parseFloat(getWeight(f.key)) || 0 };
    });

    try {
      const res = await fetch("/viz/api/weights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        setSuccess("Weights saved!");
        fetchWeights();
      } else {
        setError("Failed to save weights.");
      }
    } catch {
      setError("Failed to save weights.");
    }
    setSaving(false);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <form className="weightage-form" onSubmit={handleSave}>
      <h1 className="heading">Configure Weights</h1>
      <span>
        Assign weights to opportunity and partner attributes based on their impact on your decision-making process. Make sure each group adds up to 100%
      </span>
      <div className="container">
        <div className="section-box">
          <h2>Opportunity Weight</h2>
          <div className="note">
            Assign weights to each opportunity parameter so their total is 100%.
          </div>
          <div className="inputs-div">
            {OPPORTUNITY_FIELDS.map(f => (
              <div className="field-row" key={f.key}>
                <label>{f.label}</label>
                <div className="input-wrapper">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={getWeight(f.key)}
                    onChange={e => handleChange(f.key, e.target.value)}
                    onKeyDown={e => {
                      if (e.key === "-" || e.key === "e") e.preventDefault();
                    }}
                    disabled={saving}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className={`total ${opportunityValid ? "valid" : "invalid"}`}>
            Total: {opportunityTotal}
          </div>
          {!opportunityValid && (
            <div className="error-text">Total must be 100%</div>
          )}
        </div>

        <div className="section-box">
          <h2>Partner Weight</h2>
          <div className="note">
            Assign weights to each partner parameter so their total is 100%.
          </div>
          <div className="inputs-div">
            {PARTNER_FIELDS.map(f => (
              <div className="field-row" key={f.key}>
                <label className="field-label">{f.label}</label>
                <div className="input-wrapper">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={getWeight(f.key)}
                    onChange={e => handleChange(f.key, e.target.value)}
                    onKeyDown={e => {
                      if (e.key === "-" || e.key === "e") e.preventDefault();
                    }}
                    disabled={saving}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className={`total ${partnerValid ? "valid" : "invalid"}`}>
            Total: {partnerTotal}
          </div>
          {!partnerValid && (
            <div className="error-text">Total must be 100%</div>
          )}
        </div>
      </div>

      <button className="save-button" disabled={!canSave}>
        {saving ? "Saving..." : "Save"}
      </button>
      {success && <div className="success-text">{success}</div>}
      {error && <div className="error-text">{error}</div>}
    </form>
  );
}
