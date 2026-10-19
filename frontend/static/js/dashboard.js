/**
 * AeroNetGuard - Main Dashboard & Live Simulation Animation Engine (Step 12)
 *
 * Visualizes discrete-event simulation results using SVG, CSS classes,
 * and an event-driven requestAnimationFrame animation engine.
 *
 * Authoritative source of truth remains the Python backend simulation.
 */

// ============================================================================
// 1. Centralized Node Coordinates & Identifier Helpers
// ============================================================================
const FIXED_SOURCE = "Control Tower";

const NODE_COORDINATES = {
    "Control Tower": { x: 300, y: 70 },
    "Check-in": { x: 130, y: 190 },
    "Security": { x: 470, y: 190 },
    "Baggage": { x: 180, y: 330 },
    "Emergency Services": { x: 420, y: 330 },
};

function toNodeSlug(name) {
    return String(name).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function toNodeId(name) {
    return `node-${toNodeSlug(name)}`;
}

function toEdgeId(u, v) {
    const s1 = toNodeSlug(u);
    const s2 = toNodeSlug(v);
    const sorted = [s1, s2].sort();
    return `edge-${sorted[0]}-${sorted[1]}`;
}

function findEdgeElement(u, v) {
    if (!u || !v) return null;
    const edgeId = toEdgeId(u, v);
    let el = document.getElementById(edgeId);
    if (el) return el;
    el = document.querySelector(`.topology-edge[data-source="${u}"][data-destination="${v}"]`) ||
         document.querySelector(`.topology-edge[data-source="${v}"][data-destination="${u}"]`);
    return el;
}

// ============================================================================
// 2. API Helpers
// ============================================================================
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
    setTimeout(() => {
        banner.style.display = "none";
    }, 5000);
}

// ============================================================================
// 3. Topology Data & SVG Rendering
// ============================================================================
let networkTopologyData = null;

async function loadTopologyAndNodes() {
    try {
        const topData = await apiGet("/api/network/topology");
        networkTopologyData = topData;
        renderSVGTopology(topData.nodes, topData.connections);

        const nodeData = await apiGet("/api/network/nodes");
        populateNodeSelects(nodeData.nodes);

        const nodesCountEl = document.getElementById("statNodesCount");
        const connCountEl = document.getElementById("statConnCount");
        if (nodesCountEl) nodesCountEl.textContent = topData.nodes.length;
        if (connCountEl) connCountEl.textContent = topData.connections.length;
    } catch (err) {
        console.error("Failed to load topology:", err);
        showAlert("Failed to load network topology from backend API.");
    }
}

function updateRouteInfoDisplay(src, dst, path, cost, hops) {
    const srcEl = document.getElementById("routeInfoSource");
    const dstEl = document.getElementById("routeInfoDest");
    const pathEl = document.getElementById("routeInfoPath");
    const costEl = document.getElementById("routeInfoCost");
    const hopsEl = document.getElementById("routeInfoHops");

    if (srcEl) srcEl.textContent = src || "--";
    if (dstEl) dstEl.textContent = dst || "--";
    if (pathEl) pathEl.textContent = path && path.length ? path.join(" ➔ ") : "--";
    if (costEl) costEl.textContent = cost !== undefined ? cost : "--";
    if (hopsEl) hopsEl.textContent = hops !== undefined ? hops : "--";
}

async function fetchAndDisplayRoutePreview() {
    const destSelect = document.getElementById("destSelect");
    if (!destSelect) return;
    const src = FIXED_SOURCE;
    const dst = destSelect.value;
    if (!dst) return;

    if (src === dst) {
        updateRouteInfoDisplay(src, dst, [src], 0, 0);
        if (networkTopologyData && (!animator.animationState || !animator.animationState.running)) {
            renderSVGTopology(networkTopologyData.nodes, networkTopologyData.connections, [src]);
            animator.highlightSourceAndDestinationNodes(src, dst);
        }
        return;
    }

    try {
        const data = await apiGet(`/api/network/route?source=${encodeURIComponent(src)}&destination=${encodeURIComponent(dst)}`);
        const routePath = Array.isArray(data.path) ? data.path : (data.route?.path || (Array.isArray(data.route) ? data.route : []));
        const routeCost = data.total_cost ?? data.route?.total_cost ?? data.route_cost ?? "--";
        const hopCount = data.hop_count ?? data.route?.hop_count ?? "--";

        updateRouteInfoDisplay(src, dst, routePath, routeCost, hopCount);

        if (networkTopologyData && (!animator.animationState || !animator.animationState.running)) {
            renderSVGTopology(networkTopologyData.nodes, networkTopologyData.connections, routePath);
            animator.highlightSourceAndDestinationNodes(src, dst);
        }
    } catch (err) {
        console.warn("Could not preview route:", err);
    }
}

function populateNodeSelects(nodes) {
    const srcInput = document.getElementById("sourceSelect");
    const dstSelect = document.getElementById("destSelect");
    if (srcInput) srcInput.value = FIXED_SOURCE;
    if (!dstSelect) return;

    dstSelect.innerHTML = "";

    // Allowed destinations: Check-in, Security, Baggage, Emergency Services (exclude Control Tower)
    nodes.filter(node => node !== FIXED_SOURCE).forEach(node => {
        dstSelect.add(new Option(node, node));
    });

    dstSelect.value = "Security";

    dstSelect.addEventListener("change", fetchAndDisplayRoutePreview);

    fetchAndDisplayRoutePreview();
}

