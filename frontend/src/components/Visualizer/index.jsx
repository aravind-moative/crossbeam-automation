import React, { useState, useEffect } from 'react';
import './style.css';

export default function Visualizer() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPartner, setSelectedPartner] = useState('');
  const [selectedOpportunity, setSelectedOpportunity] = useState('');
  const [partnerView, setPartnerView] = useState(false);
  const [opportunityView, setOpportunityView] = useState(false);
  const [chatMessages, setChatMessages] = useState([
    {
      id: 1,
      type: 'bot',
      message: 'Hello! I\'m your Nexus assistant. I can help you analyze partner opportunities and provide insights.',
      timestamp: new Date()
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [queryResults, setQueryResults] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const res = await fetch(`/viz/api/pipeline-scores?_t=${new Date().getTime()}`);
        if (!res.ok) throw new Error("Failed to fetch records");
        const data = await res.json();
        setRecords(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchRecords();
  }, []);

  // Set first partner as default when records are loaded and partner view is active
  useEffect(() => {
    if (records.length > 0 && partnerView && !selectedPartner) {
      const partners = getUniquePartners();
      if (partners.length > 0) {
        setSelectedPartner(partners[0]);
      }
    }
  }, [records, partnerView, selectedPartner]);

  // Set first opportunity as default when records are loaded and opportunity view is active
  useEffect(() => {
    if (records.length > 0 && opportunityView && !selectedOpportunity) {
      const opportunities = getUniqueOpportunities();
      if (opportunities.length > 0) {
        setSelectedOpportunity(opportunities[0]);
      }
    }
  }, [records, opportunityView, selectedOpportunity]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = {
      id: chatMessages.length + 1,
      type: 'user',
      message: inputMessage,
      timestamp: new Date()
    };

    setChatMessages(prev => [...prev, userMessage]);
    const currentMessage = inputMessage;
    setInputMessage('');
    setQueryLoading(true);

    try {
      // Send query to backend
      const response = await fetch('/viz/api/chatbot-query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: currentMessage })
      });

      if (!response.ok) {
        throw new Error('Failed to process query');
      }

      const data = await response.json();
      
       setQueryResults({
         sql: data.sql_query,
         results: data.results,
         count: data.count,
         question: currentMessage,
         visualizationConfig: data.visualization_config
       });

       const botResponse = {
         id: chatMessages.length + 2,
         type: 'bot',
         message: data.natural_response,
         timestamp: new Date()
       };
       setChatMessages(prev => [...prev, botResponse]);

    } catch (error) {
      console.error('Error processing query:', error);
      const botResponse = {
        id: chatMessages.length + 2,
        type: 'bot',
        message: 'Sorry, I encountered an error processing your query. Please try rephrasing your question.',
        timestamp: new Date()
      };
      setChatMessages(prev => [...prev, botResponse]);
    } finally {
      setQueryLoading(false);
    }
  };



  const renderVisualization = () => {
    if (queryLoading) {
      return (
        <div className="visualization-container">
          <div className="visualization-header">
            <h3>Processing Query...</h3>
            <p>Analyzing your question and generating insights</p>
          </div>
          <div className="loading-visualization">
            <div className="loading-spinner"></div>
            <p>Generating visualization and insights...</p>
          </div>
        </div>
      );
    }

    if (!queryResults || !queryResults.visualizationConfig) return null;

    const config = queryResults.visualizationConfig;
    const data = queryResults.results;

    switch (config.type) {
      case 'bar_chart':
        return renderBarChart(config, data);
      case 'pie_chart':
        return renderPieChart(config, data);
      case 'line_chart':
        return renderLineChart(config, data);
      case 'scatter_plot':
        return renderScatterPlot(config, data);
      case 'metric_cards':
        return renderMetricCards(config, data);
      case 'heatmap':
        return renderHeatmap(config, data);
      case 'donut_chart':
        return renderDonutChart(config, data);
      case 'table':
        return renderTable(config, data);
      default:
        return renderMetricCards(config, data);
    }
  };

  const renderBarChart = (config, data) => {
    const xAxis = config.data.x_axis;
    const yAxis = config.data.y_axis;
    const limit = config.options?.limit || 10;
    
    // Handle different field name patterns for aggregated data
    const chartData = data.slice(0, limit).map(item => {
      let label = 'Unknown';
      let value = 0;
      
      // Try different possible field names for labels (x-axis)
      if (item[xAxis]) {
        label = item[xAxis];
      } else if (item.partner_name) {
        label = item.partner_name;
      } else if (item.opportunity_stage_label) {
        label = item.opportunity_stage_label;
      } else if (item.relationship_status_label) {
        label = item.relationship_status_label;
      } else if (item.opportunity_size_label) {
        label = item.opportunity_size_label;
      }
      
      // Try different possible field names for values (y-axis)
      if (item[yAxis]) {
        value = parseFloat(item[yAxis]) || 0;
      } else if (item.opportunity_count) {
        value = parseFloat(item.opportunity_count) || 0;
      } else if (item.stage_count) {
        value = parseFloat(item.stage_count) || 0;
      } else if (item.status_count) {
        value = parseFloat(item.status_count) || 0;
      } else if (item.size_count) {
        value = parseFloat(item.size_count) || 0;
      }
      
      return { label, value };
    });

    const maxValue = Math.max(...chartData.map(d => d.value));

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="bar-chart">
            {chartData.map((item, index) => (
              <div key={index} className="bar-item">
                <div className="bar-label">{item.label}</div>
                <div className="bar-wrapper">
                  <div 
                    className="bar-fill" 
                    style={{ 
                      width: `${(item.value / maxValue) * 100}%`,
                      backgroundColor: `hsl(${120 + (index * 30) % 360}, 70%, 50%)`
                    }}
                  ></div>
                  <span className="bar-value">{item.value}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderPieChart = (config, data) => {
    const labels = config.data.labels;
    const values = config.data.y_axis;
    const limit = config.options?.limit || 8;

    // Handle different field name patterns for aggregated data
    const chartData = data.slice(0, limit).map(item => {
      let label = 'Unknown';
      let value = 0;
      
      // Try different possible field names for labels
      if (item[labels]) {
        label = item[labels];
      } else if (item.opportunity_stage_label) {
        label = item.opportunity_stage_label;
      } else if (item.partner_name) {
        label = item.partner_name;
      } else if (item.relationship_status_label) {
        label = item.relationship_status_label;
      } else if (item.opportunity_size_label) {
        label = item.opportunity_size_label;
      }
      
      // Try different possible field names for values
      if (item[values]) {
        value = parseFloat(item[values]) || 0;
      } else if (item.stage_count) {
        value = parseFloat(item.stage_count) || 0;
      } else if (item.opportunity_count) {
        value = parseFloat(item.opportunity_count) || 0;
      } else if (item.status_count) {
        value = parseFloat(item.status_count) || 0;
      } else if (item.size_count) {
        value = parseFloat(item.size_count) || 0;
      }
      
      return { label, value };
    });

    const total = chartData.reduce((sum, item) => sum + item.value, 0);

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="pie-chart">
            <div className="pie-wrapper">
              <svg width="200" height="200" viewBox="0 0 200 200">
                {chartData.map((item, index) => {
                  const percentage = total > 0 ? (item.value / total) : 0;
                  const startAngle = chartData.slice(0, index).reduce((sum, d) => 
                    sum + (d.value / total) * 2 * Math.PI, 0
                  );
                  const endAngle = startAngle + (percentage * 2 * Math.PI);
                  
                  // Calculate the arc path
                  const radius = 80;
                  const centerX = 100;
                  const centerY = 100;
                  
                  const x1 = centerX + radius * Math.cos(startAngle);
                  const y1 = centerY + radius * Math.sin(startAngle);
                  const x2 = centerX + radius * Math.cos(endAngle);
                  const y2 = centerY + radius * Math.sin(endAngle);
                  
                  // Determine if the arc is large (more than 180 degrees)
                  const largeArcFlag = percentage > 0.5 ? 1 : 0;
                  
                  // Create the path for the pie slice
                  const pathData = [
                    `M ${centerX} ${centerY}`,
                    `L ${x1} ${y1}`,
                    `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
                    'Z'
                  ].join(' ');
                  
                  return (
                    <path
                      key={index}
                      d={pathData}
                      fill={`hsl(${120 + (index * 60) % 360}, 70%, 50%)`}
                      stroke="#fff"
                      strokeWidth="2"
                    />
                  );
                })}
              </svg>
            </div>
            <div className="pie-legend">
              {chartData.map((item, index) => {
                const percentage = total > 0 ? (item.value / total) * 100 : 0;
                return (
                  <div key={index} className="legend-item">
                    <div 
                      className="legend-color"
                      style={{ backgroundColor: `hsl(${120 + (index * 60) % 360}, 70%, 50%)` }}
                    ></div>
                    <span className="legend-label">{item.label}</span>
                    <span className="legend-value">{item.value} ({percentage.toFixed(1)}%)</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderTable = (config, data) => {
    const columns = config.data.columns || Object.keys(data[0] || {});
    const limit = config.options?.limit || 10;

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map(key => (
                  <th key={key}>{key.replace(/_/g, ' ').toUpperCase()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.slice(0, limit).map((row, index) => (
                <tr key={index}>
                  {columns.map(key => (
                    <td key={key}>
                      {typeof row[key] === 'boolean' ? (row[key] ? 'Yes' : 'No') : 
                       typeof row[key] === 'number' ? row[key] : 
                       String(row[key] || '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > limit && (
            <p className="table-note">Showing first {limit} of {data.length} results</p>
          )}
        </div>
      </div>
    );
  };

  const renderMetricCards = (config, data) => {
    // Display all data items, not just first 4
    const metrics = data.map((item, index) => {
      const keys = Object.keys(item);
      // Skip 'id' field and prefer meaningful fields
      const meaningfulKeys = keys.filter(key => key !== 'id');
      
      // Special handling for opportunity data to show both opportunity and partner names prominently
      if (item.opportunity_name && item.partner_name) {
        return {
          title: item.opportunity_name,
          value: item.partner_name,
          subtitle: item.opportunity_stage_label || item.opportunity_size_label || '',
          score: item.winnability_score || item.opportunity_size_score || item.combined_score_percent
        };
      }
      
      // Fallback to original logic for other data types
      const firstKey = meaningfulKeys[0] || keys[0];
      const secondKey = meaningfulKeys[1] || keys[1];
      
      return {
        title: firstKey?.replace(/_/g, ' ').toUpperCase() || 'Metric',
        value: typeof item[firstKey] === 'number' ? item[firstKey] : item[firstKey],
        subtitle: secondKey ? secondKey.replace(/_/g, ' ').toUpperCase() : ''
      };
    });

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="metrics-grid">
          {metrics.map((metric, index) => (
            <div key={index} className="metric-card">
              <h4>{metric.title}</h4>
              <div className="metric-value">{metric.value}</div>
              {metric.subtitle && <p className="metric-subtitle">{metric.subtitle}</p>}
              {metric.score && (
                <div className="metric-score">
                  Score: {typeof metric.score === 'number' ? metric.score.toFixed(1) : metric.score}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderLineChart = (config, data) => {
    const xAxis = config.data.x_axis;
    const yAxis = config.data.y_axis;
    const limit = config.options?.limit || 20;

    const chartData = data.slice(0, limit).map(item => ({
      label: item[xAxis] || 'Unknown',
      value: parseFloat(item[yAxis]) || 0
    }));

    const maxValue = Math.max(...chartData.map(d => d.value));
    const minValue = Math.min(...chartData.map(d => d.value));

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="line-chart">
            <svg width="100%" height="200" viewBox="0 0 400 200">
              <polyline
                fill="none"
                stroke="#3bc23b"
                strokeWidth="3"
                points={chartData.map((item, index) => 
                  `${(index / (chartData.length - 1)) * 380 + 10},${200 - ((item.value - minValue) / (maxValue - minValue)) * 180 + 10}`
                ).join(' ')}
              />
              {chartData.map((item, index) => (
                <circle
                  key={index}
                  cx={(index / (chartData.length - 1)) * 380 + 10}
                  cy={200 - ((item.value - minValue) / (maxValue - minValue)) * 180 + 10}
                  r="4"
                  fill="#3bc23b"
                />
              ))}
            </svg>
            <div className="line-labels">
              {chartData.map((item, index) => (
                <span key={index} className="line-label">{item.label}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderScatterPlot = (config, data) => {
    const xAxis = config.data.x_axis;
    const yAxis = config.data.y_axis;
    const limit = config.options?.limit || 50;

    const chartData = data.slice(0, limit).map(item => ({
      x: parseFloat(item[xAxis]) || 0,
      y: parseFloat(item[yAxis]) || 0,
      label: item[config.data.labels] || ''
    }));

    const maxX = Math.max(...chartData.map(d => d.x));
    const minX = Math.min(...chartData.map(d => d.x));
    const maxY = Math.max(...chartData.map(d => d.y));
    const minY = Math.min(...chartData.map(d => d.y));

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="scatter-plot">
            <svg width="100%" height="300" viewBox="0 0 400 300">
              {chartData.map((point, index) => (
                <circle
                  key={index}
                  cx={((point.x - minX) / (maxX - minX)) * 380 + 10}
                  cy={300 - ((point.y - minY) / (maxY - minY)) * 280 + 10}
                  r="6"
                  fill="#3bc23b"
                  opacity="0.7"
                />
              ))}
            </svg>
            <div className="scatter-labels">
              <span className="x-label">{xAxis.replace(/_/g, ' ').toUpperCase()}</span>
              <span className="y-label">{yAxis.replace(/_/g, ' ').toUpperCase()}</span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderHeatmap = (config, data) => {
    const xAxis = config.data.x_axis;
    const yAxis = config.data.y_axis;
    const values = config.data.values || config.data.y_axis;
    const limit = config.options?.limit || 20;

    const chartData = data.slice(0, limit);
    const uniqueX = [...new Set(chartData.map(item => item[xAxis]))];
    const uniqueY = [...new Set(chartData.map(item => item[yAxis]))];



    // Find the maximum value for proper scaling
    const maxValue = Math.max(...chartData.map(item => {
      const val = parseFloat(item[values]) || parseFloat(item.combined_score_percent) || parseFloat(item.opportunity_score) || 0;
      return val;
    }));

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="heatmap">
            <div className="heatmap-grid">
              {uniqueY.map((yVal, yIndex) => (
                <div key={yIndex} className="heatmap-row">
                  <div className="heatmap-y-label">{yVal}</div>
                  {uniqueX.map((xVal, xIndex) => {
                    const item = chartData.find(d => d[xAxis] === xVal && d[yAxis] === yVal);
                    let value = 0;
                    
                    if (item) {
                      // Try different score fields in order of preference
                      value = parseFloat(item.combined_score_percent) || 
                              parseFloat(item.opportunity_score) || 
                              parseFloat(item.partner_score) || 
                              parseFloat(item[values]) || 0;
                    }
                    
                    // Use different green shades based on value intensity
                    const intensity = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
                    const greenShade = intensity === 0 ? '#f0f8f0' : 
                                      intensity < 0.3 ? '#d4edda' :
                                      intensity < 0.6 ? '#a8e6a8' :
                                      intensity < 0.8 ? '#6bc26b' :
                                      '#3bc23b';
                    
                    return (
                      <div 
                        key={xIndex} 
                        className="heatmap-cell"
                        style={{
                          backgroundColor: greenShade,
                          border: '1px solid #e0e0e0'
                        }}
                        title={`${xVal} - ${yVal}: ${value.toFixed(1)}`}
                      >
                        {value > 0 ? value.toFixed(1) : ''}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
            <div className="heatmap-x-labels">
              {uniqueX.map((xVal, index) => (
                <span key={index} className="heatmap-x-label">{xVal}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderDistributionBarChart = (title, data, maxValue) => {
    return (
      <div className="distribution-chart">
        <h4>{title}</h4>
        <div className="bar-chart-container">
          {data.map((item, index) => {
            const percentage = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
            return (
              <div key={index} className="distribution-bar-item">
                <div className="bar-label">{item.label}</div>
                <div className="bar-wrapper">
                  <div 
                    className="bar-fill" 
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>
                <div className="bar-value">{item.value}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderDonutChart = (config, data) => {
    const labels = config.data.labels;
    const values = config.data.y_axis;
    const limit = config.options?.limit || 6;

    // Handle different field name patterns for aggregated data
    const chartData = data.slice(0, limit).map(item => {
      let label = 'Unknown';
      let value = 0;
      
      // Try different possible field names for labels
      if (item[labels]) {
        label = item[labels];
      } else if (item.opportunity_stage_label) {
        label = item.opportunity_stage_label;
      } else if (item.partner_name) {
        label = item.partner_name;
      } else if (item.relationship_status_label) {
        label = item.relationship_status_label;
      } else if (item.opportunity_size_label) {
        label = item.opportunity_size_label;
      }
      
      // Try different possible field names for values
      if (item[values]) {
        value = parseFloat(item[values]) || 0;
      } else if (item.stage_count) {
        value = parseFloat(item.stage_count) || 0;
      } else if (item.opportunity_count) {
        value = parseFloat(item.opportunity_count) || 0;
      } else if (item.status_count) {
        value = parseFloat(item.status_count) || 0;
      } else if (item.size_count) {
        value = parseFloat(item.size_count) || 0;
      }
      
      return { label, value };
    });

    const total = chartData.reduce((sum, item) => sum + item.value, 0);

    return (
      <div className="visualization-container">
        <div className="visualization-header">
          <h3>{config.title}</h3>
          <p>{config.subtitle}</p>
        </div>
        <div className="chart-container">
          <div className="donut-chart">
            <div className="donut-wrapper">
              <svg width="200" height="200" viewBox="0 0 200 200">
                {chartData.map((item, index) => {
                  const percentage = total > 0 ? (item.value / total) * 100 : 0;
                  const rotation = chartData.slice(0, index).reduce((sum, d) => 
                    sum + (d.value / total) * 360, 0
                  );
                  
                  return (
                    <path
                      key={index}
                      d={`M 100 100 L 100 20 A 80 80 0 0 1 ${100 + 80 * Math.cos((rotation + percentage * 3.6) * Math.PI / 180)} ${100 + 80 * Math.sin((rotation + percentage * 3.6) * Math.PI / 180)} Z`}
                      fill={`hsl(${120 + (index * 60) % 360}, 70%, 50%)`}
                    />
                  );
                })}
                <circle cx="100" cy="100" r="40" fill="white" />
              </svg>
              <div className="donut-center">
                <div className="donut-total">{total.toFixed(0)}</div>
                <div className="donut-label">Total</div>
              </div>
            </div>
            <div className="donut-legend">
              {chartData.map((item, index) => (
                <div key={index} className="legend-item">
                  <div 
                    className="legend-color"
                    style={{ backgroundColor: `hsl(${120 + (index * 60) % 360}, 70%, 50%)` }}
                  ></div>
                  <span className="legend-label">{item.label}</span>
                  <span className="legend-value">{item.value.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setInputMessage(suggestion);
    // Automatically send the message after a short delay
    setTimeout(() => {
      handleSendMessage();
    }, 100);
  };

  const handleClearChat = () => {
    setChatMessages([
      {
        id: 1,
        type: 'bot',
        message: 'Hello! I\'m your Nexus assistant. I can help you analyze partner opportunities and provide insights.',
        timestamp: new Date()
      }
    ]);
    setQueryResults(null);
  };

  // Partner-specific data processing
  const getUniquePartners = () => {
    const partners = [...new Set(records.map(rec => rec.partner_name).filter(Boolean))];
    return partners.sort();
  };

  const getPartnerData = (partnerName) => {
    return records.filter(rec => rec.partner_name === partnerName);
  };

  const getPartnerStats = (partnerName) => {
    const partnerRecords = getPartnerData(partnerName);
    if (partnerRecords.length === 0) return null;

    const totalOpportunities = partnerRecords.length;
    const avgScore = partnerRecords.reduce((sum, rec) => sum + (rec.combined_score_percent || 0), 0) / totalOpportunities;
    const highPriorityCount = partnerRecords.filter(rec => (rec.combined_score_percent || 0) > 60).length;
    const logoPotentialCount = partnerRecords.filter(rec => rec.logo_potential).length;
    const avgOpportunityScore = partnerRecords.reduce((sum, rec) => sum + (rec.opportunity_score || 0), 0) / totalOpportunities;
    const avgPartnerScore = partnerRecords.reduce((sum, rec) => sum + (rec.partner_score || 0), 0) / totalOpportunities;

    return {
      totalOpportunities,
      avgScore: avgScore.toFixed(1),
      highPriorityCount,
      logoPotentialCount,
      avgOpportunityScore: avgOpportunityScore.toFixed(1),
      avgPartnerScore: avgPartnerScore.toFixed(1)
    };
  };

  const getPartnerScoreDistribution = (partnerName) => {
    const partnerRecords = getPartnerData(partnerName);
    return [0, 20, 40, 60, 80].map((min, index) => {
      const max = min + 20;
      const count = partnerRecords.filter(rec => 
        (rec.combined_score_percent || 0) >= min && 
        (rec.combined_score_percent || 0) < max
      ).length;
      const percentage = partnerRecords.length > 0 ? (count / partnerRecords.length) * 100 : 0;
      
      return {
        range: `${min}-${max}%`,
        count,
        percentage
      };
    });
  };

  const getPartnerOpportunityBreakdown = (partnerName) => {
    const partnerRecords = getPartnerData(partnerName);
    const breakdown = {};
    
    partnerRecords.forEach(rec => {
      const opportunityName = rec.opportunity_name || 'Unknown';
      if (!breakdown[opportunityName]) {
        breakdown[opportunityName] = {
          name: opportunityName,
          score: rec.combined_score_percent || 0,
          opportunityScore: rec.opportunity_score || 0,
          partnerScore: rec.partner_score || 0,
          logoPotential: rec.logo_potential || false,
          stage: rec.opportunity_stage_label || 'Unknown',
          size: rec.opportunity_size_label || 'Unknown'
        };
      }
    });

    return Object.values(breakdown).sort((a, b) => b.score - a.score);
  };

  const getPartnerOpportunityDistribution = (partnerName) => {
    const partnerRecords = getPartnerData(partnerName);
    
    // Distribution by Opportunity Stage
    const stageDistribution = {};
    partnerRecords.forEach(rec => {
      const stage = rec.opportunity_stage_label || 'Unknown';
      stageDistribution[stage] = (stageDistribution[stage] || 0) + 1;
    });

    // Distribution by Opportunity Size
    const sizeDistribution = {};
    partnerRecords.forEach(rec => {
      const size = rec.opportunity_size_label || 'Unknown';
      sizeDistribution[size] = (sizeDistribution[size] || 0) + 1;
    });

    // Distribution by Relationship Status
    const relationshipDistribution = {};
    partnerRecords.forEach(rec => {
      const status = rec.relationship_status_label || 'Unknown';
      relationshipDistribution[status] = (relationshipDistribution[status] || 0) + 1;
    });

    // Distribution by Engagement Score
    const engagementDistribution = {};
    partnerRecords.forEach(rec => {
      const engagement = rec.engagement_score_label || 'Unknown';
      engagementDistribution[engagement] = (engagementDistribution[engagement] || 0) + 1;
    });

    // Distribution by Winnability
    const winnabilityDistribution = {};
    partnerRecords.forEach(rec => {
      const winnability = rec.winnability_label || 'Unknown';
      winnabilityDistribution[winnability] = (winnabilityDistribution[winnability] || 0) + 1;
    });

    return {
      stage: Object.entries(stageDistribution).map(([key, value]) => ({ label: key, value })),
      size: Object.entries(sizeDistribution).map(([key, value]) => ({ label: key, value })),
      relationship: Object.entries(relationshipDistribution).map(([key, value]) => ({ label: key, value })),
      engagement: Object.entries(engagementDistribution).map(([key, value]) => ({ label: key, value })),
      winnability: Object.entries(winnabilityDistribution).map(([key, value]) => ({ label: key, value }))
    };
  };

  // Opportunity-specific data processing
  const getUniqueOpportunities = () => {
    const opportunities = [...new Set(records.map(rec => rec.opportunity_name).filter(Boolean))];
    return opportunities.sort();
  };

  const getOpportunityData = (opportunityName) => {
    return records.filter(rec => rec.opportunity_name === opportunityName);
  };

  const getOpportunityStats = (opportunityName) => {
    const opportunityRecords = getOpportunityData(opportunityName);
    if (opportunityRecords.length === 0) return null;

    const totalPartners = opportunityRecords.length;
    const avgScore = opportunityRecords.reduce((sum, rec) => sum + (rec.combined_score_percent || 0), 0) / totalPartners;
    const highPriorityCount = opportunityRecords.filter(rec => (rec.combined_score_percent || 0) > 60).length;
    const logoPotentialCount = opportunityRecords.filter(rec => rec.logo_potential).length;
    const avgOpportunityScore = opportunityRecords.reduce((sum, rec) => sum + (rec.opportunity_score || 0), 0) / totalPartners;
    const avgPartnerScore = opportunityRecords.reduce((sum, rec) => sum + (rec.partner_score || 0), 0) / totalPartners;

    // Get opportunity details from first record
    const firstRecord = opportunityRecords[0];
    const opportunityDetails = {
      name: firstRecord.opportunity_name || 'Unknown',
      website: firstRecord.opportunity_website || 'N/A',
      stage: firstRecord.opportunity_stage_label || 'Unknown',
      size: firstRecord.opportunity_size_label || 'Unknown',
      relationshipStatus: firstRecord.relationship_status_label || 'Unknown',
      engagementScore: firstRecord.engagement_score_label || 'Unknown',
      winnability: firstRecord.winnability_label || 'Unknown'
    };

    return {
      totalPartners,
      avgScore: avgScore.toFixed(1),
      highPriorityCount,
      logoPotentialCount,
      avgOpportunityScore: avgOpportunityScore.toFixed(1),
      avgPartnerScore: avgPartnerScore.toFixed(1),
      details: opportunityDetails
    };
  };

  const getOpportunityScoreDistribution = (opportunityName) => {
    const opportunityRecords = getOpportunityData(opportunityName);
    return [0, 20, 40, 60, 80].map((min, index) => {
      const max = min + 20;
      const count = opportunityRecords.filter(rec => 
        (rec.combined_score_percent || 0) >= min && 
        (rec.combined_score_percent || 0) < max
      ).length;
      const percentage = opportunityRecords.length > 0 ? (count / opportunityRecords.length) * 100 : 0;
      
      return {
        range: `${min}-${max}%`,
        count,
        percentage
      };
    });
  };

  const getOpportunityPartnerBreakdown = (opportunityName) => {
    const opportunityRecords = getOpportunityData(opportunityName);
    const breakdown = {};
    
    opportunityRecords.forEach(rec => {
      const partnerName = rec.partner_name || 'Unknown';
      if (!breakdown[partnerName]) {
        breakdown[partnerName] = {
          name: partnerName,
          score: rec.combined_score_percent || 0,
          opportunityScore: rec.opportunity_score || 0,
          partnerScore: rec.partner_score || 0,
          logoPotential: rec.logo_potential || false,
          relationshipStrength: rec.relationship_strength_label || 'Unknown',
          recentDealSupport: rec.recent_deal_support_label || 'Unknown',
          stickinessScore: rec.stickiness_score || 0,
          partnerSize: rec.partner_size_label || 'Unknown',
          hasChampion: rec.partner_champion_flagged || false
        };
      }
    });

    return Object.values(breakdown).sort((a, b) => b.score - a.score);
  };

  if (loading) return <div className="visualizer-loading">Loading visualization data...</div>;
  if (error) return <div className="visualizer-error">Error: {error}</div>;

  return (
    <div className="visualizer-container">
      {/* Left Side - Main Visualization (65%) */}
      <div className="visualizer-main">
        <div className="visualizer-header">
          <h1>Nexus Analytics</h1>
          <p>Interactive analysis of partner-opportunity overlaps and scoring insights</p>
        </div>
        
        <div className="visualizer-content">
          {/* Visualization Toggle */}
          <div className="visualization-toggle">
            <button 
              className={`toggle-btn ${!partnerView && !opportunityView ? 'active' : ''}`}
              onClick={() => {
                setPartnerView(false);
                setOpportunityView(false);
              }}
            >
              Opportunity Overview
            </button>
            <button 
              className={`toggle-btn ${partnerView ? 'active' : ''}`}
              onClick={() => {
                setPartnerView(true);
                setOpportunityView(false);
                // Set first partner as default when switching to partner view
                const partners = getUniquePartners();
                if (partners.length > 0 && !selectedPartner) {
                  setSelectedPartner(partners[0]);
                }
              }}
            >
              Partner Analysis
            </button>
            <button 
              className={`toggle-btn ${opportunityView ? 'active' : ''}`}
              onClick={() => {
                setPartnerView(false);
                setOpportunityView(true);
                // Set first opportunity as default when switching to opportunity view
                const opportunities = getUniqueOpportunities();
                if (opportunities.length > 0 && !selectedOpportunity) {
                  setSelectedOpportunity(opportunities[0]);
                }
              }}
            >
              Opportunity Analysis
            </button>
          </div>

          {!partnerView ? (
            // Original Opportunity Overview
            <>
          <div className="stats-grid">
            <div className="stat-card">
              <h3>Total Opportunities</h3>
              <div className="stat-value">{records.length}</div>
            </div>
            <div className="stat-card">
              <h3>Average Score</h3>
              <div className="stat-value">
                {(records.reduce((sum, rec) => sum + (rec.combined_score_percent || 0), 0) / records.length).toFixed(1)}%
              </div>
            </div>
            <div className="stat-card">
              <h3>High Priority</h3>
              <div className="stat-value">
                {records.filter(rec => (rec.combined_score_percent || 0) > 60).length}
              </div>
            </div>
            <div className="stat-card">
              <h3>Unique Partners</h3>
              <div className="stat-value">
                {new Set(records.map(rec => rec.partner_name)).size}
              </div>
            </div>
          </div>
            </>
          ) : (
            // Partner Visualization
            <>
              <div className="partner-selector">
                <label htmlFor="partner-dropdown">Select Partner:</label>
                <select 
                  id="partner-dropdown"
                  value={selectedPartner}
                  onChange={(e) => setSelectedPartner(e.target.value)}
                  className="partner-dropdown"
                >
                  <option value="">Choose a partner...</option>
                  {getUniquePartners().map(partner => (
                    <option key={partner} value={partner}>{partner}</option>
                  ))}
                </select>
              </div>

              {selectedPartner && (
                <div className="partner-visualization">
                  {/* Partner Stats */}
                  <div className="partner-stats">
                    {(() => {
                      const stats = getPartnerStats(selectedPartner);
                      return stats ? (
                        <div className="stats-grid">
                          <div className="stat-card">
                            <h3>Total Opportunities</h3>
                            <div className="stat-value">{stats.totalOpportunities}</div>
                          </div>
                          <div className="stat-card">
                            <h3>Average Score</h3>
                            <div className="stat-value">{stats.avgScore}%</div>
                          </div>
                          <div className="stat-card">
                            <h3>High Priority</h3>
                            <div className="stat-value">{stats.highPriorityCount}</div>
                          </div>
                          <div className="stat-card">
                            <h3>Logo Potential</h3>
                            <div className="stat-value">{stats.logoPotentialCount}</div>
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>



                  {/* Partner Opportunity Distribution Charts */}
             <div className="visualization-area">
                    <h3>{selectedPartner} - Opportunity Distribution</h3>
                    <div className="distribution-charts-grid">
                      {(() => {
                        const distribution = getPartnerOpportunityDistribution(selectedPartner);
                        const maxValues = {
                          stage: Math.max(...distribution.stage.map(item => item.value)),
                          size: Math.max(...distribution.size.map(item => item.value)),
                          relationship: Math.max(...distribution.relationship.map(item => item.value)),
                          engagement: Math.max(...distribution.engagement.map(item => item.value)),
                          winnability: Math.max(...distribution.winnability.map(item => item.value))
                        };
                     
                     return (
                          <>
                            {renderDistributionBarChart('Opportunity Stage', distribution.stage, maxValues.stage)}
                            {renderDistributionBarChart('Opportunity Size', distribution.size, maxValues.size)}
                            {renderDistributionBarChart('Relationship Status', distribution.relationship, maxValues.relationship)}
                            {renderDistributionBarChart('Engagement Score', distribution.engagement, maxValues.engagement)}
                            {renderDistributionBarChart('Winnability', distribution.winnability, maxValues.winnability)}
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Partner Opportunity Breakdown */}
                  <div className="visualization-area">
                    <h3>{selectedPartner} - Opportunity Breakdown</h3>
                    <div className="opportunity-table-container">
                      <table className="opportunity-table">
                        <thead>
                          <tr>
                            <th>Opportunity</th>
                            <th>Combined Score</th>
                            <th>Opportunity Score</th>
                            <th>Partner Score</th>
                            <th>Stage</th>
                            <th>Size</th>
                            <th>Logo Potential</th>
                          </tr>
                        </thead>
                        <tbody>
                          {getPartnerOpportunityBreakdown(selectedPartner).map((opp, index) => (
                            <tr key={index}>
                              <td>{opp.name}</td>
                              <td className={`score-cell ${opp.score > 60 ? 'high' : opp.score > 40 ? 'medium' : 'low'}`}>
                                {opp.score.toFixed(1)}%
                              </td>
                              <td>{opp.opportunityScore.toFixed(1)}</td>
                              <td>{opp.partnerScore.toFixed(1)}</td>
                              <td>{opp.stage}</td>
                              <td>{opp.size}</td>
                              <td>
                                <span className={`logo-badge ${opp.logoPotential ? 'yes' : 'no'}`}>
                                  {opp.logoPotential ? 'Yes' : 'No'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
                             )}
             </>
           )}

          {opportunityView && (
            // Opportunity Visualization
            <>
              <div className="opportunity-selector">
                <label htmlFor="opportunity-dropdown">Select Opportunity:</label>
                <select 
                  id="opportunity-dropdown"
                  value={selectedOpportunity}
                  onChange={(e) => setSelectedOpportunity(e.target.value)}
                  className="opportunity-dropdown"
                >
                  <option value="">Choose an opportunity...</option>
                  {getUniqueOpportunities().map(opportunity => (
                    <option key={opportunity} value={opportunity}>{opportunity}</option>
                  ))}
                </select>
              </div>

              {selectedOpportunity && (
                <div className="opportunity-visualization">
                  {/* Opportunity Details */}
                  <div className="opportunity-details">
                    {(() => {
                      const stats = getOpportunityStats(selectedOpportunity);
                      return stats ? (
                        <div className="details-card">
                          <h3>{stats.details.name}</h3>
                          <div className="details-grid">
                            <div className="detail-item">
                              <span className="detail-label">Website:</span>
                              <span className="detail-value">{stats.details.website}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Stage:</span>
                              <span className="detail-value">{stats.details.stage}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Size:</span>
                              <span className="detail-value">{stats.details.size}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Relationship Status:</span>
                              <span className="detail-value">{stats.details.relationshipStatus}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Engagement Score:</span>
                              <span className="detail-value">{stats.details.engagementScore}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Winnability:</span>
                              <span className="detail-value">{stats.details.winnability}</span>
                            </div>
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>

                  {/* Opportunity Stats */}
                  <div className="opportunity-stats">
                    {(() => {
                      const stats = getOpportunityStats(selectedOpportunity);
                      return stats ? (
                        <div className="stats-grid">
                          <div className="stat-card">
                            <h3>Total Partners</h3>
                            <div className="stat-value">{stats.totalPartners}</div>
                          </div>
                          <div className="stat-card">
                            <h3>Average Score</h3>
                            <div className="stat-value">{stats.avgScore}%</div>
                          </div>
                          <div className="stat-card">
                            <h3>High Priority</h3>
                            <div className="stat-value">{stats.highPriorityCount}</div>
                          </div>
                          <div className="stat-card">
                            <h3>Logo Potential</h3>
                            <div className="stat-value">{stats.logoPotentialCount}</div>
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>

                  {/* Opportunity Score Distribution */}
                  <div className="visualization-area">
                    <h3>{selectedOpportunity} - Score Distribution</h3>
                    <div className="chart-container">
                      <div className="score-distribution">
                        {getOpportunityScoreDistribution(selectedOpportunity).map((item, index) => (
                          <div key={index} className="score-bar">
                            <div className="bar-label">{item.range}</div>
                         <div className="bar-container">
                           <div 
                             className="bar-fill" 
                                style={{ width: `${item.percentage}%` }}
                           ></div>
                         </div>
                            <div className="bar-count">{item.count}</div>
                       </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Opportunity Partner Breakdown */}
                  <div className="visualization-area">
                    <h3>{selectedOpportunity} - Partner Breakdown</h3>
                    <div className="partner-table-container">
                      <table className="partner-table">
                        <thead>
                          <tr>
                            <th>Partner</th>
                            <th>Combined Score</th>
                            <th>Opportunity Score</th>
                            <th>Partner Score</th>
                            <th>Relationship Strength</th>
                            <th>Recent Deal Support</th>
                            <th>Stickiness</th>
                            <th>Size</th>
                            <th>Champion</th>
                            <th>Logo Potential</th>
                          </tr>
                        </thead>
                        <tbody>
                          {getOpportunityPartnerBreakdown(selectedOpportunity).map((partner, index) => (
                            <tr key={index}>
                              <td>{partner.name}</td>
                              <td className={`score-cell ${partner.score > 60 ? 'high' : partner.score > 40 ? 'medium' : 'low'}`}>
                                {partner.score.toFixed(1)}%
                              </td>
                              <td>{partner.opportunityScore.toFixed(1)}</td>
                              <td>{partner.partnerScore.toFixed(1)}</td>
                              <td>{partner.relationshipStrength}</td>
                              <td>{partner.recentDealSupport}</td>
                              <td>{partner.stickinessScore.toFixed(1)}</td>
                              <td>{partner.partnerSize}</td>
                              <td>
                                <span className={`champion-badge ${partner.hasChampion ? 'yes' : 'no'}`}>
                                  {partner.hasChampion ? 'Yes' : 'No'}
                                </span>
                              </td>
                              <td>
                                <span className={`logo-badge ${partner.logoPotential ? 'yes' : 'no'}`}>
                                  {partner.logoPotential ? 'Yes' : 'No'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                 </div>
               </div>
             </div>
           )}
            </>
          )}

                     {queryResults ? (
             renderVisualization()
           ) : null
           }
        </div>
      </div>

      {/* Right Side - Chatbot (35%) */}
      <div className="visualizer-chat">
        <div className="chat-header">
          <div className="chat-header-content">
            <h3>Nexus Assistant</h3>
            <p>Ask me about opportunities, partners, or scoring insights</p>
          </div>
        </div>
        
                 <div className="chat-messages">
           {chatMessages.map((msg) => (
             <div key={msg.id} className={`chat-message ${msg.type}`}>
               <div className="message-content">
                 {msg.message}
               </div>
               <div className="message-time">
                 {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
               </div>
             </div>
           ))}
           
           {/* Show suggestions always */}
           <div className="chat-suggestions">
             <div className="suggestions-title">Quick Suggestions:</div>
                                                        <div className="suggestion-buttons">
                 <button
                   className="suggestion-button"
                   onClick={() => handleSuggestionClick('Which partners have the most deals?')}
                   disabled={queryLoading}
                 >
                   Which partners have the most deals?
                 </button>
                 <button
                   className="suggestion-button"
                   onClick={() => handleSuggestionClick('How are opportunities distributed across relationship statuses?')}
                   disabled={queryLoading}
                 >
                   How are opportunities distributed across relationship statuses?
                 </button>
                 <button
                   className="suggestion-button"
                   onClick={() => handleSuggestionClick('Which opportunities are close to winning but lack strong partner support?')}
                   disabled={queryLoading}
                 >
                   Which opportunities are close to winning but lack strong partner support?
                 </button>
               </div>
           </div>
           
           {queryLoading && (
             <div className="chat-message bot typing">
               <div className="message-content">
                 <div className="typing-indicator">
                   <span></span>
                   <span></span>
                   <span></span>
                 </div>
               </div>
             </div>
           )}
         </div>
        
                 <div className="chat-input">
           <input
             type="text"
             value={inputMessage}
             onChange={(e) => setInputMessage(e.target.value)}
             onKeyPress={handleKeyPress}
             placeholder="Ask about opportunities, partners, or scores..."
             className="chat-input-field"
             disabled={queryLoading}
           />
           <div className="chat-buttons">
             <button 
               onClick={handleClearChat}
               className="clear-chat-button"
               title="Clear chat history"
               disabled={queryLoading}
             >
               Clear
             </button>
             <button 
               onClick={handleSendMessage}
               className="chat-send-button"
               disabled={!inputMessage.trim() || queryLoading}
             >
               {queryLoading ? 'Processing...' : 'Send'}
             </button>
           </div>
         </div>
      </div>
    </div>
  );
}
