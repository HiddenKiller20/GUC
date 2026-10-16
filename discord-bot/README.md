# GUC Command Bot — rank policy and command attendance edition

This update loads the rank structure provided by the GUC owner, adds approval-gated promotions, and replaces voice attendance with **/startcombat + /stopcombat** and **/startonduty + /stoponduty**. One completed attendance session earns **one mark**. Combat attendance also earns **one mark**. The bot does not monitor voice channels or record audio.

## Quick start / upgrade

1. Install Python 3.11 or newer. Extract the ZIP.
2. Create/open your bot at https://discord.com/developers/applications . Enable Server Members Intent (for welcomes). Message Content Intent is not required.
3. Double-click START_WINDOWS.bat. The wizard asks for Application ID, Discord server ID and the token (hidden input). The token belongs only in your local `.env`, never in chat.
4. Invite the bot with the wizard's generated link. Move its role above the roles and members it should manage.
5. Server owner runs `/setup` to select staff role, welcome channel and ticket category. Staff need the configured role and Manage Roles permission. Moderation commands additionally require their specific Discord permissions.
6. Use `/catalog` and `/bind` to connect rank/cert/battalion keys to actual Discord roles; `/create_role` creates a missing role. Arrange Discord ranks from highest to lowest. All managed roles must have zero server-level permissions; review any channel-specific permissions separately. Keep authority permissions in separate access roles.
7. Existing members: manually ensure exactly one appropriate linked rank per era, then use `/rank_register` with verified YYYY-MM-DD service/rank dates. New members use `/enlist faction` to get Recruit and initialize their record. Faction choice is self-service; `/apply` remains a separate optional application workflow.
8. `/personnel_set` sets the respective Commander and owner-verified 18+ eligibility. No date of birth or identity document is stored. The bot cannot verify age itself.
9. `/attendance_setup log_channel` selects the channel for start/stop logs. `/menu` shows commands.

**Upgrading:** stop the old process, back up `.env` and `data/`, replace the program files, and keep your `.env` and existing `data/` (or DATA_DIR). The new tables are added automatically. Official rank definitions and ladder order are installed on startup. Existing bindings and records are retained; old noncanonical rank keys may remain for migration. Reconcile them before registering members. Do not replace a customized config without comparing your custom battalion/cert entries.