function renderSVGTopology(nodes, connections, highlightedPath = []) {
    const svg = document.getElementById("topologySvg");
    if (!svg) return;

    svg.innerHTML = "";

    // 1. Connection Lines Layer
    const edgesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    edgesGroup.setAttribute("class", "edges-group");

    connections.forEach(conn => {
        const p1 = NODE_COORDINATES[conn.source];
        const p2 = NODE_COORDINATES[conn.destination];
        if (!p1 || !p2) return;

        const isHighlighted = isEdgeInPath(conn.source, conn.destination, highlightedPath);
        const edgeElementId = toEdgeId(conn.source, conn.destination);

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", p1.x);
        line.setAttribute("y1", p1.y);
        line.setAttribute("x2", p2.x);
        line.setAttribute("y2", p2.y);
        line.setAttribute("class", `topology-edge ${isHighlighted ? "highlighted" : ""}`);
        line.setAttribute("id", edgeElementId);
        line.setAttribute("data-source", conn.source);
        line.setAttribute("data-destination", conn.destination);
        edgesGroup.appendChild(line);

        // Edge Weight Label
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2;

        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("x", midX - 11);
        bg.setAttribute("y", midY - 9);
        bg.setAttribute("width", 22);
        bg.setAttribute("height", 18);
        bg.setAttribute("class", "topology-cost-bg");
        edgesGroup.appendChild(bg);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", midX);
        text.setAttribute("y", midY + 4);
        text.setAttribute("class", "topology-edge-cost");
        text.textContent = conn.cost || conn.weight;
        edgesGroup.appendChild(text);
    });

    svg.appendChild(edgesGroup);

    // 2. Nodes Layer
    const nodesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    nodesGroup.setAttribute("class", "nodes-group");

    nodes.forEach(nodeItem => {
        const nodeName = typeof nodeItem === "string" ? nodeItem : nodeItem.name;
        const pos = NODE_COORDINATES[nodeName];
        if (!pos) return;

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "topology-node-group");
        g.setAttribute("id", toNodeId(nodeName));
        g.setAttribute("tabindex", "0");
        g.setAttribute("role", "button");
        g.setAttribute("aria-label", `Airport Node ${nodeName}`);

        const isInPath = highlightedPath.includes(nodeName);

        // Node Circle
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", 28);
        circle.setAttribute("class", `node-circle ${isInPath ? "active" : ""}`);
        g.appendChild(circle);

        // Node Icon
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "text");
        icon.setAttribute("x", pos.x);
        icon.setAttribute("y", pos.y - 2);
        icon.setAttribute("text-anchor", "middle");
        icon.setAttribute("dominant-baseline", "central");
        icon.setAttribute("font-size", "14px");
        icon.textContent = getNodeIcon(nodeName);
        g.appendChild(icon);

        // Status Indicator Dot
        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("cx", pos.x + 18);
        dot.setAttribute("cy", pos.y - 18);
        dot.setAttribute("r", 4);
        dot.setAttribute("class", "node-status-dot");
        g.appendChild(dot);

        // Node Label
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", pos.x);
        label.setAttribute("y", pos.y + 42);
        label.setAttribute("class", "node-label");
        label.textContent = nodeName;
        g.appendChild(label);

        // Node Role Tag (SOURCE / DESTINATION)
        const roleTag = document.createElementNS("http://www.w3.org/2000/svg", "text");
        roleTag.setAttribute("x", pos.x);
        roleTag.setAttribute("y", pos.y + 54);
        roleTag.setAttribute("class", "node-role-tag");
        roleTag.setAttribute("text-anchor", "middle");
        roleTag.textContent = "";
        g.appendChild(roleTag);

        // Click / Keyboard interaction
        g.addEventListener("click", () => openNodeModal(nodeName));
        g.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") openNodeModal(nodeName);
        });

        nodesGroup.appendChild(g);
    });

    svg.appendChild(nodesGroup);

    // 3. Animation Overlay Layer (Trail, Flying Frame, Flying ACK)
    const animOverlay = document.createElementNS("http://www.w3.org/2000/svg", "g");
    animOverlay.setAttribute("id", "animationOverlay");
    animOverlay.setAttribute("class", "animation-overlay");
    animOverlay.style.pointerEvents = "none";

    // Trail Line
    const trail = document.createElementNS("http://www.w3.org/2000/svg", "line");
    trail.setAttribute("id", "flyingTrail");
    trail.setAttribute("class", "flying-trail");
    trail.style.display = "none";
    trail.style.visibility = "hidden";
    animOverlay.appendChild(trail);

    // Flying Data Frame
    const flyingFrame = document.createElementNS("http://www.w3.org/2000/svg", "g");
    flyingFrame.setAttribute("id", "flyingFrame");
    flyingFrame.setAttribute("class", "flying-frame");
    flyingFrame.style.display = "none";
    flyingFrame.style.visibility = "hidden";
    flyingFrame.style.pointerEvents = "none";

    const frameRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    frameRect.setAttribute("class", "flying-frame-bg");
    frameRect.setAttribute("width", "36");
    frameRect.setAttribute("height", "22");
    frameRect.setAttribute("x", "-18");
    frameRect.setAttribute("y", "-11");
    frameRect.setAttribute("rx", "6");
    frameRect.setAttribute("ry", "6");
    flyingFrame.appendChild(frameRect);

    const frameText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    frameText.setAttribute("id", "flyingFrameText");
    frameText.setAttribute("class", "flying-frame-text");
    frameText.setAttribute("text-anchor", "middle");
    frameText.setAttribute("dominant-baseline", "central");
    frameText.textContent = "F0";
    flyingFrame.appendChild(frameText);

    animOverlay.appendChild(flyingFrame);

    // Flying ACK Badge
    const flyingAck = document.createElementNS("http://www.w3.org/2000/svg", "g");
    flyingAck.setAttribute("id", "flyingAck");
    flyingAck.setAttribute("class", "flying-ack");
    flyingAck.style.display = "none";
    flyingAck.style.visibility = "hidden";
    flyingAck.style.pointerEvents = "none";

    const ackRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    ackRect.setAttribute("class", "flying-ack-bg");
    ackRect.setAttribute("width", "54");
    ackRect.setAttribute("height", "20");
    ackRect.setAttribute("x", "-27");
    ackRect.setAttribute("y", "-10");
    ackRect.setAttribute("rx", "5");
    ackRect.setAttribute("ry", "5");
    flyingAck.appendChild(ackRect);

    const ackText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    ackText.setAttribute("id", "flyingAckText");
    ackText.setAttribute("class", "flying-ack-text");
    ackText.setAttribute("text-anchor", "middle");
    ackText.setAttribute("dominant-baseline", "central");
    ackText.textContent = "ACK F0";
    flyingAck.appendChild(ackText);

    animOverlay.appendChild(flyingAck);

    svg.appendChild(animOverlay);
}

