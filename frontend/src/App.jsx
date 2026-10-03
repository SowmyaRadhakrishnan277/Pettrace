import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function MatchCard({ match, index }) {
  return (
    <article className="match-card">
      <div className="match-card__top">
        <span className="match-number">0{index + 1}</span>
        <span className={`report-type report-type--${match.report_type}`}>
          {match.report_type === "found"
            ? "Found report"
            : match.report_type === "lost"
              ? "Lost report"
              : "Pet report"}
        </span>
        <span className="source-label">
          {match.source_type === "public" ? match.platform : "Local report"}
        </span>
        <span className="match-score">{Math.round(match.score * 100)}% match</span>
      </div>
      {match.image_url && (
        <img
          className="report-image"
          src={match.image_url}
          alt={`Pet from ${match.platform || "report"} post`}
          loading="lazy"
          referrerPolicy="no-referrer"
        />
      )}
      <h3>{match.post_title || match.pet_name || "Pet report"}</h3>
      <p className="match-description">{match.caption || match.description}</p>
      <div className="match-meta">
        <span>{match.profile_name || match.location || "Profile name not indexed"}</span>
        <span>
          {match.report_date
            ? `${match.date_is_estimated ? "Indexed date" : "Reported"} ${match.report_date}`
            : "Date unavailable"}
        </span>
      </div>
      {match.location && <p className="report-location">Reported location: {match.location}</p>}
      <div className="match-indicators" aria-label="Match indicators">
        <span>AI comparison {Math.round(match.ai_score * 100)}%</span>
        <span>Trait overlap {Math.round(match.visual_score * 100)}%</span>
        <span>Text {Math.round(match.description_score * 100)}%</span>
        <span>Location text {Math.round(match.location_score * 100)}%</span>
        <span>Date {Math.round(match.date_score * 100)}%</span>
      </div>
      <div className="match-reasons">
        <strong>Why this may match</strong>
        <p className="ai-explanation">{match.ai_explanation}</p>
        <ul>
          {match.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </div>
      {match.contact_info && (
        <p className="contact-info">Public contact information: {match.contact_info}</p>
      )}
      {match.post_url && (
        <a
          className="post-link"
          href={match.post_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {match.source_type === "public" ? "Open indexed public result" : "Open report"}
          <span aria-hidden="true"> ↗</span>
        </a>
      )}
      <p className="match-warning">
        <strong>Potential Match — Human Verification Required</strong>
        <span>AI similarity is only an indication. Verify the original post, image, location, and identifying details.</span>
      </p>
    </article>
  );
}

export default function App() {
  const [image, setImage] = useState(null);
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [dateLost, setDateLost] = useState("");
  const [matches, setMatches] = useState([]);
  const [resultNotice, setResultNotice] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    if (!image) {
      setPreviewUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMatches([]);
    setLoading(true);

    const formData = new FormData();
    formData.append("pet_image", image);
    formData.append("description", description.trim());
    formData.append("location", location.trim());
    formData.append("date_lost", dateLost);

    try {
      const response = await fetch(`${API_URL}/api/matches`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(payload.detail)
          ? payload.detail.map((item) => item.msg).join(". ")
          : payload.detail;
        throw new Error(detail || "The match search could not be completed.");
      }
      setMatches(payload.matches);
      setResultNotice(payload.notice);
      setHasSearched(true);
    } catch (requestError) {
      setError(
        requestError.message ||
          "Could not reach PetTrace. Check that the API is running and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="PetTrace home">
          <span className="brand-mark" aria-hidden="true">P</span>
          PetTrace
        </a>
        <span className="header-note">A little hope, one lead at a time</span>
      </header>

      <section className="intro">
        <p className="eyebrow">LOCAL + PUBLICLY INDEXED REPORT SEARCH</p>
        <h1>Let’s bring them<br /><span>back home.</span></h1>
        <p className="intro-copy">
          Share what you know about your missing pet. PetTrace will look for
          possible matches in local reports and publicly indexed social pages.
        </p>
      </section>

      <section className="search-panel" aria-labelledby="form-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">START A SEARCH</p>
            <h2 id="form-title">Tell us about your pet</h2>
          </div>
          <span className="step-label">01 / SEARCH</span>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="upload-box" htmlFor="pet-image">
            {previewUrl ? (
              <img className="image-preview" src={previewUrl} alt="Pet preview" />
            ) : (
              <span className="upload-icon" aria-hidden="true">+</span>
            )}
            <span className="upload-copy">
              <strong>{image ? image.name : "Add a clear photo"}</strong>
              <span>JPG, PNG or WEBP · up to 10 MB</span>
            </span>
            <span className="upload-action">Browse</span>
            <input
              id="pet-image"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              required
              onChange={(event) => setImage(event.target.files?.[0] || null)}
            />
          </label>

          <label className="field-label" htmlFor="description">
            What does your pet look like?
            <textarea
              id="description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Color, breed, size, collar, distinctive markings..."
              maxLength={1000}
              required
            />
          </label>

          <div className="field-row">
            <label className="field-label" htmlFor="location">
              Where were they last seen?
              <input
                id="location"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Neighborhood, city"
                maxLength={160}
                required
              />
            </label>
            <label className="field-label" htmlFor="date-lost">
              Date lost
              <input
                id="date-lost"
                type="date"
                value={dateLost}
                onChange={(event) => setDateLost(event.target.value)}
                max={new Date().toISOString().slice(0, 10)}
                required
              />
            </label>
          </div>

          {error && <p className="error-message" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={loading || !image}>
            {loading ? "Searching and comparing reports..." : "Find possible matches"}
            {!loading && <span aria-hidden="true">→</span>}
          </button>
          <p className="privacy-note">
            Your photo is sent to Azure OpenAI. Description, traits, and location are sent to Serper to find indexed public pages. No private content is accessed.
          </p>
        </form>
      </section>

      {hasSearched && (
        <section className="results-section" aria-live="polite">
          <div className="results-heading">
            <div>
              <p className="eyebrow">YOUR SEARCH RESULTS</p>
              <h2>Possible matches</h2>
            </div>
            <span className="results-count">{matches.length} found</span>
          </div>
          <div className="verification-notice">
            <span className="notice-icon" aria-hidden="true">!</span>
            <p>
              <strong>Potential Match — Human Verification Required.</strong>
              {" "}{resultNotice} Similarity indicators are not probabilities.
            </p>
          </div>
          {matches.length > 0 ? (
            <div className="match-list">
              {matches.map((match, index) => (
                <MatchCard key={match.id} match={match} index={index} />
              ))}
            </div>
          ) : (
            <p className="empty-hint">
              No possible matches were found in the current local reports or indexed public pages.
            </p>
          )}
        </section>
      )}

      {!hasSearched && matches.length === 0 && !loading && !error && (
        <p className="empty-hint">Your top three local report matches will appear here.</p>
      )}

      <footer className="site-footer">
        <span>PetTrace MVP</span>
        <span>Potential Match — Human Verification Required</span>
      </footer>
    </main>
  );
}
