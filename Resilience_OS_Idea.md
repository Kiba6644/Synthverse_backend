# Resilience OS
### A layered digital twin that stress-tests a city — from a single building to a global trade route

---

## The Core Idea

Cities respond to crises reactively. A building catches fire, and the ambulance gets stuck in traffic. The traffic system doesn't know the hospital it's routing to is at capacity. The hospital doesn't know a supply disruption is about to make its medicines expensive. Each system operates in isolation, so every crisis cascades further than it should.

**Resilience OS is a single platform that connects four nested scales of urban infrastructure — building, city traffic, city planning, and global supply chain — through a shared event bus.** Each layer is a sensor for the layer above it. When something breaks at any scale, every other layer knows immediately and responds.

The unifying concept: **a crisis is always a cascade. The response must be just as connected.**


### Layer 2 — City Traffic (Event Management + Live Crisis Routing)

This layer operates in two modes: **normal** and **crisis**.

**Normal mode — event permit management:**
Organisations submit event requests (concerts, protests, marathons) through a portal. The system simulates the expected crowd density and vehicle pressure on surrounding roads and returns a traffic impact score. Police see this score on their dashboard and decide whether to approve, approve with conditions, or deny. The score is calculated from estimated crowd size, venue geometry, road capacity of adjacent streets, and proximity to emergency vehicle routes. This replaces gut-feel permit decisions with a data-backed recommendation.

**Crisis mode — live rerouting:**
The moment a crisis event arrives from layer 1, this layer marks the affected road segments as blocked and recalculates routes for all traffic in the area. Emergency vehicles get the fastest unobstructed path to the crisis site. Civilian traffic is rerouted away from the zone through a maps API that any navigation app can query.

The integration point with layer 3 is the hospital routing call: when rerouting an ambulance, layer 2 doesn't just find the shortest path — it asks layer 3 which hospitals are actually capable of handling the emergency right now, then routes to that specific hospital avoiding all blocked segments.

---

### Layer 3 — City Planning (Pincode Resilience Score)

This layer runs continuously in the background, long before any crisis. It assigns every pincode in a city a resilience score based on how well-served it is by critical infrastructure:

- Distance and capacity of the nearest hospital
- Distance to the nearest police station and historical response times
- Whether the area falls within the 8-minute fire response radius of a fire station
- Road connectivity (how many routes in and out — low connectivity means high isolation risk in a crisis)
- Population vulnerability (density, elderly population percentage)

An AI model — trained on historical crisis outcome data or bootstrapped from the weighted formula — generates a score from 0 to 100 per pincode. The output is a heatmap: red zones are structurally fragile, green zones are well-served. City planners use this to decide where to build the next hospital, fire station, or road connection.

During a crisis, this layer becomes the hospital routing engine. When layer 2 needs to route an ambulance, it queries layer 3: "given these blocked roads, which of the capable hospitals within 10km has the best resilience score and the shortest reachable path?" Layer 3 returns a ranked list. The ambulance goes to the right hospital, not just the closest one.

---

### Layer 4 — Supply Chain (Global Trade Disruption Simulation)

This layer operates at the largest scale and is the most optional — build it if the other three are solid.

India's critical goods — medicines, fuel, electronics — depend on specific global trade routes. A disruption to the Strait of Malacca delays electronics. A blockage at the Strait of Hormuz spikes fuel prices. Most city planners have no visibility into how a shipping lane disruption 5,000km away will affect the availability of medicine in a specific hospital in a specific pincode.

This layer models India's import dependencies as a directed graph: nodes are ports and distribution hubs, edges are trade routes with attributes for goods carried, monthly volume, and transit time. When a route is blocked, the system finds the next available path, calculates the extra transit days, and translates that into a price impact and estimated days-to-shortage — broken down by pincode and goods category.

The connection to layers 2 and 3: during a prolonged urban crisis (a flood, an earthquake), hospitals deplete specific supplies. Layer 4 tells you how quickly those supplies can be replenished, from where, and which pincodes will feel the shortage first. It turns a reactive supply problem into a predictable one.

---

## How the Four Layers Connect

The layers are not four separate dashboards. They share a single event bus — a message broker that every layer reads from and writes to. The integration is not cosmetic; each layer's output is another layer's input.

```
FIRE DETECTED (Layer 1)
        │
        ▼
crisis.building.alert published to shared bus
        │
        ├──▶ Layer 2 receives alert
        │         Closes adjacent road segments
        │         Queries Layer 3: "which hospital, avoiding blocked roads?"
        │         Routes ambulance to answer
        │
        ├──▶ Layer 3 receives alert
        │         Queries its resilience database
        │         Returns ranked capable hospitals with traffic-adjusted ETAs
        │         Publishes city.hospital.status update
        │
        └──▶ Layer 4 receives alert (prolonged crisis mode)
                  Checks if affected hospital's critical supplies are route-dependent
                  Flags any active trade disruptions affecting those supplies
                  Returns days-to-shortage estimate
```

The key insight in the integration: **the layers share a definition of "resource."**

- Layer 1 defines the resource demand: how many people need emergency services, and where.
- Layer 2 defines the resource path: which roads can carry emergency vehicles to the supply.
- Layer 3 defines the resource supply: which facilities have the capacity to serve the demand.
- Layer 4 defines the resource origin: where those facilities' supplies come from, and how fragile that supply is.

A crisis breaks one or more of these. Resilience OS shows exactly which link broke, what it cascades into, and what the next-best option is — at every scale simultaneously.

---

## The Demo Scenario (the cascade in one story)

1. A smoke sensor on floor 3 of a building spikes. Air quality index hits 280. Occupant count is 134.
2. Layer 1 scores all exits in real time. Exit B (north stairwell) is safest. Every floor display updates within 4 seconds.
3. The alert fires to the shared bus. Layer 2 closes the adjacent street to through-traffic. Ambulance routing begins.
4. Layer 2 asks layer 3: nearest hospital with capacity, avoiding the closed road. Layer 3 returns two candidates. Ambulance is routed to the one with the better resilience score, not just the closer one.
5. (If layer 4 is built) The hospital's burn unit uses saline sourced through a specific shipping route. Layer 4 checks: is that route currently disrupted? If yes, flag a potential shortage window. The system generates a procurement alert before anyone knew there was a supply problem.

**Start with one building. End with a global trade route. One cascade. One platform.**

---

## What Makes This Different

Most smart city projects build dashboards. This builds a **nervous system** — a system where information from the smallest sensor in a building automatically propagates to every decision that depends on it, at every scale, without anyone manually connecting the dots.

The research complexity is real: dynamic graph routing under live constraint updates, spatial ML for infrastructure scoring, federated event-driven architecture across heterogeneous data sources, and supply chain disruption propagation modelling are all active areas of research. But the output — "here is the safest exit, here is the fastest ambulance route, here is the most capable hospital" — is something any person in the building, any police officer, or any city official immediately understands.

---

*Tracks: AI & Intelligent Digital Twins (01) + Cybersecurity & Blockchain (02) + Smart Infrastructure & Urban Digital Twins (03)*