function isEdgeInPath(u, v, path) {
    if (!path || path.length < 2) return false;
    for (let i = 0; i < path.length - 1; i++) {
        if ((path[i] === u && path[i + 1] === v) || (path[i] === v && path[i + 1] === u)) {
            return true;
        }
    }
    return false;
}

function getNodeIcon(name) {
    switch (name) {
        case "Control Tower": return "🗼";
        case "Check-in": return "🧳";
        case "Security": return "🛡️";
        case "Baggage": return "📦";
        case "Emergency Services": return "🚑";
        default: return "📍";
    }
}

// ============================================================================
// 4. Live Simulation Animation Engine (Step 12)
// ============================================================================

class SimulationAnimationEngine {
    constructor() {
        this.animationState = {
            running: false,
            paused: false,
            currentFrameIndex: 0,
            currentHopIndex: 0,
            progress: 0,
            speed: 1.0,
        };
        this.activeRaf = null;
        this.resumePromiseResolve = null;
        this.simResult = null;
        this.events = [];
        this.route = [];
        this.frames = [];
        this.currentEventIndex = 0;
        this.retransmissionCount = 0;
        this.simStartTime = null;
    }

    setSpeed(speedVal) {
        this.animationState.speed = Math.max(0.2, parseFloat(speedVal) || 1.0);
    }

    async start(simulationResult) {
        this.stop(); // Cancel any existing active timeline

        this.simResult = simulationResult;
        this.events = simulationResult.events || [];
        this.route = simulationResult.route || [];
        this.frames = simulationResult.frames || [];
        this.currentEventIndex = 0;
        this.retransmissionCount = 0;
        this.simStartTime = Date.now();

        this.animationState.running = true;
        this.animationState.paused = false;
        this.animationState.currentFrameIndex = 0;
        this.animationState.currentHopIndex = 0;
        this.animationState.progress = 0;

        console.log("Simulation result:", simulationResult);
        console.log("Route:", this.route);
        console.log("Frames:", this.frames);
        console.log("Events:", this.events);

        // UI Initialization
        this.updateControlButtons("playing");
        this.resetVisualHighlights();
        this.highlightSourceAndDestination();
        this.initializeFramesTable(this.frames);
        this.clearEventLog();
        this.updateProgress(0, this.events.length);
        this.setBanner("Initializing simulation event timeline...", "normal", "INIT");

        // Highlight computed Dijkstra path on SVG
        if (networkTopologyData) {
            renderSVGTopology(networkTopologyData.nodes, networkTopologyData.connections, this.route);
            this.highlightSourceAndDestination();
        }

        // Execute discrete event timeline
        try {
            await this.playTimeline();
        } catch (err) {
            if (err.message !== "ANIMATION_STOPPED") {
                console.error("Animation error:", err);
            }
        } finally {
            if (this.animationState.running) {
                this.animationState.running = false;
                this.updateControlButtons("idle");
            }
        }
    }

    pause() {
        if (this.animationState.running && !this.animationState.paused) {
            this.animationState.paused = true;
            this.updateControlButtons("paused");
            this.setBanner("Simulation PAUSED by user", "normal", "PAUSED");
        }
    }

    resume() {
        if (this.animationState.paused) {
            this.animationState.paused = false;
            this.updateControlButtons("playing");
            this.setBanner("Resuming simulation playback...", "normal", "PLAYING");
            if (this.resumePromiseResolve) {
                const resolve = this.resumePromiseResolve;
                this.resumePromiseResolve = null;
                resolve();
            }
        }
    }

    stop() {
        this.animationState.running = false;
        this.animationState.paused = false;

        if (this.activeRaf) {
            cancelAnimationFrame(this.activeRaf);
            this.activeRaf = null;
        }
        if (this.resumePromiseResolve) {
            const resolve = this.resumePromiseResolve;
            this.resumePromiseResolve = null;
            resolve();
        }

        this.hideFlyingElements();
        this.resetVisualHighlights();
        this.updateControlButtons("idle");
    }

    updateControlButtons(status) {
        const startBtn = document.getElementById("startSimulationBtn");
        const pauseBtn = document.getElementById("pauseSimulationBtn");
        const resumeBtn = document.getElementById("resumeSimulationBtn");
        const resetBtn = document.getElementById("resetSimulationBtn");

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
        } else { // idle
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
        if (!this.animationState.running) throw new Error("ANIMATION_STOPPED");

        const adjustedMs = ms / this.animationState.speed;
        let remaining = adjustedMs;
        const interval = 25;

        while (remaining > 0) {
            if (!this.animationState.running) throw new Error("ANIMATION_STOPPED");

            if (this.animationState.paused) {
                await new Promise((resolve) => {
                    this.resumePromiseResolve = resolve;
                });
                if (!this.animationState.running) throw new Error("ANIMATION_STOPPED");
            }

            const step = Math.min(interval, remaining);
            await new Promise((res) => setTimeout(res, step));
            remaining -= step;
        }
    }

    async playTimeline() {
        for (let i = 0; i < this.events.length; i++) {
            if (!this.animationState.running) throw new Error("ANIMATION_STOPPED");

            this.currentEventIndex = i;
            const evt = this.events[i];

            // Update Progress Bar
            this.updateProgress(i + 1, this.events.length);

            // Append to Event Log Live
            this.appendLiveEventLog(evt);

            // Process specific event
            await this.dispatchLiveEvent(evt);
        }

        // Final completion state
        this.animationState.running = false;
        this.updateControlButtons("idle");
        this.updateProgress(this.events.length, this.events.length);
    }

