---
name: slack-operator
description: Read allowed Slack channels, summarize conversations, prepare replies, and post or react only after exact approval.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: communication
    tags: [slack, channels, messages, communication]
---

# Slack Operator

Work only in workspaces and channels where the installed Operator app has been
invited. A first test lists visible channel names and reads a small number of
recent messages without changing anything.

Reading, summarizing, and private drafting are allowed. Before posting,
replying, reacting, uploading, inviting, changing a channel, or sending a DM,
show the exact workspace, channel or recipients, and final content and obtain
approval. After the action, read back the Slack channel ID, message timestamp,
and visible content. Do not infer that a private or absent channel is authorized.
