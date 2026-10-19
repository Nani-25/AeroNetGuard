/**
 * AeroNetGuard - Analytics & Network Performance Dashboard Controller (Step 13)
 *
 * Fetches real simulation analytics from:
 *   - /api/analytics/summary
 *   - /api/analytics/frames
 *   - /api/analytics/timeline
 *   - /api/analytics/protocol
 *
 * Renders KPI cards, protocol metrics, SVG/CSS visual analytics,
 * frame performance tables, event timeline, and route analysis.
 */

// API Helpers
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
    await loadAnalytics();
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
    const refreshBtn = document.getElementById("refreshAnalyticsBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = `<span class="spinner"></span> Refreshing...`;
            await loadAnalytics();
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<span>↻ Refresh Analytics</span>`;
        });
    }
}

async function loadAnalytics() {
    const emptyState = document.getElementById("analyticsEmptyState");
    const contentSection = document.getElementById("analyticsContentSection");

    try {
        const res = await apiGet("/api/analytics/summary");
        const a = res.analytics || res.summary;

        // If no simulation has been run
        if (!a || (a.frames && a.frames.total === 0) || a.total_frames === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (contentSection) contentSection.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (contentSection) contentSection.style.display = "block";

        // 1. Render Top KPI Cards
        renderTopKpis(a);

        // 2. Render Secondary Row
        renderSecondaryKpis(a);

        // 3. Render Visual Charts
        renderVisualCharts(a);

        // 4. Render Protocol Stack Breakdown
        renderProtocolBreakdown(a);

        // 5. Render Frame Performance Table
        await renderFramesTable();

        // 6. Render Simulation Event Timeline
        await renderTimeline();

        // 7. Render Route Analysis
        renderRouteAnalysis(a);

    } catch (err) {
        console.error("Failed to load analytics:", err);
        showAlert("Failed to load network analytics from server.");
        if (emptyState) emptyState.style.display = "block";
        if (contentSection) contentSection.style.display = "none";
    }
}

function renderTopKpis(a) {
    const totalFrames = a.frames?.total ?? a.total_frames ?? 0;
    const successfulFrames = a.frames?.successful ?? a.successful_frames ?? 0;
    const failedFrames = a.frames?.failed ?? a.failed_frames ?? 0;
    const retransCount = a.retransmission?.count ?? a.retransmission_count ?? 0;
    const crcErrors = a.crc?.invalid ?? a.crc_invalid_count ?? 0;
    const crcErrorRate = a.crc?.error_rate ?? 0.0;

    setText("kpiTotalFrames", totalFrames);
    setText("kpiSuccessfulFrames", successfulFrames);
    setText("kpiFailedFrames", failedFrames);
    setText("kpiRetransmissions", retransCount);
    setText("kpiCrcErrors", crcErrors);
    setText("kpiCrcErrorRate", `Error rate: ${(crcErrorRate * 100).toFixed(1)}%`);
}

function renderSecondaryKpis(a) {
    const txAttempts = a.transmission?.attempts ?? a.total_transmission_attempts ?? 0;
    const txSuccessRate = a.transmission?.success_rate ?? 0.0;
    const ackCount = a.acknowledgements?.count ?? a.ack_count ?? 0;
    const routeCost = a.route?.cost ?? a.route_cost ?? 0;
    const hopCount = a.route?.hop_count ?? a.hop_count ?? 0;

    setText("kpiTxAttempts", txAttempts);
    setText("kpiTxSuccessRate", `Success rate: ${(txSuccessRate * 100).toFixed(1)}%`);
    setText("kpiAckCount", ackCount);
    setText("kpiRouteCost", routeCost);
    setText("kpiHopCount", hopCount);
}

function renderVisualCharts(a) {
    // --- Chart 1: Transmission Breakdown ---
    const txAttempts = a.transmission?.attempts ?? 1;
    const txSuccess = a.transmission?.successful ?? 0;
    const txFailed = a.transmission?.failed ?? 0;
    const successPct = txAttempts > 0 ? Math.round((txSuccess / txAttempts) * 100) : 0;
    const failedPct = txAttempts > 0 ? (100 - successPct) : 0;

    setWidth("chartTxSuccessBar", `${successPct}%`);
    setWidth("chartTxFailedBar", `${failedPct}%`);
    setText("chartTxSuccessVal", txSuccess);
    setText("chartTxFailedVal", txFailed);
    setText("chartTxRatioLabel", `${successPct}% Pass`);

    const deliveryEff = a.efficiency?.frame_delivery_efficiency ?? 0.0;
    setText("chartDeliveryEff", `${(deliveryEff * 100).toFixed(1)}%`);

    // --- Chart 2: CRC Integrity ---
    const crcChecked = a.crc?.checked ?? 0;
    const crcValid = a.crc?.valid ?? 0;
    const crcInvalid = a.crc?.invalid ?? 0;
    const crcValidPct = crcChecked > 0 ? Math.round((crcValid / crcChecked) * 100) : 100;
    const crcInvalidPct = 100 - crcValidPct;

    setWidth("chartCrcValidBar", `${crcValidPct}%`);
    setWidth("chartCrcInvalidBar", `${crcInvalidPct}%`);
    setText("chartCrcValidVal", crcValid);
    setText("chartCrcInvalidVal", crcInvalid);
    setText("chartCrcTotalVal", crcChecked);
    setText("chartCrcErrRateVal", `${((a.crc?.error_rate ?? 0) * 100).toFixed(1)}%`);
    setText("chartCrcRatioLabel", crcInvalid === 0 ? "100% Valid" : `${crcValidPct}% Valid`);

    // --- Chart 3: Retransmission Overhead ---
    const totalFrames = a.frames?.total ?? 1;
    const affectedFrames = a.retransmission?.affected_frames ?? 0;
    const retransCount = a.retransmission?.count ?? 0;
    const unaffectedFrames = Math.max(0, totalFrames - affectedFrames);
    const unaffectedPct = totalFrames > 0 ? Math.round((unaffectedFrames / totalFrames) * 100) : 100;
    const affectedPct = 100 - unaffectedPct;

    setWidth("chartRetransOriginalBar", `${unaffectedPct}%`);
    setWidth("chartRetransBar", `${affectedPct}%`);
    setText("chartRetransAffectedVal", affectedFrames);
    setText("chartRetransTotalVal", retransCount);
    setText("chartRetransAvgVal", a.retransmission?.average_per_affected_frame ?? 0.0);
    setText("chartRetransPctVal", `${((a.retransmission?.rate ?? 0) * 100).toFixed(1)}%`);
    setText("chartRetransRateBadge", `${retransCount} Retx`);
}

function renderProtocolBreakdown(a) {
    const proto = a.protocol || {};
    const framingTotal = proto.framing?.total_frames ?? a.frames?.total ?? 0;
    const crcErrorRate = proto.crc?.error_rate ?? a.crc?.error_rate ?? 0.0;
    const crcValidRate = (100 - (crcErrorRate * 100)).toFixed(1);
    const windowSize = proto.sliding_window?.window_size ?? a.window_size ?? 3;
    const gbnRetrans = proto.go_back_n?.retransmissions ?? a.retransmission?.count ?? 0;

    setText("protoFramingCount", `${framingTotal} Frames`);
    setText("protoCrcValidRate", `${crcValidRate}% Valid`);
    setText("protoWindowSize", `N = ${windowSize}`);
    setText("protoGbnRetrans", `${gbnRetrans} Retransmissions`);
}

async function renderFramesTable() {
    const tbody = document.getElementById("analyticsFramesBody");
    if (!tbody) return;

    try {
        const res = await apiGet("/api/analytics/frames");
        const frames = res.frames || [];

        tbody.innerHTML = "";
        if (frames.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-dim);">No frame analytics available.</td></tr>`;
            return;
        }

        frames.forEach(f => {
            const tr = document.createElement("tr");

            const crcStatusClass = f.crc_status === "valid" ? "badge-success" : (f.crc_status === "invalid" ? "badge-danger" : "badge-muted");
            const statusClass = f.status === "acknowledged" ? "badge-success" : (f.status === "failed" ? "badge-danger" : "badge-accent");

            const crcHex = (f.crc !== null && f.crc !== undefined)
                ? (typeof f.crc === "number" ? `0x${f.crc.toString(16).toUpperCase().padStart(2, '0')}` : f.crc)
                : "--";

            tr.innerHTML = `
                <td><strong>F${f.sequence_number}</strong></td>
                <td><code>${escapeHtml(f.payload)}</code></td>
                <td><code>${crcHex}</code> <span class="badge ${crcStatusClass}" style="margin-left:0.35rem;">${f.crc_status}</span></td>
                <td><span class="badge ${statusClass}">${f.status}</span></td>
                <td><strong>${f.transmission_attempts}</strong></td>
                <td><span class="${f.retransmission_count > 0 ? 'badge badge-warning' : ''}">${f.retransmission_count}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to render frames table:", e);
    }
}

async function renderTimeline() {
    const container = document.getElementById("analyticsTimelineContainer");
    if (!container) return;

    try {
        const res = await apiGet("/api/analytics/timeline");
        const timeline = res.timeline || [];

        container.innerHTML = "";
        if (timeline.length === 0) {
            container.innerHTML = `<div class="empty-state">No timeline events recorded.</div>`;
            return;
        }

        timeline.forEach(item => {
            const row = document.createElement("div");
            row.className = "log-entry";

            let tagClass = "tag-tx";
            let tagText = `[${(item.event_type || 'EVENT').toUpperCase()}]`;

            switch (item.event_type) {
                case "routing": tagClass = "tag-routing"; tagText = "[ROUTING]"; break;
                case "packet_created": tagClass = "tag-packet"; tagText = "[PACKET]"; break;
                case "frame_created": tagClass = "tag-framing"; tagText = "[FRAMING]"; break;
                case "crc_calculated": tagClass = "tag-crc"; tagText = "[CRC-GEN]"; break;
                case "crc_verification": tagClass = "tag-crc"; tagText = "[CRC-CHK]"; break;
                case "transmission": tagClass = item.status === "failed" ? "tag-fail" : "tag-tx"; tagText = "[TX]"; break;
                case "failure": tagClass = "tag-fail"; tagText = "[FAIL]"; break;
                case "retransmission": tagClass = "tag-gbn"; tagText = "[GBN-RETRY]"; break;
                case "acknowledgement": tagClass = "tag-ack"; tagText = "[ACK]"; break;
                case "discarded_out_of_order": tagClass = "tag-fail"; tagText = "[DISCARD]"; break;
                case "delivery": tagClass = "tag-delivery"; tagText = "[DELIVERY]"; break;
            }

            const stepIndexStr = String(item.event_index).padStart(2, '0');

            row.innerHTML = `
                <span style="color:var(--text-dim); margin-right:0.4rem; font-family:var(--font-mono); font-size:0.75rem;">#${stepIndexStr}</span>
                <span class="log-tag ${tagClass}">${tagText}</span>
                <span class="log-msg">${escapeHtml(item.description || JSON.stringify(item.details))}</span>
            `;
            container.appendChild(row);
        });
    } catch (e) {
        console.error("Failed to render timeline:", e);
    }
}

function renderRouteAnalysis(a) {
    const route = a.route || {};
    setText("routeSourceVal", route.source || "--");
    setText("routeDestVal", route.destination || "--");
    setText("routeCostVal", route.cost ?? 0);
    setText("routeHopsVal", route.hop_count ?? 0);

    const isDelivered = a.simulation?.delivery_successful ?? a.delivery_successful ?? false;
    const badge = document.getElementById("routeDeliveryBadge");
    if (badge) {
        badge.className = isDelivered ? "badge badge-success" : "badge badge-danger";
        badge.textContent = isDelivered ? "DELIVERED" : "FAILED";
    }

    const container = document.getElementById("routePathTags");
    if (container && route.path) {
        container.innerHTML = "";
        route.path.forEach((node, idx) => {
            const tag = document.createElement("span");
            tag.className = "route-node-tag";
            tag.textContent = node;
            container.appendChild(tag);

            if (idx < route.path.length - 1) {
                const arrow = document.createElement("span");
                arrow.className = "route-arrow";
                arrow.textContent = "➔";
                container.appendChild(arrow);
            }
        });
    }
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setWidth(id, val) {
    const el = document.getElementById(id);
    if (el) el.style.width = val;
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
