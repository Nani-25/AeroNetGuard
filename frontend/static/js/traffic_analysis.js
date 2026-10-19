/**
 * AeroNetGuard - Traffic Analysis & Wireshark PCAP Controller
 *
 * Fetches captured simulation packets, displays interactive telemetry and
 * handles on-demand PCAP binary file generation and download.
 */

document.addEventListener("DOMContentLoaded", () => {
    initTrafficAnalysis();
});

function initTrafficAnalysis() {
    bindActionButtons();
    loadTrafficData();
}

function bindActionButtons() {
    const refreshBtn = document.getElementById("refreshTrafficBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = `<span>↻ Refreshing...</span>`;
            await loadTrafficData();
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<span>↻ Refresh</span>`;
        });
    }

    const generateBtn = document.getElementById("generatePcapActionBtn");
    const topGenerateBtn = document.getElementById("topGeneratePcapBtn");

    if (generateBtn) {
        generateBtn.addEventListener("click", () => triggerPcapExport());
    }
    if (topGenerateBtn) {
        topGenerateBtn.addEventListener("click", () => triggerPcapExport());
    }
}

async function loadTrafficData() {
    const emptyState = document.getElementById("trafficEmptyState");
    const contentSection = document.getElementById("trafficContentSection");
    const statusBadge = document.getElementById("topCaptureStatus");

    try {
        const [sumRes, pktRes] = await Promise.all([
            fetch("/api/wireshark/summary").then(r => r.json()),
            fetch("/api/wireshark/packets").then(r => r.json()),
        ]);

        const summary = sumRes.summary || {};
        const packets = pktRes.packets || [];

        if (!packets.length && (!summary.packet_count || summary.packet_count === 0)) {
            if (emptyState) emptyState.style.display = "block";
            if (contentSection) contentSection.style.display = "none";
            if (statusBadge) {
                statusBadge.textContent = "No Simulation Data";
                statusBadge.className = "badge badge-warning";
            }
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (contentSection) contentSection.style.display = "block";
        if (statusBadge) {
            statusBadge.textContent = "Simulation Capture Ready";
            statusBadge.className = "badge badge-success";
        }

        renderSummaryKpis(summary, packets.length);
        renderTrafficTable(packets);

    } catch (err) {
        console.error("Failed to load traffic capture data:", err);
        if (emptyState) emptyState.style.display = "block";
        if (contentSection) contentSection.style.display = "none";
        if (statusBadge) {
            statusBadge.textContent = "Capture Service Error";
            statusBadge.className = "badge badge-danger";
        }
    }
}

function renderSummaryKpis(summary, packetCount) {
    const total = summary.packet_count ?? packetCount ?? 0;
    const frames = summary.frame_packets ?? 0;
    const acks = summary.ack_packets ?? 0;
    const retrans = summary.retransmission_packets ?? 0;
    const crcFails = summary.crc_failure_packets ?? 0;

    setText("kpiTotalPackets", total);
    setText("kpiFramePackets", frames);
    setText("kpiAckPackets", acks);
    setText("kpiRetransPackets", retrans);
    setText("kpiCrcFailPackets", crcFails);
    setText("trafficTableCount", total);
}

function renderTrafficTable(packets) {
    const tbody = document.getElementById("trafficTableBody");
    if (!tbody) return;

    if (!packets || packets.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; color: var(--text-dim); padding: 2rem;">
                    No packet records available.
                </td>
            </tr>
        `;
        return;
    }

    let rowsHtml = "";
    packets.forEach((p, idx) => {
        const typeBadge = getTypeBadge(p.event_type);
        const statusBadge = getStatusBadge(p.status);
        const crcLabel = p.crc !== null && p.crc !== undefined ? `0x${Number(p.crc).toString(16).toUpperCase()}` : "—";
        const crcBadge = p.crc_status === "valid"
            ? `<span style="color: var(--success); font-weight:600;">✓ Valid</span>`
            : p.crc_status === "invalid"
            ? `<span style="color: var(--danger); font-weight:600;">✗ Error</span>`
            : `<span style="color: var(--text-dim);">—</span>`;

        rowsHtml += `
            <tr>
                <td style="font-weight: 700; color: var(--text-primary);">${p.capture_id ?? (idx + 1)}</td>
                <td style="color: var(--text-dim); font-size: 0.8rem;">E#${p.event_index ?? idx}</td>
                <td><span class="badge badge-info" style="font-size:0.72rem;">${escapeHtml(p.frame_id ?? "N/A")}</span></td>
                <td>
                    <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(p.source ?? "")}</div>
                    <div style="font-size: 0.72rem; color: var(--text-dim);">${escapeHtml(p.source_ip ?? "")}</div>
                </td>
                <td>
                    <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(p.destination ?? "")}</div>
                    <div style="font-size: 0.72rem; color: var(--text-dim);">${escapeHtml(p.destination_ip ?? "")}</div>
                </td>
                <td style="text-align: center; font-weight: 600;">${p.sequence_number !== null && p.sequence_number !== undefined ? p.sequence_number : "—"}</td>
                <td>${typeBadge}</td>
                <td>${statusBadge}</td>
                <td>${crcBadge} <span style="font-size:0.75rem; color:var(--text-dim);">(${crcLabel})</span></td>
                <td style="text-align: center; color: ${p.retransmission_count > 0 ? "var(--warning)" : "var(--text-dim)"}; font-weight: 600;">
                    ${p.retransmission_count ?? 0}
                </td>
                <td>
                    <code style="font-size: 0.72rem; background: var(--bg-surface); padding: 0.2rem 0.4rem; border-radius: 4px; border: 1px solid var(--border); display: block; max-width: 320px; overflow-x: auto; white-space: nowrap;">
                        ${escapeHtml(p.raw_payload ?? "")}
                    </code>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

async function triggerPcapExport() {
    const filenameInput = document.getElementById("pcapFilenameInput");
    const generateBtn = document.getElementById("generatePcapActionBtn");
    const topGenerateBtn = document.getElementById("topGeneratePcapBtn");
    const downloadBtn = document.getElementById("downloadPcapActionBtn");
    const noticeBox = document.getElementById("pcapExportNotice");
    const noticeText = document.getElementById("pcapNoticeText");
    const statusBadge = document.getElementById("topCaptureStatus");

    let filename = filenameInput ? filenameInput.value.trim() : "aeronetguard_capture.pcap";
    if (!filename) filename = "aeronetguard_capture.pcap";

    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.innerHTML = `<span>⏳ Writing PCAP...</span>`;
    }
    if (topGenerateBtn) {
        topGenerateBtn.disabled = true;
    }

    try {
        const res = await fetch("/api/wireshark/capture", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: filename }),
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.error || "Failed to generate PCAP capture.");
        }

        if (statusBadge) {
            statusBadge.textContent = "PCAP Ready";
            statusBadge.className = "badge badge-success";
        }

        if (noticeBox && noticeText) {
            noticeBox.style.display = "block";
            noticeText.innerHTML = `
                <strong>✓ PCAP Successfully Generated:</strong>
                <code>${escapeHtml(data.filename)}</code> containing <strong>${data.packet_count}</strong> synthetic Ethernet/IPv4/UDP packets.
            `;
        }

        if (downloadBtn) {
            downloadBtn.style.display = "inline-flex";
            downloadBtn.href = data.download_url || `/api/wireshark/download/${encodeURIComponent(data.filename)}`;
            downloadBtn.setAttribute("download", data.filename);
        }

    } catch (err) {
        console.error("PCAP export error:", err);
        alert(err.message || "PCAP Export failed. Please ensure a simulation has been run.");
    } finally {
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = `<span>⚡ Generate PCAP</span>`;
        }
        if (topGenerateBtn) {
            topGenerateBtn.disabled = false;
        }
    }
}

function getTypeBadge(type) {
    switch (type) {
        case "FRAME":
            return `<span class="badge badge-info">FRAME</span>`;
        case "ACK":
            return `<span class="badge badge-success">ACK</span>`;
        case "RETRANSMISSION":
            return `<span class="badge badge-warning">RETRANS</span>`;
        case "CRC_FAILURE":
            return `<span class="badge badge-danger">CRC FAIL</span>`;
        case "ROUTE":
            return `<span class="badge badge-secondary">ROUTE</span>`;
        default:
            return `<span class="badge badge-secondary">${escapeHtml(type || "UNKNOWN")}</span>`;
    }
}

function getStatusBadge(status) {
    const s = String(status || "").toLowerCase();
    if (s === "success" || s === "acknowledged") {
        return `<span class="badge badge-success">SUCCESS</span>`;
    } else if (s === "failed" || s === "crc_invalid") {
        return `<span class="badge badge-danger">FAILURE</span>`;
    } else if (s === "retransmitted") {
        return `<span class="badge badge-warning">RETRANSMISSION</span>`;
    }
    return `<span class="badge badge-secondary">${escapeHtml(status || "PENDING")}</span>`;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
