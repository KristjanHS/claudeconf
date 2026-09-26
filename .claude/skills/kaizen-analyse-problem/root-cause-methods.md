# Root-Cause Methods

The two sub-methods A3 Step 4 (Root Cause Analysis) draws on. Read this when Step 4 needs more than a
one-line cause statement. Merged here from the former `kaizen-why` and `kaizen-cause-and-effect` skills.

Pick by shape: a **single causal chain** you can walk backwards → Five Whys. A **problem with many
plausible contributors across domains** → Fishbone. They compose — use Fishbone to enumerate, then Five
Whys to dig into the highest-priority branch.

---

## Five Whys — symptom to root cause

Iteratively ask "why" to move from surface symptoms to fundamental causes. Identifies systemic issues rather than quick fixes.

### Steps

1. State the problem clearly
2. Ask "Why did this happen?" and document the answer
3. For that answer, ask "Why?" again
4. Continue until reaching root cause (usually 5 iterations)
5. Validate by working backwards: root cause → symptom
6. Explore branches if multiple causes emerge
7. Propose solutions addressing root causes, not symptoms

Tracing mechanics (backward call-stack tracing, code-level instrumentation, test-pollution bisection): use the `systematic-debugging` skill — canonical owner.

---

## Fishbone (Ishikawa) — 6M cause-and-effect

Apply Fishbone diagram analysis to systematically explore all potential causes of a problem across multiple categories.

Systematically examine potential causes across six categories: People, Process, Technology, Environment, Methods, and Materials. Creates structured "fishbone" view identifying contributing factors.

### Steps

1. State the problem clearly (the "head" of the fish)
2. For each category, brainstorm potential causes:
   - **People**: Skills, training, communication, team dynamics
   - **Process**: Workflows, procedures, standards, reviews
   - **Technology**: Tools, infrastructure, dependencies, configuration
   - **Environment**: Workspace, deployment targets, external factors
   - **Methods**: Approaches, patterns, architectures, practices
   - **Materials**: Data, dependencies, third-party services, resources
3. For each potential cause, ask "why" to dig deeper
4. Identify which causes are contributing vs. root causes
5. Prioritize causes by impact and likelihood
6. Propose solutions for highest-priority causes

### Example: API Response Latency

```
Problem: API responses take 3+ seconds (target: <500ms)

PEOPLE
├─ Team unfamiliar with performance optimization
├─ No one owns performance monitoring
└─ Frontend team doesn't understand backend constraints

PROCESS
├─ No performance testing in CI/CD
├─ No SLA defined for response times
└─ Performance regression not caught in code review

TECHNOLOGY
├─ Database queries not optimized
│  └─ Why: No query analysis tools in place
├─ N+1 queries in ORM
│  └─ Why: Eager loading not configured
├─ No caching layer
│  └─ Why: Redis not in tech stack
└─ Synchronous external API calls
   └─ Why: No async architecture in place

ENVIRONMENT
├─ Production uses smaller database instance than needed
├─ No CDN for static assets
└─ Single region deployment (high latency for distant users)

METHODS
├─ REST API design requires multiple round trips
├─ No pagination on large datasets
└─ Full object serialization instead of selective fields

MATERIALS
├─ Large JSON payloads (unnecessary data)
├─ Uncompressed responses
└─ Third-party API (payment gateway) is slow
   └─ Why: Free tier with rate limiting

ROOT CAUSES:
- No performance requirements defined (Process)
- Missing performance monitoring tooling (Technology)
- Architecture doesn't support caching/async (Methods)

SOLUTIONS (Priority Order):
1. Add database indexes (quick win, high impact)
2. Implement Redis caching layer (medium effort, high impact)
3. Make external API calls async with webhooks (high effort, high impact)
4. Define and monitor performance SLAs (low effort, prevents regression)
```

### Notes

- Fishbone reveals systemic issues across domains
- Multiple causes often combine to create problems
- Don't stop at first cause in each category—dig deeper
- Some causes span multiple categories (mark them)
- Root causes usually in Process or Methods (not just Technology)
- Follow a high-priority branch with Five Whys (above) for deeper analysis
- Prioritize solutions by: impact × feasibility ÷ effort
- Address root causes, not just symptoms
