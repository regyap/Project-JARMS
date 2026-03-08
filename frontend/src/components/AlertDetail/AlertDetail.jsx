import { useState, useRef, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { 
  X, CheckSquare, Square, Mic, Volume2, Play, Pause, HeartPulse, 
  ShieldAlert, Phone, Building2, BellRing, MapPin, Truck, 
  CheckCircle2, UserCheck, PlusCircle, AlertTriangle, MessageSquare, Info,
  Users, Car, ShieldCheck
} from 'lucide-react';
import { updateCaseBackend, refreshAlerts } from '../../store/alertsSlice';
import './AlertDetail.css';

export default function AlertDetail({ alert, onClose }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef(null);

  // Reset audio state when alert changes
  useEffect(() => {
    setIsPlaying(false);
    setProgress(0);
    setDuration(alert?.audio_duration_seconds || 0);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
  }, [alert?.id]);

  if (!alert) return null;

  const headerClass = `detail-header tier-${alert.tier}`;

  const togglePlay = () => {
    if (isPlaying) {
      audioRef.current?.pause();
      setIsPlaying(false);
    } else {
      audioRef.current?.play();
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current && isFinite(audioRef.current.duration) && audioRef.current.duration > 0) {
      const p = (audioRef.current.currentTime / audioRef.current.duration) * 100;
      setProgress(p);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current && isFinite(audioRef.current.duration)) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setProgress(0);
  };

  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

  return (
    <div className="alert-detail h-full flex flex-col">
      <div className={headerClass}>
        <div className="detail-header-left">
          <span className={`detail-badge detail-badge-${alert.tier}`}>
            {(alert.tier || 'new').replace('_', ' ').toUpperCase()}
          </span>
          <h1 className="alert-id mono">CASE #{alert.id}</h1>
        </div>
        <button className="btn-close cursor-pointer" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="detail-content flex-1 overflow-y-auto">
        {/* Audio Player Section */}
        <section className="detail-section p-4 bg-black/40 rounded-xl border border-[var(--panel-border)] mb-4">
          <h3 className="section-title mono !border-none !pb-0 !mb-4">AUDIO PLAYBACK</h3>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={togglePlay}
              className="w-12 h-12 rounded-full bg-[var(--color-active)] flex items-center justify-center text-black hover:bg-white transition-colors flex-shrink-0 cursor-pointer"
            >
              {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
            </button>
            
            <div className="flex-1">
              <div className="h-2 bg-[var(--panel-border)] rounded-full overflow-hidden">
                <div 
                  className="h-full bg-[var(--color-active)] transition-all duration-100 ease-linear"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between mt-2 text-xs text-[var(--text-secondary)] mono">
                <span>{isPlaying ? 'PLAYING...' : 'READY'}</span>
                <span>
                  {isFinite(duration) && duration > 0 ? `${Math.round(duration)}s` : 
                   (isFinite(alert.audio_duration_seconds) && alert.audio_duration_seconds > 0 ? `${Math.round(alert.audio_duration_seconds)}s` : 'Unknown')} REC
                </span>
              </div>
            </div>
          </div>
          <audio 
            ref={audioRef}
            src={`${backendUrl}/cases/audio/${alert.id}`}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onEnded={handleEnded}
            className="hidden"
          />
        </section>

        {/* AI Triage & Summary Section */}
        <section className="detail-section mb-6">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2 mb-4">
            <h3 className="section-title mono border-b border-dashed border-[var(--panel-border)] pb-3 mb-0 flex-1">
              <span>AI TRIAGE & SUMMARY</span>
            </h3>
            <span className="text-[10px] bg-[#10b981]/20 px-2 py-0.5 rounded text-[#10b981] border border-[#10b981]/50 w-fit">AI Generated</span>
          </div>

          {/* Transcript Snippet */}
          {alert.transcript && (
            <div className="mb-4 p-3 bg-black/20 rounded border-l-2 border-[var(--color-med)] italic text-sm text-[#ddd]">
              "{alert.transcript}"
            </div>
          )}

          {/* AI Audio Caption / Sound Description */}
          {alert.audio_caption_text && (
            <div className="mb-4 p-3 bg-[#10b981]/5 rounded border border-[#10b981]/20">
              <div className="text-[10px] text-[#10b981] font-mono uppercase tracking-widest mb-1.5 flex items-center gap-1">
                <Volume2 size={10} /> AI Sound Description
              </div>
              <p className="text-sm text-[#ccc] leading-relaxed">{alert.audio_caption_text}</p>
            </div>
          )}

          {/* SBAR Card */}
          {alert.sbar && (
            <div className="sbar-container grid gap-3 mb-6">
              <div className="sbar-item">
                <span className="sbar-label text-blue-400">SITUATION</span>
                <p className="sbar-text">{alert.sbar.situation}</p>
              </div>
              <div className="sbar-item">
                <span className="sbar-label text-purple-400">BACKGROUND</span>
                <p className="sbar-text">{alert.sbar.background}</p>
              </div>
              <div className="sbar-item">
                <span className="sbar-label text-amber-400">ASSESSMENT</span>
                <p className="sbar-text">{alert.sbar.assessment}</p>
              </div>
              {/* User requested to ignore "recommendation" field from SBAR json */}
            </div>
          )}

          {/* Triage Flags */}
          {alert.triage_flags && alert.triage_flags.length > 0 && (
            <div className="triage-flags mb-6">
              <h4 className="text-[10px] text-[var(--text-secondary)] font-mono mb-2 uppercase tracking-widest">Triage Flags</h4>
              <div className="flex flex-wrap gap-2">
                {alert.triage_flags.map((flag, idx) => (
                  <span key={idx} className="flag-pill">
                    {flag.replace(/_/g, ' ').toUpperCase()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Case Metadata Section - Restored and combined */}
        <section className="detail-section mb-6">
          <h3 className="section-title mono">CASE METADATA</h3>
          <div className="bg-[#000]/20 p-3 rounded border border-white/5 space-y-3">
             <div className="flex justify-between items-center text-xs">
               <span className="text-[var(--text-secondary)] font-mono uppercase tracking-tighter">Location</span>
               <span className="text-white font-medium text-right max-w-[200px]">{alert.location || 'Unknown'}</span>
             </div>
             {alert.button_location && (
               <div className="flex justify-between items-center text-xs">
                 <span className="text-[var(--text-secondary)] font-mono uppercase tracking-tighter">PAB Placement</span>
                 <span className="text-white font-medium text-right">{alert.button_location.replace('_', ' ').toUpperCase()}</span>
               </div>
             )}
             <div className="flex justify-between items-center text-xs">
               <span className="text-[var(--text-secondary)] font-mono uppercase tracking-tighter">Languages Detect</span>
               <div className="flex gap-1 justify-end flex-wrap">
                 {alert.languages?.map((lang, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-white/10 rounded text-[10px]">{lang}</span>
                 )) || '-'}
               </div>
             </div>
             <div className="flex justify-between items-center text-xs">
               <span className="text-[var(--text-secondary)] font-mono uppercase tracking-tighter">Trigger Source</span>
               <span className="text-red-400 font-mono flex items-center gap-1">
                 {alert.source === 'audio' ? <Mic size={12} /> : <Info size={12} />} 
                 {alert.source === 'audio' ? 'Voice/Audio' : 'PAB Button'}
               </span>
             </div>
          </div>
        </section>

        {/* Beneficiary Profile Section */}
        {alert.beneficiary && (
          <section className="detail-section mb-4">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2 mb-4">
              <h3 className="section-title mono border-b border-dashed border-[var(--panel-border)] pb-3 mb-0 flex-1">
                <span>BENEFICIARY PROFILE</span>
              </h3>
              <span className="text-[10px] bg-[#333] px-2 py-0.5 rounded text-[var(--color-med)] w-fit">PAB DB Match</span>
            </div>
            
            <div className="bg-[#111] p-3 rounded-lg border border-[#333]">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="font-bold text-lg">{alert.beneficiary.full_name}</div>
                  <div className="text-xs text-[var(--text-secondary)] font-mono">NRIC: {alert.beneficiary.nric} • Age {alert.beneficiary.age}</div>
                </div>
                {alert.beneficiary.dnr_status === true && (
                  <div className="bg-red-900/30 text-[var(--color-urgent)] border border-[var(--color-urgent)] px-2 py-1 rounded text-xs font-bold animate-pulse">
                    DNR ACTIVE
                  </div>
                )}
              </div>

              <div className="space-y-2 mt-4 text-xs">
                <div className="flex justify-between border-b border-[#222] pb-1">
                  <span className="text-[var(--text-secondary)] font-mono uppercase">Primary Language</span>
                  <span>{alert.beneficiary.primary_language}</span>
                </div>
                {alert.beneficiary.secondary_language && (
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-[var(--text-secondary)] font-mono uppercase">Secondary Language</span>
                    <span>{alert.beneficiary.secondary_language}</span>
                  </div>
                )}
                <div className="flex justify-between border-b border-[#222] pb-1">
                  <span className="text-[var(--text-secondary)] font-mono uppercase">Phone</span>
                  <span className="text-[var(--color-med)]">{alert.beneficiary.phone_number}</span>
                </div>
                <div className="flex justify-between border-b border-[#222] pb-1">
                  <span className="text-[var(--text-secondary)] font-mono uppercase">Emergency Contact</span>
                  <span className="text-[var(--color-med)]">{alert.beneficiary.emergency_contact_name} ({alert.beneficiary.emergency_contact})</span>
                </div>
                <div className="flex justify-between border-b border-[#222] pb-1">
                  <span className="text-[var(--text-secondary)] font-mono uppercase">Hospital</span>
                  <span>{alert.beneficiary.primary_hospital} ({alert.beneficiary.insurance_ward_class})</span>
                </div>
                {alert.beneficiary.consent_private_ambulance && (
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-[var(--text-secondary)] font-mono uppercase">Private Ambulance Consent</span>
                    <span className="text-green-400 font-bold">YES</span>
                  </div>
                )}
              </div>

              {alert.beneficiary.patient_medical_summary && (
                <div className="mt-4 p-2 bg-[#1a1a1a] rounded border border-[#222]">
                  <div className="text-[10px] text-[var(--text-secondary)] font-mono mb-1 uppercase tracking-wider flex items-center gap-1">
                    <HeartPulse size={12} /> Medical Summary
                  </div>
                  <p className="text-sm leading-relaxed text-[#eee]">
                    {alert.beneficiary.patient_medical_summary}
                  </p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Agent Actions */}
        <section className="detail-section mb-12">
           <h3 className="section-title mono">CASE STATUS & ACTIONS</h3>
           <ActionController alert={alert} />
        </section>

        {/* Metadata section (formerly LOCATION & TIME but narrowed down to system logs) */}
        <section className="detail-section">
          <h3 className="section-title mono">SYSTEM LOGS</h3>
          <div className="w-full text-xs text-[var(--text-secondary)]">
            <div className="flex justify-between py-2 border-b border-[var(--panel-border)]">
              <span>Opened At</span>
              <span className="text-[var(--text-primary)] font-mono">
                {alert.opened_at ? new Date(alert.opened_at).toLocaleString() : 'Unknown'}
              </span>
            </div>
            {alert.closed_at && (
              <div className="flex justify-between py-2 border-b border-[var(--panel-border)]">
                <span>Closed At</span>
                <span className="text-[var(--text-primary)] font-mono">
                  {new Date(alert.closed_at).toLocaleString()}
                </span>
              </div>
            )}
            <div className="flex justify-between py-2 border-b border-[var(--panel-border)]">
              <span>Urgency Score</span>
              <span className={`font-mono text-[var(--color-${alert.tier})] font-bold`}>{alert.queue_score}%</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function ActionController({ alert }) {
  const dispatch = useDispatch();
  const currentUser = useSelector((state) => state.alerts.currentUser);
  const [selectedActions, setSelectedActions] = useState([]);
  
  // Initialize selected actions from recommendations
  useEffect(() => {
    if (alert.recommended_actions) {
      setSelectedActions(alert.recommended_actions);
    }
  }, [alert.id, alert.recommended_actions]);

  const allPossibleActions = [
    { id: 'call_patient_now', label: 'Call Patient', icon: Phone },
    { id: 'inform_emergency_contact', label: 'Contact NOK', icon: UserCheck },
    { id: 'call_sgsecure_volunteers', label: 'SGSecure Volunteers', icon: Users },
    { id: 'call_995', label: 'Call 995', icon: Truck },
    { id: 'call_private_ambulance_1777', label: 'Call 1777 (Pv Ambl)', icon: ShieldCheck },
    { id: 'call_ed_by_private_transport', label: 'Pv Transport (ED)', icon: Car },
    { id: 'call_999', label: 'Call 999 (Police)', icon: ShieldAlert },
    { id: 'notify_lift_lobby', label: 'Notify Lift Lobby', icon: BellRing }
  ];

  const handleToggleAction = (id) => {
    setSelectedActions(prev => 
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  };

  const handleExecute = async () => {
    await dispatch(updateCaseBackend({ 
      caseId: alert.id, 
      updates: { 
        status: 'dispatched',
        assigned_operator_id: currentUser?.operator_id
      } 
    }));
    dispatch(refreshAlerts());
  };

  const handleResolve = async () => {
    await dispatch(updateCaseBackend({ 
      caseId: alert.id, 
      updates: { 
        status: 'resolved'
      } 
    }));
    dispatch(refreshAlerts());
  };

  const status = alert.status || alert.actionState || 'new';

  return (
    <div className="space-y-6">
      <div className="grid gap-2">
        <h4 className="text-[10px] text-[var(--text-secondary)] font-mono uppercase tracking-widest mb-1">Select Interventions</h4>
        {allPossibleActions.map(action => {
          const isRecommended = alert.recommended_actions?.includes(action.id);
          const isSelected = selectedActions.includes(action.id);
          const Icon = action.icon;

          return (
            <div 
              key={action.id}
              onClick={() => handleToggleAction(action.id)}
              className={`p-3 rounded-lg border flex items-center justify-between cursor-pointer transition-all ${
                isSelected 
                  ? 'bg-[var(--color-med)]/20 border-[var(--color-med)] text-white' 
                  : 'bg-black/20 border-white/5 text-[var(--text-secondary)] hover:border-white/20'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon size={16} className={isSelected ? 'text-[var(--color-med)]' : ''} />
                <span className="text-sm font-medium">{action.label}</span>
              </div>
              {isRecommended && !isSelected && (
                <span className="text-[9px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded border border-red-500/30 flex items-center gap-1">
                  <AlertTriangle size={8} /> REC
                </span>
              )}
              {isSelected && <CheckSquare size={16} className="text-[var(--color-med)]" />}
            </div>
          );
        })}
      </div>

      <div className="pt-6 space-y-3">
        {status === 'processing' ? (
          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl text-center">
            <div className="text-blue-400 font-bold mono text-sm mb-1 uppercase tracking-widest flex items-center justify-center gap-2 animate-pulse">
              AI TRIAGE IN PROGRESS...
            </div>
            <div className="text-[10px] text-[var(--text-secondary)] mono">Wait for analysis to complete.</div>
          </div>
        ) : status === 'queued' ? (
          <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-center">
            <div className="text-amber-400 font-bold mono text-sm mb-1 uppercase tracking-widest flex items-center justify-center gap-2">
              QUEUED FOR RECOMMENDATION
            </div>
            <div className="text-[10px] text-[var(--text-secondary)] mono">Waiting for system prioritize actions...</div>
          </div>
        ) : status === 'error' ? (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-center">
            <div className="text-red-400 font-bold mono text-sm mb-1 uppercase tracking-widest flex items-center justify-center gap-2">
              TRIAGE PIPELINE ERROR
            </div>
            <div className="text-[10px] text-[var(--text-secondary)] mono">AI analysis failed. Please triage manually.</div>
          </div>
        ) : status !== 'resolved' ? (
          <div className="space-y-3">
            {(status === 'new' || status === 'claimed') && (
              <button 
                onClick={handleExecute}
                disabled={selectedActions.length === 0}
                className={`w-full py-4 bg-white text-black font-bold mono tracking-widest rounded-xl transition-colors shadow-lg disabled:opacity-50 ${selectedActions.length > 0 ? 'hover:bg-[var(--color-active)] cursor-pointer' : 'cursor-default'}`}
              >
                {status === 'new' ? 'CLAIM & EXECUTE' : 'EXECUTE PLAN'}
              </button>
            )}
            
            {(status === 'dispatched') && (
              <button 
                onClick={handleResolve}
                className={`w-full py-3 bg-[#10b981] text-black font-bold mono tracking-widest rounded-lg hover:bg-[#0ea870] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] transition-all shadow-[0_0_10px_rgba(16,185,129,0.2)] text-sm cursor-pointer`}
              >
                MARK AS RESOLVED / CLOSED
              </button>
            )}
          </div>
        ) : (
          <div className="p-4 bg-[#10b981]/10 border border-[#10b981]/30 rounded-xl text-center">
            <div className="text-[#10b981] font-bold mono text-sm mb-1 uppercase tracking-widest flex items-center justify-center gap-2">
              <CheckCircle2 size={16} /> CASE CLOSED
            </div>
            <div className="text-[10px] text-[var(--text-secondary)] mono">Case resolution protocol complete.</div>
          </div>
        )}
      </div>
    </div>
  );
}
