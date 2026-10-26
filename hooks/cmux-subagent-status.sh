#!/bin/bash

# Claude Code hook: show running subagents as a cmux sidebar status pill.
# cmux's injected Claude hooks ignore SubagentStart/SubagentStop, so a workspace
# reads "Waiting" while a background agent is still working.
# Events: SubagentStart, SubagentStop, SessionEnd

[ -n "$CMUX_WORKSPACE_ID" ] && [ -n "$CMUX_SURFACE_ID" ] || exit 0
cmux_bin="${CMUX_BUNDLED_CLI_PATH:-cmux}"
command -v "$cmux_bin" >/dev/null 2>&1 || exit 0

IFS=$'\t' read -r event session_id agent_id agent_type transcript < <(
  jq -r '[.hook_event_name, .session_id, .agent_id, .agent_type, .transcript_path] | map(. // "") | @tsv'
)
[ -n "$session_id" ] || exit 0

state_dir="${TMPDIR:-/tmp}/cmux-subagents/$session_id"
key="subagents_$CMUX_SURFACE_ID"

case "$event" in
  SubagentStart)
    [ -n "$agent_id" ] || exit 0
    mkdir -p "$state_dir"
    printf '%s\n' "${agent_type:-agent}" >"$state_dir/$agent_id"
    ;;
  SubagentStop)
    [ -n "$agent_id" ] && rm -f "$state_dir/$agent_id"
    ;;
  SessionEnd)
    rm -rf "$state_dir"
    ;;
  *) exit 0 ;;
esac

# Returns 1 when the description was not available yet.
render() {
  local latest count meta label value
  latest=$(ls -t "$state_dir" 2>/dev/null | head -1)
  if [ -z "$latest" ]; then
    "$cmux_bin" clear-status "$key" >/dev/null 2>&1
    return 0
  fi

  count=$(ls "$state_dir" | wc -l | tr -d ' ')
  # Claude Code writes the Agent tool's description next to the subagent
  # transcript, shortly after SubagentStart fires.
  meta="${transcript%.jsonl}/subagents/agent-$latest.meta.json"
  label=$(jq -r '.description // empty' "$meta" 2>/dev/null)
  [ -n "$label" ] || label=$(cat "$state_dir/$latest" 2>/dev/null)

  if [ "$count" -eq 1 ]; then
    value="Subagent · $label"
  else
    value="$count subagents · $label +$((count - 1))"
  fi
  "$cmux_bin" set-status "$key" "$value" --icon person.2.fill --color "#BF5AF2" --priority 1 >/dev/null 2>&1
  [ -f "$meta" ]
}

if ! render && [ "$event" = SubagentStart ]; then
  (sleep 2; render) </dev/null >/dev/null 2>&1 &
fi
exit 0
