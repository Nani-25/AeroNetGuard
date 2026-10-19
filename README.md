# AeroNetGuard: Airport Communication & Monitoring Network Simulator

## 1. Project Title
**AeroNetGuard: Airport Communication & Monitoring Network Simulator**

## 2. Project Description
AeroNetGuard is a modular, software-based computer networks simulation platform designed to model and simulate communication across critical airport functional departments. The system provides an educational and analytical environment to observe routing protocols, reliable data link transmission, flow control, error detection, error simulation, and real-time network telemetry without interfacing with physical or operational airport infrastructure.

## 3. Problem Statement
> "Design a simulated airport communication network connecting the control tower, security department, baggage system, check-in counters, and emergency services. Data should be transmitted reliably using framing, CRC, sliding-window flow control, and Go-Back-N. The system should simulate packet loss and transmission errors and provide visualization and network performance analysis."

## 4. Project Objective
- Model a realistic airport network topology connecting core airport nodes: Control Tower, Check-in, Security, Baggage, and Emergency Services.
- Implement shortest-path routing using Dijkstra's algorithm.
- Provide robust data link layer mechanisms including byte stuffing/framing and Cyclic Redundancy Check (CRC-32/CRC-CCITT) error detection.
- Simulate flow control and reliable transmission using Sliding Window and Go-Back-N (GBN) Automatic Repeat reQuest (ARQ).
- Introduce configurable network degradation such as packet corruption, drop/loss, and latency to observe recovery behaviors.
- Decouple the simulation engine from visualization, offering an interactive Flask web dashboard, animated packet tracing, and network performance analytics.
- Enable optional packet export and inspection compatible with Wireshark.

## 5. Main Networking Concepts
- **Network Topology & Graph Theory**: Representing airport nodes and bi-directional weighted links.
- **Shortest Path Routing**: Dijkstra's algorithm for optimal route selection based on link cost/latency.
- **Packet & Frame Encapsulation**: Separation of network-layer packets and data-link-layer frames.
- **Framing & Byte Stuffing**: Delimiting frame boundaries and escaping flags.
- **Error Detection**: Cyclic Redundancy Check (CRC) calculation and checksum verification.
- **Flow Control & ARQ**: Sliding Window protocol and Go-Back-N retransmission logic with sequence numbers, timeouts, and ACKs/NAKs.
- **Network Impairments**: Stochastic packet loss, bit flips, and corruption generators.
- **Telemetry & Metrics**: Throughput, packet delivery ratio (PDR), retransmission rates, and latency.

## 6. Planned Architecture
The project strictly separates core networking logic from the presentation tier:

```
Frontend (HTML5 / CSS / Vanilla JS Dashboard)
       ↓ (HTTP REST / WebSocket Events)
Flask Backend (API Routes & Orchestration)
       ↓
Simulation Engine (Event Loop & Node State)
       ↓
Networking Algorithms (Dijkstra, Framing, CRC, Sliding Window, GBN)
       ↓
Simulation Results & Analytics
       ↓
Flask API Response
       ↓
Frontend Visualization & Live Monitor
```

## 7. Technology Stack
- **Backend & Simulation**: Python 3.10+
- **Graph & Routing**: NetworkX
- **Web Framework**: Flask, Flask-CORS
- **Testing**: PyTest
- **Frontend Visualization**: HTML5, CSS3, JavaScript (ES6+), Canvas/SVG
- **Packet Analysis**: Python-based packet logger with optional PCAP export for Wireshark inspection

## 8. Development Roadmap
1. **Project Structure** ✅ - Baseline directories, placeholder modules, configuration.
2. **network.py** ✅ - Airport graph representation, nodes, and link weights.
3. **dijkstra.py** ✅ - Dynamic shortest path calculation and route tables.
4. **packet.py + frame.py** ✅ - Packet and frame data models with serialization.
5. **framing.py** ✅ - Frame delineation, byte stuffing, and de-stuffing.
6. **crc.py** ✅ - CRC generator, checker, and bitwise validation.
7. **sliding_window.py** ✅ - Window sizing, sequence tracking, and buffer handling.
8. **go_back_n.py** ✅ - GBN ARQ state machine, timers, ACK processing, and window rollback.
9. **network_simulator.py** ✅ - End-to-end discrete event simulation orchestrator and error generator.
10. **Flask Backend** ✅ - REST endpoints serving topology, simulation triggers, and telemetry.
11. **Dashboard** ✅ - Web interface layout, telemetry, and control panels.
12. **Live Animations** ✅ - Interactive Canvas/SVG topology, animated frames, and queueing visual cues.
13. **Analytics & Performance Dashboard** ✅ - Telemetry engine, protocol breakdown, and 7-tier analytics dashboard.
14. **Wireshark Exporter** ✅ - Binary PCAP capture generation and Wireshark inspection workflow.
15. **Final Integration Testing & Validation** ✅ - Comprehensive integration, edge case validation, 100% test coverage.

