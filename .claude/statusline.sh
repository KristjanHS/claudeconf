#!/bin/bash
# Claude Code status line: reads the session JSON on stdin, prints one line. No network, no file writes;
# besides jq it runs only `git branch --show-current`. C0/C1 control chars are stripped; numbers must be numbers.
{ export LC_ALL=C.UTF-8; } 2>/dev/null
# Token budget: WINDOW = 100% of the bar; AMBER/RED colour it; "← /clear soon" shows within WARN of STOP.
WINDOW=300000
STOP=225000
AMBER=200000
RED=240000
WARN=30000
IFS=$'\x1f' read -r MODEL TOK H5 D7 CWD < <(jq -r '[(.model.display_name? // "?" | tostring | gsub("[[:cntrl:]]"; "")),
  ([.context_window.current_usage? | objects | .input_tokens, .cache_creation_input_tokens, .cache_read_input_tokens
    | numbers] | add // 0 | floor), (.rate_limits.five_hour.used_percentage? | numbers | floor) // "",
  (.rate_limits.seven_day.used_percentage? | numbers | floor) // "", (.workspace.current_dir? // .cwd? // "")]
  | map(tostring) | join("\u001f")' 2>/dev/null)
[[ $TOK =~ ^[0-9]+$ ]] || TOK=0   # bash arithmetic evaluates a[$(cmd)]: numbers only
BRANCH=$(git -C "${CWD:-.}" branch --show-current 2>/dev/null) DIR=${CWD##*/}
for v in MODEL DIR BRANCH; do printf -v "$v" '%s' "${!v//[[:cntrl:]]/}"; done
PCT=$((TOK * 100 / WINDOW)) C=32 W=""; N=$((PCT > 100 ? 10 : PCT / 10))
((TOK >= AMBER)) && C=33; ((TOK >= RED)) && C=31; ((STOP - TOK <= WARN)) && W=$' \e[31m← /clear soon\e[0m'
printf -v F '%*s' $N ''; printf -v E '%*s' $((10 - N)) ''
printf '[%s] \e[%sm%s%s\e[0m %s%% \e[2m(%sk) %s%s\e[0m%s\e[2m%s%s\e[0m\n' "$MODEL" $C "${F// /█}" "${E// /░}" \
  $PCT $((TOK / 1000)) "$DIR" "${BRANCH:+[$BRANCH]}" "$W" "${H5:+ | 5h:$H5%}" "${D7:+ | 7d:$D7%}"
