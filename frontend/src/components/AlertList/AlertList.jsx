import { Mic, CircleDot } from 'lucide-react';
import { useDispatch, useSelector } from 'react-redux';
import { updateCaseBackend } from '../../store/alertsSlice';
import './AlertList.css';

export default function AlertList({ alerts, selectedAlertId, onSelectAlert }) {
  const dispatch = useDispatch();
  const currentUser = useSelector((state) => state.alerts.currentUser);
  
  const renderPill = (text, type, idx) => {
    let className = 'pill ';
    if (type === 'keyword') {
      className += text.match(/[\u0B80-\u0BFF\u4E00-\u9FFF]/) ? 'pill-keyword-foreign ' : 'pill-keyword ';
    } else {
      className += 'pill-lang ';
    }

    return (
      <span key={idx} className={className}>
        {text}
      </span>
    );
  };

  const getSourceIcon = (source) => {
    if (source === 'audio') return <Mic size={14} className="icon-source icon-mic" />;
    return <CircleDot size={14} className="icon-source icon-btn" />;
  };

  const getTimeElapsed = (openedAt) => {
    if (!openedAt) return '??';
    const seconds = Math.floor((new Date() - new Date(openedAt)) / 1000);
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  return (
    <div className="alert-list-container">
      <div className="alert-list-header mono">
        <div className="cell-tier">TIER</div>
        <div className="cell-source flex-center">SOURCE</div>
        <div className="cell-keywords">KEYWORDS | LANGUAGES</div>
        <div className="cell-location">LOCATION</div>
        <div className="cell-pitch flex-center">URGENCY %</div>
        <div className="cell-time flex-center">TIME</div>
        <div className="cell-action flex-center">ACTION</div>
      </div>

      <div className="alert-list-body">
        {alerts.map((alert) => {
          const isSelected = alert.id === selectedAlertId;
          const isResolved = alert.actionState === 'resolved';
          const rowClass = `alert-row tier-${alert.tier} ${isSelected ? 'selected' : ''} ${isResolved ? 'resolved' : ''}`;
          
          return (
            <div 
              key={alert.id} 
              className={rowClass}
              onClick={() => onSelectAlert(alert.id)}
            >
              {/* Tier Column */}
              <div className="cell-tier relative">
                {(alert.tier === 'urgent' || alert.tier === 'life_threatening' || alert.tier === 'emergency') && <div className="pulse-dot"></div>}
                <span className={`badge badge-${alert.tier}`}>
                  {(alert.tier || 'new').replace('_', ' ').toUpperCase()}
                </span>
              </div>

              {/* Source Column */}
              <div className="cell-source flex-center-col">
                {getSourceIcon(alert.source)}
                <span className="source-text">{alert.source === 'btn' ? 'PAB Button' : 'Voice/Audio'}</span>
                {alert.source === 'audio' && (
                  <span className="duration-text mono">
                    [{isFinite(alert.audio_duration_seconds) && alert.audio_duration_seconds > 0 
                      ? `${Math.round(alert.audio_duration_seconds)}s` 
                      : 'Unknown'}]
                  </span>
                )}
              </div>

              {/* Keywords & Languages Column */}
              <div className="cell-keywords">
                <div className="pill-container">
                  {alert.keywords?.map((kw, i) => renderPill(`"${kw}"`, 'keyword', i))}
                  {alert.languages?.map((lang, i) => renderPill(lang, 'language', i))}
                </div>
              </div>

              {/* Location Column */}
              <div className="cell-location">
                <span className="location-text">{alert.location}</span>
              </div>

              {/* Urgency Column */}
              <div className="cell-pitch flex-center-col">
                <div className="pitch-value mono">{alert.queue_score}% urgent</div>
                <div className="pitch-bar-container">
                  <div className={`pitch-bar fill-${alert.tier}`} style={{ width: `${alert.queue_score}%` }}></div>
                </div>
              </div>

              {/* Time Column */}
              <div className="cell-time flex-center">
                <span className="time-text mono">{getTimeElapsed(alert.opened_at)} ago</span>
              </div>

              {/* Action Column */}
              <div className="cell-action flex-center">
                <div className="action-wrapper">
                  {['processing', 'queued', 'error'].includes(alert.actionState) ? (
                    <div className={`status-tag state-${alert.actionState}`}>
                      {alert.actionState === 'processing' ? 'AI TRIAGE...'
                       : alert.actionState === 'queued' ? 'QUEUED'
                       : 'AI ERROR'}
                    </div>
                  ) : (
                    <button 
                      className={`btn-action mono state-${alert.actionState || 'new'}`}
                      disabled={alert.actionState === 'resolved' || alert.actionState === 'claimed'}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (alert.actionState === 'new' || !alert.actionState) {
                          dispatch(updateCaseBackend({ 
                            caseId: alert.id, 
                            updates: { status: 'claimed', assigned_operator_id: currentUser?.operator_id } 
                          }));
                        } else if (alert.actionState === 'dispatched') {
                          dispatch(updateCaseBackend({ 
                            caseId: alert.id, 
                            updates: { status: 'resolved' } 
                          }));
                        }
                      }}
                    >
                      {alert.actionState === 'new' || !alert.actionState ? 'CLAIM' 
                       : alert.actionState === 'claimed' ? 'CLAIMED'
                       : alert.actionState === 'dispatched' ? 'RESOLVE'
                       : 'CLOSED'}
                    </button>
                  )}
                  {!['processing', 'queued', 'error'].includes(alert.actionState) && (
                    <div className="action-dots">
                      <span className={`dot ${alert.actionState === 'new' || !alert.actionState ? 'dot-active' : ''}`}></span>
                      <span className={`dot ${alert.actionState === 'claimed' ? 'dot-active' : ''}`}></span>
                      <span className={`dot ${alert.actionState === 'dispatched' ? 'dot-active' : ''}`}></span>
                      <span className={`dot ${alert.actionState === 'resolved' ? 'dot-active' : ''}`}></span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
