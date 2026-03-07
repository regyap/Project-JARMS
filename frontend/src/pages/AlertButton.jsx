import { useState, useRef, useEffect } from "react";

const STATUS = {
  IDLE: "idle",
  RECORDING: "recording",
  SENDING: "sending",
  SUCCESS: "success",
  ERROR: "error",
};

const fmt = (s) =>
  `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

// Soft dark palette
const C = {
  bg: "#16181D", // page background
  surface: "#1E2028", // card surface
  border: "#2C2F3A", // subtle borders
  borderSoft: "#252830", // very soft dividers
  textPrimary: "#E8EAF0", // headings
  textSecondary: "#8B90A0", // labels
  textMuted: "#545868", // timestamps
  accent: "#E55A5A", // red — softened from pure #DC2626
  amber: "#D4883A", // amber
  green: "#3EA876", // green
};

export default function AlertButton() {
  const [status, setStatus] = useState(STATUS.IDLE);
  const [seconds, setSeconds] = useState(0);
  const [log, setLog] = useState([]);
  const [audioURL, setAudioURL] = useState(null);
  const [buttonId, setButtonId] = useState("BTN-1001");

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const fileInputRef = useRef(null);

  const [beneficiaries, setBeneficiaries] = useState([]);
  const [selectedBeneficiary, setSelectedBeneficiary] = useState(null);

  useEffect(() => {
    async function loadBeneficiaries() {
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL}/beneficiaries`,
        );
        const data = await res.json();
        setBeneficiaries(data.items || []);
        if (data.items?.length) {
          setButtonId(data.items[0].button_id);
          setSelectedBeneficiary(data.items[0]);
        }
      } catch (err) {
        console.error(err);
      }
    }
    loadBeneficiaries();
  }, []);

  useEffect(
    () => () => {
      clearInterval(timerRef.current);
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop());
      if (audioURL) URL.revokeObjectURL(audioURL);
    },
    [audioURL],
  );

  const addLog = (msg, type = "info") =>
    setLog((prev) =>
      [{ msg, type, ts: new Date().toLocaleTimeString() }, ...prev].slice(
        0,
        20,
      ),
    );

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleRecordingStop;
      recorder.start(100);
      mediaRecorderRef.current = recorder;
      setStatus(STATUS.RECORDING);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
      addLog("Recording started — microphone active", "record");
    } catch (err) {
      addLog(`Microphone access denied: ${err.message}`, "error");
      setStatus(STATUS.ERROR);
    }
  }

  function stopRecording() {
    clearInterval(timerRef.current);
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop());
  }

  async function handleRecordingStop() {
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    setAudioURL(URL.createObjectURL(blob));
    addLog(
      `Recording captured — ${(blob.size / 1024).toFixed(1)} KB`,
      "success",
    );
    await submitAudioBlob(blob, `alert-${Date.now()}.webm`);
  }

  async function submitAudioBlob(blob, filename) {
    setStatus(STATUS.SENDING);
    addLog("Uploading audio + creating case…", "info");
    try {
      const result = await sendAlertAudio(blob, buttonId, filename);
      setStatus(STATUS.SUCCESS);
      addLog(`Case created: ${result.case?.case_id ?? "ok"}`, "success");
    } catch (err) {
      setStatus(STATUS.ERROR);
      addLog(`Send failed: ${err.message}`, "error");
    }
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      if (audioURL) URL.revokeObjectURL(audioURL);
      setAudioURL(URL.createObjectURL(file));
      addLog(
        `Audio file selected — ${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
        "info",
      );
      await submitAudioBlob(file, file.name);
    } finally {
      e.target.value = "";
    }
  }

  function handlePress() {
    if ([STATUS.IDLE, STATUS.SUCCESS, STATUS.ERROR].includes(status)) {
      if (audioURL) URL.revokeObjectURL(audioURL);
      setAudioURL(null);
      startRecording();
    } else if (status === STATUS.RECORDING) {
      stopRecording();
    }
  }

  function handleReset() {
    setStatus(STATUS.IDLE);
    setSeconds(0);
    if (audioURL) URL.revokeObjectURL(audioURL);
    setAudioURL(null);
    setLog([]);
  }

  const btnConfig = {
    idle: {
      bg: "#2C2F3A",
      color: C.textPrimary,
      label: "HOLD TO ALERT",
      icon: "🛡",
    },
    recording: {
      bg: C.accent,
      color: "#fff",
      label: `RECORDING ${fmt(seconds)}`,
      icon: "■",
    },
    sending: { bg: C.amber, color: "#fff", label: "SENDING…", icon: "↑" },
    success: { bg: C.green, color: "#fff", label: "SENT", icon: "✓" },
    error: { bg: C.accent, color: "#fff", label: "FAILED — RETRY", icon: "✕" },
  }[status];

  const logColors = {
    info: C.textSecondary,
    record: C.accent,
    success: C.green,
    error: C.accent,
  };

  const uploadDisabled =
    status === STATUS.RECORDING || status === STATUS.SENDING;

  const card = {
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 10,
  };

  const sectionLabel = {
    fontSize: 10,
    fontWeight: 700,
    color: C.textSecondary,
    letterSpacing: "0.09em",
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh" }}>
      <div
        className="page-container"
        style={{ fontFamily: "'DM Mono', 'Courier New', monospace" }}
      >
        <div style={{ maxWidth: 440, margin: "0 auto" }}>
          {/* Page title */}
          <div style={{ marginBottom: 24 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.12em",
                color: C.textSecondary,
                border: `1px solid ${C.border}`,
                borderRadius: 20,
                padding: "3px 10px",
              }}
            >
              PERSONAL ALERT
            </span>
            <h1
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: C.textPrimary,
                margin: "10px 0 4px",
                letterSpacing: "-0.02em",
              }}
            >
              Send an Alert
            </h1>
            <p style={{ fontSize: 12, color: C.textSecondary, margin: 0 }}>
              Select a beneficiary, then record or upload audio.
            </p>
          </div>

          {/* Beneficiary card */}
          <div style={{ ...card, overflow: "hidden", marginBottom: 20 }}>
            <div
              style={{
                padding: "10px 14px",
                borderBottom: `1px solid ${C.borderSoft}`,
              }}
            >
              <span style={sectionLabel}>BENEFICIARY</span>
            </div>
            <div style={{ padding: "12px 14px" }}>
              <select
                value={buttonId}
                onChange={(e) => {
                  const sel = beneficiaries.find(
                    (b) => b.button_id === e.target.value,
                  );
                  setButtonId(e.target.value);
                  setSelectedBeneficiary(sel);
                }}
                disabled={uploadDisabled}
                style={{
                  width: "100%",
                  border: `1px solid ${C.border}`,
                  borderRadius: 7,
                  padding: "9px 10px",
                  fontFamily: "inherit",
                  fontSize: 12,
                  color: C.textPrimary,
                  background: C.bg,
                  marginBottom: selectedBeneficiary ? 14 : 0,
                  cursor: uploadDisabled ? "default" : "pointer",
                }}
              >
                {beneficiaries.map((b) => (
                  <option key={b.button_id} value={b.button_id}>
                    {b.full_name} ({b.button_id})
                  </option>
                ))}
              </select>

              {selectedBeneficiary && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "10px 20px",
                  }}
                >
                  {[
                    ["NRIC", selectedBeneficiary.nric],
                    ["Language", selectedBeneficiary.primary_language],
                    ["Phone", selectedBeneficiary.phone_number],
                    [
                      "Emergency",
                      `${selectedBeneficiary.emergency_contact_name} (${selectedBeneficiary.emergency_contact})`,
                    ],
                    [
                      "Address",
                      `${selectedBeneficiary.address} ${selectedBeneficiary.unit_number}`,
                      true,
                    ],
                    [
                      "Medical",
                      selectedBeneficiary.patient_medical_summary,
                      true,
                    ],
                  ].map(([label, value, full]) => (
                    <div
                      key={label}
                      style={{ gridColumn: full ? "1 / -1" : undefined }}
                    >
                      <div
                        style={{
                          ...sectionLabel,
                          fontSize: 9,
                          marginBottom: 2,
                        }}
                      >
                        {label}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: C.textPrimary,
                          lineHeight: 1.5,
                        }}
                      >
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Record button */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginBottom: 20,
              position: "relative",
              height: 160,
            }}
          >
            {status === STATUS.RECORDING && (
              <>
                <div
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%,-50%)",
                    width: 160,
                    height: 160,
                    borderRadius: "50%",
                    border: `2px solid ${C.accent}`,
                    opacity: 0.25,
                    animation: "ripple 1.5s ease-out infinite",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%,-50%)",
                    width: 160,
                    height: 160,
                    borderRadius: "50%",
                    border: `2px solid ${C.accent}`,
                    opacity: 0.1,
                    animation: "ripple 1.5s ease-out infinite 0.6s",
                  }}
                />
              </>
            )}
            <button
              onClick={handlePress}
              disabled={status === STATUS.SENDING}
              style={{
                width: 130,
                height: 130,
                borderRadius: "50%",
                background: btnConfig.bg,
                color: btnConfig.color,
                border: "none",
                cursor: status === STATUS.SENDING ? "default" : "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 5,
                boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
                transition: "background 0.2s, transform 0.1s",
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%,-50%)",
                zIndex: 1,
              }}
              onMouseDown={(e) =>
                (e.currentTarget.style.transform =
                  "translate(-50%,-50%) scale(0.96)")
              }
              onMouseUp={(e) =>
                (e.currentTarget.style.transform =
                  "translate(-50%,-50%) scale(1)")
              }
            >
              <span style={{ fontSize: 20 }}>{btnConfig.icon}</span>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textAlign: "center",
                  lineHeight: 1.4,
                }}
              >
                {btnConfig.label}
              </span>
            </button>
          </div>

          {/* Upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,.webm,.wav,.mp3,.m4a,.ogg"
            onChange={handleFileUpload}
            style={{ display: "none" }}
          />
          <button
            type="button"
            disabled={uploadDisabled}
            onClick={() => fileInputRef.current?.click()}
            style={{
              width: "100%",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: "10px 12px",
              marginBottom: 20,
              background: "transparent",
              color: uploadDisabled ? C.textMuted : C.textSecondary,
              fontFamily: "inherit",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              cursor: uploadDisabled ? "default" : "pointer",
              transition: "border-color 0.15s, color 0.15s",
            }}
          >
            ↑ UPLOAD AUDIO FILE
          </button>

          {/* Playback */}
          {audioURL && (
            <div style={{ ...card, padding: "12px 14px", marginBottom: 16 }}>
              <p style={{ ...sectionLabel, margin: "0 0 8px" }}>
                CAPTURED AUDIO
              </p>
              <audio
                controls
                src={audioURL}
                style={{ width: "100%", height: 32 }}
              />
            </div>
          )}

          {/* Log */}
          {log.length > 0 && (
            <div style={{ ...card, overflow: "hidden" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderBottom: `1px solid ${C.borderSoft}`,
                }}
              >
                <span style={sectionLabel}>TRANSMISSION LOG</span>
                <button
                  onClick={handleReset}
                  style={{
                    fontSize: 10,
                    color: C.textMuted,
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    fontFamily: "inherit",
                  }}
                >
                  clear
                </button>
              </div>
              <ul
                style={{
                  listStyle: "none",
                  margin: 0,
                  padding: 0,
                  maxHeight: 160,
                  overflowY: "auto",
                }}
              >
                {log.map((entry, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      gap: 10,
                      padding: "8px 14px",
                      borderBottom: `1px solid ${C.borderSoft}`,
                      fontSize: 11,
                    }}
                  >
                    <span style={{ color: C.textMuted, flexShrink: 0 }}>
                      {entry.ts}
                    </span>
                    <span
                      style={{ color: logColors[entry.type] || C.textPrimary }}
                    >
                      {entry.msg}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <style>{`
          @keyframes ripple {
            0%   { transform: translate(-50%,-50%) scale(1); opacity: 0.4; }
            100% { transform: translate(-50%,-50%) scale(1.6); opacity: 0; }
          }
        `}</style>
      </div>
    </div>
  );
}

async function sendAlertAudio(
  blob,
  buttonId,
  filename = `alert-${Date.now()}.webm`,
) {
  const formData = new FormData();
  formData.append("button_id", buttonId);
  formData.append("audio", blob, filename);
  const res = await fetch(`${import.meta.env.VITE_API_URL}/cases/audio`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}