For manual startup:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python setup_wizard.py
python bot.py
```

## Member commands

| Command | What it does |
|---|---|
| `/enlist faction` | Adds the linked Recruit role and creates the initial record |
| `/startcombat faction` | Starts your combat attendance timer |
| `/stopcombat` | Ends your combat attendance; awards one mark |
| `/startonduty faction` | Starts your On-Duty attendance timer |
| `/stoponduty` | Ends your On-Duty attendance; awards one mark |
| `/attendance_active` | Shows your currently running timer |
| `/attendance` | Exports your recorded start/stop timestamps |
| `/rank_status faction` | Shows registered rank, marks and pending promotion IDs |
| `/status create faction prefix number nickname` | Saves your identity and generates account status text |
| `/status show` | Uses your saved identity and current registered rank to refresh status text |
| `/cert_lookup` | Shows certification roles and issuer/date/reason records |
| `/structure`, `/rules`, `/menu` | Read hierarchy, published rules and command guide |

Example: `/status create faction:Republic prefix:CT number:7567 nickname:Rex` produces `CT-7567 Captain "Rex"` if your registered rank is Captain. Members cannot choose a fake rank in the command. The bot cannot change Discord/VRChat personal account status; copy and paste the generated text into the desired account. `/member_status` remains a one-off generator; staff can use it for another member. Trooper numbers are labels, not a uniqueness-enforced registry.

## Attendance and marks

There is no voice tracking. Time is measured from the **start command to the stop command**, regardless of voice membership. Only one session can be active per member, across both factions and kinds. A mismatched stop command will not close a session or award a mark. Active sessions survive restarts; time continues until the matching stop command, including time while the bot was offline. Repeating a stop command cannot duplicate an award. Regular and combat sessions each award one mark, not marks per minute. There is no minimum duration or daily limit because none was specified. Starting a new session after stopping can earn another mark; staff should review misuse.

`/attendance_export` exports all members' logs. `/attendance_void session_id reason` voids a mistaken or abused session and removes its associated mark, retaining historical timestamps. `/mark_award` adds one manual mark for a unique event ID; `/mark_revoke` lets the owner correct a manual mark. Use manual awards only for genuinely missing attendance: separate manually named IDs are not automatically matched to command sessions. Marks are cumulative and are not spent during promotion. They are tracked separately by faction. Historical voice records from an older version remain in the database but are no longer used or awarded marks.

Exports contain up to 10,000 sessions overlapping the requested 1–365 day window, with full session durations and UTC timestamps. Logs contain member IDs, so choose the log channel visibility deliberately.

## Full rank ladder, lowest to highest

The same ladder is available for Republic and Empire. Emperor is the server/group owner and is **outside** the promotable ladder.

Recruit → Private → Private Second Class → Private First Class → Specialist → Corporal → Sergeant → Staff Sergeant → Sergeant First Class → Master Sergeant → First Sergeant → Sergeant Major → Command Sergeant Major → Sergeant Major of the Era → Warrant Officer → Chief Warrant Officer → High Warrant Officer → Command Warrant Officer → Commanding Warrant Officer → Second Lieutenant → First Lieutenant → Captain → Major → Lieutenant Colonel → Colonel → Brigadier General → Lieutenant General → General → Commander → Marshal Commander → High Commander.

## Promotion workflow

1. Staff runs `/rankup member faction reason`. This creates a request ID; it does not immediately change roles.
2. `/promotion_status proposal_id` shows wait, mark, age and approval requirements.
3. Approvers use `/promotion_approve proposal_id kind evidence`. Evidence must describe the actual assessment; the bot does not independently verify leadership, combat ability or observation.
4. Any linked Commander, Marshal Commander or High Commander, or the Emperor, may use `/promotion_deny` to challenge/deny a pending request. Denial stops the staged queue and a fresh request needs fresh approvals.
5. Staff executes `/promotion_execute` once eligible. The bot rechecks live approver roles, target rank, dates, marks and all approvals immediately before changing Discord roles. Commander/Marshal Commander/High Commander appointments must be executed by the Emperor.

Distinct approver IDs count once. Candidates cannot approve themselves. Commander, Marshal Commander and High Commander roles qualify as Commander authority; commissioned-officer sponsorship is limited to the candidate's era. High Command authority is recognized across eras. Staff access remains a separate role; rank alone does not grant generic moderation or role-management commands. Permission checks enforce the acting staff member's and bot's Discord hierarchy.

| Destination | Requirements |
|---|---|
| Private | 5 marks **or** two days of verified group service |
| Private Second Class / PFC / Specialist / Corporal / Sergeant / Staff Sergeant | 10 / 15 / 20 / 25 / 30 / 35 cumulative marks |
| Sergeant First Class / Master Sergeant | Same-era CO sponsorship with leadership and combat skills evidence |
| First Sergeant / Sergeant Major | CO sponsorship with **good** leadership and combat skills evidence |
| Command Sergeant Major / Sergeant Major of the Era | CO sponsorship with **amazing** leadership and combat skills evidence |
| Warrant ranks | Respective Commander's approval |
| Second Lieutenant | Respective Commander's approval **and** combat-host shadow assessment |
| First Lieutenant through Colonel | Respective Commander's approval with leadership capability/mindset evidence |
| Brigadier General | Respective Commander's approval **and** Emperor's On-Duty shadow assessment; 18+ |
| Lieutenant General | At least 2 distinct Commanders; 18+ |
| General | At least 3 distinct Commanders; 18+ |
| Commander / Marshal Commander / High Commander | Emperor appointment approval and execution; 18+ |

### Timing interpretations requiring owner confirmation

- Waits are applied according to the **destination tier**: Enlisted 1 day, NCO 3 days, Commissioned Officer 6 days, High Command 10 days.
- **Warrant ranks provisionally use 6 days** because no unambiguous separate warrant wait was supplied.
- Private's two-day service alternative does not waive the one-day rank hold.
- `/rank_queue` supports staged enlisted jumps through Staff Sergeant when the final mark threshold is already met. It requires three days in each current rank before progressing one step, then automatically creates the next **pending request**, not an automatic role change. Staff must execute each stage. There is no additional queue delay beyond that three-day hold.
- The wording about further pending promotions having “no wait” is ambiguous. This version does not waive ordinary waits for additional requests beyond the staged queue. Confirm that policy before changing it.

Policy is implemented in `promotion_policy.py`; hierarchy editing via the former `/rank_add` and `/rank_order` commands is disabled. `/assign` and `/revoke` cannot change ranks. `/rankdown` is removed because demotion authority/procedure was not supplied: the owner can change Discord roles manually and reconcile with `/rank_register`, which is audited and cancels stale pending requests. This import capability is intentionally owner-only.

## Rules and other features

`/rules` defaults to the rank/command rules supplied in this conversation, with the provisional timing assumptions marked. If an earlier owner-published rules text exists, it remains authoritative and is not overwritten. `/rules_set` lets the owner publish updated display text (up to 3,800 characters); **editing display text does not change executable policy**. `/structure` shows all ranks and role bindings. The bot does not automatically police cross-era conversations or conduct.

Other included features: applications and private review; certification granting/revocation; battalion assignments; announcements; welcome messages; private tickets; warnings, timeouts, kicks, bans and audit exports. Certs do not expire automatically. `/cert_grant` and `/cert_revoke` are staff-controlled; cert lookup distinguishes bot-issued records from roles granted outside the bot. Application approval does not automatically grant ranks. Tickets retain staff-visible archives when closed. Unban through Discord settings.

## Hosting, data and reliability

Keep the process running on a computer or always-on host. This package is not already deployed. Set DATA_DIR to persistent storage; use one process and one server per database. Stop the process before backing up `data/guc.sqlite3`. Protect `.env`, backups, records, application text and staff assessment evidence. Retention and deletion are administrator responsibilities. Discord Administrator users can see private channels regardless of their normal overwrites.

Discord role updates and SQLite are separate systems. A failed promotion attempts to roll back the new role. If Discord or the database fails mid-operation, verify roles and `/rank_status`; an inconsistent record blocks subsequent promotions until the owner reconciles it. Generic role changes and cert records have the same external-system limitation. Avoid direct rank edits during promotion execution.

Local tests cover policy thresholds, distinct approvals, age/waits, sponsorship, shadowing, rank-command bypass prevention, slash payloads, command-only attendance, duplicate stop prevention and restart persistence. Live Discord verification still requires your configured application and server.

```sh
python -m unittest discover -s tests -v
```

Official API reference: https://discordpy.readthedocs.io/en/stable/interactions/api.html

## Three-strike system and handbook

- `/strike add member reason`: staff issues one active strike, with issuer and timestamp. Maximum **three active strikes per member across the server**, not three per faction. A fourth active strike is rejected.
- `/strike list`: a member sees their own count and history privately. Staff can select another member. Up to 500 recent records are exported; full history remains in SQLite.
- `/strike remove strike_id reason`: authorized staff removes a strike with an explanation. The original record and removal history remain. Removing one permits a later new strike, but active count never exceeds three. Only the owner can remove strikes for members who have left.
- At **3/3**, the response flags staff review. No automatic ban, kick, demotion, promotion block, expiration or DM is configured. Decide those policies separately. Staff cannot strike themselves, protected members or members above their authority; normal bot role hierarchy checks apply.
- `/handbook`: opens **The Galactic Unification Corp — Galactic Republic Handbook — Revised Draft**, located in your connected Google Drive. The button uses https://docs.google.com/document/d/1CtAVvPZMJGQDYdTCUMrYyhG6QPJYxMEiiStpgLkUULM/edit?usp=drivesdk . It does not modify sharing settings or import handbook text into executable policy. Readers need the document's existing Drive access.

Upgrade by replacing program files while keeping `.env` and `data/`, then restart. Strike tables are created automatically without clearing existing records.


## Marshal Commander update

Order: **Commander → Marshal Commander → High Commander** in both eras. Link it with `/bind key:rep_mc` or `/bind key:emp_mc`, or create it using `/create_role`. Place the Discord role directly below High Commander and above Commander. Its provisional requirements match Commander: Emperor appointment approval and execution, verified age 18+, and a ten-day wait. It counts as Commander authority for approval workflows. Pending Commander-to-High-Commander requests are cancelled during startup so they cannot skip Marshal Commander. Existing completed ranks remain unchanged.

## Railway deployment files

A Dockerfile is included. Configure Railway with root directory /discord-bot, start command python bot.py, one replica, zero deployment overlap, and service sleep disabled. The deprecated railway.json format is not used. Attach a persistent volume at `/data` and set `DATA_DIR=/data`. Add `DISCORD_TOKEN` securely in Railway Variables, plus your `DISCORD_GUILD_ID` (Discord server ID, not Application ID). No HTTP domain or inbound port is needed. Missing Discord variables cause startup to stop with a clear error. Railway service sleep is disabled; one replica and zero deployment overlap are configured. Do not run a second copy of the bot locally while hosting it.
