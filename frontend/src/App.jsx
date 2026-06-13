import { useState } from "react";
import { InspectorPanel } from "./components/InspectorPanel";
import { StatusPanel } from "./components/StatusPanel";
import { WorkspaceNav } from "./components/WorkspaceNav";
import { VIEW_DEFS } from "./data/testScenarios";
import { useChat } from "./hooks/useChat";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { ChatPage } from "./pages/ChatPage";
import { ProtocolPage } from "./pages/ProtocolPage";
import { RagPage } from "./pages/RagPage";
import { SystemPage } from "./pages/SystemPage";

function buildBrandFacts(health, activeView) {
  return [
    {
      label: "状态",
      value: health?.status || "pending",
    },
    {
      label: "模式",
      value: health?.profile || "pending",
    },
    {
      label: "RAG",
      value: health?.rag_db_exists ? "ready" : "missing",
    },
    {
      label: "工作区",
      value: activeView,
    },
  ];
}

function renderView(activeView, props) {
  if (activeView === "rag") {
    return <RagPage />;
  }
  if (activeView === "protocol") {
    return <ProtocolPage />;
  }
  if (activeView === "system") {
    return <SystemPage {...props} />;
  }
  return <ChatPage chat={props.chat} onLaunchScenario={props.onLaunchScenario} />;
}

export default function App() {
  const [activeView, setActiveView] = useState("chat");
  const chat = useChat();
  const { health, loading, error } = useSystemHealth();
  const brandFacts = buildBrandFacts(health, activeView);

  async function handleLaunchScenario(prompt) {
    setActiveView("chat");
    await chat.sendMessage(prompt);
  }

  return (
    <div className="app-shell">
      <aside className="left-rail">
        <div className="brand-block">
          <p className="eyebrow">MoniBox Control</p>
          <h1>MoniBox 控制台</h1>
          <dl className="brand-facts">
            {brandFacts.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <WorkspaceNav
          activeView={activeView}
          views={VIEW_DEFS}
          onChange={setActiveView}
        />

        <StatusPanel health={health} loading={loading} error={error} />
      </aside>

      <main className="main-stage">
        {renderView(activeView, {
          chat,
          health,
          loading,
          error,
          onLaunchScenario: handleLaunchScenario,
        })}
      </main>

      <InspectorPanel
        activeView={activeView}
        health={health}
        chat={chat}
        onLaunchScenario={handleLaunchScenario}
      />
    </div>
  );
}
