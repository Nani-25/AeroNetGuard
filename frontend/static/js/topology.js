/**
 * AeroNetGuard - Network Topology & Route Finder Controller
 * Communicates with /api/network/topology, /api/network/nodes, /api/network/route
 */

const NODE_COORDINATES = {
    "Control Tower": { x: 300, y: 70 },
    "Check-in": { x: 130, y: 190 },
    "Security": { x: 470, y: 190 },
    "Baggage": { x: 180, y: 330 },
    "Emergency Services": { x: 420, y: 330 },
};

let topologyData = null;

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
    await loadTopologyAndNodes();
    setupRouteFinder();
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

async function loadTopologyAndNodes() {
    try {
        const topRes = await apiGet("/api/network/topology");
        topologyData = topRes;
        renderSVGTopology(topRes.nodes, topRes.connections);
        renderConnectionsTable(topRes.connections);

        const nodeRes = await apiGet("/api/network/nodes");
        populateNodeSelects(nodeRes.nodes);
        renderNodesList(topRes.nodes, topRes.connections);
    } catch (err) {
        console.error("Failed to load topology:", err);
        showAlert("Failed to load topology from server.");
    }
}

function populateNodeSelects(nodes) {
    const srcSelect = document.getElementById("routeSourceSelect");
    const dstSelect = document.getElementById("routeDestSelect");
    if (!srcSelect || !dstSelect) return;

    srcSelect.innerHTML = "";
    dstSelect.innerHTML = "";

    nodes.forEach(node => {
        srcSelect.add(new Option(node, node));
        dstSelect.add(new Option(node, node));
    });

    srcSelect.value = "Security";
    dstSelect.value = "Baggage";
}

