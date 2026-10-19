# AeroNetGuard: Wireshark Traffic Inspection & PCAP Capture Guide

## 1. Overview & Simulation Architecture

AeroNetGuard is an educational, software-based computer network simulator for airport communication systems. 

The **Wireshark Traffic Analysis Layer** converts discrete simulation events (routing path calculation, frame transmissions, Go-Back-N retransmissions, acknowledgements, and CRC verifications) into standard, binary `.pcap` files. These packet captures can be inspected in Wireshark, tcpdump, TShark, or parsed programmatically with Scapy.

> [!IMPORTANT]
> **SYNTHETIC SIMULATION NOTICE**:
> AeroNetGuard does NOT transmit live packets over real airport hardware, physical networking gear, or operational interfaces. All captured packets are synthetic representations of internal simulation events encapsulated in standard Ethernet/IPv4/UDP protocols.

---

## 2. Packet Encapsulation & Protocol Stack

Each simulation event is encapsulated as a standard 4-layer packet:

```
+-----------------------------------------------------------+
| Layer 2: Ethernet II (MAC Addresses: 02:00:00:00:00:XX)   |
+-----------------------------------------------------------+
| Layer 3: IPv4 (Deterministic Simulation IPs: 10.0.0.X)    |
+-----------------------------------------------------------+
| Layer 4: UDP (Dedicated Simulation Port: 5001)            |
+-----------------------------------------------------------+
| Layer 7: AeroNetGuard Raw Wire Metadata Payload           |
+-----------------------------------------------------------+
```

### Deterministic Airport Node IP & MAC Mapping

To provide realistic and easily filterable traffic traces, airport functional nodes are mapped to reserved documentation IP addresses and locally administered MAC addresses:

| Node Name | Simulated IPv4 Address | Simulated MAC Address | Role |
| :--- | :--- | :--- | :--- |
| **Control Tower** | `10.0.0.1` | `02:00:00:00:00:01` | Air Traffic Control & Clearance |
| **Check-in** | `10.0.0.2` | `02:00:00:00:00:02` | Passenger Ticketing & Baggage Check |
| **Security** | `10.0.0.3` | `02:00:00:00:00:03` | Checkpoint & Threat Screening |
| **Baggage** | `10.0.0.4` | `02:00:00:00:00:04` | Luggage Sorting & Routing Conveyors |
| **Emergency Services** | `10.0.0.5` | `02:00:00:00:00:05` | Fire, Rescue & Medical Dispatch |

*Default simulation gateway / unassigned: `10.0.0.254` (`02:00:00:00:00:fe`)*

---

## 3. Payload Wire Format & Markers

Every simulated packet carries a structured ASCII payload starting with the unique `AERONETGUARD` signature:

### A. Frame Transmission (`FRAME`)
- **Successful Transmission**:
  `AERONETGUARD|FRAME|SEQ=0|SRC=Security|DST=Baggage|STATUS=SUCCESS|PAYLOAD=SECURITY`
- **Impaired / Dropped Transmission**:
  `AERONETGUARD|FRAME|SEQ=2|SRC=Security|DST=Baggage|STATUS=FAILED|PAYLOAD=GATE`

### B. Acknowledgement Packet (`ACK`)
Carried in reverse direction from receiver back to sender:
- `AERONETGUARD|ACK|SEQ=0|SRC=Baggage|DST=Security|STATUS=SUCCESS`

### C. Retransmission (`RETRANSMISSION`)
Issued during Go-Back-N window rollbacks:
- `AERONETGUARD|FRAME|SEQ=2|SRC=Security|DST=Baggage|RETRANSMISSION=1|PAYLOAD=GATE`

### D. CRC Verification Failure (`CRC_FAILURE`)
- `AERONETGUARD|FRAME|SEQ=2|CRC=INVALID|PAYLOAD=GATE`

### E. Shortest Path Routing Announcement (`ROUTE`)
- `AERONETGUARD|ROUTE|SRC=Security|DST=Baggage|PATH=Security->Control Tower->Check-in->Baggage`

---

## 4. How to Inspect Captures in Wireshark

1. **Generate the PCAP**:
   - Run a simulation from the **Dashboard** or **Simulation** view.
   - Navigate to `/traffic-analysis`.
   - Click **⚡ Generate PCAP** (or use the REST endpoint `POST /api/wireshark/capture`).
   - Click **📥 Download PCAP File** to save `aeronetguard_capture.pcap` locally.
2. **Open in Wireshark**:
   - Open Wireshark.
   - Go to **File ➔ Open...** and select the downloaded `.pcap` file.
3. **Inspect Layers**:
   - Expand the **Frame**, **Ethernet II**, **Internet Protocol Version 4**, **User Datagram Protocol**, and **Data** sections.
   - The ASCII metadata will be visible directly in the packet bytes pane.

---

## 5. Useful Wireshark Display Filters

Use these verified Wireshark display filters to isolate specific simulation behaviors:

| Filter Purpose | Wireshark Display Filter Expression |
| :--- | :--- |
| **All AeroNetGuard Traffic** | `frame contains "AERONETGUARD"` or `udp contains "AERONETGUARD"` |
| **Simulation Port Only** | `udp.port == 5001` |
| **Filter by Security Node** | `ip.addr == 10.0.0.3` |
| **Filter by Baggage Node** | `ip.addr == 10.0.0.4` |
| **Filter by Control Tower** | `ip.addr == 10.0.0.1` |
| **Isolate Acknowledgements** | `frame contains "ACK"` |
| **Isolate Retransmissions** | `frame contains "RETRANSMISSION"` |
| **Isolate Transmission Failures** | `frame contains "STATUS=FAILED"` |
| **Isolate CRC Corruptions** | `frame contains "CRC=INVALID"` |

---

## 6. Timestamp Design & Limitations

- **Sequential Discrete Ordering**:
  Simulation packets do not represent physical hardware transit latencies or real-world clock time. Instead, timestamps use a sequential baseline (`1700000000.0 + event_index * 0.001s`) to guarantee exact preservation of event ordering.
- **Academic Simulation Scope**:
  Captures are generated programmatically on demand and saved securely in `wireshark/captures/`. No live network interfaces are monitored, and no real packet injection is performed.
