/**
 * AeroNetGuard - Dedicated Simulation Page Controller (Step 12)
 *
 * Implements live discrete-event playback timeline synchronization:
 * Pause, Resume, Reset, Speed control, live progress bar, current event banner,
 * frame table row updates, and terminal event log.
 */

// Fixed Source Node Constant
const FIXED_SOURCE = "Control Tower";

// API Helpers
async function apiGet(url) {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok || data.success === false) {
        throw new Error(data.error || `HTTP error ${res.status}`);
    }
    return data;
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.success === false) {
        throw new Error(data.error || `HTTP error ${res.status}`);
    }
    return data;
}

function showAlert(message, type = "error") {
    const banner = document.getElementById("alertBanner");
    if (!banner) return;
    banner.className = `alert-banner active alert-${type}`;
    banner.textContent = message;
    banner.style.display = "flex";
    setTimeout(() => { banner.style.display = "none"; }, 5000);
}

class DedicatedSimulationPlayer {
    constructor() {
        this.state = "idle";
        this.speed = 1.0;
        this.events = [];
        this.route = [];
        this.frames = [];
        this.currentIndex = 0;
        this.resumeCallback = null;
        this.simStartTime = null;
        this.retransmissionCount = 0;
    }

    setSpeed(speedVal) {
        this.speed = Math.max(0.2, parseFloat(speedVal) || 1.0);
    }

    async start(simResult) {
        this.stop();

        this.events = simResult.events || [];
        this.route = simResult.route || [];
        this.frames = simResult.frames || [];
        this.currentIndex = 0;
        this.state = "playing";
        this.simStartTime = Date.now();
        this.retransmissionCount = 0;

        this.updateButtons("playing");
        this.initializeFramesTable(this.frames);
        this.clearEventLog();
        this.updateProgress(0, this.events.length);
        this.setBanner("Initializing simulation event timeline...", "normal", "INIT");

        try {
            await this.playTimeline();
        } catch (err) {
            if (err.message !== "ANIMATION_STOPPED") {
                console.error("Simulation animation error:", err);
            }
        }
    }

    pause() {
        if (this.state === "playing") {
            this.state = "paused";
            this.updateButtons("paused");
            this.setBanner("Simulation PAUSED by user", "normal", "PAUSED");
        }
    }

    resume() {
        if (this.state === "paused") {
            this.state = "playing";
            this.updateButtons("playing");
            this.setBanner("Resuming simulation playback...", "normal", "PLAYING");
            if (this.resumeCallback) {
                const cb = this.resumeCallback;
                this.resumeCallback = null;
                cb();
            }
        }
    }

    stop() {
        this.state = "stopped";
        if (this.resumeCallback) {
            this.resumeCallback = null;
        }
        this.updateButtons("idle");
    }

    updateButtons(status) {
        const startBtn = document.getElementById("simStartBtn");
        const pauseBtn = document.getElementById("simPauseBtn");
        const resumeBtn = document.getElementById("simResumeBtn");
        const resetBtn = document.getElementById("simResetBtn");

        if (status === "playing") {
            if (startBtn) startBtn.style.display = "none";
            if (pauseBtn) { pauseBtn.style.display = "inline-flex"; pauseBtn.disabled = false; }
            if (resumeBtn) resumeBtn.style.display = "none";
            if (resetBtn) resetBtn.disabled = false;
        } else if (status === "paused") {
            if (startBtn) startBtn.style.display = "none";
            if (pauseBtn) pauseBtn.style.display = "none";
            if (resumeBtn) { resumeBtn.style.display = "inline-flex"; resumeBtn.disabled = false; }
            if (resetBtn) resetBtn.disabled = false;
        } else {
            if (startBtn) {
                startBtn.style.display = "inline-flex";
                startBtn.disabled = false;
                startBtn.innerHTML = `<span>⚡ Start Simulation</span>`;
            }
            if (pauseBtn) pauseBtn.style.display = "none";
            if (resumeBtn) resumeBtn.style.display = "none";
            if (resetBtn) resetBtn.disabled = false;
        }
    }

