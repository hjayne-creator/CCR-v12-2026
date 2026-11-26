import { Link, Navigate, Route, Routes } from "react-router-dom";
import NewRun from "./pages/NewRun";
import RulesEditor from "./pages/RulesEditor";
import RunDetail from "./pages/RunDetail";
import RunList from "./pages/RunList";

export default function App() {
  return (
    <div className="shell">
      <nav className="nav">
        <Link to="/" className="brand">
          CCR <span>v12</span>
        </Link>
        <div className="nav-links">
          <Link to="/">Runs</Link>
          <Link to="/new">New run</Link>
          <Link to="/rules">Rules</Link>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<RunList />} />
        <Route path="/new" element={<NewRun />} />
        <Route path="/rules" element={<RulesEditor />} />
        <Route path="/runs/:id" element={<RunDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