## 9. Project Structure
```
AeroNetGuard/
│
├── simulation/
│   ├── __init__.py
│   ├── network.py
│   ├── dijkstra.py
│   ├── packet.py
│   ├── frame.py
│   ├── network_simulator.py
│   └── error_generator.py
│
├── algorithms/
│   ├── __init__.py
│   ├── framing.py
│   ├── crc.py
│   ├── sliding_window.py
│   └── go_back_n.py
│
├── backend/
│   ├── __init__.py
│   ├── app.py
│   └── routes/
│       ├── __init__.py
│       ├── network_routes.py
│       ├── simulation_routes.py
│       ├── analytics_routes.py
│       └── wireshark_routes.py
│
├── frontend/
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── app.js
│   │       └── network_canvas.js
│   └── templates/
│       ├── index.html
│       ├── topology.html
│       ├── simulation.html
│       ├── packet_monitor.html
│       ├── analytics.html
│       └── traffic_analysis.html
│
├── analytics/
│   ├── __init__.py
│   └── metrics.py
│
├── wireshark/
│   ├── __init__.py
│   └── capture.py
│
├── data/
│   ├── __init__.py
│   └── .gitkeep
│
├── tests/
│   ├── test_network.py
│   ├── test_dijkstra.py
│   ├── test_packet.py
│   ├── test_frame.py
│   ├── test_framing.py
│   ├── test_crc.py
│   ├── test_sliding_window.py
│   ├── test_go_back_n.py
│   ├── test_simulator.py
│   ├── test_metrics.py
│   ├── test_pages.py
│   └── test_api.py
│
├── requirements.txt
├── README.md
├── .gitignore
└── run.py
```

## 10. Simulation Workflow
```
User selects source/destination node and inputs message
                    ↓
Dijkstra calculates shortest route path & cost
                    ↓
Network Message encapsulated into Packet
                    ↓
Packet tokenized & converted to Frames (word-based framing)
                    ↓
CRC-32 checksum calculated & attached to each Frame
                    ↓
Sliding Window controls transmission rate (Window N)
                    ↓
Frame failures / Drops / Corruptions simulated
                    ↓
Go-Back-N ARQ retransmits unACKed frames upon timeout
                    ↓
Receiver validates CRC & sequence number
                    ↓
Cumulative ACKs returned to sender
                    ↓
Delivery completes & Telemetry Analytics generated
                    ↓
Wireshark binary .pcap file generated for packet capture inspection
```

## 11. Installation & Running Instructions

### Prerequisites
- Python 3.10+
- Virtual Environment (`venv`)

### Setup & Installation
```bash
# Clone or navigate to the repository directory
cd AeroNetGuard

# Create and activate virtual environment
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
python run.py
```
Open your browser and navigate to: `http://127.0.0.1:5000`

### Running Automated Tests
```bash
pytest -q
```

## 12. Wireshark Traffic Analysis (Step 14)

AeroNetGuard includes a native packet capture engine (`wireshark/capture.py`) that exports discrete simulation events into standard binary `.pcap` files for deep packet inspection.

### Key Characteristics:
- **Synthetic Simulation Representation**: AeroNetGuard exports simulated communication events as PCAP files. PCAP traffic is entirely synthetic and does NOT represent real airport network traffic.
- **Deterministic IP & MAC Addressing**: Packets use deterministic simulation IP addresses (`Control Tower: 10.0.0.1`, `Check-in: 10.0.0.2`, `Security: 10.0.0.3`, `Baggage: 10.0.0.4`, `Emergency Services: 10.0.0.5`) and locally administered MAC addresses (`02:00:00:00:00:0X`).
- **Container Protocol**: UDP (User Datagram Protocol) on dedicated simulation port `5001` encapsulates all data link frame events and control messages.
- **Embedded Metadata**: Structured AeroNetGuard metadata is embedded directly in the Raw wire payload (e.g. `AERONETGUARD|FRAME|SEQ=2|SRC=Security|DST=Baggage|STATUS=SUCCESS|PAYLOAD=GATE`).
- **Event-Order Timestamps**: PCAP timestamps represent sequential simulation event ordering (`base_timestamp + event_index * 1ms`) rather than physical hardware propagation latencies.

### Wireshark Display Filters:
| Filter Purpose | Display Filter |
| :--- | :--- |
| **All AeroNetGuard Traffic** | `frame contains "AERONETGUARD"` or `udp contains "AERONETGUARD"` |
| **Simulation Port Only** | `udp.port == 5001` |
| **Security Traffic** | `ip.addr == 10.0.0.3` |
| **Baggage Traffic** | `ip.addr == 10.0.0.4` |
| **Acknowledgements** | `frame contains "ACK"` |
| **Retransmissions** | `frame contains "RETRANSMISSION"` |

### REST Endpoints for Traffic Analysis:
- `POST /api/wireshark/capture`: Generates PCAP file in `wireshark/captures/` from latest simulation.
- `GET /api/wireshark/summary`: Returns packet counts broken down by frame, ack, retransmission, and CRC failure.
- `GET /api/wireshark/packets`: Returns structured packet capture records for UI display.
- `GET /api/wireshark/download/<filename>`: Safely serves the generated PCAP with strict path traversal prevention.
- `POST /api/wireshark/reset`: Resets capture buffer state.

## 13. Project Limitations
- **Software Simulation Only**: AeroNetGuard is a high-fidelity software simulator designed for academic and analytical demonstration.
- **Simulated Entities**: Airport nodes, communication channels, and telemetry are simulated.
- **Synthetic IP Addresses**: IP addresses and Ethernet MAC addresses generated in PCAP files are synthetic.
- **No Real Hardware/Network Interface**: The system does not interface with physical airport infrastructure or operational flight networks.
- **Discrete Event Timing**: Simulation event steps represent logical time ticks rather than real-world physical propagation delay.

## 14. Project Readiness & Verification
- **Automated Test Coverage**: 205 passed out of 205 tests (100% pass rate).
- **Core Networking Algorithms**: Intact and untouched (`AirportNetwork`, `DijkstraRouter`, `Packet`, `Frame`, `FramingEngine`, `CRCProcessor`, `SlidingWindow`, `GoBackNProtocol`, `NetworkSimulator`).