    async delay(ms) {
        if (this.state === "stopped") throw new Error("ANIMATION_STOPPED");

        const adjustedMs = ms / this.speed;
        let remaining = adjustedMs;
        const interval = 50;

        while (remaining > 0) {
            if (this.state === "stopped") throw new Error("ANIMATION_STOPPED");

            if (this.state === "paused") {
                await new Promise((resolve) => {
                    this.resumeCallback = resolve;
                });
                if (this.state === "stopped") throw new Error("ANIMATION_STOPPED");
            }

            const step = Math.min(interval, remaining);
            await new Promise((res) => setTimeout(res, step));
            remaining -= step;
        }
    }

    async playTimeline() {
        for (let i = 0; i < this.events.length; i++) {
            if (this.state === "stopped") throw new Error("ANIMATION_STOPPED");

            this.currentIndex = i;
            const evt = this.events[i];

            this.updateProgress(i + 1, this.events.length);
            this.appendLiveEventLog(evt);

            await this.dispatchLiveEvent(evt);
        }

        this.state = "idle";
        this.updateButtons("idle");
        this.updateProgress(this.events.length, this.events.length);
    }

    async dispatchLiveEvent(evt) {
        switch (evt.event) {
            case "routing":
                this.setBanner(`Route Computed: ${evt.route.join(" ➔ ")} (Cost: ${evt.route_cost}, Hops: ${evt.hop_count})`, "normal", "ROUTING");
                const routeText = document.getElementById("simRouteText");
                if (routeText) routeText.textContent = evt.route.join(" ➔ ");
                await this.delay(400);
                break;
            case "packet_created":
                this.setBanner(`Packet Created: [${evt.packet_id.substring(0, 8)}] "${evt.payload}"`, "normal", "PACKET");
                await this.delay(300);
                break;
            case "frame_created":
                this.setBanner(`Framing: Tokenized Frame F${evt.sequence_number}: "${evt.payload}"`, "normal", "FRAMING");
                this.updateFrameRow(evt.sequence_number, {
                    payload: evt.payload,
                    status: "created",
                    statusClass: "badge-muted",
                });
                await this.delay(200);
                break;
            case "crc_calculated":
                this.setBanner(`CRC Generator: Frame F${evt.sequence_number} CRC-8 = 0x${evt.crc.toString(16).toUpperCase()}`, "normal", "CRC-8");
                this.updateFrameRow(evt.sequence_number, {
                    crc: `0x${evt.crc.toString(16).toUpperCase().padStart(2, '0')}`,
                    crcStatus: "computed",
                    crcClass: "badge-accent",
                });
                await this.delay(150);
                break;
            case "transmission":
                const isFailed = evt.status === "failed";
                this.setBanner(`Transmitting Frame F${evt.sequence_number}...`, "normal", "TX");
                this.highlightFrameRow(evt.sequence_number, "row-transmitting");
                this.updateFrameRow(evt.sequence_number, { status: "transmitting", statusClass: "badge-accent" });
                await this.delay(450);
                if (isFailed) {
                    this.setBanner(`Frame F${evt.sequence_number} Transmission Failed!`, "error", "FAIL");
                }
                this.unhighlightFrameRow(evt.sequence_number, "row-transmitting");
                break;
            case "crc_verification":
                this.setBanner(`Receiver CRC Check: Frame F${evt.sequence_number} CRC ${evt.is_valid ? "VALID ✓" : "INVALID ✗"}`, evt.is_valid ? "success" : "error", "CRC-CHK");
                this.updateFrameRow(evt.sequence_number, {
                    crcStatus: evt.is_valid ? "valid" : "invalid",
                    crcClass: evt.is_valid ? "badge-success" : "badge-danger",
                });
                await this.delay(250);
                break;
            case "failure":
                this.setBanner(`Frame F${evt.sequence_number} FAILED (${evt.reason || "packet_loss"})`, "error", "FAILURE");
                this.updateFrameRow(evt.sequence_number, {
                    status: "failed",
                    statusClass: "badge-danger",
                });
                this.highlightFrameRow(evt.sequence_number, "row-failed");
                await this.delay(350);
                break;
            case "acknowledgement":
                this.setBanner(`ACK Received for Frame F${evt.sequence_number}`, "success", "ACK");
                this.unhighlightFrameRow(evt.sequence_number, "row-failed");
                this.unhighlightFrameRow(evt.sequence_number, "frame-retransmission");
                this.highlightFrameRow(evt.sequence_number, "row-acknowledged");
                this.updateFrameRow(evt.sequence_number, {
                    status: "acknowledged",
                    statusClass: "badge-success",
                });
                await this.delay(300);
                break;
            case "retransmission":
                this.retransmissionCount++;
                const attempt = evt.attempt || 1;
                this.setBanner(`Go-Back-N Retransmitting Frame F${evt.sequence_number} (Attempt #${attempt})`, "retrans", "GBN-RETX");
                const retransEl = document.getElementById("simRetransCount");
                if (retransEl) retransEl.textContent = this.retransmissionCount;
                this.highlightFrameRow(evt.sequence_number, "frame-retransmission");
                this.updateFrameRow(evt.sequence_number, {
                    status: "retransmitting",
                    statusClass: "badge-warning",
                    retransCount: attempt,
                });
                await this.delay(400);
                break;
            case "discarded_out_of_order":
                this.setBanner(`Frame F${evt.sequence_number} Discarded (Out of order)`, "error", "DISCARD");
                this.updateFrameRow(evt.sequence_number, {
                    status: "discarded",
                    statusClass: "badge-danger",
                });
                await this.delay(250);
                break;
            case "delivery":
                this.setBanner("✓ MESSAGE DELIVERED — All frames delivered successfully", "success", "DELIVERED");
                const statusBadge = document.getElementById("simStatusBadge");
                if (statusBadge) {
                    statusBadge.className = "badge badge-success";
                    statusBadge.textContent = "DELIVERED";
                }
                await this.delay(500);
                break;
            default:
                await this.delay(200);
        }
    }

