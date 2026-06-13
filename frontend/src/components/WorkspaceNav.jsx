export function WorkspaceNav({ activeView, views, onChange }) {
  return (
    <nav className="workspace-nav" aria-label="workspace">
      {views.map((view) => {
        const selected = activeView === view.id;
        return (
          <button
            key={view.id}
            type="button"
            className={`nav-item ${selected ? "selected" : ""}`}
            onClick={() => onChange(view.id)}
          >
            <span className="nav-title">{view.label}</span>
            <span className="nav-summary">{view.summary}</span>
          </button>
        );
      })}
    </nav>
  );
}
