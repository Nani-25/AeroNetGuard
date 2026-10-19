/**
 * AeroNetGuard Main Application Controller
 */

let canvasInstance = null;
let currentSimulationData = null;
let currentStepIndex = 0;
let autoPlayTimer = null;

document.addEventListener("DOMContentLoaded", () => {
    canvasInstance = new NetworkCanvas("networkCanvas");
    window.addEventListener("resize", () => canvasInstance && canvasInstance.resize());

    // Event Listeners for Simulation Controls
    const runBtn = document.getElementById("runSimulationBtn");
    if (runBtn) runBtn.addEventListener("click", handleRunSimulation);

    const playBtn = document.getElementById("playBtn");
    if (playBtn) playBtn.addEventListener("click", toggleAutoPlay);

    const stepBtn = document.getElementById("stepBtn");
    if (stepBtn) stepBtn.addEventListener("click", stepForward);

    const resetBtn = document.getElementById("resetBtn");
    if (resetBtn) resetBtn.addEventListener("click", resetSimulation);

    const pcapBtn = document.getElementById("downloadPcapBtn");
    if (pcapBtn) pcapBtn.addEventListener("click", downloadPcapCapture);
});

async function handleRunSimulation() {
    const source = document.getElementById("sourceNode")?.value || "Control Tower";
    const destination = document.getElementById("destNode")?.value || "Baggage";
    const windowSize = parseInt(document.getElementById("windowSize")?.value || "4");
    const lossRate = parseFloat(document.getElementById("lossRate")?.value || "0.0");
    const corruptionRate = parseFloat(document.getElementById("corruptionRate")?.value || "0.0");
    const allowEmergency = document.getElementById("allowEmergency")?.checked || false;

    const payloadText = document.getElementById("payloadInput")?.value || "Clearance Data 01\nFlight Manifest 02";
    const payloads = payloadText.split("\n").filter(p => p.trim().length > 0);

    const requestBody = {
        source: source,
        destination: destination,
        payloads: payloads,
        window_size: windowSize,
        loss_rate: lossRate,
        corruption_rate: corruptionRate,
        allow_emergency_transit: allowEmergency
    };

    try {
        const response = await fetch("/api/simulation/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const err = await response.json();
            alert("Simulation Error: " + (err.error || "Execution failed"));
            return;
        }

        currentSimulationData = await response.json();
        currentStepIndex = 0;
        
        // Update Canvas Route
        if (canvasInstance) {
            canvasInstance.setActiveRoute(currentSimulationData.route);
        }

        // Render Telemetry & Reset Terminal
        renderTelemetry(currentSimulationData);
        resetSimulation();
        updateStepUI();

    } catch (e) {
        console.error("Simulation request error:", e);
        alert("Failed to connect to backend server.");
    }
}

function updateStepUI() {
    if (!currentSimulationData || !currentSimulationData.event_logs) return;

    const logs = currentSimulationData.event_logs;
    if (currentStepIndex >= logs.length) {
        pauseAutoPlay();
        return;
    }

    const currentLog = logs[currentStepIndex];
    appendTerminalLine(currentLog);
    renderSlidingWindow(currentLog.window_state);

    // Animate canvas packet if frame is transmitting
    if (currentLog.event === "FRAME_TRANSMITTING" && canvasInstance) {
        let status = "normal";
        // Look ahead for outcome
        if (currentStepIndex + 1 < logs.length) {
            const nextLog = logs[currentStepIndex + 1];
            if (nextLog.event === "FRAME_DROPPED") status = "dropped";
            else if (nextLog.event === "FRAME_CORRUPTED") status = "corrupted";
        }
        canvasInstance.animatePacket(currentLog.node, currentLog.next_node, status);
    }
}

function stepForward() {
    if (!currentSimulationData) return;
    if (currentStepIndex < currentSimulationData.event_logs.length) {
        updateStepUI();
        currentStepIndex++;
    }
}

function toggleAutoPlay() {
    if (autoPlayTimer) {
        pauseAutoPlay();
    } else {
        const playBtn = document.getElementById("playBtn");
        if (playBtn) playBtn.textContent = "⏸️ Pause";
        autoPlayTimer = setInterval(() => {
            if (currentStepIndex >= currentSimulationData?.event_logs?.length) {
                pauseAutoPlay();
            } else {
                stepForward();
            }
        }, 800);
    }
}

function pauseAutoPlay() {
    if (autoPlayTimer) {
        clearInterval(autoPlayTimer);
        autoPlayTimer = null;
    }
    const playBtn = document.getElementById("playBtn");
    if (playBtn) playBtn.textContent = "▶️ Play";
}

function resetSimulation() {
    pauseAutoPlay();
    currentStepIndex = 0;
    const term = document.getElementById("terminalLog");
    if (term) term.innerHTML = `<div class="terminal-line ROUTE">> Simulator Initialized. Press Play or Step to observe telemetry.</div>`;
    const winContainer = document.getElementById("windowVisualizer");
    if (winContainer) winContainer.innerHTML = "";
}

function appendTerminalLine(log) {
    const term = document.getElementById("terminalLog");
    if (!term) return;

    const line = document.createElement("div");
    line.className = `terminal-line ${log.event.replace("FRAME_", "")}`;
    line.textContent = `[Step ${log.step}] [${log.event}] ${log.description}`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
}

function renderSlidingWindow(windowState) {
    const container = document.getElementById("windowVisualizer");
    if (!container || !windowState) return;

    container.innerHTML = "";
    const size = windowState.window_size || 4;
    const sendBase = windowState.send_base || 0;
    const nextSeq = windowState.next_seq_num || 0;

    for (let i = 0; i < size + 2; i++) {
        const slot = document.createElement("div");
        slot.className = "window-slot";
        
        const isInWindow = i >= sendBase && i < sendBase + size;
        const isSent = i >= sendBase && i < nextSeq;
        
        if (isInWindow) slot.classList.add("in-window");
        if (i < sendBase) slot.classList.add("acked");

        slot.innerHTML = `
            <div>Seq ${i}</div>
            <div style="font-size:0.7rem; color:var(--text-muted);">${i < sendBase ? "ACKED" : isSent ? "IN-FLIGHT" : "BUFFER"}</div>
        `;
        container.appendChild(slot);
    }
}

function renderTelemetry(data) {
    const pdrEl = document.getElementById("pdrVal");
    if (pdrEl) pdrEl.textContent = `${data.packet_delivery_ratio}%`;

    const crcEl = document.getElementById("crcPassVal");
    if (crcEl) crcEl.textContent = `${data.crc_pass_rate}%`;

    const retransEl = document.getElementById("retransVal");
    if (retransEl) retransEl.textContent = data.total_retransmissions;

    const routeEl = document.getElementById("routeText");
    if (routeEl) routeEl.textContent = data.route.join(" ➔ ");
}

async function downloadPcapCapture() {
    if (!currentSimulationData || !currentSimulationData.event_logs) {
        alert("Run a simulation first to export PCAP packet capture data.");
        return;
    }

    try {
        const response = await fetch("/api/simulation/pcap", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event_logs: currentSimulationData.event_logs })
        });

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "aeronetguard_simulation.pcap";
        document.body.appendChild(a);
        a.click();
        a.remove();
    } catch (e) {
        console.error("PCAP download error:", e);
        alert("Failed to export PCAP file.");
    }
}
