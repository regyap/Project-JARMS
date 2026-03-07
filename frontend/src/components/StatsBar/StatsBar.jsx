import './StatsBar.css';

export default function StatsBar({ stats, activeFilter, onFilterChange }) {
  return (
    <div className="stats-bar">
      <div 
        className={`stat-card urgent-stat ${activeFilter === 'urgent' ? 'active' : ''}`}
        onClick={() => onFilterChange('urgent')}
      >
        <div className="stat-value mono">{stats.urgent}</div>
        <div className="stat-label">CRITICAL</div>
        <div className="stat-desc mono">Requires Immediate Action</div>
      </div>
      
      <div 
        className={`stat-card med-stat ${activeFilter === 'med' ? 'active' : ''}`}
        onClick={() => onFilterChange('med')}
      >
        <div className="stat-value mono">{stats.med}</div>
        <div className="stat-label">ASSESSMENT NEEDED</div>
        <div className="stat-desc mono">Review Signal Integrity</div>
      </div>
      
      <div 
        className={`stat-card low-stat ${activeFilter === 'low' ? 'active' : ''}`}
        onClick={() => onFilterChange('low')}
      >
        <div className="stat-value mono">{stats.low}</div>
        <div className="stat-label">NON-URGENT</div>
        <div className="stat-desc mono">Environmental / Testing</div>
      </div>
      
      <div 
        className={`stat-card total-stat ${activeFilter === 'active' ? 'active' : ''}`}
        onClick={() => onFilterChange('active')}
      >
        <div className="stat-value mono">{stats.total}</div>
        <div className="stat-label">TOTAL ACTIVE</div>
        <div className="stat-desc mono">Cases in Queue</div>
      </div>

      <div 
        className={`stat-card closed-stat ${activeFilter === 'closed' ? 'active' : ''}`}
        onClick={() => onFilterChange('closed')}
      >
        <div className="stat-value mono">{stats.closed}</div>
        <div className="stat-label">CLOSED CASES</div>
        <div className="stat-desc mono">Resolved Alerts</div>
      </div>
    </div>
  );
}