    setBanner(text, style = "normal", badge = "EVENT") {
        const banner = document.getElementById("simCurrentEventBanner");
        const textEl = document.getElementById("simCurrentEventText");
        const badgeEl = document.getElementById("simCurrentEventBadge");

        if (banner) {
            banner.className = `current-event-banner ${style !== 'normal' ? style : ''}`;
        }
        if (textEl) textEl.textContent = text;
        if (badgeEl) {
            badgeEl.textContent = badge;
            if (style === "error") badgeEl.className = "badge badge-danger";
            else if (style === "success") badgeEl.className = "badge badge-success";
            else if (style === "retrans") badgeEl.className = "badge badge-warning";
            else badgeEl.className = "badge badge-accent";
        }
    }

    updateProgress(current, total) {
        const fill = document.getElementById("simProgressFill");
        const label = document.getElementById("simProgressText");
        if (!total || total === 0) return;

        const percent = Math.min(100, Math.round((current / total) * 100));
        if (fill) fill.style.width = `${percent}%`;
        if (label) label.textContent = `${percent}%`;
    }

    initializeFramesTable(frames) {
        const tbody = document.getElementById("simFramesBody");
        const emptyState = document.getElementById("simFramesEmpty");
        if (!tbody) return;

        tbody.innerHTML = "";
        if (!frames || frames.length === 0) {
            if (emptyState) emptyState.style.display = "block";
            return;
        }

        if (emptyState) emptyState.style.display = "none";

        frames.forEach(frame => {
            const tr = document.createElement("tr");
            tr.setAttribute("id", `sim-frame-row-${frame.sequence_number}`);
            tr.innerHTML = `
                <td><strong>F${frame.sequence_number}</strong></td>
                <td class="col-payload"><code>${escapeHtml(frame.payload)}</code></td>
                <td class="col-crc"><code>--</code></td>
                <td class="col-crc-status"><span class="badge badge-muted">pending</span></td>
                <td class="col-status"><span class="badge badge-muted">created</span></td>
                <td class="col-retrans">0</td>
            `;
            tbody.appendChild(tr);
        });
    }

