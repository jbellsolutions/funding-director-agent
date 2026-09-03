---
name: operator-onboarding
description: Personalize a newly hosted Operator through a short one-question-at-a-time interview and create the private persona, context, connections, priorities, and skills it needs.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: business
    tags: [onboarding, persona, business, skills, setup]
---

# Operator Onboarding

Use this when `00.Onboarding.md` is not complete or the owner asks to change the
operator's role. This is a conversation, not a form. Ask one short question at
a time and write confirmed answers into the knowledge files.

## Opening

Say: “Your Operator is online. Do you want to jump in and go, or personalize it
with me first?” Offer:

1. Jump in and use it now.
2. Personalize it with a short guided setup.

If they jump in, mark the mode `quick_start`, record the task, complete it, and
offer to resume personalization later. Do not make an urgent job wait for intake.

## Guided sequence

1. Ask what the owner wants to call the operator and what to call them.
2. Ask the main business or personal use case in ordinary language.
3. Ask for the first three outcomes the operator should help produce.
4. Ask which recurring responsibility would be most valuable.
5. Offer three concise persona/tone choices based on their answers; let them
   choose or describe another. Update `01.Operator Profile.md` and `SOUL.md`.
6. Confirm the permission boundary in `03.Permissions.md`.
7. Ask where they want to message the operator: Telegram, Slack, iMessage via
   BlueBubbles, WhatsApp, Discord, or the private browser dashboard. Record the
   choice and guide only the requested connection.
8. Ask which inboxes, calendars, files, documents, CRM, or other apps matter.
   Use read-only connection tests before any write test.
9. Translate the first workflows into a small skill plan. Reuse a generic skill
   when it fits. Create an owner-specific skill privately only when a repeated
   procedure truly needs one.
10. Set the first priority and summarize what is connected, verified, missing,
    and approval-gated.

## Creating a private skill

Write it only under `/opt/data/skills/<skill-name>/SKILL.md`. Include YAML
frontmatter with `name` and `description`, then document trigger, required
inputs, procedure, approval boundary, output, and a safe acceptance test. Never
copy a proprietary third-party or agency procedure into the public repository.

## Finish

Ask: “Any last skills or anything else you want me to think through before I
finish?” Incorporate the answer, mark `00.Onboarding.md` complete, and say:
“All right — we're all done. I'm ready whenever you are.”
