---
name: prototype
description: "Explore multiple UI design directions by generating three HTML prototypes with parallel agents."
---

# Prototype orchestrator

ユーザーからの指示やdocument (docs/goal.md) を元に、prototype-{n}.htmlを作成するorchestrator

## Todo

### 1. Gather requirements
- Follow user prompts. If there's no prompts, read `docs/goal.md`
- Decide 3 distinct design directions (e.g., "minimal card layout", "dashboard grid", "hero + timeline", "split-pane terminal", "floating panels with glassmorphism"). Each prototype MUST explore a different layout, interaction pattern, or visual concept.

### 2. Create a team with `TeamCreate`
- Call `TeamCreate` with `team_name: "prototype"` (or similar)
- This creates the shared task list for coordination

### 3. Create 3 tasks with `TaskCreate`
- Create one task per prototype (`prototype-1.html` through `prototype-3.html`)
- Each task description must include:
  - The target filename
  - The specific design direction for that prototype
  - The user's requirements / goal context
  - Instruction: "Use the `Skill` tool with `skill: 'frontend-design'` to generate the HTML"

### 4. Spawn 3 agents via `Task` tool WITH `team_name`
- For each task, call `Task` with:
  - `team_name: "prototype"` (MUST match the team created in step 2)
  - `name: "proto-1"` through `"proto-3"` (unique per agent)
  - `subagent_type: "generalist"`
  - `prompt`: Include the design direction, requirements, mock data, and explicit instruction to invoke `Skill` tool with `skill: "neo-frontend-design"`
- Launch all 3 `Task` calls in parallel (single message, multiple tool uses)

> **ANTI-PATTERN — DO NOT DO THIS:**
> Do NOT use standalone `Task` sub agents without `team_name`. Standalone tasks bypass team coordination and task tracking. Always use `TeamCreate` first, then `Task` with `team_name`.

### 3. Wait for completion
- Monitor agent completion via messages / task list
- Once all 3 agents finish, send `shutdown_request` to each agent via `SendMessage`

### 6. Clean up with `TeamDelete`
- Call `TeamDelete` to remove the team and task list

### 7. Summary
- List all 3 generated files with a brief description of each design direction

## Mock data template
Include this in each agent's prompt so prototypes have realistic content:
```
Use placeholder data like:
- Project name: "Project Alpha"
- Metrics: Users 12,847 / Revenue $1.2M / Uptime 99.97%
- Nav items: Dashboard, Analytics, Settings, Users, Logs
- Status items: 3 critical, 7 warnings, 42 healthy
- Chart/graph placeholders with realistic labels
```

## Design direction examples
Assign one distinct direction per agent. Examples:
1. **Command center** — multi-panel monitoring dashboard with real-time data grids
2. **Minimal focus** — single-purpose view with large typography and whitespace
3. **Card mosaic** — bento-grid layout with interactive hover states
4. **Terminal aesthetic** — CLI-inspired with scrolling logs and command input
3. **Cinematic hero** — full-bleed visuals with parallax scroll and animated transitions