    updateFrameRow(seq, data) {
        const row = document.getElementById(`sim-frame-row-${seq}`);
        if (!row) return;

        if (data.payload !== undefined) {
            const el = row.querySelector(".col-payload code");
            if (el) el.textContent = data.payload;
        }
        if (data.crc !== undefined) {
            const el = row.querySelector(".col-crc code");
            if (el) el.textContent = data.crc;
        }
        if (data.crcStatus !== undefined) {
            const el = row.querySelector(".col-crc-status");
            if (el) el.innerHTML = `<span class="badge ${data.crcClass || 'badge-muted'}">${data.crcStatus}</span>`;
        }
        if (data.status !== undefined) {
            const el = row.querySelector(".col-status");
            if (el) el.innerHTML = `<span class="badge ${data.statusClass || 'badge-accent'}">${data.status}</span>`;
        }
        if (data.retransCount !== undefined) {
            const el = row.querySelector(".col-retrans");
            if (el) el.textContent = data.retransCount;
        }
    }

    highlightFrameRow(seq, className) {
        const row = document.getElementById(`sim-frame-row-${seq}`);
        if (row) row.classList.add(className);
    }

    unhighlightFrameRow(seq, className) {
        const row = document.getElementById(`sim-frame-row-${seq}`);
        if (row) row.classList.remove(className);
    }

    clearEventLog() {
        const container = document.getElementById("simEventLog");
        if (container) container.innerHTML = "";
    }

    appendLiveEventLog(evt) {
        const container = document.getElementById("simEventLog");
        if (!container) return;

        const row = document.createElement("div");
        row.className = "log-entry";

        let tagClass = "tag-tx";
        let tagText = `[${evt.event.toUpperCase()}]`;

        switch (evt.event) {
            case "routing": tagClass = "tag-routing"; tagText = "[ROUTING]"; break;
            case "packet_created": tagClass = "tag-packet"; tagText = "[PACKET]"; break;
            case "frame_created": tagClass = "tag-framing"; tagText = "[FRAMING]"; break;
            case "crc_calculated": tagClass = "tag-crc"; tagText = "[CRC-GEN]"; break;
            case "crc_verification": tagClass = "tag-crc"; tagText = "[CRC-CHK]"; break;
            case "transmission": tagClass = evt.status === "failed" ? "tag-fail" : "tag-tx"; tagText = "[TX]"; break;
            case "failure": tagClass = "tag-fail"; tagText = "[FAIL]"; break;
            case "retransmission": tagClass = "tag-gbn"; tagText = "[GBN-RETRY]"; break;
            case "acknowledgement": tagClass = "tag-ack"; tagText = "[ACK]"; break;
            case "out_of_order_discard":
            case "discarded_out_of_order": tagClass = "tag-fail"; tagText = "[DISCARD]"; break;
            case "delivery": tagClass = "tag-delivery"; tagText = "[DELIVERY]"; break;
        }

        const elapsedSec = Math.floor((Date.now() - this.simStartTime) / 1000);
        const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
        const secs = String(elapsedSec % 60).padStart(2, '0');
        const timestamp = `[${mins}:${secs}]`;

        const msgText = formatEventMessage(evt);

        row.innerHTML = `
            <span style="color:var(--text-dim); margin-right:0.35rem; font-size:0.75rem;">${timestamp}</span>
            <span class="log-tag ${tagClass}">${tagText}</span>
            <span class="log-msg">${escapeHtml(msgText)}</span>
        `;
        container.appendChild(row);
        container.scrollTop = container.scrollHeight;
    }
}

const simPlayer = new DedicatedSimulationPlayer();

document.addEventListener("DOMContentLoaded", async () => {
    setupMobileSidebar();
    await loadNodes();
    setupFormHandlers();
    await checkInitialState();
});

function setupMobileSidebar() {
    const toggleBtn = document.getElementById("sidebarToggleBtn");
    const sidebar = document.querySelector(".sidebar");
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });
    }
}

async function loadNodes() {
    try {
        const data = await apiGet("/api/network/nodes");
        const srcInput = document.getElementById("simSourceSelect");
        const dstSelect = document.getElementById("simDestSelect");

        if (srcInput) {
            srcInput.value = FIXED_SOURCE;
        }

        if (!dstSelect) return;
        dstSelect.innerHTML = "";

        // Allowed destinations: exclude FIXED_SOURCE ("Control Tower")
        data.nodes.filter(node => node !== FIXED_SOURCE).forEach(node => {
            dstSelect.add(new Option(node, node));
        });

        dstSelect.value = "Security";
    } catch (err) {
        console.error("Failed to load nodes:", err);
        showAlert("Failed to load airport nodes from server.");
    }
}

