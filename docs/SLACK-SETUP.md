# Slack Setup: One Screen at a Time

This is the current Slack Socket Mode setup for Funding Director. A setup agent can
operate the browser and server while the owner approves the Slack workspace and
privately enters tokens. No public web address is required.

Official reference: [Hermes Slack guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack).

## Before creating the app

Use a new Slack app for a new installation. The included manifest enables
Slack's current **Agent view**. Slack does not let that app return to the old
messages interface after Agent view is applied.

Have these two pages open:

1. [Slack Apps](https://api.slack.com/apps)
2. This repository's [slack-manifest.yml](../slack-manifest.yml)

## Step 1: Create the Slack app

1. On Slack Apps, select **Create New App**.
2. Select **From an app manifest**.
3. Choose the workspace where Funding Director should live.
4. Select the **YAML** tab.
5. Replace the sample text with the complete contents of
   `slack-manifest.yml`.
6. Select **Next**, review the summary, then select **Create**.

The manifest includes Socket Mode, Agent view, interactive buttons, message and
file access, required events, and the current 50 native Hermes commands.

## Step 2: Install it and copy the Bot Token

1. In the left menu, open **OAuth & Permissions**.
2. Select **Install to Workspace** and approve the requested permissions.
3. Copy the **Bot User OAuth Token**. It begins with `xoxb-`.
4. Paste it only into the installer's hidden **Slack Bot Token** prompt.

Treat the token like a password. Never paste it into Slack, a document, or a
GitHub issue.

## Step 3: Turn on Socket Mode and copy the App Token

1. In the left menu, open **Socket Mode** and turn it on.
2. When Slack asks for an app-level token, name it `funding-director-socket`.
3. Add the scope `connections:write`.
4. Create the token and copy the value beginning with `xapp-`.
5. Paste it only into the installer's hidden **Slack App Token** prompt.

## Step 4: Authorize the owner

Hermes denies Slack messages unless the sender is explicitly authorized.

1. In Slack, open the owner's profile.
2. Select the three-dot menu.
3. Select **Copy member ID**.
4. Paste the ID, which looks like `U01ABC123`, into the installer.

For multiple trusted owners, use comma-separated Member IDs. Do not enter a
display name or email address.

The installer optionally asks for a home channel ID. This is useful for daily
briefs but is not required for the first message.

## Step 5: Start Funding Director

The installer saves private values in `/srv/<operator>/.env` with owner-only
permissions, builds the reviewed image, starts it, and waits for a healthy
result. It also creates the exact runtime-generated manifest at:

```text
/srv/<operator>/hermes/data/slack-manifest.json
```

That generated copy is the source of truth after runtime updates.

## Step 6: Prove the real Slack behavior

Run all three tests before calling the installation complete:

1. **Direct message:** Open Funding Director under Apps and send `hello`. An
   authorized DM should receive a reply without an `@mention`.
2. **Channel thread:** Invite Funding Director to one approved channel. Send
   `@Funding Director Give me a one-sentence status check.` It should reply in a
   thread.
3. **Thread follow-up:** Reply in that same thread without another mention. It
   should continue the active conversation.

Also test `/help`, `/btw give me a one-sentence update`, `/reload-skills`, and
one clarify/approval button. Slack limits apps to 50 native slash commands, so
skills that are not in the picker can always be typed as `!skill-name` or
through `/hermes skill-name ...`.

## After a Hermes update

Run the repository's `./update.sh /srv/<operator>/.env`. Then:

1. Open the generated `hermes/data/slack-manifest.json`.
2. In Slack Apps, open **Features → App Manifest**.
3. Replace the old manifest, save it, and reinstall when Slack asks.
4. Repeat the DM, channel-thread, and thread-follow-up tests.

If a message is ignored, check the exact Member ID first. If channel messages
fail, confirm the app was invited, the first message includes `@Funding Director`,
and the app was reinstalled after a manifest change.
