import React, { useEffect, useState } from "react";
import "./style.css";

const LANES = [
  { label: "0-20", min: 0, max: 20 },
  { label: "21-40", min: 21, max: 40 },
  { label: "41-60", min: 41, max: 60 },
  { label: "61-80", min: 61, max: 80 },
  { label: "81-100", min: 81, max: 100 },
];

const laneDescriptions = {
  "0-20": "Seed stage | Think long-term | Hidden gems",
  "21-40": "Warming up | Light signals | Stay curious",
  "41-60": "Momentum building | Worth a deeper look",
  "61-80": "Strong plays | Push forward | Sync up",
  "81-100": "Prime targets | Go big | Win together",
};

export default function PipeLineLander() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        // Add a cache-busting query parameter
        const res = await fetch(`/viz/api/pipeline-scores?_t=${new Date().getTime()}`);
        
        if (!res.ok) {
          const errorText = await res.text();
          console.error('API Error Response:', errorText);
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        // Check if response is JSON
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          const responseText = await res.text();
          console.error('Non-JSON Response:', responseText);
          throw new Error('Server returned non-JSON response. Please check if the backend is running.');
        }
        
        const data = await res.json();
        setRecords(data);
        setLoading(false);
      } catch (err) {
        console.error('Fetch error:', err);
        setError(`Failed to load pipeline data: ${err.message}`);
        setLoading(false);
      }
    };

    fetchRecords();
  }, []); // Empty dependency array ensures fetch on mount

  if (loading) return <div>Loading pipeline records...</div>;
  if (error) return (
    <div className="pipeline-error">
      <h3>Error Loading Pipeline Data</h3>
      <p>{error}</p>
      <div className="error-troubleshooting">
        <p><strong>Troubleshooting:</strong></p>
        <ul>
          <li>Make sure the backend server is running on port 8000</li>
          <li>Check if the database is properly configured</li>
          <li>Verify the API endpoint is accessible</li>
        </ul>
        <button 
          onClick={() => window.location.reload()} 
          className="retry-button"
        >
          Retry
        </button>
      </div>
    </div>
  );

  const lanes = LANES.map((lane) => {
    const filtered = records.filter(
      (rec) =>
        rec.combined_score_percent >= lane.min &&
        rec.combined_score_percent <= lane.max
    );
    // Sort descending by combined_score_percent
    filtered.sort((a, b) => b.combined_score_percent - a.combined_score_percent);
    return {
      ...lane,
      records: filtered,
    };
  });

  return (
    <div>
      <div className="intro-card">
        <div className="intro-header">
          <h1>Pipeline View</h1>
        </div>
        <span>
          Explore opportunities segmented by partner overlap percentage. Each lane gives insight into how aligned a partner is with an opportunity, helping prioritize engagement and co-sell strategies.
        </span>
      </div>

      <div className="pipeline-lanes">
        {lanes.map((lane) => (
          <div key={lane.label} className="pipeline-lane">
            <h3 className="pipeline-lane-title">{lane.label}</h3>
            <p className="pipeline-lane-description">{laneDescriptions[lane.label]}</p>
            {lane.records.length === 0 ? (
              <div className="pipeline-no-records">No records</div>
            ) : (
              <div className="pipeline-card-list">
                {lane.records.map((rec) => (
                  <div key={rec.id} className="pipeline-card">
                    <div className="pipeline-card-title">{rec.opportunity_name}</div>
                    <div className="pipeline-card-meta">
                      <span>Partner: {rec.partner_name}</span>
                      <span>{rec.combined_score_percent.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}