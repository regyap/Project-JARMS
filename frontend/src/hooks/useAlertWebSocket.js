import { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { addAlert, setAlerts, mapCase } from '../store/alertsSlice';
import { supabase } from '../services/supabaseClient';

const SIMULATED_KEYWORDS = ['emergency', 'வலிக்குது', 'help me', 'silence', 'background', '救命'];
const SIMULATED_LANGUAGES = ['English', 'Tamil', 'Hokkien', 'Mandarin', 'Malay', 'Teochew'];
const LOCATIONS = [
  'Blk 123 #11-20, Bedok',
  'Blk 456 #02-14, Tampines',
  'Blk 789 #15-05, Yishun',
  'Blk 234 #04-44, Jurong East'
];

/**
 * Custom hook managing the data layer for Live incoming alerts via Supabase.
 * Falls back to local generated mock generator if .env isn't configured.
 */
export default function useAlertWebSocket() {
  const dispatch = useDispatch();
  const mockTimerRef = useRef(null);

  useEffect(() => {

    // =========================================================================
    // [SECTION] REAL_LOGIC: Supabase Realtime & Backend API Integration
    // =========================================================================

    /**
     * Authored for actual deployment.
     * This function hits your Backend REST API to fetch the authoritative list.
     */
    const fetchActiveCases = async () => {
      try {
        console.log('[REAL_LOGIC] Re-fetching authoritative data from Backend API...');
        const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/cases/`);
        if (!response.ok) throw new Error('API fetch failed');

        const data = await response.json();
        const apiData = data.items || [];

        // Map backend cases to frontend alert structure using shared helper
        const mappedData = apiData.map(mapCase);

        dispatch(setAlerts(mappedData));
      } catch (err) {
        console.error('[REAL_LOGIC] Failed to fetch cases pipeline:', err);
      }
    };

    // If Supabase is connected, we use it strictly as an EVENT EMITTER.
    if (supabase) {
      console.log('[REAL_LOGIC] Supabase active. Initializing Event Emitter (Pub/Sub) on <cases>...');

      // 1. Load initial data on mount
      fetchActiveCases();

      // 2. Subscribe to Realtime events on the 'cases' table
      const channel = supabase
        .channel('public-cases-changes')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'cases' }, (payload) => {
          console.log('[REAL_LOGIC] Database change detected! Type:', payload.eventType);

          // Whenever a change happens, we don't parse the payload.
          // We trigger our authoritative REST API re-fetch.
          fetchActiveCases();
        })
        .subscribe();

      return () => {
        console.log('[REAL_LOGIC] Unsubscribing from Supabase changes.');
        supabase.removeChannel(channel);
      }
    }


    // =========================================================================
    // [SECTION] MOCK_LOGIC: Local Simulation Fallback
    // =========================================================================

    if (!supabase) {
      console.log('[MOCK_LOGIC] Initializing Local Simulator (5-Tier Urgency Mode)...');

      const BUCKETS = ['life_threatening', 'emergency', 'requires_review', 'minor_emergency', 'non_emergency'];

      const emitMockMessage = () => {
        const tier = BUCKETS[Math.floor(Math.random() * BUCKETS.length)];
        const isHighUrgency = tier === 'life_threatening' || tier === 'emergency';
        const queueScore = Math.floor(Math.random() * (isHighUrgency ? 30 : 50)) + (isHighUrgency ? 70 : 10);

        const newAlert = {
          id: Math.floor(Math.random() * 900) + 100 + '',
          tier: tier,
          source: Math.random() > 0.5 ? 'audio' : 'btn',
          keywords: [SIMULATED_KEYWORDS[Math.floor(Math.random() * SIMULATED_KEYWORDS.length)]],
          languages: [SIMULATED_LANGUAGES[Math.floor(Math.random() * SIMULATED_LANGUAGES.length)]],
          location: LOCATIONS[Math.floor(Math.random() * LOCATIONS.length)],
          coordinates: `${(Math.random() * 0.1 + 1.3).toFixed(4)}°N, ${(Math.random() * 0.1 + 103.8).toFixed(4)}°E`,
          pitch: queueScore, // backward compatibility
          queue_score: queueScore, // matching user schema
          timeAgo: 0,
          timestamp: new Date().toISOString(),
          actionState: 'new',
          metadata: {
            mlSource: tier === 'life_threatening' ? 'Critial Audio Peak Detected' : (Math.random() > 0.5 ? 'Audio ML' : 'Keyword match'),
            pitchScoreDetail: `Confidence score mapped to ${tier.replace('_', ' ')} bucket.`,
            dialectDetected: 'Multiple',
            falsePositiveAnalysis: {
              extraClicks: { passed: Math.random() > 0.1, desc: 'Signal verified' },
              backgroundNoise: { passed: Math.random() > 0.2, desc: 'Above threshold' },
              silentAudio: { passed: tier !== 'life_threatening', desc: 'Audio check complete' }
            }
          },
          beneficiary: {
            nric: `S${Math.floor(Math.random() * 9000000) + 1000000}A`,
            full_name: ['Tan Ah Kow', 'Lim Mei Ling', 'Siti Binte Omar', 'Muthu Kumar'][Math.floor(Math.random() * 4)],
            age: Math.floor(Math.random() * 25) + 65,
            phone_number: `+65 ${Math.floor(Math.random() * 90000000) + 80000000}`,
            emergency_contact_name: ['Shirley Tan', 'David Lim', 'Ali Bin Hassan', 'Priya Kumar'][Math.floor(Math.random() * 4)],
            emergency_contact: `+65 ${Math.floor(Math.random() * 90000000) + 80000000}`,
            patient_medical_summary: isHighUrgency ? 'History of ischemic heart disease and recurrent falls.' : 'Hypertension, Type 2 Diabetes.',
            DNR_status: isHighUrgency && Math.random() > 0.5 ? 'ACTIVE' : 'NONE',
            primary_language: 'English',
            insurance_ward_class: Math.random() > 0.5 ? 'A1' : 'B2',
            primary_hospital: ['Singapore General Hospital', 'Tan Tock Seng Hospital', 'Changi General Hospital'][Math.floor(Math.random() * 3)]
          }
        };

        dispatch(addAlert(newAlert));

        mockTimerRef.current = setTimeout(emitMockMessage, Math.random() * 15000 + 20000);
      };

      mockTimerRef.current = setTimeout(emitMockMessage, 3000);

      return () => {
        if (mockTimerRef.current) clearTimeout(mockTimerRef.current);
      }
    }
  }, [dispatch]);

}