    async dispatchLiveEvent(evt) {
        switch (evt.event) {
            case "routing":
                await this.handleRoutingEvent(evt);
                break;
            case "packet_created":
                await this.handlePacketCreatedEvent(evt);
                break;
            case "frame_created":
                await this.handleFrameCreatedEvent(evt);
                break;
            case "crc_calculated":
                await this.handleCrcCalculatedEvent(evt);
                break;
            case "transmission":
                await this.handleTransmissionEvent(evt);
                break;
            case "crc_verification":
                await this.handleCrcVerificationEvent(evt);
                break;
            case "failure":
                await this.handleFailureEvent(evt);
                break;
            case "acknowledgement":
                await this.handleAcknowledgementEvent(evt);
                break;
            case "retransmission":
                await this.handleRetransmissionEvent(evt);
                break;
            case "discarded_out_of_order":
                await this.handleDiscardEvent(evt);
                break;
            case "delivery":
                await this.handleDeliveryEvent(evt);
                break;
            default:
                await this.delay(200);
        }
    }

    // --- Specific Event Handlers ---

    async handleRoutingEvent(evt) {
        this.setBanner(`Route Computed: ${evt.route.join(" ➔ ")} (Cost: ${evt.route_cost}, Hops: ${evt.hop_count})`, "normal", "ROUTING");
        if (networkTopologyData) {
            renderSVGTopology(networkTopologyData.nodes, networkTopologyData.connections, evt.route);
            this.highlightSourceAndDestination();
        }
        await this.delay(400);
    }

    async handlePacketCreatedEvent(evt) {
        this.setBanner(`Packet Created: [${evt.packet_id ? evt.packet_id.substring(0, 8) : 'PKT'}] "${evt.payload}"`, "normal", "PACKET");
        const statPackets = document.getElementById("statPacketsCount");
        if (statPackets) statPackets.textContent = "1";
        await this.delay(250);
    }

    async handleFrameCreatedEvent(evt) {
        this.setBanner(`Framing: Encapsulated Frame F${evt.sequence_number}: "${evt.payload}"`, "normal", "FRAMING");
        this.updateFrameRow(evt.sequence_number, {
            payload: evt.payload,
            status: "created",
            statusClass: "badge-muted",
        });
        const statFrames = document.getElementById("statFramesCount");
        if (statFrames) statFrames.textContent = evt.sequence_number + 1;
        await this.delay(180);
    }

    async handleCrcCalculatedEvent(evt) {
        this.setBanner(`CRC Generator: Frame F${evt.sequence_number} CRC-8 = 0x${evt.crc.toString(16).toUpperCase()}`, "normal", "CRC-8");
        this.updateFrameRow(evt.sequence_number, {
            crc: `0x${evt.crc.toString(16).toUpperCase().padStart(2, '0')}`,
            crcStatus: "computed",
            crcClass: "badge-accent",
        });
        await this.delay(120);
    }

    async handleTransmissionEvent(evt) {
        const seq = evt.sequence_number;
        const isFailed = evt.status === "failed";
        this.animationState.currentFrameIndex = seq;

        console.log("Animating frame:", `F${seq}`, isFailed ? "(Failure expected)" : "(Normal transmission)");

        this.setBanner(`Transmitting Frame F${seq} along Dijkstra path...`, "normal", "TX");
        this.highlightFrameRow(seq, "row-transmitting");
        this.updateFrameRow(seq, { status: "transmitting", statusClass: "badge-accent" });

        const flyingEl = document.getElementById("flyingFrame");
        if (flyingEl) {
            this.showFrame(seq, isFailed);
            await this.animateElementAlongRoute(flyingEl, this.route, false, isFailed);

            if (isFailed) {
                flyingEl.setAttribute("class", "flying-frame failed");
                this.setBanner(`Frame F${seq} transmission failed or dropped in transit!`, "error", "FAIL");
                this.highlightFrameRow(seq, "row-failed");
                this.updateFrameRow(seq, { status: "failed", statusClass: "badge-danger" });
                await this.delay(400);
                this.hideFrame();
            } else {
                this.updateFrameRow(seq, { status: "received", statusClass: "badge-accent" });
                await this.delay(200);
                this.hideFrame();
            }
        } else {
            await this.delay(600);
        }

        this.unhighlightFrameRow(seq, "row-transmitting");
    }

    async handleCrcVerificationEvent(evt) {
        const seq = evt.sequence_number;
        const isValid = evt.is_valid;

        this.setBanner(`Receiver CRC Check: Frame F${seq} CRC is ${isValid ? "VALID ✓" : "INVALID ✗"}`, isValid ? "success" : "error", "CRC-CHK");
        this.updateFrameRow(seq, {
            crcStatus: isValid ? "valid" : "invalid",
            crcClass: isValid ? "badge-success" : "badge-danger",
        });
        await this.delay(250);
    }

    async handleFailureEvent(evt) {
        const seq = evt.sequence_number;
        this.setBanner(`Frame F${seq} FAILED (${evt.reason || "packet_loss"})`, "error", "FAILURE");
        this.updateFrameRow(seq, {
            status: "failed",
            statusClass: "badge-danger",
        });
        this.highlightFrameRow(seq, "row-failed");
        await this.delay(350);
    }

    async handleAcknowledgementEvent(evt) {
        const seq = evt.sequence_number;
        this.setBanner(`ACK Received for Frame F${seq} — Cumulative window slide`, "success", "ACK");

        this.updateFrameRow(seq, { status: "acknowledged", statusClass: "badge-success" });
        this.highlightFrameRow(seq, "row-acknowledged");

        const flyingAck = document.getElementById("flyingAck");
        if (flyingAck) {
            this.showAck(seq);
            await this.animateElementAlongRoute(flyingAck, this.route, true, false);
            this.hideAck();
        } else {
            await this.delay(350);
        }

        this.unhighlightFrameRow(seq, "row-failed");
        this.unhighlightFrameRow(seq, "frame-retransmission");
        await this.delay(150);
    }

