/**
 * AeroNetGuard - Packet & Frame Monitor Controller
 * Fetches real simulation telemetry from /api/simulation/state, /api/simulation/frames, /api/simulation/events
 */

async function apiGet(url) {
    const res = await fetch(url);
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

document.addEventListener("DOMContentLoaded", async () => {
    setupMobileSidebar();
    setupRefreshButton();
    await loadMonitorData();
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

function setupRefreshButton() {
    const refreshBtn = document.getElementById("refreshMonitorBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = `<span class="spinner"></span> Refreshing...`;
            await loadMonitorData();
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<span>🔄 Refresh Telemetry</span>`;
        });
    }
}

async function loadMonitorData() {
    const emptyState = document.getElementById("monitorEmptyState");
    const contentSection = document.getElementById("monitorContentSection");

    try {
        const stateRes = await apiGet("/api/simulation/state");
        const simState = stateRes.state;

        // If no active simulation has completed or run
        if (!simState || simState.state === "initialized" || !simState.packet) {
            if (emptyState) emptyState.style.display = "block";
            if (contentSection) contentSection.style.display = "none";
            return;
        }

        // Active simulation exists
        if (emptyState) emptyState.style.display = "none";
        if (contentSection) contentSection.style.display = "block";

        renderPacketDetails(simState);

        const framesRes = await apiGet("/api/simulation/frames");
        renderFramesTable(framesRes.frames);

        const eventsRes = await apiGet("/api/simulation/events");
        renderEventsLog(eventsRes.events);

    } catch (err) {
        console.error("Failed to load monitor data:", err);
        showAlert("Failed to load packet monitor telemetry.");
        if (emptyState) emptyState.style.display = "block";
        if (contentSection) contentSection.style.display = "none";
    }
}

function renderPacketDetails(state) {
    const pkt = state.packet;
    const pktIdEl = document.getElementById("pktId");
    const pktSrcEl = document.getElementById("pktSource");
    const pktDstEl = document.getElementById("pktDest");
    const pktPayloadEl = document.getElementById("pktPayload");
    const pktRouteEl = document.getElementById("pktRoute");
    const pktCostEl = document.getElementById("pktCost");
    const pktHopsEl = document.getElementById("pktHops");
    const pktStatusEl = document.getElementById("pktDeliveryStatus");

    if (pktIdEl) pktIdEl.textContent = pkt.packet_id || "--";
    if (pktSrcEl) pktSrcEl.textContent = pkt.source || "--";
    if (pktDstEl) pktDstEl.textContent = pkt.destination || "--";
    if (pktPayloadEl) pktPayloadEl.textContent = pkt.payload || "--";
    if (pktRouteEl && state.route) pktRouteEl.textContent = state.route.join(" ➔ ");
    if (pktCostEl) pktCostEl.textContent = state.route_cost;
    if (pktHopsEl) pktHopsEl.textContent = state.hop_count;

    if (pktStatusEl) {
        const isDelivered = state.delivery_successful;
        pktStatusEl.className = `badge ${isDelivered ? "badge-success" : "badge-danger"}`;
        pktStatusEl.textContent = isDelivered ? "DELIVERED" : "FAILED";
    }
}

function renderFramesTable(frames) {
    const tbody = document.getElementById("monitorFramesBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!frames || frames.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-dim);">No frames available.</td></tr>`;
        return;
    }

    frames.forEach(frame => {
        const tr = document.createElement("tr");
        const crcStatusClass = frame.crc_status === "valid" ? "badge-success" : (frame.crc_status === "invalid" ? "badge-danger" : "badge-muted");
        const statusClass = frame.status === "acknowledged" ? "badge-success" : (frame.status === "failed" ? "badge-danger" : (frame.status === "retransmitted" ? "badge-warning" : "badge-accent"));

        tr.innerHTML = `
            <td><strong>F${frame.sequence_number}</strong></td>
            <td><code>${escapeHtml(frame.payload)}</code></td>
            <td><code>0x${(frame.crc !== null && frame.crc !== undefined) ? frame.crc.toString(16).toUpperCase().padStart(2, '0') : '--'}</code></td>
            <td><span class="badge ${crcStatusClass}">${frame.crc_status}</span></td>
            <td><span class="badge ${statusClass}">${frame.status}</span></td>
            <td>${frame.retransmission_count}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderEventsLog(events) {
    const container = document.getElementById("monitorEventLog");
    if (!container) return;

    container.innerHTML = "";

    if (!events || events.length === 0) {
        container.innerHTML = `<div class="empty-state">No events recorded.</div>`;
        return;
    }

    events.forEach(evt => {
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

        row.innerHTML = `
            <span class="log-tag ${tagClass}">${tagText}</span>
            <span class="log-msg">${escapeHtml(formatEventMessage(evt))}</span>
        `;
        container.appendChild(row);
    });

    container.scrollTop = container.scrollHeight;
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
