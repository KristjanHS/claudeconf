---
name: claude-code-guide
description: Use this agent when the user asks questions ("Can Claude...", "Does Claude...", "How do I...") about Claude Code (the CLI tool), the Claude Agent SDK, the Claude API (Messages API, tool runner, managed agents, prompt caching, SDK usage), Claude Tag (Claude in Slack), or `claude plugin eval` and the `/skill-doctor` report. Before spawning a new agent, check whether a running or recently completed claude-code-guide agent can be continued via SendMessage.
tools: Bash, Read, WebFetch, WebSearch
model: opus
effort: high
---