    async handleRetransmissionEvent(evt) {
        const seq = evt.sequence_number;
        const attempt = evt.attempt || 1;
        this.retransmissionCount++;

        this.setBanner(`Go-Back-N Window Rollback: Retransmitting Frame F${seq} (Attempt #${attempt})`, "retrans", "GBN-RETX");

        const statRetrans = document.getElementById("statRetransCount");
        if (statRetrans) statRetrans.textContent = this.retransmissionCount;

        const sumRetrans = document.getElementById("metricRetransmissions");
        if (sumRetrans) sumRetrans.textContent = this.retransmissionCount;

        this.highlightFrameRow(seq, "frame-retransmission");
        this.updateFrameRow(seq, {
            status: "retransmitting",
            statusClass: "badge-warning",
            retransCount: attempt,
        });

        await this.delay(400);
    }

    async handleDiscardEvent(evt) {
        const seq = evt.sequence_number;
        this.setBanner(`Receiver: Frame F${seq} discarded (Out of sequence window)`, "error", "DISCARD");
        this.updateFrameRow(seq, {
            status: "discarded",
            statusClass: "badge-danger",
        });
        await this.delay(300);
    }

    async handleDeliveryEvent(evt) {
        this.setBanner("✓ Transmission Complete — All frames delivered & verified", "success", "DELIVERED");

        if (this.route && this.route.length > 0) {
            const destNode = this.route[this.route.length - 1];
            const destEl = document.getElementById(toNodeId(destNode));
            if (destEl) destEl.classList.add("node-success");

            for (let i = 0; i < this.route.length - 1; i++) {
                const edgeEl = findEdgeElement(this.route[i], this.route[i + 1]);
                if (edgeEl) edgeEl.classList.add("edge-complete");
            }
        }

        const statDelivery = document.getElementById("statDeliveryStatus");
        if (statDelivery) {
            statDelivery.textContent = "● DELIVERED";
            statDelivery.style.color = "var(--success)";
        }

        const statusBadge = document.getElementById("metricStatusBadge");
        if (statusBadge) {
            statusBadge.setAttribute("class", "badge badge-success");
            statusBadge.textContent = "DELIVERED";
        }

        await this.delay(600);
    }

    // --- Visual Gliding Animation along Dijkstra Route ---

    showFrame(seq, isFailed = false) {
        const el = document.getElementById("flyingFrame");
        const txt = document.getElementById("flyingFrameText");
        if (!el || !txt) return;
        txt.textContent = `F${seq}`;
        el.setAttribute("class", isFailed ? "flying-frame failed" : "flying-frame");
        el.style.display = "inline";
        el.style.visibility = "visible";
    }

    hideFrame() {
        const el = document.getElementById("flyingFrame");
        if (el) {
            el.style.display = "none";
            el.style.visibility = "hidden";
        }
    }

    showAck(seq) {
        const el = document.getElementById("flyingAck");
        const txt = document.getElementById("flyingAckText");
        if (!el || !txt) return;
        txt.textContent = `ACK F${seq}`;
        el.setAttribute("class", "flying-ack");
        el.style.display = "inline";
        el.style.visibility = "visible";
    }

    hideAck() {
        const el = document.getElementById("flyingAck");
        if (el) {
            el.style.display = "none";
            el.style.visibility = "hidden";
        }
    }

    hideFlyingElements() {
        this.hideFrame();
        this.hideAck();
        const trail = document.getElementById("flyingTrail");
        if (trail) {
            trail.style.display = "none";
            trail.style.visibility = "hidden";
        }
    }

    async animateElementAlongRoute(element, route, isReverse = false, isError = false) {
        if (!route || route.length < 2) return;

        const pathNodes = isReverse ? [...route].reverse() : [...route];
        const hopCount = pathNodes.length - 1;

        for (let i = 0; i < hopCount; i++) {
            if (!this.animationState.running) throw new Error("ANIMATION_STOPPED");

            this.animationState.currentHopIndex = i;
            const u = pathNodes[i];
            const v = pathNodes[i + 1];
            const p1 = NODE_COORDINATES[u];
            const p2 = NODE_COORDINATES[v];
            if (!p1 || !p2) continue;

            console.log("Current hop:", u, "➔", v);

            const edgeEl = findEdgeElement(u, v);
            const nodeUEl = document.getElementById(toNodeId(u));
            const nodeVEl = document.getElementById(toNodeId(v));

            // Edge and Node active transmission styling
            if (edgeEl) edgeEl.classList.add("edge-active");
            if (nodeUEl) nodeUEl.classList.add("node-transmitting");
            if (nodeVEl) nodeVEl.classList.add("node-receiving");

            const isLastHop = (i === hopCount - 1);
            const isFailingHop = isError && isLastHop;
            const hopDuration = 650 / this.animationState.speed;

            await this.glideElementBetweenPoints(element, p1, p2, hopDuration, (hopProg) => {
                const totalHops = Math.max(1, hopCount);
                const hopFrac = (i + hopProg) / totalHops;
                const totalEvents = Math.max(1, this.events.length);
                const overallFrac = Math.min(1.0, (this.currentEventIndex + hopFrac) / totalEvents);
                this.updateProgressFraction(overallFrac);
            });

            // Clean active hop styles
            if (edgeEl) edgeEl.classList.remove("edge-active");
            if (nodeUEl) nodeUEl.classList.remove("node-transmitting");
            if (nodeVEl) nodeVEl.classList.remove("node-receiving");

            if (isFailingHop) {
                if (edgeEl) {
                    edgeEl.classList.add("edge-error");
                    setTimeout(() => edgeEl?.classList.remove("edge-error"), 800);
                }
                if (nodeVEl) {
                    nodeVEl.classList.add("node-error");
                    setTimeout(() => nodeVEl?.classList.remove("node-error"), 800);
                }
                break;
            } else {
                if (nodeVEl && isLastHop) {
                    nodeVEl.classList.add("node-success");
                    setTimeout(() => nodeVEl?.classList.remove("node-success"), 600);
                }
            }

            if (!isLastHop) {
                await this.delay(120);
            }
        }
    }