function setupFormHandlers() {
    const startBtn = document.getElementById("simStartBtn");
    const pauseBtn = document.getElementById("simPauseBtn");
    const resumeBtn = document.getElementById("simResumeBtn");
    const resetBtn = document.getElementById("simResetBtn");
    const speedSelect = document.getElementById("simSpeedSelect");

    if (startBtn) startBtn.addEventListener("click", handleStartSimulation);
    if (pauseBtn) pauseBtn.addEventListener("click", () => simPlayer.pause());
    if (resumeBtn) resumeBtn.addEventListener("click", () => simPlayer.resume());
    if (resetBtn) resetBtn.addEventListener("click", handleResetSimulation);

    if (speedSelect) {
        speedSelect.addEventListener("change", (e) => {
            simPlayer.setSpeed(e.target.value);
        });
    }
}

async function handleStartSimulation() {
    const startBtn = document.getElementById("simStartBtn");
    const src = FIXED_SOURCE;
    const dst = document.getElementById("simDestSelect").value;
    const msg = document.getElementById("simMessageInput").value;
    const windowSize = parseInt(document.getElementById("simWindowSizeInput").value, 10);
    const failSeqInput = document.getElementById("simFailureSequenceInput").value.trim();

    if (!msg || !msg.trim()) {
        showAlert("Message cannot be empty.");
        return;
    }

    let failureSequence = [];
    if (failSeqInput) {
        const parts = failSeqInput.split(",");
        for (const p of parts) {
            const val = parseInt(p.trim(), 10);
            if (isNaN(val) || val < 0) {
                showAlert("Failure sequence must contain positive integers separated by commas.");
                return;
            }
            failureSequence.push(val);
        }
    }

    startBtn.disabled = true;
    startBtn.innerHTML = `<span class="spinner"></span> Running Simulation...`;

    try {
        const payload = {
            source: FIXED_SOURCE,
            destination: dst,
            message: msg.trim(),
            window_size: windowSize || 3,
            failure_sequence: failureSequence,
        };

        const res = await apiPost("/api/simulation/run", payload);
        const sim = res.simulation;

        displayStaticSummary(sim);
        await simPlayer.start(sim);

    } catch (err) {
        console.error("Simulation run error:", err);
        showAlert(err.message || "Simulation execution failed.");
        startBtn.disabled = false;
        startBtn.innerHTML = `<span>⚡ Start Simulation</span>`;
    }
}

async function handleResetSimulation() {
    try {
        simPlayer.stop();
        await apiPost("/api/simulation/reset", {});
        clearResults();
        showAlert("Simulation reset successfully.", "info");
    } catch (err) {
        console.error("Reset error:", err);
        showAlert("Failed to reset simulation.");
    }
}

function displayStaticSummary(sim) {
    const resultCard = document.getElementById("simResultCard");
    const statusBadge = document.getElementById("simStatusBadge");
    const routeText = document.getElementById("simRouteText");
    const costEl = document.getElementById("simRouteCost");
    const hopsEl = document.getElementById("simHopCount");
    const framesEl = document.getElementById("simTotalFrames");
    const retransEl = document.getElementById("simRetransCount");

    if (resultCard) resultCard.style.display = "block";

    if (statusBadge) {
        statusBadge.className = "badge badge-accent";
        statusBadge.textContent = "RUNNING";
    }

    if (routeText && sim.route) {
        routeText.textContent = sim.route.join(" ➔ ");
    }

    if (costEl) costEl.textContent = sim.route_cost;
    if (hopsEl) hopsEl.textContent = sim.hop_count;
    if (framesEl) framesEl.textContent = sim.total_frames;
    if (retransEl) retransEl.textContent = 0;
}

