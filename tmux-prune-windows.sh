#!/usr/bin/env bash

set -euo pipefail

max_age_hours=24
execute=0

usage() {
    cat <<'EOF'
Usage: tmux-prune-windows [--hours HOURS] [--execute]

Find tmux windows that have been inactive for at least 24 hours.

Safety rules:
  - Windows currently viewed by a tmux client are always kept.
  - A window named _init is always kept.
  - The default is a dry run. Pass --execute to kill eligible windows.
  - Killing a window terminates every process running in its panes.

Options:
  --hours HOURS  Inactivity threshold in hours (default: 24).
  --execute      Kill eligible windows after rechecking their state.
  -h, --help     Show this help.
EOF
}

while (($# > 0)); do
    case "$1" in
        --hours)
            if (($# < 2)); then
                echo "tmux-prune-windows: --hours requires a value" >&2
                exit 2
            fi
            max_age_hours=$2
            shift 2
            ;;
        --execute)
            execute=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "tmux-prune-windows: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$max_age_hours" in
    ''|*[!0-9]*)
        echo "tmux-prune-windows: --hours must be a non-negative integer" >&2
        exit 2
        ;;
esac

readonly max_age_seconds=$((max_age_hours * 60 * 60))
readonly tab=$'\t'
readonly window_format="#{window_id}${tab}#{session_name}${tab}#{window_index}${tab}#{window_name}${tab}#{?#{@last_viewed},#{@last_viewed},untracked}${tab}#{window_activity}${tab}#{window_active_clients}${tab}#{window_panes}"

format_duration() {
    local total_seconds=$1
    local days hours minutes

    days=$((total_seconds / 86400))
    hours=$(((total_seconds % 86400) / 3600))
    minutes=$(((total_seconds % 3600) / 60))

    if ((days > 0)); then
        printf '%dd %dh' "$days" "$hours"
    elif ((hours > 0)); then
        printf '%dh %dm' "$hours" "$minutes"
    else
        printf '%dm' "$minutes"
    fi
}

window_commands() {
    local window_id=$1
    local command commands=''

    while IFS= read -r command; do
        [[ -n "$command" ]] || continue
        case ",$commands," in
            *",$command,"*)
                ;;
            *)
                if [[ -n "$commands" ]]; then
                    commands+=",$command"
                else
                    commands=$command
                fi
                ;;
        esac
    done < <(tmux list-panes -t "$window_id" -F '#{pane_current_command}' 2>/dev/null || true)

    printf '%s' "${commands:-none}"
}

# Sets: window_label, window_state, window_reason, inactive_seconds.
inspect_window() {
    local window_id=$1
    local metadata session_name window_index window_name last_viewed window_activity
    local active_clients pane_count now commands activity_time activity_label

    if ! metadata=$(tmux display-message -p -t "$window_id" "$window_format" 2>/dev/null); then
        window_label=$window_id
        window_state='gone'
        window_reason='window disappeared'
        inactive_seconds=0
        return
    fi

    IFS=$'\t' read -r _window_id session_name window_index window_name last_viewed window_activity active_clients pane_count <<< "$metadata"
    window_label="${session_name}:${window_index} ${window_name}"
    commands=$(window_commands "$window_id")

    case "$last_viewed" in
        untracked|''|*[!0-9]*)
            activity_time=$window_activity
            activity_label='output inactive (untracked)'
            ;;
        *)
            activity_time=$last_viewed
            activity_label='not viewed'
            ;;
    esac

    now=$(date +%s)
    inactive_seconds=$((now - activity_time))
    if ((inactive_seconds < 0)); then
        inactive_seconds=0
    fi

    if [[ "$window_name" == '_init' ]]; then
        window_state='keep'
        window_reason="protected panes=$pane_count commands=$commands"
        return
    fi

    if ((active_clients > 0)); then
        window_state='keep'
        window_reason="viewed clients=$active_clients panes=$pane_count commands=$commands"
        return
    fi

    if ((inactive_seconds < max_age_seconds)); then
        window_state='keep'
        window_reason="$activity_label $(format_duration "$inactive_seconds") panes=$pane_count commands=$commands"
        return
    fi

    window_state='eligible'
    window_reason="$activity_label $(format_duration "$inactive_seconds") panes=$pane_count commands=$commands"
}

if ! windows=$(tmux list-windows -a -F '#{window_id}' 2>/dev/null); then
    echo 'No tmux server is running.'
    exit 0
fi

if [[ -z "$windows" ]]; then
    echo 'No tmux windows found.'
    exit 0
fi

eligible_count=0
killed_count=0
kept_count=0

while IFS= read -r window_id; do
    [[ -n "$window_id" ]] || continue
    inspect_window "$window_id"

    case "$window_state" in
        keep)
            printf 'KEEP       %-38s %s\n' "$window_label" "$window_reason"
            kept_count=$((kept_count + 1))
            ;;
        gone)
            printf 'SKIP       %-38s %s\n' "$window_label" "$window_reason"
            ;;
        eligible)
            eligible_count=$((eligible_count + 1))
            if ((execute == 0)); then
                printf 'WOULD KILL %-38s %s\n' "$window_label" "$window_reason"
                continue
            fi

            # Close the race between listing and deletion.
            inspect_window "$window_id"
            if [[ "$window_state" != 'eligible' ]]; then
                printf 'SKIP       %-38s state changed: %s\n' "$window_label" "$window_reason"
                continue
            fi

            tmux kill-window -t "$window_id"
            printf 'KILLED     %-38s %s\n' "$window_label" "$window_reason"
            killed_count=$((killed_count + 1))
            ;;
    esac
done <<< "$windows"

if ((execute == 0)); then
    printf '\nDry run: %d eligible, %d kept. Re-run with --execute to delete.\n' "$eligible_count" "$kept_count"
else
    printf '\nDone: %d killed, %d kept.\n' "$killed_count" "$kept_count"
fi