    glideElementBetweenPoints(element, p1, p2, durationMs, onProgress = null) {
        return new Promise((resolve, reject) => {
            if (!this.animationState.running) {
                return reject(new Error("ANIMATION_STOPPED"));
            }

            let lastTime = performance.now();
            let progress = 0;
            const trail = document.getElementById("flyingTrail");

            // Initial position directly at start node
            element.setAttribute("transform", `translate(${p1.x}, ${p1.y})`);
            element.style.display = "inline";
            element.style.visibility = "visible";

            if (trail) {
                trail.setAttribute("x1", p1.x);
                trail.setAttribute("y1", p1.y);
                trail.setAttribute("x2", p1.x);
                trail.setAttribute("y2", p1.y);
                trail.style.display = "inline";
                trail.style.visibility = "visible";
            }

            const step = (now) => {
                if (!this.animationState.running) {
                    if (trail) {
                        trail.style.display = "none";
                        trail.style.visibility = "hidden";
                    }
                    this.activeRaf = null;
                    return reject(new Error("ANIMATION_STOPPED"));
                }

                if (this.animationState.paused) {
                    lastTime = now; // Prevent jumping when resumed
                    this.activeRaf = requestAnimationFrame(step);
                    return;
                }

                const dt = now - lastTime;
                lastTime = now;

                progress += dt / durationMs;
                if (progress > 1.0) progress = 1.0;
                this.animationState.progress = progress;

                if (onProgress) {
                    onProgress(progress);
                }

                // Linear interpolation of coordinates
                const curX = p1.x + (p2.x - p1.x) * progress;
                const curY = p1.y + (p2.y - p1.y) * progress;

                element.setAttribute("transform", `translate(${curX}, ${curY})`);

                if (trail) {
                    trail.setAttribute("x2", curX);
                    trail.setAttribute("y2", curY);
                }

                if (progress < 1.0) {
                    this.activeRaf = requestAnimationFrame(step);
                } else {
                    if (trail) {
                        trail.style.display = "none";
                        trail.style.visibility = "hidden";
                    }
                    this.activeRaf = null;
                    resolve();
                }
            };

            this.activeRaf = requestAnimationFrame(step);
        });
    }

    // --- Helper UI Setters ---