function clearResults() {
    const resultCard = document.getElementById("simResultCard");
    const tbody = document.getElementById("simFramesBody");
    const emptyState = document.getElementById("simFramesEmpty");
    const container = document.getElementById("simEventLog");
    const fill = document.getElementById("simProgressFill");
    const label = document.getElementById("simProgressText");
    const banner = document.getElementById("simCurrentEventBanner");
    const textEl = document.getElementById("simCurrentEventText");
    const badgeEl = document.getElementById("simCurrentEventBadge");

    if (resultCard) resultCard.style.display = "none";
    if (tbody) tbody.innerHTML = "";
    if (emptyState) emptyState.style.display = "block";
    if (container) container.innerHTML = `<div class="empty-state">Simulation reset. Ready to run.</div>`;

    if (fill) fill.style.width = "0%";
    if (label) label.textContent = "0%";
    if (banner) banner.className = "current-event-banner";
    if (textEl) textEl.textContent = "IDLE — Ready to run simulation";
    if (badgeEl) { badgeEl.className = "badge badge-muted"; badgeEl.textContent = "READY"; }
}

async function checkInitialState() {
    try {
        const stateRes = await apiGet("/api/simulation/state");
        if (stateRes.state && stateRes.state.state !== "initialized") {
            const framesRes = await apiGet("/api/simulation/frames");
            const eventsRes = await apiGet("/api/simulation/events");

            simPlayer.initializeFramesTable(framesRes.frames);
            framesRes.frames.forEach(f => {
                simPlayer.updateFrameRow(f.sequence_number, {
                    payload: f.payload,
                    crc: (f.crc !== null && f.crc !== undefined) ? `0x${f.crc.toString(16).toUpperCase().padStart(2, '0')}` : '--',
                    crcStatus: f.crc_status,
                    crcClass: f.crc_status === 'valid' ? 'badge-success' : (f.crc_status === 'invalid' ? 'badge-danger' : 'badge-muted'),
                    status: f.status,
                    statusClass: f.status === 'acknowledged' ? 'badge-success' : (f.status === 'failed' ? 'badge-danger' : 'badge-accent'),
                    retransCount: f.retransmission_count,
                });
            });

            eventsRes.events.forEach(evt => simPlayer.appendLiveEventLog(evt));

            const resultCard = document.getElementById("simResultCard");
            if (resultCard) resultCard.style.display = "block";

            const routeText = document.getElementById("simRouteText");
            if (routeText && stateRes.state.route) {
                routeText.textContent = stateRes.state.route.join(" ➔ ");
            }
        }
    } catch (e) {
        // Initial blank launch
    }
}

function formatEventMessage(evt) {
    switch (evt.event) {
        case "routing":
            return `Calculated route: ${evt.route ? evt.route.join(" ➔ ") : ""} (Cost: ${evt.route_cost}, Hops: ${evt.hop_count})`;
        case "packet_created":
            return `Packet created [ID: ${evt.packet_id ? evt.packet_id.substring(0, 8) : "--"}] Payload: "${evt.payload}"`;
        case "frame_created":
            return `Frame F${evt.sequence_number} tokenized: "${evt.payload}"`;
        case "crc_calculated":
            return `Frame F${evt.sequence_number} CRC-8 computed: 0x${evt.crc.toString(16).toUpperCase()}`;
        case "crc_verification":
            return `Frame F${evt.sequence_number} CRC check: ${evt.is_valid ? "VALID" : "INVALID"}`;
        case "transmission":
            return `Frame F${evt.sequence_number} transmitted. Result: ${evt.status.toUpperCase()}`;
        case "failure":
            return `Frame F${evt.sequence_number} dropped or failed transmission (${evt.reason || 'loss'})`;
        case "retransmission":
            return `GBN retransmitted Frame F${evt.sequence_number} (Attempt #${evt.attempt})`;
        case "acknowledgement":
            return `Cumulative ACK received for Frame F${evt.sequence_number}`;
        case "out_of_order_discard":
        case "discarded_out_of_order":
            return `Frame F${evt.sequence_number} discarded by receiver (Out-of-order)`;
        case "delivery":
            return `All frames delivered. Packet delivery marked as COMPLETED.`;
        default:
            return JSON.stringify(evt);
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
