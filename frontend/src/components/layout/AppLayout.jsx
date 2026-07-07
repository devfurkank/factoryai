import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import AlarmToasts from "../alarms/AlarmToasts";

/** Ana yerleşim: sol sabit sidebar + üst bar + sayfa içeriği + global toast'lar. */
export default function AppLayout() {
  return (
    <div className="flex min-h-screen relative">
      {/* Glacier atmosferik arka plan glow'ları */}
      <div className="fixed inset-0 pointer-events-none z-[-1] bg-gradient-to-br from-background via-surface-container-lowest to-surface-container overflow-hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60vw] h-[60vw] rounded-full bg-tertiary/5 blur-[150px]" />
      </div>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 p-6 md:p-8">
          <Outlet />
        </main>
      </div>
      <AlarmToasts />
    </div>
  );
}
