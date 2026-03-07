import { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import {
  fetchInitialAlerts,
  selectAlert,
  closeDetail,
  logout,
} from "../store/alertsSlice";
import Header from "../components/Header/Header";
import StatsBar from "../components/StatsBar/StatsBar";
import AlertList from "../components/AlertList/AlertList";
import AlertDetail from "../components/AlertDetail/AlertDetail";

export default function Dashboard() {
  const [filter, setFilter] = useState('active'); // active, urgent, med, low, closed
  const dispatch = useDispatch();
  const {
    items: alerts,
    selectedAlertId,
    status,
    currentUser,
  } = useSelector((state) => state.alerts);

  const navigate = useNavigate();

  useEffect(() => {
    if (!currentUser) {
      navigate('/login');
    }
  }, [currentUser, navigate]);

  // Validate restored session against the backend on mount
  useEffect(() => {
    if (!currentUser) return;
    const validateSession = async () => {
      try {
        const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
        const res = await fetch(`${backendUrl}/cases/operators`);
        if (!res.ok) throw new Error('Failed to fetch operators');
        const data = await res.json();
        const stillValid = (data.operators || []).some(
          (op) => op.operator_id === currentUser.operator_id
        );
        if (!stillValid) {
          dispatch(logout());
          navigate('/login');
        }
      } catch {
        // On network error, keep session alive (fail-open)
      }
    };
    validateSession();
  // Only run once on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (status === "idle" && currentUser) {
      dispatch(fetchInitialAlerts());
    }
  }, [status, dispatch, currentUser]);

  // Stabilize sorting: only re-sort when the set of alerts actually changes (length or significant event)
  // This prevents the list from "jumping" when minor status/score updates happen during interaction
  const sortedAlerts = useMemo(() => {
    const TIER_PRIORITY = {
      'life_threatening': 100,
      'emergency': 80,
      'requires_review': 60,
      'minor_emergency': 40,
      'non_emergency': 20
    };

    return [...alerts].sort((a, b) => {
      // Primary sort: Urgency Bucket (Tier)
      const tierDiff = (TIER_PRIORITY[b.tier] || 0) - (TIER_PRIORITY[a.tier] || 0);
      if (tierDiff !== 0) return tierDiff;

      // Secondary sort: Fine-grained Queue Score
      const scoreDiff = (b.queue_score || 0) - (a.queue_score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      
      // Tertiary sort: Recency
      return new Date(b.opened_at) - new Date(a.opened_at) || b.id.localeCompare(a.id);
    });
  }, [alerts]); 

  // Aggregate stats
  const activeAlerts = alerts.filter(a => a.actionState !== 'resolved');
  const closedAlerts = alerts.filter(a => a.actionState === 'resolved');

  const stats = {
    urgent: activeAlerts.filter((a) => a.tier === "life_threatening" || a.tier === "emergency").length,
    med: activeAlerts.filter((a) => a.tier === "requires_review").length,
    low: activeAlerts.filter((a) => a.tier === "minor_emergency" || a.tier === "non_emergency").length,
    total: activeAlerts.length,
    closed: closedAlerts.length
  };

  // Apply filtering to the already sorted alerts
  const filteredAlerts = useMemo(() => {
    if (filter === 'active') return sortedAlerts.filter(a => a.actionState !== 'resolved');
    if (filter === 'urgent') return sortedAlerts.filter(a => (a.tier === 'life_threatening' || a.tier === 'emergency') && a.actionState !== 'resolved');
    if (filter === 'med') return sortedAlerts.filter(a => a.tier === 'requires_review' && a.actionState !== 'resolved');
    if (filter === 'low') return sortedAlerts.filter(a => (a.tier === 'minor_emergency' || a.tier === 'non_emergency') && a.actionState !== 'resolved');
    if (filter === 'closed') return sortedAlerts.filter(a => a.actionState === 'resolved');
    return sortedAlerts;
  }, [sortedAlerts, filter]);

  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-color)]">
      {/* Header */}
      <div className="flex-none border-b border-[var(--panel-border)]">
        <Header />
      </div>

      {/* Stats */}
      <div className="flex-none border-b border-[var(--panel-border)]">
        <StatsBar 
          stats={stats} 
          activeFilter={filter} 
          onFilterChange={setFilter} 
        />
      </div>

      {/* Main Content Area: Split dynamically based on selection */}
      <div className="flex flex-1 overflow-hidden">
        {/* Alert List Container (grows) */}
        <div
          className={`flex flex-col ${selectedAlertId ? "w-full lg:w-[calc(100%-400px)] lg:border-r border-[var(--panel-border)]" : "w-full"} overflow-hidden transition-all duration-300`}
        >
          <AlertList
            alerts={filteredAlerts}
            selectedAlertId={selectedAlertId}
            onSelectAlert={(id) => dispatch(selectAlert(id))}
          />
        </div>

        {/* Alert Detail Side Panel (fixed width on desktop, overlays/slides on mobile ideally) */}
        {selectedAlertId && (
          <div className="w-[400px] flex-none bg-[var(--panel-bg)] overflow-y-auto hidden lg:block border-l border-[var(--panel-border)] animate-slideIn">
            <AlertDetail
              alert={selectedAlert}
              onClose={() => dispatch(closeDetail())}
            />
          </div>
        )}
      </div>
    </div>
  );
}
