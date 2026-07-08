import { Routes, Route } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import LivePage from "./pages/LivePage";
import EventsPage from "./pages/EventsPage";
import ZonesPage from "./pages/ZonesPage";
import ReportsPage from "./pages/ReportsPage";
import AssistantPage from "./pages/AssistantPage";
import CamerasPage from "./pages/CamerasPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/zones" element={<ZonesPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
      </Route>
    </Routes>
  );
}
