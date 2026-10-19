/**
 * AeroNetGuard Interactive Network Topology & Packet Transit Animator
 * Light Enterprise Theme
 */

class NetworkCanvas {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');

        // Canonical Node Positions (normalized for 800x400 canvas)
        this.nodes = {
            "Control Tower": { x: 400, y: 70, color: "#2563EB", icon: "🗼" },
            "Check-in": { x: 180, y: 200, color: "#2563EB", icon: "🧳" },
            "Security": { x: 620, y: 200, color: "#2563EB", icon: "🛡️" },
            "Baggage": { x: 250, y: 340, color: "#16A34A", icon: "📦" },
            "Emergency Services": { x: 550, y: 340, color: "#DC2626", icon: "🚑" }
        };

        this.connections = [
            { source: "Control Tower", destination: "Check-in", weight: 2 },
            { source: "Control Tower", destination: "Security", weight: 3 },
            { source: "Check-in", destination: "Baggage", weight: 2 },
            { source: "Security", destination: "Emergency Services", weight: 2 },
            { source: "Baggage", destination: "Emergency Services", weight: 4 }
        ];

        this.activeRoute = [];
        this.activePacket = null; // { from, to, progress, status }

        this.resize();
        this.startAnimationLoop();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.scaleX = rect.width / 800;
        this.scaleY = rect.height / 400;
    }

    setActiveRoute(routeNodes) {
        this.activeRoute = routeNodes || [];
    }

    animatePacket(fromNode, toNode, status = "normal", callback = null) {
        this.activePacket = {
            from: fromNode,
            to: toNode,
            progress: 0.0,
            status: status,
            callback: callback
        };
    }

    startAnimationLoop() {
        const render = () => {
            this.draw();
            requestAnimationFrame(render);
        };
        requestAnimationFrame(render);
    }

    draw() {
        if (!this.ctx) return;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // 1. Draw Connections (Links)
        this.connections.forEach(conn => {
            const src = this.nodes[conn.source];
            const dst = this.nodes[conn.destination];
            if (!src || !dst) return;

            const isRouteEdge = this.isEdgeInRoute(conn.source, conn.destination);

            this.ctx.beginPath();
            this.ctx.moveTo(src.x * this.scaleX, src.y * this.scaleY);
            this.ctx.lineTo(dst.x * this.scaleX, dst.y * this.scaleY);
            this.ctx.lineWidth = isRouteEdge ? 3.5 : 2;
            this.ctx.strokeStyle = isRouteEdge ? "#2563EB" : "#CBD5E1";
            if (isRouteEdge) {
                this.ctx.shadowColor = "rgba(37, 99, 235, 0.4)";
                this.ctx.shadowBlur = 8;
            } else {
                this.ctx.shadowBlur = 0;
            }
            this.ctx.stroke();
            this.ctx.shadowBlur = 0;

            // Draw Link Weight Label (White circular pill)
            const midX = ((src.x + dst.x) / 2) * this.scaleX;
            const midY = ((src.y + dst.y) / 2) * this.scaleY;

            this.ctx.fillStyle = "#FFFFFF";
            this.ctx.beginPath();
            this.ctx.arc(midX, midY, 12, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.strokeStyle = isRouteEdge ? "#2563EB" : "#CBD5E1";
            this.ctx.lineWidth = 1.5;
            this.ctx.stroke();

            this.ctx.fillStyle = isRouteEdge ? "#2563EB" : "#0F172A";
            this.ctx.font = "bold 11px 'JetBrains Mono', monospace";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.fillText(conn.weight.toString(), midX, midY);
        });

        // 2. Draw Packet Particles in Transit
        if (this.activePacket) {
            const p = this.activePacket;
            const src = this.nodes[p.from];
            const dst = this.nodes[p.to];
            if (src && dst) {
                p.progress += 0.02;
                if (p.progress > 1.0) p.progress = 1.0;

                const currX = (src.x + (dst.x - src.x) * p.progress) * this.scaleX;
                const currY = (src.y + (dst.y - src.y) * p.progress) * this.scaleY;

                this.ctx.beginPath();
                this.ctx.arc(currX, currY, 8, 0, Math.PI * 2);
                if (p.status === "corrupted") {
                    this.ctx.fillStyle = "#DC2626";
                    this.ctx.shadowColor = "rgba(220, 38, 38, 0.5)";
                } else if (p.status === "dropped") {
                    this.ctx.fillStyle = "#D97706";
                    this.ctx.shadowColor = "rgba(217, 119, 6, 0.5)";
                } else {
                    this.ctx.fillStyle = "#16A34A";
                    this.ctx.shadowColor = "rgba(22, 163, 74, 0.5)";
                }
                this.ctx.shadowBlur = 10;
                this.ctx.fill();
                this.ctx.shadowBlur = 0;

                if (p.progress >= 1.0) {
                    if (p.callback) p.callback();
                    this.activePacket = null;
                }
            }
        }

        // 3. Draw Airport Department Nodes
        Object.entries(this.nodes).forEach(([name, node]) => {
            const nx = node.x * this.scaleX;
            const ny = node.y * this.scaleY;
            const isInRoute = this.activeRoute.includes(name);

            // Node Circle
            this.ctx.beginPath();
            this.ctx.arc(nx, ny, 28, 0, Math.PI * 2);
            this.ctx.fillStyle = isInRoute ? "#EFF6FF" : "#FFFFFF";
            this.ctx.strokeStyle = isInRoute ? "#2563EB" : "#94A3B8";
            this.ctx.lineWidth = isInRoute ? 3.5 : 2;
            if (isInRoute) {
                this.ctx.shadowColor = "rgba(37, 99, 235, 0.35)";
                this.ctx.shadowBlur = 10;
            } else {
                this.ctx.shadowColor = "rgba(15, 23, 42, 0.08)";
                this.ctx.shadowBlur = 6;
            }
            this.ctx.fill();
            this.ctx.stroke();
            this.ctx.shadowBlur = 0;

            // Icon & Text
            this.ctx.font = "16px sans-serif";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.fillText(node.icon, nx, ny - 2);

            this.ctx.fillStyle = isInRoute ? "#2563EB" : "#0F172A";
            this.ctx.font = "600 12px 'Inter', sans-serif";
            this.ctx.fillText(name, nx, ny + 42);
        });
    }

    isEdgeInRoute(u, v) {
        if (this.activeRoute.length < 2) return false;
        for (let i = 0; i < this.activeRoute.length - 1; i++) {
            const r1 = this.activeRoute[i];
            const r2 = this.activeRoute[i + 1];
            if ((r1 === u && r2 === v) || (r1 === v && r2 === u)) return true;
        }
        return false;
    }
}