    setBanner(text, style = "normal", badge = "EVENT") {
        const banner = document.getElementById("currentEventBanner");
        const textEl = document.getElementById("currentEventText");
        const badgeEl = document.getElementById("currentEventBadge");

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

    updateProgressFraction(fraction) {
        const fill = document.getElementById("simulationProgressFill");
        const label = document.getElementById("simulationProgressText");
        const percent = Math.min(100, Math.max(0, Math.round(fraction * 100)));
        if (fill) fill.style.width = `${percent}%`;
        if (label) label.textContent = `${percent}%`;
    }

    updateProgress(current, total) {
        if (!total || total === 0) return;
        this.updateProgressFraction(current / total);
    }

    highlightSourceAndDestination() {
        if (!this.route || this.route.length === 0) return;
        const src = this.route[0];
        const dst = this.route[this.route.length - 1];
        this.highlightSourceAndDestinationNodes(src, dst);
    }

    highlightSourceAndDestinationNodes(src, dst) {
        if (!src || !dst) return;
        this.resetVisualHighlights();
        const srcEl = document.getElementById(toNodeId(src));
        const dstEl = document.getElementById(toNodeId(dst));
        if (srcEl) {
            srcEl.classList.add("node-source");
            const tag = srcEl.querySelector(".node-role-tag");
            if (tag) {
                tag.textContent = "SOURCE";
                tag.setAttribute("class", "node-role-tag source");
            }
        }
        if (dstEl) {
            dstEl.classList.add("node-destination");
            const tag = dstEl.querySelector(".node-role-tag");
            if (tag) {
                tag.textContent = "DESTINATION";
                tag.setAttribute("class", "node-role-tag destination");
            }
        }
    }

    resetVisualHighlights() {
        document.querySelectorAll(".topology-edge").forEach(el => {
            el.classList.remove("edge-active", "edge-error", "edge-complete");
        });
        document.querySelectorAll(".topology-node-group").forEach(el => {
            el.classList.remove("node-source", "node-destination", "node-transmitting", "node-receiving", "node-error", "node-success");
        });
        document.querySelectorAll(".node-role-tag").forEach(el => {
            el.textContent = "";
            el.setAttribute("class", "node-role-tag");
        });
    }

    // --- Frame Table Synchronization ---

    initializeFramesTable(frames) {
        const tbody = document.getElementById("framesTableBody");
        const emptyState = document.getElementById("framesEmptyState");
        if (!tbody) return;

        tbody.innerHTML = "";
        if (!frames || frames.length === 0) {
            if (emptyState) emptyState.style.display = "block";
            return;
        }

        if (emptyState) emptyState.style.display = "none";

        frames.forEach(frame => {
            const tr = document.createElement("tr");
            tr.setAttribute("id", `frame-row-${frame.sequence_number}`);
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
        const row = document.getElementById(`frame-row-${seq}`);
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
        const row = document.getElementById(`frame-row-${seq}`);
        if (row) row.classList.add(className);
    }

    unhighlightFrameRow(seq, className) {
        const row = document.getElementById(`frame-row-${seq}`);
        if (row) row.classList.remove(className);
    }

    // --- Live Event Log Synchronization ---

    clearEventLog() {
        const terminalBody = document.getElementById("terminalEventLog");
        if (terminalBody) terminalBody.innerHTML = "";
    }

    appendLiveEventLog(evt) {
        const terminalBody = document.getElementById("terminalEventLog");
        if (!terminalBody) return;

        const row = document.createElement("div");
        row.className = "log-entry";

        let tagClass = "tag-tx";
        let tagText = `[${evt.event ? evt.event.toUpperCase() : 'EVENT'}]`;

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

        // Frontend simulation timestamp: [MM:SS]
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
        terminalBody.appendChild(row);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }
}

// Global Animator Instance
const animator = new SimulationAnimationEngine();

// ============================================================================
// 5. Form Handlers & User Action Bindings
// ============================================================================

function setupFormHandlers() {
    const startBtn = document.getElementById("startSimulationBtn");
    const pauseBtn = document.getElementById("pauseSimulationBtn");
    const resumeBtn = document.getElementById("resumeSimulationBtn");
    const resetBtn = document.getElementById("resetSimulationBtn");
    const speedSelect = document.getElementById("speedSelect");
    const modalCloseBtn = document.getElementById("modalCloseBtn");
    const modalOverlay = document.getElementById("nodeModal");

    if (startBtn) startBtn.addEventListener("click", handleStartSimulation);
    if (pauseBtn) pauseBtn.addEventListener("click", () => animator.pause());
    if (resumeBtn) resumeBtn.addEventListener("click", () => animator.resume());
    if (resetBtn) resetBtn.addEventListener("click", handleResetSimulation);

    if (speedSelect) {
        speedSelect.addEventListener("change", (e) => {
            animator.setSpeed(e.target.value);
        });
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeNodeModal);
    if (modalOverlay) {
        modalOverlay.addEventListener("click", (e) => {
            if (e.target === modalOverlay) closeNodeModal();
        });
    }
}

async function handleStartSimulation() {
    const startBtn = document.getElementById("startSimulationBtn");
    const src = FIXED_SOURCE;
    const dst = document.getElementById("destSelect").value;
    const msg = document.getElementById("messageInput").value;
    const windowSize = parseInt(document.getElementById("windowSizeInput").value, 10);
    const failSeqInput = document.getElementById("failureSequenceInput").value.trim();

    if (!msg || !msg.trim()) {
        showAlert("Message cannot be empty.");
        return;
    }

    if (src === dst) {
        showAlert("Source and destination nodes cannot be the same.");
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

    // Set UI loading state before API request
    startBtn.disabled = true;
    startBtn.innerHTML = `<span class="spinner"></span> Simulating...`;

    try {
        const payload = {
            source: FIXED_SOURCE,
            destination: dst,
            message: msg.trim(),
            window_size: windowSize || 3,
            failure_sequence: failureSequence,
        };

        // 1. Call Backend Simulation REST API
        const res = await apiPost("/api/simulation/run", payload);
        const sim = res.simulation;

        // 2. Display Static Result Summary Card
        displaySimulationSummary(sim);

        // 3. Update top summary statistics
        updateDashboardStats(sim);

        // 4. Launch Live SVG Animation Timeline
        await animator.start(sim);

    } catch (err) {
        console.error("Simulation error:", err);
        showAlert(err.message || "Simulation execution failed.");
        startBtn.disabled = false;
        startBtn.innerHTML = `<span>⚡ Start Simulation</span>`;
        animator.stop();
    }
}

async function handleResetSimulation() {
    try {
        // Stop active animation timeline
        animator.stop();

        // Call backend reset
        await apiPost("/api/simulation/reset", {});

        // Reset UI Components
        clearSimulationDisplay();
        showAlert("Simulation reset successfully.", "info");

        // Re-render unhighlighted topology
        if (networkTopologyData) {
            renderSVGTopology(networkTopologyData.nodes, networkTopologyData.connections, []);
        }
    } catch (err) {
        console.error("Reset error:", err);
        showAlert("Failed to reset simulation.");
    }
}

function displaySimulationSummary(sim) {
    const summaryCard = document.getElementById("simulationSummaryCard");
    const routeContainer = document.getElementById("routeDisplayContainer");
    const routeCostEl = document.getElementById("metricRouteCost");
    const hopCountEl = document.getElementById("metricHopCount");
    const totalFramesEl = document.getElementById("metricTotalFrames");
    const retransCountEl = document.getElementById("metricRetransmissions");
    const statusBadgeEl = document.getElementById("metricStatusBadge");

    if (summaryCard) summaryCard.style.display = "block";

    if (routeContainer && sim.route) {
        routeContainer.innerHTML = "";
        sim.route.forEach((node, idx) => {
            const tag = document.createElement("span");
            tag.className = "route-node-tag";
            tag.textContent = node;
            routeContainer.appendChild(tag);

            if (idx < sim.route.length - 1) {
                const arrow = document.createElement("span");
                arrow.className = "route-arrow";
                arrow.textContent = "➔";
                routeContainer.appendChild(arrow);
            }
        });
    }

    if (routeCostEl) routeCostEl.textContent = sim.route_cost;
    if (hopCountEl) hopCountEl.textContent = sim.hop_count;
    if (totalFramesEl) totalFramesEl.textContent = sim.total_frames;
    if (retransCountEl) retransCountEl.textContent = sim.retransmission_count;

    if (statusBadgeEl) {
        statusBadgeEl.setAttribute("class", "badge badge-accent");
        statusBadgeEl.textContent = "RUNNING";
    }

    updateRouteInfoDisplay(sim.source, sim.destination, sim.route, sim.route_cost, sim.hop_count);
}

function updateDashboardStats(sim) {
    const statPackets = document.getElementById("statPacketsCount");
    const statFrames = document.getElementById("statFramesCount");
    const statRetrans = document.getElementById("statRetransCount");
    const statDelivery = document.getElementById("statDeliveryStatus");

    if (statPackets) statPackets.textContent = 1;
    if (statFrames) statFrames.textContent = sim.total_frames;
    if (statRetrans) statRetrans.textContent = 0; // Starts at 0, animator increments it live!
    if (statDelivery) {
        statDelivery.textContent = "● RUNNING";
        statDelivery.style.color = "var(--accent)";
    }
}

function clearSimulationDisplay() {
    const summaryCard = document.getElementById("simulationSummaryCard");
    const tbody = document.getElementById("framesTableBody");
    const emptyState = document.getElementById("framesEmptyState");
    const terminalBody = document.getElementById("terminalEventLog");
    const statPackets = document.getElementById("statPacketsCount");
    const statFrames = document.getElementById("statFramesCount");
    const statRetrans = document.getElementById("statRetransCount");
    const statDelivery = document.getElementById("statDeliveryStatus");
    const fill = document.getElementById("simulationProgressFill");
    const label = document.getElementById("simulationProgressText");
    const banner = document.getElementById("currentEventBanner");
    const textEl = document.getElementById("currentEventText");
    const badgeEl = document.getElementById("currentEventBadge");

    if (summaryCard) summaryCard.style.display = "none";
    if (tbody) tbody.innerHTML = "";
    if (emptyState) emptyState.style.display = "block";
    if (terminalBody) terminalBody.innerHTML = `<div class="empty-state">Simulation reset. Ready to run.</div>`;

    if (statPackets) statPackets.textContent = "0";
    if (statFrames) statFrames.textContent = "0";
    if (statRetrans) statRetrans.textContent = "0";
    if (statDelivery) {
        statDelivery.textContent = "● READY";
        statDelivery.style.color = "var(--accent)";
    }

    if (fill) fill.style.width = "0%";
    if (label) label.textContent = "0%";
    if (banner) banner.className = "current-event-banner";
    if (textEl) textEl.textContent = "IDLE — Ready to run simulation";
    if (badgeEl) { badgeEl.className = "badge badge-muted"; badgeEl.textContent = "READY"; }

    fetchAndDisplayRoutePreview();
}

function formatEventMessage(evt) {
    switch (evt.event) {
        case "routing":
            return `Dijkstra: Optimal path calculated: ${evt.route.join(" ➔ ")} (Cost: ${evt.route_cost}, Hops: ${evt.hop_count})`;
        case "packet_created":
            return `Network: Packet [${evt.packet_id ? evt.packet_id.substring(0, 8) : 'PKT'}] created with payload "${evt.payload}"`;
        case "frame_created":
            return `DataLink: Frame F${evt.sequence_number} encapsulated with payload "${evt.payload}"`;
        case "crc_calculated":
            return `CRC-8: Calculated polynomial remainder for Frame F${evt.sequence_number} = 0x${evt.crc.toString(16).toUpperCase()}`;
        case "transmission":
            return `Physical: Transmitted Frame F${evt.sequence_number} over transmission link (${evt.status})`;
        case "crc_verification":
            return `CRC Check: Destination verified Frame F${evt.sequence_number} CRC is ${evt.is_valid ? 'VALID ✓' : 'INVALID ✗'}`;
        case "failure":
            return `Impairment: Simulated frame drop / corruption on Frame F${evt.sequence_number} (${evt.reason})`;
        case "retransmission":
            return `Go-Back-N: Retransmitting unacknowledged Frame F${evt.sequence_number} (Attempt #${evt.attempt || 1})`;
        case "acknowledgement":
            return `ARQ: Cumulative ACK received for Frame F${evt.sequence_number}`;
        case "out_of_order_discard":
        case "discarded_out_of_order":
            return `Receiver: Discarded Frame F${evt.sequence_number} (Received out of sequence order)`;
        case "delivery":
            return `Transport: Entire packet payload successfully reconstructed and delivered to destination.`;
        default:
            return JSON.stringify(evt);
    }
}

// ============================================================================
// 6. Node Detail Modal Inspection
// ============================================================================

async function openNodeModal(nodeName) {
    const modal = document.getElementById("nodeModal");
    const title = document.getElementById("modalNodeTitle");
    const body = document.getElementById("modalNodeBody");
    if (!modal || !title || !body) return;

    title.textContent = `Airport Node: ${nodeName}`;
    body.innerHTML = `<div class="spinner"></div> Loading node telemetry...`;
    modal.classList.add("open");

    try {
        const nodeRes = await apiGet(`/api/network/node/${encodeURIComponent(nodeName)}`);
        const node = nodeRes.node;

        let connectionsHtml = "";
        if (node.neighbors && node.neighbors.length > 0) {
            connectionsHtml = node.neighbors
                .map(n => `<span class="badge badge-accent">${n.destination || n.neighbor} (Cost: ${n.cost || n.weight})</span>`)
                .join(" ");
        } else {
            connectionsHtml = `<span style="color:var(--text-dim);">No connections</span>`;
        }

        body.innerHTML = `
            <div class="detail-row">
                <span class="detail-label">Node Identifier:</span>
                <span class="detail-value">${node.name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Department Role:</span>
                <span class="detail-value">${node.role || "Operational Facility"}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">IP Address:</span>
                <span class="detail-value"><code>${node.ip || "10.0.0.x"}</code></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Direct Neighbors:</span>
                <span class="detail-value" style="display:flex; gap:0.35rem; flex-wrap:wrap;">${connectionsHtml}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Hardware Health:</span>
                <span class="detail-value" style="color:var(--success);">● NORMAL / OPERATIONAL</span>
            </div>
        `;
    } catch (err) {
        body.innerHTML = `<div style="color:var(--danger);">Failed to load node information.</div>`;
    }
}

function closeNodeModal() {
    const modal = document.getElementById("nodeModal");
    if (modal) modal.classList.remove("open");
}

function setupMobileSidebar() {
    const toggleBtn = document.getElementById("sidebarToggleBtn");
    const sidebar = document.querySelector(".sidebar");
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });
    }
}

async function checkInitialState() {
    try {
        const stateRes = await apiGet("/api/simulation/state");
        if (stateRes.state && stateRes.state.state !== "initialized") {
            const summaryRes = await apiGet("/api/analytics/summary");
            if (summaryRes.summary && summaryRes.summary.total_frames) {
                const statPackets = document.getElementById("statPacketsCount");
                const statFrames = document.getElementById("statFramesCount");
                const statRetrans = document.getElementById("statRetransCount");
                const statDelivery = document.getElementById("statDeliveryStatus");

                if (statPackets) statPackets.textContent = 1;
                if (statFrames) statFrames.textContent = summaryRes.summary.total_frames;
                if (statRetrans) statRetrans.textContent = summaryRes.summary.retransmission_count || summaryRes.summary.retransmissions || 0;
                if (statDelivery) {
                    const isDel = summaryRes.summary.delivery_successful;
                    statDelivery.textContent = isDel ? "● DELIVERED" : "● FAILED";
                    statDelivery.style.color = isDel ? "var(--success)" : "var(--danger)";
                }
            }
        }
    } catch (e) {
        // Safe on initial blank launch
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

document.addEventListener("DOMContentLoaded", async () => {
    setupMobileSidebar();
    await loadTopologyAndNodes();
    setupFormHandlers();
    await checkInitialState();
});
