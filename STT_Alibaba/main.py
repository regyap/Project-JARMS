"""
main.py — Project JARMS Parallel AI Pipeline
=============================================
Project JARMS | Alibaba Cloud / DashScope

Purpose:
  Orchestrates the full audio analysis pipeline by running three different
  AI services in parallel using ThreadPoolExecutor:
    1. pureadio      — ASR transcription and translation
    2. situationeval — Paralinguistic signal detection (breathing, impairment)
    3. captioner     — Narrative scene description

  Once all three parallel tasks complete, it combines the results and
  feeds them into the stt_triage.py module for final urgency classification.

Usage:
  python main.py
"""

import os
import time
import concurrent.futures
from dotenv import load_dotenv

# Import our modules
import pureadio
import situationeval
import captioner
import stt_triage

load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")
USER_ID    = int(os.getenv("USER_ID", "1"))
DRY_RUN    = os.getenv("DRY_RUN", "false").lower() == "true"

# ------------------------------------------------------------------
# PIPELINE EXECUTION
# ------------------------------------------------------------------

def run_pipeline():
    print("\n" + "="*60)
    print("🚀 PROJECT JARMS — PARALLEL AI PIPELINE STARTING")
    print(f"   Audio File : {AUDIO_FILE}")
    print(f"   User ID    : {USER_ID}")
    print("="*60)

    start_time = time.time()

    # Step 0: Pre-fetch context (Protocol + Language)
    print("\n[INIT] Loading triage protocol & user language...")
    triage_protocol = stt_triage.load_triage_protocol()
    language        = stt_triage.get_user_language(USER_ID)
    print(f"[INIT] Protocol loaded. Language: {language}")

    # Step 1: Run core AI services in parallel
    print("\n[PARALLEL] Spawning AI workers (pureadio, situationeval, captioner)...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        print(f"[PARALLEL] Spawning workers at {time.strftime('%H:%M:%S')}")
        
        # Submit tasks
        start_pureadio = time.time()
        future_pureadio = executor.submit(pureadio.run, AUDIO_FILE)
        
        start_situeval = time.time()
        future_situeval = executor.submit(situationeval.run, AUDIO_FILE)
        
        start_caption = time.time()
        future_caption  = executor.submit(captioner.run, AUDIO_FILE)

        # Collect results
        try:
            print("[PARALLEL] Waiting for all AI services to complete...")
            res_pureadio = future_pureadio.result() or {}
            print(f"[PARALLEL] pureadio finished in {time.time() - start_pureadio:.2f}s")
            
            res_situeval = future_situeval.result() or {}
            print(f"[PARALLEL] situationeval finished in {time.time() - start_situeval:.2f}s")
            
            res_caption  = future_caption.result() or {}
            print(f"[PARALLEL] captioner finished in {time.time() - start_caption:.2f}s")
            
            print(f"[DEBUG] res_pureadio keys: {list(res_pureadio.keys())}")
            print(f"[DEBUG] res_situeval keys: {list(res_situeval.keys())}")
            print(f"[DEBUG] res_caption keys: {list(res_caption.keys())}")

        except Exception as e:
            import traceback
            print(f"\n[ERROR] One or more AI services failed: {e}")
            traceback.print_exc()
            return

    parallel_time = time.time() - start_time
    print(f"\n[PARALLEL] All AI services finished in {parallel_time:.2f}s")

    # Step 2: Prepare enriched context for Triage
    # Format stt_result to match what stt_triage expects
    raw_tx = res_pureadio.get("raw_transcript") or ""
    stt_result = {
        "transcript": res_pureadio.get("translation") or "NO_TRANSLATION",
        "confidence": 0.8, 
        "language_detected": language,
        "silence_detected": "SILENCE_DETECTED" in raw_tx
    }

    # Step 3: Run Enriched Triage
    print("\n[TRIAGE] Running final urgency classification with enriched context...")
    triage_result = stt_triage.run_triage(
        transcript=stt_result["transcript"],
        stt_confidence=stt_result["confidence"],
        protocol=triage_protocol,
        situation_eval=res_situeval,
        caption=res_caption
    )

    # Step 4: Display Summary
    stt_triage.print_summary(stt_result, triage_result)

    # Step 5: Save to Supabase
    print("\n[DB] Saving enriched results to Supabase...")
    stt_triage.save_to_supabase(
        user_id=USER_ID,
        audio_file=AUDIO_FILE,
        stt_result=stt_result,
        triage_result=triage_result,
        situation_eval=res_situeval,
        caption=res_caption
    )

    total_time = time.time() - start_time
    print(f"\n✅ Pipeline complete in {total_time:.2f}s.")


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n[ABORT] Pipeline stopped by user.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline crashed: {e}")
