import React, { useEffect, useState } from "react";
import "./style.css";

export default function InternalTeamTable() {
  const [team, setTeam] = useState([]);
  const [editIndex, setEditIndex] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchTeam();
  }, []);

  const fetchTeam = () => {
    fetch("/viz/api/internal-team")
      .then(res => res.json())
      .then(data => setTeam(data || []))
      .catch(err => console.error("Error loading internal team:", err));
  };

  const handleEdit = (index) => {
    setEditIndex(index);
    setError("");
  };

  const validateMember = (member) => {
    if (!member.name || !member.designation || !member.hierarchy || !member.webhook_url || !member.max_message) {
      return "All fields are required.";
    }
    if (!/^https:\/\/hooks.slack.com\/.+/.test(member.webhook_url)) {
      return "Webhook URL must be a valid Slack webhook.";
    }
    return "";
  };

  const handleSave = async (index) => {
    const updated = team[index];
    const validationError = validateMember(updated);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");
    setEditIndex(null);

    try {
      await fetch(`/viz/api/internal-team/${updated.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      });

      const updatedTeam = [...team];
      updatedTeam[index] = updated;
      setTeam(updatedTeam);
    } catch (error) {
      console.error("Save failed", error);
    }
  };

  const handleDelete = async (index) => {
    const toDelete = team[index];
    const confirmDelete = window.confirm("Are you sure you want to delete this team member?");
    if (!confirmDelete) return;

    try {
      await fetch(`/viz/api/internal-team/${toDelete.id}`, {
        method: "DELETE",
      });

      const updatedTeam = [...team];
      updatedTeam.splice(index, 1);
      setTeam(updatedTeam);
      setError("");
    } catch (error) {
      console.error("Delete failed", error);
    }
  };

  const handleAdd = async () => {
    const newMember = {
      name: "",
      designation: "",
      hierarchy: 1,
      channel_id: "",
      webhook_url: "",
      max_message: 3,
    };

    try {
      await fetch("/viz/api/internal-team", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newMember),
      });

      fetchTeam(); // Reload full list to get ID & fields
      setEditIndex(team.length); // Focus on new row
      setError("");
    } catch (error) {
      console.error("Add failed", error);
    }
  };

  const handleChange = (e, index, key) => {
    const newTeam = [...team];
    newTeam[index][key] = e.target.value;
    setTeam(newTeam);
    const validationError = validateMember(newTeam[index]);
    setError(validationError);
  };

  return (
    <>
      <div className="table-header">
        <h1 className="team-header">Internal Team Configuration</h1>
        <p className="team-subtext">
          These are the internal team members set up in your system. You can edit their Slack settings and hierarchy levels.
        </p>
      </div>

      <div className="team-table-container">
        <table className="team-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Designation</th>
              <th>Hierarchy</th>
              <th>Slack Channel ID</th>
              <th>Webhook URL</th>
              <th>Max Message</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {team.map((member, index) => (
              <tr key={index}>
                {editIndex === index ? (
                  <>
                    <td>
                      <input
                        value={member.name}
                        onChange={(e) => handleChange(e, index, "name")}
                      />
                    </td>
                    <td>
                      <select
                        value={member.designation}
                        onChange={(e) => handleChange(e, index, "designation")}
                      >
                        <option value="">Select</option>
                        <option value="Account Executive">Account Executive</option>
                        <option value="Sales Manager">Sales Manager</option>
                        <option value="General Executive">General Executive</option>
                      </select>
                    </td>
                    <td>
                      <select
                        value={member.hierarchy}
                        onChange={(e) => handleChange(e, index, "hierarchy")}
                      >
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={3}>3</option>
                      </select>
                    </td>
                    <td>
                      <input
                        value={member.channel_id}
                        onChange={(e) => handleChange(e, index, "channel_id")}
                      />
                    </td>
                    <td>
                      <input
                        value={member.webhook_url}
                        onChange={(e) => handleChange(e, index, "webhook_url")}
                      />
                    </td>
                    <td>
                      <select
                        value={member.max_message}
                        onChange={(e) => handleChange(e, index, "max_message")}
                      >
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={3}>3</option>
                      </select>
                    </td>
                    <td className="action-buttons">
                      <button className="save-button" onClick={() => handleSave(index)}>Save</button>
                      <button className="delete-button" onClick={() => handleDelete(index)}>Delete</button>
                    </td>
                  </>
                ) : (
                  <>
                    <td>{member.name}</td>
                    <td>{member.designation}</td>
                    <td>{member.hierarchy}</td>
                    <td><code>{member.channel_id}</code></td>
                    <td><code className="truncate">{member.webhook_url}</code></td>
                    <td>{member.max_message}</td>
                    <td className="action-buttons">
                      <button className="edit-button" onClick={() => handleEdit(index)}>Edit</button>
                      <button className="delete-button" onClick={() => handleDelete(index)}>Delete</button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        {error && <div className="form-error">{error}</div>}

        <button className="add-button" onClick={handleAdd} disabled={!!error}>+ Add</button>
      </div>
    </>
  );
}
