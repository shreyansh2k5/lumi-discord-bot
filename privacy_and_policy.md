# Lumi Privacy Policy

**Last updated:** November 3, 2026

This Privacy Policy explains what data Lumi ("Lumi", "the bot", "we") collects, how it is used, who it is shared with, and the choices you have. Lumi is a Discord bot operated by Shreyansh ([shreyansh2k5](https://github.com/shreyansh2k5)).

By using Lumi or being in a server where Lumi is present, you acknowledge this policy. Your use of Discord is also subject to [Discord's Privacy Policy](https://discord.com/privacy) and [Terms of Service](https://discord.com/terms).

## 1. What Lumi does

Lumi is a multipurpose community bot. Its core feature is an AI chat companion that replies when a user mentions Lumi or replies to one of Lumi's messages. Lumi also provides per-server auto-moderation (a configurable bad-word filter with role exceptions), moderation commands (`/mute`, `/unmute`, `/kick`, `/ban`), an economy and games system, dead-chat revival, optional welcome messages, and utilities such as `/status` and `/server_info`. Basic and economy commands are also available with the `$` prefix.

## 2. Data we store

Lumi stores the following data in Google Firebase Cloud Firestore:

| Data | Details |
|---|---|
| Discord user IDs | Used as identifiers for economy data |
| Economy data | Coin balances, daily-reward timestamps and counters, bank state, owned pets |
| Discord server (guild) IDs | Used as identifiers for server configuration |
| Server settings | Bad-word filter entries, exempt role names, configured channel IDs, dead-chat inactivity threshold, welcome-message settings |

Lumi does **not** store message content, AI conversation history, or member profile data (such as usernames, avatars, or nicknames) in Firestore or any other database.

## 3. Message content and AI chat

Lumi uses Discord's Message Content Intent. Message text is processed for the following purposes:

- **Auto-moderation:** reading messages to apply the server's bad-word filter.
- **Commands:** reading `$` prefix commands.
- **AI chat:** when a user mentions Lumi, replies to Lumi, or sends Lumi a direct message, Lumi sends that message to an AI provider to generate a response. The message is trimmed to a maximum of 7,000 characters, and the bot mention is removed first.
- **Conversation context:** to make replies coherent, Lumi may also include up to five recent non-bot messages from the same channel, plus short-term conversation memory (see below). This means messages from users who did not mention Lumi can be included as context when someone else triggers AI chat.

**Short-term memory:** Lumi keeps the last eight user/assistant turns per user in the memory of the running bot process only. This memory is not written to disk or to a database and is lost when the bot restarts.

**AI chat is Lumi's primary feature.** Server administrators can control where Lumi operates by configuring channel permissions, restricting the bot's access to specific channels, or removing Lumi from the server. Individual users can avoid direct AI interactions by not mentioning or replying to Lumi, although recent channel messages may be included as context when another user intentionally invokes the AI, as described above.

Lumi does not use users' message content to train machine learning or AI models. AI requests are sent only for inference. Third-party AI providers process requests according to their own published data policies and the privacy settings configured for the Lumi account.

## 4. Third-party services

Lumi relies on the following services to operate:

| Service | Purpose | Data involved |
|---|---|---|
| Google Firebase (Cloud Firestore) | Stores economy data and server settings | User IDs, server IDs, economy data, settings |
| Groq | AI provider (primary or fallback) | Message text and context sent for AI replies |
| OpenRouter | AI provider (primary or fallback), which may route requests to an upstream model provider | Message text and context sent for AI replies |

These providers process data under their own policies:

- [Groq Privacy Policy](https://groq.com/privacy-policy) and [Your Data in GroqCloud](https://console.groq.com/docs/your-data)
- [OpenRouter Privacy Policy](https://openrouter.ai/privacy) and [Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection)
- [Google Firebase Privacy and Security](https://firebase.google.com/support/privacy)

We configure our AI provider accounts to avoid routing requests to providers that may train on submitted data, where supported by the provider's privacy controls.

## 5. Discord privileged intents

- **Server Members Intent:** used for optional welcome messages (member-join events), moderation commands (resolving members and checking role hierarchy), and auto-moderation role exceptions. Member profile data is not stored.
- **Message Content Intent:** used as described in Section 3.
- **Presence Intent:** Lumi does not request or use it. Lumi only sets its own status.

## 6. How we use data

We use the data above only to provide and improve Lumi's features: running the economy and games, applying server settings, performing moderation actions, generating AI replies, and keeping the bot stable and secure. We do not use your data for advertising, and we do not sell it.

## 7. Retention

- Economy data and server settings are kept until a deletion is requested (see Section 8) or the bot is removed from the server and the data is cleared.
- Message content is not retained by Lumi. Short-term conversation memory exists only in the running process and is cleared on restart.
- Technical logs and error output may be kept briefly for debugging and are not used to build user profiles.
- AI providers may retain data according to their own policies (see Section 4).

## 8. Your choices and rights

- **Deletion:** you can ask us to delete your economy data or your server's settings by contacting us (Section 11). Please include your Discord user ID (and server ID for settings). We will respond within a reasonable time.
- **Access:** you can ask what data we hold about your Discord ID.
- **Avoiding processing:** because AI chat cannot be turned off, the only way to avoid your messages being processed is to not use channels where Lumi is active or to ask a server administrator to restrict Lumi's channel access.
- **Server administrators** can configure or disable the bad-word filter, role exceptions, dead-chat revival, and welcome messages, and can remove Lumi from their server at any time.

Depending on where you live, you may have additional rights under laws such as the GDPR. Contact us to exercise them.

## 9. Security

Secrets such as the Discord token and API keys are kept in environment variables and are not committed to the repository. Lumi's data connections to Discord, Firebase, and AI providers are made over encrypted connections. No system is completely secure, and we cannot guarantee absolute security.

## 10. Children

Lumi is intended for users who meet Discord's minimum age requirement (13 or older, or higher where local law requires). We do not knowingly collect data from children below that age. If you believe a child's data has been collected, contact us and we will delete it.

## 11. Contact

For questions, data access, or deletion requests:

- **Discord support server:** [support server](https://discord.gg/9qhSEtdVh7)
- **GitHub issues:** https://github.com/shreyansh2k5/lumi-discord-bot/issues

## 12. Changes to this policy

We may update this policy from time to time. The "Last updated" date at the top shows when it last changed, and the full history is available in this repository's commit history. Continued use of Lumi after a change means you accept the updated policy.