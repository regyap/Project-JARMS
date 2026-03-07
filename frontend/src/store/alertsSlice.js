import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// --- Session Persistence Helpers ---
const SESSION_KEY = 'jarms_operator_session';

const loadSession = () => {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const saveSession = (user) => {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  } catch { /* ignore */ }
};

const clearSession = () => {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch { /* ignore */ }
};

// Helper to unify mapping from backend schema to frontend structure
export const mapCase = (c) => ({
  id: c.case_id || c.id,
  tier: c.urgency_bucket || 'requires_review',
  source: c.source === 'pab_audio' ? 'audio' : 'btn',
  location: c.address ? `${c.address} ${c.unit_number || ''}`.trim() : 'Unknown Location',
  queue_score: Number(c.live_queue_score || c.queue_score || 0),
  opened_at: c.opened_at || c.created_at,
  closed_at: c.closed_at,
  actionState: c.status || 'new',
  audio_file_url: c.audio_file_url,
  audio_duration_seconds: c.audio_duration_seconds,
  transcript: c.transcript_english || c.transcript_raw || '',
  sbar: typeof c.sbar_json === 'string' ? JSON.parse(c.sbar_json) : c.sbar_json,
  triage_flags: c.triage_flags || [],
  recommended_actions: c.recommended_actions || [],
  languages: [c.primary_language, c.secondary_language].filter(Boolean),
  keywords: c.triage_flags || [],
  button_location: c.button_location,
  beneficiary: {
    nric: c.nric,
    full_name: c.full_name,
    age: c.age,
    primary_language: c.primary_language,
    secondary_language: c.secondary_language,
    address: c.address,
    unit_number: c.unit_number,
    phone_number: c.phone_number,
    emergency_contact_name: c.emergency_contact_name,
    emergency_contact: c.emergency_contact,
    primary_hospital: c.primary_hospital,
    insurance_ward_class: c.insurance_ward_class,
    patient_medical_summary: c.patient_medical_summary,
    dnr_status: c.dnr_status,
    consent_private_ambulance: c.consent_private_ambulance
  }
});

// Async thunk to fetch initial alerts from backend
export const fetchInitialAlerts = createAsyncThunk(
  'alerts/fetchInitial',
  async () => {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
    const response = await fetch(`${backendUrl}/cases/`);
    if (!response.ok) throw new Error('Failed to fetch cases');
    const data = await response.json();
    return (data.items || []).map(mapCase);
  }
);

// Async thunk to update case in backend
export const updateCaseBackend = createAsyncThunk(
  'alerts/updateCaseBackend',
  async ({ caseId, updates }) => {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
    const response = await fetch(`${backendUrl}/cases/${caseId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    if (!response.ok) throw new Error('Failed to update case');
    return await response.json();
  }
);

const alertsSlice = createSlice({
  name: 'alerts',
  initialState: {
    items: [],
    selectedAlertId: null,
    status: 'idle', // idle, loading, succeeded, failed
    currentUser: loadSession(), // Restore from localStorage on app start
  },
  reducers: {
    setOperator: (state, action) => {
      state.currentUser = action.payload;
      saveSession(action.payload); // Persist session
    },
    logout: (state) => {
      state.currentUser = null;
      clearSession(); // Clear persisted session
    },
    addAlert: (state, action) => {
      const exists = state.items.some(item => item.id === action.payload.id);
      if (exists) return;

      state.items.unshift(action.payload);
      if (state.items.length > 50) {
        state.items.pop();
      }
    },
    setAlerts: (state, action) => {
      state.items = action.payload;
      state.status = 'succeeded';
    },
    selectAlert: (state, action) => {
      // Toggle selection: if clicking the same one, deselect it
      if (state.selectedAlertId === action.payload) {
        state.selectedAlertId = null;
      } else {
        state.selectedAlertId = action.payload;
      }
    },
    closeDetail: (state) => {
      state.selectedAlertId = null;
    },
    advanceAlertState: (state, action) => {
      // Local optimistic update
      const { id } = action.payload;
      const alert = state.items.find(a => a.id === id);
      
      if (alert) {
        if (!alert.actionHistory) alert.actionHistory = [];

        const now = new Date().toISOString();
        
        if (alert.actionState === 'new') {
          alert.actionState = 'claimed';
        } else if (alert.actionState === 'claimed') {
          alert.actionState = 'dispatched';
        } else if (alert.actionState === 'dispatched') {
          alert.actionState = 'resolved';
        }

        alert.actionHistory.push({
          state: alert.actionState,
          agentId: state.currentUser?.operator_id || state.currentUser?.id,
          agentName: state.currentUser?.username || state.currentUser?.name,
          timestamp: now
        });
      }
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchInitialAlerts.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchInitialAlerts.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.items = action.payload;
      })
      .addCase(fetchInitialAlerts.rejected, (state) => {
        state.status = 'failed';
      })
      .addCase(updateCaseBackend.fulfilled, (state, action) => {
        const updatedCaseRaw = action.payload.case;
        if (!updatedCaseRaw) return;
        
        const index = state.items.findIndex(a => a.id === updatedCaseRaw.case_id);
        if (index !== -1) {
          const mappedCase = mapCase(updatedCaseRaw);
          state.items[index] = { ...state.items[index], ...mappedCase };
        }
      });
  }
});

export const { addAlert, setAlerts, selectAlert, closeDetail, advanceAlertState, setOperator, logout } = alertsSlice.actions;
export default alertsSlice.reducer;