function renderSVGTopology(nodes, connections, highlightedPath = []) {
    const svg = document.getElementById("topologySvgLarge");
    if (!svg) return;

    svg.innerHTML = "";

    // 1. Connection lines
    const edgesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    edgesGroup.setAttribute("class", "edges-group");

    connections.forEach(conn => {
        const p1 = NODE_COORDINATES[conn.source];
        const p2 = NODE_COORDINATES[conn.destination];
        if (!p1 || !p2) return;

        const isHighlighted = isEdgeInPath(conn.source, conn.destination, highlightedPath);

        const edgeElementId = `edge-${[conn.source, conn.destination].map(s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-")).sort().join("-")}`;
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

        // Edge cost badge
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2;

        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("x", midX - 12);
        bg.setAttribute("y", midY - 10);
        bg.setAttribute("width", 24);
        bg.setAttribute("height", 20);
        bg.setAttribute("class", "topology-cost-bg");
        edgesGroup.appendChild(bg);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", midX);
        text.setAttribute("y", midY + 4);
        text.setAttribute("class", "topology-edge-cost");
        text.textContent = conn.cost;
        edgesGroup.appendChild(text);
    });

    svg.appendChild(edgesGroup);

    // 2. Nodes
    const nodesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    nodesGroup.setAttribute("class", "nodes-group");

    nodes.forEach(nodeItem => {
        const nodeName = typeof nodeItem === "string" ? nodeItem : nodeItem.name;
        const pos = NODE_COORDINATES[nodeName];
        if (!pos) return;

        const isInPath = highlightedPath.includes(nodeName);
        const nodeElementId = `node-${nodeName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "topology-node-group");
        g.setAttribute("id", nodeElementId);
        g.setAttribute("tabindex", "0");
        g.setAttribute("role", "button");
        g.setAttribute("aria-label", `Select node ${nodeName}`);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", 28);
        circle.setAttribute("class", `node-circle ${isInPath ? "active" : ""}`);
        g.appendChild(circle);

        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("cx", pos.x);
        dot.setAttribute("cy", pos.y - 4);
        dot.setAttribute("r", 6);
        dot.setAttribute("class", "node-status-dot");
        g.appendChild(dot);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", pos.x);
        label.setAttribute("y", pos.y + 44);
        label.setAttribute("class", "node-label");
        label.textContent = nodeName;
        g.appendChild(label);

        g.addEventListener("click", () => inspectNode(nodeName));
        nodesGroup.appendChild(g);
    });

    svg.appendChild(nodesGroup);
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

function inspectNode(nodeName) {
    const nameEl = document.getElementById("inspectNodeName");
    const neighborsEl = document.getElementById("inspectNodeNeighbors");
    const countEl = document.getElementById("inspectNodeCount");
    const statusEl = document.getElementById("inspectNodeStatus");

    if (nameEl) nameEl.textContent = nodeName;

    const neighbors = [];
    if (topologyData && topologyData.connections) {
        topologyData.connections.forEach(conn => {
            if (conn.source === nodeName) neighbors.push(`${conn.destination} (weight: ${conn.cost})`);
            else if (conn.destination === nodeName) neighbors.push(`${conn.source} (weight: ${conn.cost})`);
        });
    }

    if (neighborsEl) neighborsEl.textContent = neighbors.join(", ") || "None";
    if (countEl) countEl.textContent = neighbors.length;
    if (statusEl) statusEl.textContent = "ONLINE";
}

function renderNodesList(nodes, connections) {
    const container = document.getElementById("nodesListContainer");
    if (!container) return;

    container.innerHTML = "";
    nodes.forEach(nodeItem => {
        const nodeName = typeof nodeItem === "string" ? nodeItem : nodeItem.name;
        const count = connections.filter(c => c.source === nodeName || c.destination === nodeName).length;

        const card = document.createElement("div");
        card.className = "node-info-pill";
        card.innerHTML = `
            <div>
                <strong>${escapeHtml(nodeName)}</strong>
                <span style="font-size:0.75rem; color:var(--text-dim); display:block;">${count} links</span>
            </div>
            <span class="badge badge-success">ONLINE</span>
        `;
        card.addEventListener("click", () => inspectNode(nodeName));
        container.appendChild(card);
    });

    // Inspect first node by default
    if (nodes.length > 0) {
        inspectNode(typeof nodes[0] === "string" ? nodes[0] : nodes[0].name);
    }
}

function renderConnectionsTable(connections) {
    const tbody = document.getElementById("connectionsTableBody");
    if (!tbody) return;

    tbody.innerHTML = "";
    connections.forEach(conn => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${escapeHtml(conn.source)}</strong></td>
            <td><strong>${escapeHtml(conn.destination)}</strong></td>
            <td><span class="badge badge-accent">${conn.cost}</span></td>
            <td><span class="badge badge-success">Bidirectional</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function setupRouteFinder() {
    const btn = document.getElementById("findRouteBtn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
        const src = document.getElementById("routeSourceSelect").value;
        const dst = document.getElementById("routeDestSelect").value;

        if (!src || !dst) {
            showAlert("Please select a source and destination node.");
            return;
        }

        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> Finding Route...`;

        try {
            const data = await apiGet(`/api/network/route?source=${encodeURIComponent(src)}&destination=${encodeURIComponent(dst)}`);

            const routePath = Array.isArray(data.path) ? data.path : (data.route?.path || (Array.isArray(data.route) ? data.route : []));
            const routeCost = data.total_cost ?? data.route?.total_cost ?? data.route_cost ?? "--";
            const hopCount = data.hop_count ?? data.route?.hop_count ?? "--";

            if (resultContainer) resultContainer.style.display = "block";
            if (pathText) pathText.textContent = routePath.join(" → ");
            if (costEl) costEl.textContent = routeCost;
            if (hopsEl) hopsEl.textContent = hopCount;

            // Highlight path on SVG
            if (topologyData) {
                renderSVGTopology(topologyData.nodes, topologyData.connections, routePath);
            }
        } catch (err) {
            console.error("Route calculation error:", err);
            showAlert(err.message || "Failed to calculate shortest path.");
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<span>🔍 Find Route</span>`;
        }
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
